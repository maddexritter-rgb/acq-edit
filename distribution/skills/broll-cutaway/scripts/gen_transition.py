#!/usr/bin/env python3
"""Generate a full-frame flash + glare-sweep transition overlay (RGBA -> ProRes 4444 with
alpha) for full-screen B-roll cutaways. White flash IN at the start, a diagonal glare streak
sweeping across early, white flash OUT at the end -- sized to the insert's duration. Overlaid
on top of a full-screen B-roll clip in ffmpeg so the in/out cuts read as intentional/premium.

CLI:
  gen_transition.py --out overlay.mov --dur 2.0 --fps 30 --w 1080 --h 1920
Importable:
  from gen_transition import gen_transition
  gen_transition("overlay.mov", dur=2.0, fps=30, w=1080, h=1920)

needs: pip install --break-system-packages numpy pillow
"""
import os
import sys
import argparse
import shutil
import subprocess
import tempfile
import numpy as np
from PIL import Image


def gen_transition(out_path, dur=2.0, fps=30, w=1080, h=1920,
                   flash=238.0, flash_in_s=0.20, flash_out_s=0.27,
                   glare_start_s=0.13, glare_dur_s=0.87,
                   glare_width=95.0, glare_angle=0.30, ffmpeg="ffmpeg"):
    """Write a ProRes-4444 (alpha) flash/glare transition overlay to out_path. Returns out_path.

    The overlay is sized to `dur`: flash-in lands at the start (hides the cut INTO the b-roll),
    flash-out lands at the end (hides the cut BACK), glare sweeps across diagonally early.
    """
    N = max(2, int(round(dur * fps)))
    fi = max(1, int(round(flash_in_s * fps)))
    fo = max(1, int(round(flash_out_s * fps)))
    fo_start = max(fi + 1, N - fo)
    gs = int(round(glare_start_s * fps))
    ge = max(gs + 1, gs + int(round(glare_dur_s * fps)))
    glare_peak = max(0.0, flash - 33.0)
    Y, X = np.mgrid[0:h, 0:w]
    tmp = tempfile.mkdtemp(prefix="brollxn_")
    try:
        for f in range(N):
            a = np.zeros((h, w), dtype=np.float32)
            if f <= fi:                                   # flash IN (white -> clear)
                a = np.maximum(a, flash * (1.0 - f / float(fi)))
            if f >= fo_start:                             # flash OUT (clear -> white)
                a = np.maximum(a, flash * ((f - fo_start) / float(max(1, N - 1 - fo_start))))
            if gs <= f <= ge:                             # diagonal glare sweep across the frame
                p = (f - gs) / float(max(1, ge - gs))
                cx = -300.0 + p * (w + 600.0)
                d = X - (cx + glare_angle * (Y - h / 2.0))
                a = np.maximum(a, np.exp(-(d ** 2) / (2.0 * glare_width ** 2)) * glare_peak)
            img = np.zeros((h, w, 4), dtype=np.uint8)
            img[:, :, 0:3] = 255                          # white streak/flash
            img[:, :, 3] = np.clip(a, 0, 255).astype(np.uint8)
            Image.fromarray(img, "RGBA").save(os.path.join(tmp, f"f_{f:04d}.png"))
        out_dir = os.path.dirname(os.path.abspath(out_path))
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        subprocess.run([ffmpeg, "-y", "-framerate", str(fps),
                        "-i", os.path.join(tmp, "f_%04d.png"),
                        "-c:v", "prores_ks", "-profile:v", "4444",
                        "-pix_fmt", "yuva444p10le", out_path],
                       check=True, capture_output=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return out_path


def main():
    p = argparse.ArgumentParser(description="Generate a flash/glare B-roll transition overlay (ProRes 4444 alpha).")
    p.add_argument("--out", required=True)
    p.add_argument("--dur", type=float, default=2.0)
    p.add_argument("--fps", type=int, default=30)
    p.add_argument("--w", type=int, default=1080)
    p.add_argument("--h", type=int, default=1920)
    p.add_argument("--flash", type=float, default=238.0, help="flash brightness 0-255")
    p.add_argument("--glare-width", type=float, default=95.0, help="streak softness (px sigma)")
    p.add_argument("--glare-angle", type=float, default=0.30, help="diagonal slant of the streak")
    p.add_argument("--ffmpeg", default="ffmpeg")
    a = p.parse_args()
    out = gen_transition(a.out, dur=a.dur, fps=a.fps, w=a.w, h=a.h, flash=a.flash,
                         glare_width=a.glare_width, glare_angle=a.glare_angle, ffmpeg=a.ffmpeg)
    print(out)


if __name__ == "__main__":
    main()
