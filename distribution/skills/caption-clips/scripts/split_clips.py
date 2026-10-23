#!/usr/bin/env python3
"""Detect clip boundaries in a source reel separated by black-frame + silence gaps.

Runs ffmpeg's blackdetect AND silencedetect, intersects the intervals, and emits
per-clip start/end times (the content between gaps). Requires BOTH black and
silence to mark a gap — avoids splitting on a quiet pause or a dark shot.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


BLACK_RE = re.compile(r"black_start:(?P<start>[\d.]+)\s+black_end:(?P<end>[\d.]+)")
SIL_START_RE = re.compile(r"silence_start:\s*(?P<start>-?[\d.]+)")
SIL_END_RE = re.compile(r"silence_end:\s*(?P<end>-?[\d.]+)")


def probe_duration(path: Path) -> float:
    out = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    return float(out)


def detect_black(path: Path, min_dur: float, pix_th: float) -> list[tuple[float, float]]:
    proc = subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
            "-vf", f"blackdetect=d={min_dur}:pix_th={pix_th}",
            "-an", "-f", "null", "-",
        ],
        capture_output=True, text=True,
    )
    intervals = []
    for m in BLACK_RE.finditer(proc.stderr):
        intervals.append((float(m["start"]), float(m["end"])))
    return intervals


def detect_silence(path: Path, min_dur: float, noise_db: float) -> list[tuple[float, float]]:
    proc = subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
            "-af", f"silencedetect=n={noise_db}dB:d={min_dur}",
            "-vn", "-f", "null", "-",
        ],
        capture_output=True, text=True,
    )
    starts = [float(m["start"]) for m in SIL_START_RE.finditer(proc.stderr)]
    ends = [float(m["end"]) for m in SIL_END_RE.finditer(proc.stderr)]
    return list(zip(starts, ends))


def intersect(a: list[tuple[float, float]], b: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Return intervals where both a and b overlap."""
    out = []
    i = j = 0
    a_sorted = sorted(a)
    b_sorted = sorted(b)
    while i < len(a_sorted) and j < len(b_sorted):
        s = max(a_sorted[i][0], b_sorted[j][0])
        e = min(a_sorted[i][1], b_sorted[j][1])
        if s < e:
            out.append((s, e))
        if a_sorted[i][1] < b_sorted[j][1]:
            i += 1
        else:
            j += 1
    return out


def merge_close(intervals: list[tuple[float, float]], max_gap: float = 0.15) -> list[tuple[float, float]]:
    if not intervals:
        return []
    intervals = sorted(intervals)
    merged = [intervals[0]]
    for s, e in intervals[1:]:
        ps, pe = merged[-1]
        if s - pe <= max_gap:
            merged[-1] = (ps, max(pe, e))
        else:
            merged.append((s, e))
    return merged


def boundaries_from_gaps(duration: float, gaps: list[tuple[float, float]], min_clip_len: float = 1.0) -> list[dict]:
    """Turn gap intervals into clip intervals (the content between gaps)."""
    clips = []
    cursor = 0.0
    for gs, ge in gaps:
        if gs - cursor >= min_clip_len:
            clips.append({"start": round(cursor, 3), "end": round(gs, 3)})
        cursor = ge
    if duration - cursor >= min_clip_len:
        clips.append({"start": round(cursor, 3), "end": round(duration, 3)})
    for idx, c in enumerate(clips):
        c["index"] = idx
    return clips


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path)
    ap.add_argument("--min-gap", type=float, default=0.4,
                    help="Minimum gap duration (seconds) to count as a separator")
    ap.add_argument("--pix-th", type=float, default=0.10,
                    help="blackdetect pixel luminance threshold (0-1)")
    ap.add_argument("--silence-db", type=float, default=-35.0,
                    help="silencedetect noise floor in dB (negative)")
    ap.add_argument("--min-clip-len", type=float, default=1.0,
                    help="Drop detected clips shorter than this (seconds)")
    ap.add_argument("--out", type=Path, default=Path("boundaries.json"))
    args = ap.parse_args()

    if not args.input.exists():
        print(f"Input not found: {args.input}", file=sys.stderr)
        return 1

    duration = probe_duration(args.input)
    black = detect_black(args.input, args.min_gap, args.pix_th)
    silence = detect_silence(args.input, args.min_gap, args.silence_db)
    gaps = merge_close(intersect(black, silence))
    clips = boundaries_from_gaps(duration, gaps, args.min_clip_len)

    result = {
        "input": str(args.input),
        "duration": round(duration, 3),
        "detection": {
            "black_intervals": [{"start": s, "end": e} for s, e in black],
            "silence_intervals": [{"start": s, "end": e} for s, e in silence],
            "gaps": [{"start": s, "end": e} for s, e in gaps],
        },
        "clips": clips,
    }
    args.out.write_text(json.dumps(result, indent=2))

    print(f"Duration: {duration:.2f}s")
    print(f"Black intervals: {len(black)}  Silence intervals: {len(silence)}  Gaps (both): {len(gaps)}")
    print(f"Detected clips: {len(clips)}")
    for c in clips:
        print(f"  clip {c['index']:02d}: {c['start']:.2f} → {c['end']:.2f}  ({c['end']-c['start']:.2f}s)")
    print(f"\nWrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
