#!/usr/bin/env python3
"""Apply a human-edited transcript back to a source clip — produces a new
MP4 containing only the words the user kept.

Input:
  - Original clip MP4 (source of truth for video + audio)
  - Original transcript JSON (word-level timings, from transcribe_groq.py)
  - Edited transcript file — either:
      * prose format (A_transcript.txt) — user deleted words/sentences
      * per-line format (A_transcript_edit.txt) — user deleted `[time] word` lines

Process:
  1. Load original word list
  2. Parse edited file → list of kept word tokens (order preserved)
  3. Align edited tokens back to original (match by word + order)
  4. Group aligned words into contiguous KEEP ranges
  5. ffmpeg concat filter: cut the clip to those ranges, crossfade audio between
  6. (Optional) re-burn Pro captions from the new word list
  7. Output <name>_v2.mp4

Usage:
  python3 apply_transcript_edit.py \
      --clip A_original.mp4 \
      --transcript A_transcript_ORIGINAL.json \
      --edited A_transcript.txt \
      --out A_v2.mp4
"""
from __future__ import annotations

import argparse
import difflib
import glob
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path


FFMPEG = sorted(glob.glob("/opt/homebrew/Cellar/ffmpeg-full/*/bin/ffmpeg"))[0] \
         if glob.glob("/opt/homebrew/Cellar/ffmpeg-full/*/bin/ffmpeg") \
         else "ffmpeg"
FFPROBE = str(Path(FFMPEG).parent / "ffprobe")

# ACQ FAST-RENDER STANDARD — VideoToolbox HW encode (~4x), resolution-aware single source of truth.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
try:
    from fast_encode import encoder_args_for as _encoder_args_for
except Exception:
    _encoder_args_for = None


def _venc(path, *, tier="delivery"):
    """ACQ encoder args (VideoToolbox HW, sized to `path`); libx264 fallback if import/probe fails."""
    if _encoder_args_for:
        try:
            return list(_encoder_args_for(str(path), FFMPEG, tier=tier))
        except Exception:
            pass
    return ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p"]


def tokenize(s: str) -> list[str]:
    """Strip all whitespace + punctuation except ending punct; lowercase."""
    # Split on whitespace, keep only alphanumeric + apostrophes
    out = []
    for w in s.split():
        clean = re.sub(r"[^\w']", "", w.lower())
        if clean:
            out.append(clean)
    return out


def parse_prose(path: Path) -> list[str]:
    """Parse prose-format edited file: strip comments, return token list."""
    text = path.read_text()
    # Remove comment lines (start with #)
    lines = [l for l in text.splitlines() if not l.lstrip().startswith("#")]
    return tokenize("\n".join(lines))


def parse_per_line(path: Path) -> list[str]:
    """Parse per-line format: `[timestamp]  word` entries."""
    text = path.read_text()
    tokens = []
    for line in text.splitlines():
        if line.lstrip().startswith("#") or not line.strip():
            continue
        m = re.match(r"\[\s*[\d.]+\s*\]\s+(\S+)", line)
        if m:
            tokens.append(tokenize(m.group(1))[0] if tokenize(m.group(1)) else "")
    return [t for t in tokens if t]


def parse_edited(path: Path) -> list[str]:
    """Auto-detect format: if any line matches `[X.X] word` → per-line; else prose."""
    text = path.read_text()
    for line in text.splitlines()[:20]:
        if re.match(r"\[\s*[\d.]+\s*\]\s+\S", line):
            return parse_per_line(path)
    return parse_prose(path)


def align_to_original(original_words: list[dict],
                      edited_tokens: list[str]) -> list[int]:
    """Find which ORIGINAL word indices the user kept, in edited order.

    Uses difflib.SequenceMatcher to align the edited token stream back to
    the original tokenized sequence. Returns list of original-word indices.
    """
    orig_tokens = [re.sub(r"[^\w']", "", w["word"].lower()) for w in original_words]
    # SequenceMatcher's matching_blocks returns preserved subsequences
    sm = difflib.SequenceMatcher(None, orig_tokens, edited_tokens, autojunk=False)
    kept_orig_indices = []
    for block in sm.get_matching_blocks():
        if block.size == 0:
            continue
        for i in range(block.a, block.a + block.size):
            kept_orig_indices.append(i)
    return kept_orig_indices


def snap_end_to_silence(t: float, silences: list[dict],
                         search_window: float = 0.6) -> float:
    """Push cut-OUT time FORWARD to land inside the nearest silence AFTER t.

    The kept range ends when speech ends → land 20ms into the silence region
    so the cut happens on silence, not on the speech tail.
    """
    candidates = [s for s in silences
                  if s["start"] >= t - 0.08 and s["start"] <= t + search_window]
    if not candidates:
        return t
    # Prefer the silence that starts closest to t (just after the word)
    best = min(candidates, key=lambda s: abs(s["start"] - t))
    # Land 20 ms into the silence (safely past the speech tail)
    return best["start"] + 0.02


def snap_start_to_silence(t: float, silences: list[dict],
                           search_window: float = 0.6) -> float:
    """Pull cut-IN time BACKWARD to land inside the nearest silence BEFORE t.

    The kept range starts in silence → land 20ms before the silence ends so
    the first audible frames are the last bit of silence + speech onset.
    """
    candidates = [s for s in silences
                  if s["end"] <= t + 0.08 and s["end"] >= t - search_window]
    if not candidates:
        return t
    best = min(candidates, key=lambda s: abs(s["end"] - t))
    return max(0.0, best["end"] - 0.02)


def group_to_ranges(original_words: list[dict],
                    kept_indices: list[int],
                    gap_tolerance: float = 0.05,
                    silences: list[dict] | None = None) -> list[tuple[float, float]]:
    """Group contiguous kept word-indices into (start, end) time ranges.

    If `silences` is provided, SNAP each range boundary into the nearest
    acoustic silence region (via ffmpeg silencedetect). This eliminates
    mid-word phoneme clicks that happen when Whisper's word boundaries
    don't align to actual speech offsets/onsets.

    Padding: range edges that are NOT snapped to silence get a conservative
    padding (5 ms head, 30 ms tail) to capture word attack/decay.
    """
    if not kept_indices:
        return []
    ranges = []
    cur_start = original_words[kept_indices[0]]["start"]
    cur_end = original_words[kept_indices[0]]["end"]
    prev_idx = kept_indices[0]

    for idx in kept_indices[1:]:
        w = original_words[idx]
        if idx == prev_idx + 1:
            # contiguous in original — extend range
            cur_end = w["end"]
        else:
            # gap — close current range, start new
            ranges.append((cur_start, cur_end))
            cur_start = w["start"]
            cur_end = w["end"]
        prev_idx = idx
    ranges.append((cur_start, cur_end))

    # Apply silence-snap per boundary
    if silences:
        snapped = []
        for i, (s, e) in enumerate(ranges):
            is_first = (i == 0)
            is_last = (i == len(ranges) - 1)
            if is_first:
                new_s = max(0.0, s - 0.05)  # clip start: small head pad
            else:
                new_s = snap_start_to_silence(s, silences)
            if is_last:
                new_e = e + 0.30  # clip end: bigger tail (catch word-final s/t)
            else:
                new_e = snap_end_to_silence(e, silences)
            snapped.append((new_s, new_e))
        return snapped

    # Fallback: no silence map → use simple padding
    padded = [(max(0.0, s - 0.02), e + 0.03) for s, e in ranges]
    return padded

    # Snap to small padding
    padded = []
    for s, e in ranges:
        padded.append((max(0, s - 0.02), e + 0.03))
    return padded


def concat_ranges(source_mp4: Path, ranges: list[tuple[float, float]],
                  out_path: Path):
    """Use ffmpeg concat filter to stitch multiple source ranges together.

    Video: direct cut (no fade). Audio: S-curve crossfade between ranges.
    """
    if not ranges:
        raise SystemExit("no ranges to concat")

    # Build filter_complex that does trim+concat
    parts_v = []
    parts_a = []
    for i, (s, e) in enumerate(ranges):
        parts_v.append(
            f"[0:v]trim=start={s}:end={e},setpts=PTS-STARTPTS[v{i}]"
        )
        # Audio: small 5ms fade in/out at each edit point for click-free stitching
        dur = e - s
        fade_in = 0.005
        fade_out = 0.005
        parts_a.append(
            f"[0:a]atrim=start={s}:end={e},asetpts=PTS-STARTPTS,"
            f"afade=t=in:st=0:d={fade_in},"
            f"afade=t=out:st={max(0,dur-fade_out):.3f}:d={fade_out}[a{i}]"
        )
    concat_inputs_v = "".join(f"[v{i}]" for i in range(len(ranges)))
    concat_inputs_a = "".join(f"[a{i}]" for i in range(len(ranges)))
    concat = (
        f"{concat_inputs_v}concat=n={len(ranges)}:v=1:a=0[vout];"
        f"{concat_inputs_a}concat=n={len(ranges)}:v=0:a=1[aout]"
    )
    filter_complex = "; ".join(parts_v + parts_a + [concat])

    cmd = [FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
           "-i", str(source_mp4),
           "-filter_complex", filter_complex,
           "-map", "[vout]", "-map", "[aout]",
           *_venc(source_mp4, tier="intermediate"),  # ACQ fast-render — concat scratch (re-encoded on caption burn)
           "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
           "-movflags", "+faststart",
           str(out_path)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print("STDERR:", r.stderr[-2000:], file=sys.stderr)
        raise SystemExit("ffmpeg concat failed")


def build_new_transcript(original_words: list[dict],
                         kept_indices: list[int],
                         ranges: list[tuple[float, float]]) -> list[dict]:
    """Re-time kept words to the new clip's timeline (0-based, accounting for
    concatenation)."""
    # Map each original time to new-timeline time by summing range lengths
    def new_time(orig_t: float) -> float:
        elapsed = 0.0
        for (s, e) in ranges:
            if orig_t < s:
                return elapsed + 0  # before this range
            if orig_t <= e:
                return elapsed + (orig_t - s)
            elapsed += (e - s)
        return elapsed

    new_words = []
    for idx in kept_indices:
        w = original_words[idx]
        ns = new_time(w["start"])
        ne = new_time(w["end"])
        if ne - ns < 0.01:
            ne = ns + 0.02
        new_words.append({"word": w["word"], "start": round(ns, 3),
                          "end": round(ne, 3), "prob": w.get("prob", 1.0)})
    return new_words


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clip", type=Path, required=True,
                    help="Source clip MP4")
    ap.add_argument("--transcript", type=Path, required=True,
                    help="Original word-level transcript JSON")
    ap.add_argument("--edited", type=Path, required=True,
                    help="Human-edited transcript (.txt — prose or per-line)")
    ap.add_argument("--silence-map", type=Path, default=None,
                    help="Silence map JSON from silence_map.py — if provided, "
                         "cut boundaries snap to acoustic silences (eliminates "
                         "mid-phoneme clicks from Whisper-only cuts)")
    ap.add_argument("--out", type=Path, required=True,
                    help="Output MP4 path")
    ap.add_argument("--reburn-captions", action="store_true", default=True,
                    help="Re-generate Pro captions from the new word list")
    args = ap.parse_args()

    # Load original
    tr = json.loads(args.transcript.read_text())
    original_words = tr["words"]
    print(f"Original: {len(original_words)} words, "
          f"{original_words[-1]['end']:.1f}s")

    # Parse edited
    edited_tokens = parse_edited(args.edited)
    print(f"Edited:   {len(edited_tokens)} words")

    # Align
    kept_indices = align_to_original(original_words, edited_tokens)
    print(f"Kept:     {len(kept_indices)}/{len(original_words)} original words")

    # Load silence map if provided
    silences = None
    if args.silence_map and args.silence_map.exists():
        sil_data = json.loads(args.silence_map.read_text())
        silences = sil_data.get("silences", [])
        print(f"Silences: {len(silences)} regions loaded (cuts will snap to these)")

    # Group into ranges
    ranges = group_to_ranges(original_words, kept_indices, silences=silences)
    print(f"Ranges:   {len(ranges)} contiguous segments")
    for i, (s, e) in enumerate(ranges):
        print(f"   [{i+1}]  {s:7.2f} → {e:7.2f}  ({e-s:.2f}s)")
    total_dur = sum(e - s for s, e in ranges)
    print(f"Output duration: {total_dur:.1f}s (was {original_words[-1]['end']:.1f}s)")

    # Concat
    concat_out = args.out.with_name(f"_tmp_{args.out.name}")
    concat_ranges(args.clip, ranges, concat_out)

    if args.reburn_captions:
        # Build new word-list at new timeline
        new_words = build_new_transcript(original_words, kept_indices, ranges)
        new_tr = {"words": new_words}
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False,
                                         mode="w") as f:
            json.dump(new_tr, f)
            new_tr_path = Path(f.name)
        new_ass = args.out.with_suffix(".ass")
        # ONE caption style: spice. Run the spice chain on the EDITED transcript, then gblur-burn it
        # onto the cut video via the locked engine (replaces the retired flat-caption burn).
        cc = Path(__file__).resolve().parents[2] / "caption-clips/scripts"
        spice_words = args.out.with_suffix(".spice.json")
        subprocess.run(["python3", str(cc / "spice_normalize.py"), str(new_tr_path), str(spice_words)], check=True)
        style_json = args.out.with_suffix(".director.json")
        subprocess.run(["python3", str(cc / "caption_director.py"), str(spice_words), "--out", str(style_json)])
        spice_cmd = ["python3", str(cc / "generate_spice.py"), str(spice_words),
                     "--preset", str(cc.parent / "presets" / "spice.json"),
                     "--out", str(new_ass), "--burn", str(concat_out), "--burn-out", str(args.out)]
        if style_json.exists():
            spice_cmd += ["--style", str(style_json)]
        subprocess.run(spice_cmd, check=True)
        concat_out.unlink()
    else:
        concat_out.replace(args.out)

    print(f"\n✓ Wrote {args.out}")


if __name__ == "__main__":
    main()
