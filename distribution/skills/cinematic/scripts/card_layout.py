#!/usr/bin/env python3
"""card_layout.py — THE canvas rig for the cinematic-card style.

Measured from the reference reels (see STYLE_SPEC.md §1):
  canvas 1080x1920 black · card 980x980 · x 50..1029 · y 470..1449 (v-centered)
  corner radius 48px · source scaled to FILL the card (center-crop), never letterboxed

Modes:
  single  one 980x980 square card
  split   two 980x696 cards stacked, 29px gap, whole stack v-centered
  colour  flat white / flat black card (interstitial)

Usage:
  card_layout.py single SRC OUT --ss 10 --t 8 [--crop-x 0.5] [--crop-y 0.4]
  card_layout.py split  SRC_TOP SRC_BOT OUT --ss-top 3 --ss-bot 12 --t 2
  card_layout.py colour OUT --fill white --t 0.8
"""
import argparse, os, subprocess, sys, tempfile
from PIL import Image, ImageDraw

W, H = 1080, 1920
CARD_W = 980
CARD_X = 50
SQ_H = 980
SQ_Y = 470
SPLIT_H, SPLIT_GAP = 696, 29
SPLIT_Y = 258      # measured off the reference (stack sits ~8px below true centre)
RADIUS = 48


def mask_png(w, h, path):
    im = Image.new("L", (w, h), 0)
    ImageDraw.Draw(im).rounded_rectangle([0, 0, w - 1, h - 1], RADIUS, fill=255)
    im.save(path)
    return path


def fill_chain(w, h, cx, cy):
    """scale-to-fill + crop, anchored at fractional cx/cy (0..1)."""
    return (f"scale={w}:{h}:force_original_aspect_ratio=increase,"
            f"crop={w}:{h}:(iw-{w})*{cx}:(ih-{h})*{cy}")


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"ffmpeg failed:\n{r.stderr[-2500:]}")


def single(a):
    tmp = tempfile.mkdtemp(prefix="card_")
    m = mask_png(CARD_W, SQ_H, f"{tmp}/m.png")
    fc = (f"[0:v]{fill_chain(CARD_W, SQ_H, a.crop_x, a.crop_y)},format=yuva420p[c];"
          f"[1:v]format=gray[m];[c][m]alphamerge[card];"
          f"color=c=black:s={W}x{H}:r=30[bg];"
          f"[bg][card]overlay={CARD_X}:{SQ_Y}:shortest=1,format=yuv420p[v]")
    run(["ffmpeg", "-v", "error", "-y", "-ss", str(a.ss), "-t", str(a.t), "-i", a.src,
         "-i", m, "-filter_complex", fc, "-map", "[v]",
         "-map", "0:a?", "-ss", "0", "-t", str(a.t),
         "-c:v", "libx264", "-crf", "17", "-preset", "medium", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", a.out])


def split(a):
    tmp = tempfile.mkdtemp(prefix="card_")
    m = mask_png(CARD_W, SPLIT_H, f"{tmp}/m.png")
    y2 = SPLIT_Y + SPLIT_H + SPLIT_GAP
    fc = (f"[0:v]{fill_chain(CARD_W, SPLIT_H, 0.5, 0.4)},format=yuva420p[t];"
          f"[1:v]{fill_chain(CARD_W, SPLIT_H, 0.5, 0.4)},format=yuva420p[b];"
          f"[2:v]format=gray,split=2[m1][m2];"
          f"[t][m1]alphamerge[tc];[b][m2]alphamerge[bc];"
          f"color=c=black:s={W}x{H}:r=30[bg];"
          f"[bg][tc]overlay={CARD_X}:{SPLIT_Y}[s1];"
          f"[s1][bc]overlay={CARD_X}:{y2}:shortest=1,format=yuv420p[v]")
    run(["ffmpeg", "-v", "error", "-y",
         "-ss", str(a.ss_top), "-t", str(a.t), "-i", a.src_top,
         "-ss", str(a.ss_bot), "-t", str(a.t), "-i", a.src_bot,
         "-i", m, "-filter_complex", fc, "-map", "[v]",
         "-c:v", "libx264", "-crf", "17", "-preset", "medium", "-pix_fmt", "yuv420p",
         "-an", a.out])


def colour(a):
    tmp = tempfile.mkdtemp(prefix="card_")
    m = mask_png(CARD_W, SQ_H, f"{tmp}/m.png")
    fc = (f"color=c={a.fill}:s={CARD_W}x{SQ_H}:r=30,format=yuva420p[c];"
          f"[0:v]format=gray[m];[c][m]alphamerge[card];"
          f"color=c=black:s={W}x{H}:r=30[bg];"
          f"[bg][card]overlay={CARD_X}:{SQ_Y}:shortest=1,format=yuv420p[v]")
    run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-t", str(a.t), "-i", m,
         "-filter_complex", fc, "-map", "[v]", "-t", str(a.t),
         "-c:v", "libx264", "-crf", "17", "-preset", "medium", "-pix_fmt", "yuv420p",
         "-an", a.out])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="mode", required=True)
    s = sub.add_parser("single"); s.add_argument("src"); s.add_argument("out")
    s.add_argument("--ss", type=float, default=0); s.add_argument("--t", type=float, required=True)
    s.add_argument("--crop-x", type=float, default=0.5); s.add_argument("--crop-y", type=float, default=0.4)
    s.set_defaults(fn=single)
    p = sub.add_parser("split"); p.add_argument("src_top"); p.add_argument("src_bot"); p.add_argument("out")
    p.add_argument("--ss-top", type=float, default=0); p.add_argument("--ss-bot", type=float, default=0)
    p.add_argument("--t", type=float, required=True); p.set_defaults(fn=split)
    c = sub.add_parser("colour"); c.add_argument("out")
    c.add_argument("--fill", default="white"); c.add_argument("--t", type=float, default=0.8)
    c.set_defaults(fn=colour)
    a = ap.parse_args(); a.fn(a)
    print(a.out)
