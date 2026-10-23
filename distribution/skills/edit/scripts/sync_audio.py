#!/usr/bin/env python3
"""Find the time offset between a separate WAV mic recording and the MP4's embedded audio.

Cross-correlates a probe window from the WAV against a scan window of the MP4 at a
downsampled rate, then prints the offset (in seconds) where WAV sample 0 aligns on
the MP4 timeline.

Positive offset = WAV recording started LATER than video.
Negative offset = WAV recording started EARLIER than video.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
try:
    import librosa
    from scipy.signal import correlate, correlation_lags
except ImportError:
    sys.stderr.write("Install deps: pip install librosa scipy numpy\n")
    sys.exit(2)


def find_offset(mp4: Path, wav: Path, sr: int, wav_probe_start: float,
                wav_probe_len: float, mp4_scan_len: float) -> tuple[float, float]:
    wav_probe, _ = librosa.load(str(wav), sr=sr, mono=True,
                                 offset=wav_probe_start, duration=wav_probe_len)
    mp4_scan, _ = librosa.load(str(mp4), sr=sr, mono=True,
                                offset=0.0, duration=mp4_scan_len)
    if len(wav_probe) == 0 or len(mp4_scan) == 0:
        raise RuntimeError("One of the audio loads returned zero samples.")
    wav_probe = wav_probe / (np.max(np.abs(wav_probe)) + 1e-9)
    mp4_scan = mp4_scan / (np.max(np.abs(mp4_scan)) + 1e-9)

    corr = correlate(mp4_scan, wav_probe, mode="valid")
    lags = correlation_lags(len(mp4_scan), len(wav_probe), mode="valid")
    peak_idx = int(np.argmax(np.abs(corr)))
    peak_lag_samples = int(lags[peak_idx])
    peak_val = float(corr[peak_idx])

    peak_seconds = peak_lag_samples / sr
    offset_wav_start_in_mp4 = peak_seconds - wav_probe_start

    # Confidence: peak vs median absolute correlation.
    sorted_corr = np.sort(np.abs(corr))[::-1]
    median_abs = sorted_corr[len(sorted_corr) // 2] + 1e-9
    ratio = float(abs(peak_val) / median_abs)
    return offset_wav_start_in_mp4, ratio


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mp4", type=Path)
    ap.add_argument("wav", type=Path)
    ap.add_argument("--sr", type=int, default=8000, help="Downsample rate for correlation")
    ap.add_argument("--wav-probe-start", type=float, default=5.0)
    ap.add_argument("--wav-probe-len", type=float, default=60.0)
    ap.add_argument("--mp4-scan-len", type=float, default=300.0,
                    help="How much of the MP4 to scan from the start")
    ap.add_argument("--out", type=Path, default=Path("sync.json"))
    args = ap.parse_args()

    offset, confidence = find_offset(
        args.mp4, args.wav, args.sr,
        args.wav_probe_start, args.wav_probe_len, args.mp4_scan_len,
    )
    result = {
        "mp4": str(args.mp4),
        "wav": str(args.wav),
        "wav_start_in_mp4_seconds": round(offset, 3),
        "confidence": round(confidence, 2),
    }
    args.out.write_text(json.dumps(result, indent=2))
    print(f"WAV start aligns to MP4 time: {offset:.3f}s  (confidence {confidence:.2f})")
    print(f"Wrote {args.out}")
    if confidence < 3.0:
        print("WARNING: low confidence — verify by ear before trusting this offset.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
