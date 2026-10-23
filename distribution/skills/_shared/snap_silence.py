#!/usr/bin/env python3
"""snap_silence.py — purely-acoustic cut-boundary snapping (no transcript needed).

Given a source file + an approximate cut time, returns the nearest inter-word SILENCE so a splice
lands clean (no mid-word chop, no pop). Used by the render cut stage so the snap-to-silence rule is
the DEFAULT, not just something `audit-audio` catches after the fact.

Transcript-free cousin of faded_trim_cut.py's quietest()/snap_end()/snap_start(): the render cut
stage only has in/out timestamps (cuts.json), not word indices, so it snaps acoustically around the
given boundary. Reads audio via ffmpeg's FAST seek (`-ss` before `-i`) — a small window at any offset,
even in a 2-hour source — instead of librosa/audioread (which decodes from the start = slow on long
sources). numpy-only; no librosa dependency.
"""
import subprocess
import numpy as np


def _read_window(src, t_lo, dur, sr=16000):
    """Decode a small mono PCM window [t_lo, t_lo+dur] of `src` via ffmpeg fast-seek. None on failure."""
    try:
        p = subprocess.run(
            ["ffmpeg", "-v", "error", "-ss", f"{max(0.0, t_lo):.3f}", "-i", str(src),
             "-t", f"{max(0.02, dur):.3f}", "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"],
            capture_output=True, check=True)
        return np.frombuffer(p.stdout, dtype=np.float32)
    except Exception:
        return None


def quietest(src, t_lo, t_hi, sr=16000, win=0.01):
    """Time of the quietest ~`win`s window in [t_lo, t_hi] of `src`'s audio. None if unavailable."""
    t_lo = max(0.0, float(t_lo))
    if t_hi - t_lo < 0.02:
        return t_lo
    y = _read_window(src, t_lo, t_hi - t_lo, sr)
    if y is None or len(y) == 0:
        return None
    fl = int(win * sr)
    best_db, best_t = 1e9, (t_lo + t_hi) / 2
    for k in range(0, max(1, len(y) - fl), max(1, fl // 2)):
        seg = y[k:k + fl]
        db = 20 * np.log10(float(np.sqrt(np.mean(seg ** 2)) + 1e-9))
        if db < best_db:
            best_db, best_t = db, t_lo + (k + fl / 2) / sr
    return best_t


def snap_in(src, t, back=0.10, fwd=0.05):
    """Snap a segment START into the leading silence just before the word (quiet first sample,
    no previous-word tail dragged in). Returns the snapped time, or the original t if unavailable."""
    q = quietest(src, t - back, t + fwd)
    return q if q is not None else t


def snap_out(src, t, back=0.06, fwd=0.20):
    """Snap a segment END into the trailing silence after the word's TRUE acoustic end (so the word's
    full decay is kept and the cut lands in silence). Returns the snapped time, or the original t."""
    q = quietest(src, t - back, t + fwd)
    return q if q is not None else t


if __name__ == "__main__":   # self-test: snap a few times on a clip, print snapped Δ + dB at each
    import sys
    src = sys.argv[1]
    for t in [float(x) for x in sys.argv[2:]]:
        si, so = snap_in(src, t), snap_out(src, t)
        def db(tt):
            y = _read_window(src, tt - 0.015, 0.03)
            return 20 * np.log10(float(np.sqrt(np.mean(y ** 2)) + 1e-9)) if y is not None and len(y) else -99
        print(f"  t={t:.3f} ({db(t):6.1f}dB) -> in {si:.3f} ({db(si):6.1f}dB)  out {so:.3f} ({db(so):6.1f}dB)")
