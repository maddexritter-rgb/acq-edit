#!/usr/bin/env python3
"""Transcribe each detected clip with AssemblyAI word-level granularity.

Reads boundaries.json from split_clips.py, runs the selected provider ONCE on the full
source audio, then slices word-level hits into per-clip JSON files with
timestamps rebased to the clip's own timeline (clip-relative, starting at 0).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path



def transcribe_full(video: Path, model_size: str, device: str, compute_type: str):
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise RuntimeError("Whisper is optional and is not installed. Use the default AssemblyAI route or explicitly install Whisper in toolkit Python.") from None
    model = WhisperModel(model_size, device=device, compute_type=compute_type)
    segments, info = model.transcribe(
        str(video),
        word_timestamps=True,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 300},
    )
    words = []
    for seg in segments:
        if seg.words is None:
            continue
        for w in seg.words:
            words.append({
                "word": w.word.strip(),
                "start": float(w.start),
                "end": float(w.end),
                "prob": float(w.probability or 0.0),
            })
    return words, info


def slice_for_clip(words: list[dict], start: float, end: float) -> list[dict]:
    """Return words fully inside [start, end], rebased so clip starts at 0."""
    out = []
    for w in words:
        if w["end"] <= start or w["start"] >= end:
            continue
        ws = max(w["start"], start) - start
        we = min(w["end"], end) - start
        if we - ws < 0.02:
            continue
        out.append({
            "word": w["word"],
            "start": round(ws, 3),
            "end": round(we, 3),
            "prob": round(w["prob"], 3),
        })
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path, help="Source video")
    ap.add_argument("boundaries", type=Path, help="boundaries.json from split_clips.py")
    ap.add_argument("--out", type=Path, default=Path("transcripts"),
                    help="Output directory for per-clip transcripts")
    ap.add_argument("--provider", choices=["assemblyai", "whisper"], default="assemblyai")
    ap.add_argument("--model", default="large-v3",
                    help="Whisper model size (tiny/base/small/medium/large-v2/large-v3)")
    ap.add_argument("--device", default="auto",
                    help="Device: auto, cpu, cuda")
    ap.add_argument("--compute-type", default="auto",
                    help="Compute type: auto, int8, float16, float32")
    args = ap.parse_args()

    if not args.input.exists():
        print(f"Input not found: {args.input}", file=sys.stderr)
        return 1
    if not args.boundaries.exists():
        print(f"Boundaries not found: {args.boundaries}", file=sys.stderr)
        return 1

    bounds = json.loads(args.boundaries.read_text())
    clips = bounds.get("clips", [])
    if not clips:
        print("No clips in boundaries file.", file=sys.stderr)
        return 1

    device = args.device
    compute_type = args.compute_type
    if device == "auto":
        try:
            import torch  # noqa
            device = "cuda" if torch.cuda.is_available() else "cpu"
        except Exception:
            device = "cpu"
    if compute_type == "auto":
        compute_type = "float16" if device == "cuda" else "int8"

    if args.provider == 'assemblyai':
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'_shared'))
        from asr import transcribe
        result = transcribe(str(args.input), profile='editorial_ingest', allow_fallback=False)
        words = [{**w, 'prob': w.get('confidence') or 0.0} for w in result['words']]
    else:
        words, info = transcribe_full(args.input, args.model, device, compute_type)
    print(f"Transcribed {len(words)} words with {args.provider}.")

    args.out.mkdir(parents=True, exist_ok=True)
    for clip in clips:
        idx = clip["index"]
        clip_words = slice_for_clip(words, clip["start"], clip["end"])
        payload = {
            "clip_index": idx,
            "source_start": clip["start"],
            "source_end": clip["end"],
            "duration": round(clip["end"] - clip["start"], 3),
            "words": clip_words,
        }
        out_path = args.out / f"clip_{idx:02d}.json"
        out_path.write_text(json.dumps(payload, indent=2))
        text_preview = " ".join(w["word"] for w in clip_words[:15])
        print(f"  clip {idx:02d}: {len(clip_words)} words  → {out_path}")
        print(f"           preview: {text_preview}…")

    print(f"\nTranscripts written to {args.out}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
