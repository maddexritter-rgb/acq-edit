#!/usr/bin/env python3
"""framing_gate.py — flag a talking-head framed TOO WIDE (face too small in frame).

Origin: ThreeFunctions V5 (2026-06-22) — Alex shipped as a small full-body standing figure (face ~11% of
frame height, detected in only 37% of frames); a vertical short needs a tight face/upper-body crop (~15-30%).
Samples frames, detects the largest face, measures face-height / frame-height, and FAILS when the median is
below a floor.

CAVEAT (calibrated conservative): Haar misses non-frontal/moving faces, so a LOW detect-rate is treated as a
soft 'eyeball it' advisory, not a hard fail — only a confident, well-detected, clearly-small median FAILS.
Split-screen panels legitimately have ~30% faces, so the median naturally clears the floor for split clips;
to focus on a single-cam span pass --start/--end.

Usage: framing_gate.py --clip CLIP.mp4 [--min-face-h 0.13] [--start S] [--end S]
Exit 0 = ok / advisory · 1 = TOO WIDE (block).
"""
import cv2, argparse, statistics as st, sys, os

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clip", required=True)
    ap.add_argument("--min-face-h", type=float, default=0.13, help="min median face-height as fraction of frame (default 0.13)")
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--end", type=float, default=1e9)
    a = ap.parse_args()
    name = os.path.basename(a.clip)
    face = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    cap = cv2.VideoCapture(a.clip)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)); H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if not W or not H:
        print(f"framing_gate: could not open {name}"); return 0
    fh = []; n = 0; present = 0; i = 0; step = max(1, int(fps))   # ~1 fps
    while True:
        ok = cap.grab()
        if not ok: break
        t = i / fps
        if a.start <= t <= a.end and i % step == 0:
            ok, fr = cap.retrieve()
            if ok:
                n += 1; g = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY); sc = 480 / W
                gs = cv2.resize(g, (480, int(H * sc)))
                d = face.detectMultiScale(gs, 1.2, 5, minSize=(24, 24))
                if len(d):
                    present += 1; bb = max(d, key=lambda r: r[2] * r[3])
                    fh.append((bb[3] / sc) / H)
        i += 1
    cap.release()
    print(f"=== framing_gate ({name}) ===")
    if n == 0:
        print("  no frames sampled"); return 0
    rate = present / n
    if not fh:
        print(f"  ⚠ face detected in 0/{n} frames — likely too small or non-frontal. EYEBALL the framing.")
        return 0
    med = st.median(fh)
    print(f"  face-height median = {med*100:.1f}% of frame · detected {present}/{n} ({rate*100:.0f}%) · floor {a.min_face_h*100:.0f}%")
    if rate >= 0.20 and med < a.min_face_h:
        print(f"  ✗ TOO WIDE — face is only ~{med*100:.0f}% of frame height (want >= {a.min_face_h*100:.0f}%). "
              f"Re-reframe: punch in + face-track so head+torso fill the frame, not the whole stage.")
        return 1
    if rate < 0.20:
        print(f"  ⚠ face rarely detected ({rate*100:.0f}%) — non-frontal or too small; eyeball the framing.")
        return 0
    print(f"  ✓ framing ok (face ~{med*100:.0f}% of frame)")
    return 0

if __name__ == "__main__":
    sys.exit(main())
