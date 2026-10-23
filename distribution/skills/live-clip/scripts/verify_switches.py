#!/usr/bin/env python3
"""Verify camera-switch candidates: a REAL angle switch discontinuously moves or
resizes the face box across the cut frame; a gesture/lighting flicker doesn't.

  python3 verify_switches.py <src.mp4> <candidates.txt> <out.json>

For each candidate time t (a showinfo pts_time = first frame of the new shot),
detect the face on frame(t - 1/fps) and frame(t): IoU < 0.55 OR face-height
ratio outside [0.8, 1.25] -> verified switch. No face on either side (graphics,
wide) -> fall back to frame-histogram correlation < 0.6.
Outputs [{"t": pts_time, "frame": n, "verdict": "switch"|"reject", "why": ...}].
"""
import json, subprocess, sys
import numpy as np
import cv2
from pathlib import Path

SRC, CAND, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
FPS = 30.0
YUNET = str(Path(__file__).resolve().parents[2] / "horizontal-to-vertical/scripts/yunet.onnx")


def grab(t):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error",
                        "-ss", f"{t:.4f}", "-i", SRC, "-frames:v", "1",
                        "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
                       capture_output=True)
    buf = np.frombuffer(r.stdout, dtype=np.uint8)
    if buf.size < 1280 * 720 * 3:
        return None
    return buf[: 1280 * 720 * 3].reshape(720, 1280, 3)


det = cv2.FaceDetectorYN.create(YUNET, "", (1280, 720), 0.6)


def face_box(img):
    _, faces = det.detect(img)
    if faces is None or not len(faces):
        return None
    f = faces[np.argmax(faces[:, -1])]
    return f[0], f[1], f[2], f[3]


def iou(a, b):
    ax0, ay0, ax1, ay1 = a[0], a[1], a[0] + a[2], a[1] + a[3]
    bx0, by0, bx1, by1 = b[0], b[1], b[0] + b[2], b[1] + b[3]
    ix = max(0, min(ax1, bx1) - max(ax0, bx0))
    iy = max(0, min(ay1, by1) - max(ay0, by0))
    inter = ix * iy
    union = a[2] * a[3] + b[2] * b[3] - inter
    return inter / union if union > 0 else 0.0


def hist_corr(i1, i2):
    h = [cv2.calcHist([cv2.cvtColor(i, cv2.COLOR_BGR2HSV)], [0, 1], None,
                      [32, 32], [0, 180, 0, 256]) for i in (i1, i2)]
    return float(cv2.compareHist(h[0], h[1], cv2.HISTCMP_CORREL))


cands = [float(x) for x in open(CAND) if x.strip()]
results = []
for t in cands:
    before, after = grab(t - 1.0 / FPS), grab(t)
    if before is None or after is None:
        results.append({"t": t, "verdict": "reject", "why": "frame grab failed"})
        continue
    fb, fa = face_box(before), face_box(after)
    if fb is not None and fa is not None:
        v = iou(fb, fa)
        hr = fa[3] / fb[3] if fb[3] > 0 else 1.0
        switch = v < 0.55 or not (0.8 <= hr <= 1.25)
        why = f"face IoU {v:.2f}, h-ratio {hr:.2f}"
    else:
        c = hist_corr(before, after)
        switch = c < 0.6
        why = f"no face ({'before' if fb is None else 'after'}); hist corr {c:.2f}"
    results.append({"t": t, "frame": round(t * FPS),
                    "verdict": "switch" if switch else "reject", "why": why})
    print(results[-1], flush=True)

json.dump(results, open(OUT, "w"), indent=1)
n = sum(1 for r in results if r["verdict"] == "switch")
print(f"\n{n}/{len(results)} verified switches -> {OUT}")
