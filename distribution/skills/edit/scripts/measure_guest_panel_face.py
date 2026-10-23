#!/usr/bin/env python3
"""Measure the guest face position in a delivered Q&A clip's lower split-screen panel.

Extracts a frame from clip-time t (default 1.0s — when the split is showing), crops the
BOTTOM HALF (= the guest panel), runs Haar face detection on it, and reports the face
center's y% within the panel.

Threshold per the L1 post-mortem (2026-06-16): face center should land in the UPPER THIRD
of the panel (face_y% < 35%). Above that = guest reads as "too low," requires reframer
re-tune (lower eye / higher zoom).

Usage:
  measure_guest_panel_face.py <clip.mp4> [--t 1.0] [--out report.json]

Exit 0 = face in upper third (<35%). Exit 1 = face below upper third (≥35%) OR not detected.
"""
from __future__ import annotations
import argparse, json, subprocess, sys, tempfile
from pathlib import Path

def find_face_in_bottom_panel(clip: str, t: float = 1.0) -> dict:
    """Extract frame at t, crop bottom half, run Haar face-detect, return face_y_pct of panel."""
    import cv2
    with tempfile.TemporaryDirectory() as td:
        frame_path = f"{td}/frame.png"
        # Extract frame
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                        "-ss", f"{t:.3f}", "-i", clip, "-frames:v", "1", frame_path],
                       check=True)
        img = cv2.imread(frame_path)
        if img is None:
            return {"error": "could not read frame"}
        h, w = img.shape[:2]
        # Bottom half = guest panel
        bot = img[h//2:, :]
        bh, bw = bot.shape[:2]
        gray = cv2.cvtColor(bot, cv2.COLOR_BGR2GRAY)
        # Try multiple cascades — frontal first, then profile
        cascades = [
            cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_alt2.xml"),
            cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml"),
            cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_profileface.xml"),
        ]
        face = None
        cascade_used = None
        for i, c in enumerate(cascades):
            faces = c.detectMultiScale(gray, 1.1, 5, minSize=(int(bw*0.07), int(bw*0.07)))
            if len(faces):
                face = max(faces, key=lambda b: b[2]*b[3])
                cascade_used = ["alt2","default","profile"][i]
                break
        if face is None:
            return {"error": "no face detected in guest panel", "panel_h": bh, "panel_w": bw}
        x, y, fw, fh = face
        face_cy = y + fh / 2
        face_y_pct = round(face_cy / bh * 100, 1)
        face_h_pct = round(fh / bh * 100, 1)
        return {
            "frame_t": t,
            "panel_h": bh, "panel_w": bw,
            "face_x": int(x + fw/2), "face_y": int(face_cy),
            "face_h_px": int(fh),
            "face_y_pct_of_panel": face_y_pct,
            "face_h_pct_of_panel": face_h_pct,
            "cascade_used": cascade_used,
        }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("clip", help="path to delivered Q&A .mp4 with split-screen open")
    ap.add_argument("--t", type=float, default=1.0, help="clip-time to sample (default 1.0s)")
    ap.add_argument("--threshold", type=float, default=55.0, help="face_y pct threshold; >= this = too low")
    ap.add_argument("--target-face-h", type=float, default=35.0, help="TARGET face height as pct of panel. Measured from IG reference reels 2026-06-17: guest is a chest-up medium at ~35%% face_h. >42%% = too big (Maddex 'way too big'); <28%% = too small. Tune guest_split.zoom: zoom_new = zoom_cur * (35/measured_face_h).")
    ap.add_argument("--out", type=Path, help="JSON report path")
    args = ap.parse_args()

    result = find_face_in_bottom_panel(args.clip, args.t)
    result["clip"] = args.clip
    if "error" in result:
        verdict = "FAIL"
        print(f"FAIL  {Path(args.clip).name}  {result['error']}")
    else:
        too_low = result["face_y_pct_of_panel"] >= args.threshold
        verdict = "FAIL" if too_low else "PASS"
        print(f"{verdict}  {Path(args.clip).name}  face_y={result['face_y_pct_of_panel']}% face_h={result['face_h_pct_of_panel']}% (cascade={result['cascade_used']})")

    result["verdict"] = verdict
    if args.out:
        args.out.write_text(json.dumps(result, indent=2))
    sys.exit(0 if verdict == "PASS" else 1)

if __name__ == "__main__":
    main()
