#!/usr/bin/env python3
"""Align whisper word.start timestamps to actual speech onset using ffmpeg silencedetect.

Whisper's word.start is often early during natural pauses (the model interpolates) —
when Alex pauses 1.3s to emphasize a point, Whisper may say the next word starts at
0.3s into the pause instead of 1.3s. Captions then reveal during the silence.

This pass:
  1. Runs ffmpeg silencedetect on the audio (≥-30dB, ≥0.5s segments)
  2. For each word whose .start falls inside a silence region, pushes .start to silence_end + small buffer
  3. Adjusts .end if needed (preserves min duration)
"""
import argparse, json, re, subprocess
from pathlib import Path


def detect_silence(audio_path: Path, noise_db: int = -45, min_dur: float = 0.6):
    cmd = ["ffmpeg", "-hide_banner", "-i", str(audio_path),
           "-af", f"silencedetect=noise={noise_db}dB:duration={min_dur}",
           "-vn", "-f", "null", "/dev/null"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    silences = []
    cur_start = None
    for ln in r.stderr.splitlines():
        m1 = re.search(r'silence_start: ([\d.]+)', ln)
        m2 = re.search(r'silence_end: ([\d.]+)', ln)
        if m1: cur_start = float(m1.group(1))
        elif m2 and cur_start is not None:
            silences.append((cur_start, float(m2.group(1))))
            cur_start = None
    return silences


def align(words: list, silences: list, buffer: float = 0.05) -> list:
    """For each silence region, push ALL words that fall inside it forward by the same offset
    (preserves their relative spacing — fixes the bug where multiple sequential words all
    collapse to the same timestamp)."""
    if not silences:
        return words
    for s, e in silences:
        affected = [w for w in words if s <= w["start"] < e]
        if not affected:
            continue
        first_start = min(w["start"] for w in affected)
        target = e + buffer
        shift = target - first_start
        for w in affected:
            w["start"] += shift
            w["end"] += shift
    return words


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--in", dest="inp", required=True, type=Path)
    p.add_argument("--out", dest="out", required=True, type=Path)
    p.add_argument("--audio", required=True, type=Path, help="Source audio/video for silencedetect")
    args = p.parse_args()

    data = json.loads(args.inp.read_text())
    words = data.get("words", data) if isinstance(data, dict) else data
    if isinstance(data, dict) and "words" not in data:
        words = data

    silences = detect_silence(args.audio)
    print(f"  detected {len(silences)} silence regions ≥0.5s")

    n_shifted = 0
    for w in words:
        for s, e in silences:
            if s <= w["start"] < e:
                n_shifted += 1
                break
    align(words, silences)
    print(f"  shifted {n_shifted} word starts to align with speech onset")

    out_data = {"words": words} if isinstance(data, dict) else words
    args.out.write_text(json.dumps(out_data, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
