#!/usr/bin/env python3
"""Build a silence map for a WAV file using ffmpeg's silencedetect filter.

Outputs JSON list of silence intervals: [{start, end}, ...].
Used by cut_clip.py to snap filler-cut boundaries to actual quiet moments
so cuts don't slice mid-word.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


SIL_START_RE = re.compile(r"silence_start:\s*(-?[\d.]+)")
SIL_END_RE = re.compile(r"silence_end:\s*(-?[\d.]+)")


def detect_silences(wav: Path, noise_db: float, min_dur: float) -> list[dict]:
    proc = subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-nostats", "-i", str(wav),
            "-af", f"silencedetect=n={noise_db}dB:d={min_dur}",
            "-vn", "-f", "null", "-",
        ],
        capture_output=True, text=True,
    )
    starts = [float(m.group(1)) for m in SIL_START_RE.finditer(proc.stderr)]
    ends = [float(m.group(1)) for m in SIL_END_RE.finditer(proc.stderr)]
    # Sometimes the last silence extends to EOF and has no end — trim to min length.
    intervals = [{"start": round(s, 3), "end": round(e, 3)}
                 for s, e in zip(starts, ends)]
    return intervals


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("wav", type=Path)
    ap.add_argument("--noise-db", type=float, default=-40.0,
                    help="Silence threshold in dB (negative, more negative = stricter)")
    ap.add_argument("--min-dur", type=float, default=0.04,
                    help="Minimum silence duration in seconds")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    if not args.wav.exists():
        print(f"WAV not found: {args.wav}", file=sys.stderr)
        return 1
    intervals = detect_silences(args.wav, args.noise_db, args.min_dur)
    payload = {
        "wav": str(args.wav),
        "noise_db": args.noise_db,
        "min_dur": args.min_dur,
        "silences": intervals,
    }
    args.out.write_text(json.dumps(payload, indent=2))
    print(f"Wrote {args.out}  ({len(intervals)} silence intervals)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
