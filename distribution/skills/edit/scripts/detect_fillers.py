#!/usr/bin/env python3
"""Scan a word-level transcript for filler words/phrases per the Alex SOP.

Returns a JSON list of {start, end, match} intervals to CUT from the clip.
Conservative — favors precision over recall: single-word fillers plus exact multi-word phrase matches.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


# Single-token fillers: cut without context (safe to always remove).
SINGLE_FILLERS = {"um", "uh", "uhm", "umm", "uhh", "ugh", "fundamentally",
                  "ah", "ahh", "ahhh", "aha", "oh", "ohh"}

# Words that are fillers when isolated (preceded OR followed by a pause >200ms).
# "right?" ticks, "like..." hesitations, stranded "so..." etc.
ISOLATED_ONLY = {"right", "like", "okay", "ok"}

# Multi-word phrase fillers — must match consecutive words exactly (case-insensitive, punct stripped).
# From Alex SOP filler list. Order matters: longer first (match greedily).
PHRASE_FILLERS = [
    ["the", "thing", "is", "is", "that"],
    ["and", "so", "for", "context"],
    ["so", "if", "you", "think", "about"],
    ["for", "me", "personally"],
    ["for", "example"],
    ["you", "know"],
    ["i", "mean"],
    ["and", "so"],
]

# Phrases/tokens that are ONLY fillers when sentence-initial
# (follow a pause > 200ms or come right after sentence-ending punctuation).
# We cut these aggressively at sentence boundaries but leave mid-sentence uses alone.
SENTENCE_INITIAL_ONLY = {
    "and so": ["and", "so"],
    "now": ["now"],
    "so": ["so"],
}

PUNCT_RE = re.compile(r"[^\w']", flags=re.UNICODE)


def norm(w: str) -> str:
    return PUNCT_RE.sub("", w.strip().lower())


def detect(words: list[dict], pad_before: float, pad_after: float,
           acoustic_silences: list[dict] | None = None,
           scope_start: float = 0.0, scope_end: float = float("inf")) -> list[dict]:
    """Find filler intervals in the transcript. `words` is the transcript's 'words' list.

    Each cut carries prev_end / next_start bounds so downstream snapping CANNOT
    cross into the preceding/following word.
    """
    def _bounds(idx_first, idx_last):
        prev_end = words[idx_first - 1]["end"] if idx_first > 0 else max(0.0, words[idx_first]["start"] - 1.0)
        next_start = words[idx_last + 1]["start"] if idx_last + 1 < len(words) else words[idx_last]["end"] + 1.0
        return prev_end, next_start

    def _safe_end(last_end, next_start, pad_after):
        """Return a cut-end that eliminates filler-tail bleed.
        If there's a real gap, use pad but stay 20ms clear of next word.
        If no gap (zero-silence between words), cut AT filler_end — accept a
        tiny next-word clip rather than leaving filler residue audible.
        """
        gap = next_start - last_end
        if gap >= 0.05:
            return min(last_end + pad_after, next_start - 0.02)
        return last_end  # zero-gap case: cut exactly where whisper says filler ends

    def _safe_start(first_start, prev_end, pad_before):
        gap = first_start - prev_end
        if gap >= 0.05:
            return max(first_start - pad_before, prev_end + 0.02)
        return first_start  # zero-gap: cut exactly where filler begins

    cuts: list[dict] = []
    n = len(words)
    i = 0
    while i < n:
        w = words[i]
        tok = norm(w["word"])

        # Context: was the previous word's end followed by a pause, or is this the first word?
        prev_gap = (w["start"] - words[i - 1]["end"]) if i > 0 else 999.0
        prev_text = (words[i - 1].get("word", "") if i > 0 else "").rstrip()
        is_sentence_initial = (prev_gap >= 0.20) or prev_text.endswith((".", "!", "?"))

        # Try SENTENCE_INITIAL_ONLY phrases first (need the sentence-start context).
        sio_hit = None
        if is_sentence_initial:
            for name, phrase in SENTENCE_INITIAL_ONLY.items():
                if i + len(phrase) > n:
                    continue
                window = [norm(words[i + k]["word"]) for k in range(len(phrase))]
                if window == phrase:
                    sio_hit = (name, phrase)
                    break
        if sio_hit:
            name, phrase = sio_hit
            first_idx = i
            last_idx = i + len(phrase) - 1
            prev_end, next_start = _bounds(first_idx, last_idx)
            start = _safe_start(words[first_idx]["start"], prev_end, pad_before)
            end = _safe_end(words[last_idx]["end"], next_start, pad_after)
            cuts.append({"start": round(max(0.0, start), 3),
                         "end": round(end, 3),
                         "match": f"[sent-init] {name}",
                         "_prev_end": prev_end, "_next_start": next_start})
            i += len(phrase)
            continue

        # Try always-cut phrase match.
        phrase_hit = None
        for phrase in PHRASE_FILLERS:
            if i + len(phrase) > n:
                continue
            window = [norm(words[i + k]["word"]) for k in range(len(phrase))]
            if window == phrase:
                phrase_hit = phrase
                break
        if phrase_hit:
            first_idx = i
            last_idx = i + len(phrase_hit) - 1
            prev_end, next_start = _bounds(first_idx, last_idx)
            start = _safe_start(words[first_idx]["start"], prev_end, pad_before)
            end = _safe_end(words[last_idx]["end"], next_start, pad_after)
            cuts.append({"start": round(max(0.0, start), 3),
                         "end": round(end, 3),
                         "match": " ".join(phrase_hit),
                         "_prev_end": prev_end, "_next_start": next_start})
            i += len(phrase_hit)
            continue

        # Single-token filler.
        if tok in SINGLE_FILLERS:
            prev_end, next_start = _bounds(i, i)
            start = max(w["start"] - pad_before, prev_end + 0.005)
            end = min(w["end"] + pad_after, next_start - 0.02)
            cuts.append({"start": round(max(0.0, start), 3),
                         "end": round(end, 3),
                         "match": tok,
                         "_prev_end": prev_end, "_next_start": next_start})
            i += 1
            continue

        # Isolated-only fillers: cut if surrounded by pauses.
        if tok in ISOLATED_ONLY:
            next_gap = (words[i + 1]["start"] - w["end"]) if i + 1 < n else 999.0
            if prev_gap >= 0.20 or next_gap >= 0.20 or w.get("word", "").rstrip().endswith("?"):
                prev_end, next_start = _bounds(i, i)
                start = max(w["start"] - pad_before, prev_end + 0.005)
                end = min(w["end"] + pad_after, next_start - 0.02)
                cuts.append({"start": round(max(0.0, start), 3),
                             "end": round(end, 3),
                             "match": f"[isolated] {tok}",
                             "_prev_end": prev_end, "_next_start": next_start})
        i += 1

    # Whisper word-gap silence (rougher — word boundaries ≠ audio silence).
    SILENCE_GAP_THRESHOLD = 0.55
    KEEP_GAP = 0.15
    for i in range(1, len(words)):
        prev_end = words[i - 1]["end"]
        curr_start = words[i]["start"]
        gap = curr_start - prev_end
        if gap >= SILENCE_GAP_THRESHOLD:
            cut_start = prev_end + KEEP_GAP / 2
            cut_end = curr_start - KEEP_GAP / 2
            if cut_end - cut_start >= 0.1:
                cuts.append({
                    "start": round(cut_start, 3),
                    "end": round(cut_end, 3),
                    "match": f"[silence] {gap:.2f}s pause",
                    "_prev_end": prev_end,
                    "_next_start": curr_start,
                })

    # Acoustic silence cuts — uses actual audio-level silence detection (ffmpeg
    # silencedetect), catches breath-tails and dead air that whisper's word-gaps
    # miss. This is what "can you hear what I hear" required.
    if acoustic_silences:
        ACOUSTIC_MIN = 0.25  # silences shorter than this aren't worth cutting
        ACOUSTIC_KEEP = 0.12  # leave 120ms total so speech doesn't bump
        for sil in acoustic_silences:
            ss = max(sil["start"], scope_start)
            se = min(sil["end"], scope_end)
            dur = se - ss
            if dur < ACOUSTIC_MIN:
                continue
            cut_start = ss + ACOUSTIC_KEEP / 2
            cut_end = se - ACOUSTIC_KEEP / 2
            if cut_end - cut_start < 0.1:
                continue
            cuts.append({
                "start": round(cut_start, 3),
                "end": round(cut_end, 3),
                "match": f"[acoustic] {dur:.2f}s silence",
                "_prev_end": ss,
                "_next_start": se,
            })

    # Merge cuts that are within 50ms of each other. When merging, take the
    # widest bounds (_prev_end min, _next_start max) so downstream clamping
    # doesn't truncate the merged range prematurely.
    cuts.sort(key=lambda c: c["start"])
    merged: list[dict] = []
    for c in cuts:
        if merged and c["start"] - merged[-1]["end"] <= 0.05:
            merged[-1]["end"] = max(merged[-1]["end"], c["end"])
            merged[-1]["match"] += "+" + c["match"]
            if "_prev_end" in c:
                merged[-1]["_prev_end"] = min(
                    merged[-1].get("_prev_end", c["_prev_end"]), c["_prev_end"])
            if "_next_start" in c:
                merged[-1]["_next_start"] = max(
                    merged[-1].get("_next_start", c["_next_start"]), c["_next_start"])
        else:
            merged.append(dict(c))
    return merged


def slice_words(words: list[dict], t0: float, t1: float) -> list[dict]:
    return [w for w in words if w["end"] > t0 and w["start"] < t1]


def snap_to_silence(cuts: list[dict], silences: list[dict],
                    tol: float = 0.25, margin: float = 0.01) -> list[dict]:
    """For each cut, try to snap its start/end to the nearest actual silence interval.

    - cut.start → start of silence whose END is near cut.start (so we remove from start-of-silence through the filler)
    - cut.end   → end of silence whose START is near cut.end (so we resume right when the next word begins)
    - tol: max distance from the intended cut point to consider a silence match (seconds)
    - margin: tiny safety buffer inside the silence so we don't clip the word edges
    """
    if not silences:
        return cuts
    # Build sorted lists for quick lookup.
    sil_starts = [s["start"] for s in silences]
    sil_ends = [s["end"] for s in silences]

    def find_near(target, values, tol):
        """Return index of closest value within tol, or None."""
        if not values:
            return None
        import bisect
        i = bisect.bisect_left(values, target)
        best = None
        best_d = tol + 1e-9
        for j in (i - 1, i):
            if 0 <= j < len(values):
                d = abs(values[j] - target)
                if d <= tol and d < best_d:
                    best = j
                    best_d = d
        return best

    snapped = []
    for c in cuts:
        fs, fe = c["start"], c["end"]
        # Hard bounds from the transcript — never cross neighboring words.
        prev_end = c.get("_prev_end", fs - 1.0)
        next_start = c.get("_next_start", fe + 1.0)

        # Snap start — find a silence whose END is close to fs.
        s_idx = find_near(fs, sil_ends, tol)
        if s_idx is not None:
            new_start = silences[s_idx]["start"] + margin
            # Only accept if it's AFTER prev_end (don't cut into prev word)
            if prev_end + margin <= new_start < fs:
                fs = new_start
        # Snap end — find a silence whose START is close to fe.
        e_idx = find_near(fe, sil_starts, tol)
        if e_idx is not None:
            new_end = silences[e_idx]["end"] - margin
            # Only accept if it's BEFORE next_start (don't cut into next word)
            if fe < new_end <= next_start - margin:
                fe = new_end
        # Final safety clamp — never cross word bounds.
        # End: allow reaching next_start exactly (zero-gap case from _safe_end);
        # Start: keep margin after prev_end (don't clip prev word's tail).
        fs = max(prev_end + margin, fs)
        fe = min(next_start, fe)
        snapped.append({**c, "start": round(fs, 3), "end": round(fe, 3), "snapped": True})
    return snapped


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("transcript", type=Path, help="Word-level transcript JSON")
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--end", type=float, default=None,
                    help="Limit detection to [start, end]. Default: full transcript.")
    ap.add_argument("--pad-before", type=float, default=0.04,
                    help="Extra seconds trimmed BEFORE each filler (breath space)")
    ap.add_argument("--pad-after", type=float, default=0.08,
                    help="Extra seconds trimmed AFTER each filler")
    ap.add_argument("--silence-map", type=Path, default=None,
                    help="Path to silence_map.json. If given, cut boundaries are snapped to actual silence points for clean cuts.")
    ap.add_argument("--snap-tolerance", type=float, default=0.25,
                    help="Max distance (seconds) from intended cut to consider a silence for snapping")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    tr = json.loads(args.transcript.read_text())
    all_words = tr.get("words", [])
    end_t = args.end or float("inf")
    words = slice_words(all_words, args.start, end_t)

    # Load acoustic silences early so detect() can add them directly (catches
    # breath-tails and dead air between words that whisper's word-gaps miss).
    acoustic_silences = []
    all_silences = []
    if args.silence_map and args.silence_map.exists():
        sil_data = json.loads(args.silence_map.read_text())
        all_silences = sil_data.get("silences", [])
        acoustic_silences = [s for s in all_silences
                             if s["end"] > args.start and s["start"] < end_t]

    cuts = detect(words, args.pad_before, args.pad_after,
                  acoustic_silences=acoustic_silences,
                  scope_start=args.start, scope_end=end_t)

    # Optional: snap cut boundaries to real silence points.
    if all_silences:
        cuts = snap_to_silence(cuts, all_silences, tol=args.snap_tolerance)

    payload = {
        "transcript": str(args.transcript),
        "scope": {"start": args.start, "end": args.end},
        "cuts": cuts,
    }
    if args.out:
        args.out.write_text(json.dumps(payload, indent=2))
        print(f"Wrote {args.out}  ({len(cuts)} cuts)")
    else:
        print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
