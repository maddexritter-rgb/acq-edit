#!/usr/bin/env python3
# LEGACY 2026-06-08 — NOT the canonical face-tracker (that is qa_reframe_v2.py --preset <name>,
# Y-LOCK + xcenter box). STILL LIVE, do not delete: listicle-short/scripts/build_short.py runs
# reframe.sh -> reframe_h2v.py -> detect_face_dense.py at two call sites (verified 2026-08-03).
# (The old rationale named shortform/pipeline.py + qa_detect_speaker.py — both long gone.)
"""Dense (per-frame) multi-cascade Haar face detector -> reframe_h2v.py face-curve.

THE canonical face detector for the reframe pipeline. Emits ONE entry per source
frame (reframe_h2v indexes the curve by frame_idx) with the rich fields the
reframer reads. Replaces (a) the dead MediaPipe trackers (mp.solutions removed in
mediapipe 0.10.35) and (b) the sparse ~6/sec detect_face_curve.py.

Output: {"meta":{"fps":F,"w":W,"h":H}, "curve":[{"t","face_cx","face_cy","face_h","conf"}, ...]}
Usage: detect_face_dense.py <video> <out.json> [detect_width=960]
"""
import cv2, json, sys, statistics
from pathlib import Path

video, out = sys.argv[1], sys.argv[2]
DETW = int(sys.argv[3]) if len(sys.argv) > 3 else 960

casc = cv2.data.haarcascades
fa2  = cv2.CascadeClassifier(casc + "haarcascade_frontalface_alt2.xml")
fdef = cv2.CascadeClassifier(casc + "haarcascade_frontalface_default.xml")
prof = cv2.CascadeClassifier(casc + "haarcascade_profileface.xml")

def detect(gray):
    ms = (int(gray.shape[1] * 0.07),) * 2
    for c in (fa2, fdef):
        f = c.detectMultiScale(gray, 1.1, 5, minSize=ms)
        if len(f): return max(f, key=lambda b: b[2] * b[3])
    f = prof.detectMultiScale(gray, 1.1, 5, minSize=ms)
    if len(f): return max(f, key=lambda b: b[2] * b[3])
    fl = cv2.flip(gray, 1)
    f = prof.detectMultiScale(fl, 1.1, 5, minSize=ms)
    if len(f):
        x, y, w, h = max(f, key=lambda b: b[2] * b[3])
        return (gray.shape[1] - x - w, y, w, h)
    return None

cap = cv2.VideoCapture(video)
if not cap.isOpened():
    sys.exit(f"cannot open {video}")
fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)); H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
scale = DETW / W if W > DETW else 1.0

curve = []; idx = 0; last = None; hits = 0
while True:
    ok, frame = cap.read()
    if not ok: break
    small = cv2.resize(frame, (int(W * scale), int(H * scale))) if scale != 1.0 else frame
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    d = detect(gray); t = idx / fps
    if d is not None:
        x, y, w, h = d
        cx = (x + w / 2) / small.shape[1] * W
        cy = (y + h / 2) / small.shape[0] * H
        fh = h / small.shape[0] * H
        last = (cx, cy, fh); hits += 1
        curve.append({"t": round(t, 3), "face_cx": round(cx, 1), "face_cy": round(cy, 1),
                      "face_h": round(fh, 1), "conf": 1.0})
    elif last:
        curve.append({"t": round(t, 3), "face_cx": round(last[0], 1), "face_cy": round(last[1], 1),
                      "face_h": round(last[2], 1), "conf": 0.0})
    else:
        curve.append({"t": round(t, 3), "face_cx": W * 0.5, "face_cy": H * 0.42,
                      "face_h": H * 0.25, "conf": 0.0})
    idx += 1
cap.release()
json.dump({"meta": {"fps": fps, "w": W, "h": H}, "curve": curve}, open(out, "w"))
hitpts = [(c["face_cx"] / W, c["face_cy"] / H) for c in curve if c["conf"] > 0]
pct = 100 * hits // max(1, len(curve))
if hitpts:
    mcx = statistics.median([p[0] for p in hitpts]); mcy = statistics.median([p[1] for p in hitpts])
    print(f"{Path(video).name}: frames={len(curve)} hits={hits} ({pct}%) "
          f"median_cx={mcx:.3f} median_cy={mcy:.3f} fps={fps:.3f}")
    if pct < 25:
        print(f"  note: low hit-rate ({pct}%) — typical for hat+beard. Median is clean, so "
              f"X is near-static (correct for a stationary subject). Verify framing by eye.")
else:
    print(f"{Path(video).name}: frames={len(curve)} hits=0 — NO FACES (check footage / detect width)")
