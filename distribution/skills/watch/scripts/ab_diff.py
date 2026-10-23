#!/usr/bin/env python3
"""A/B compare two clips into one labeled PNG.

  --mode side : matched-timestamp frames placed side by side. Use to compare
                YOUR render vs a REFERENCE reel (style / captions / framing).
  --mode diff : pixel diff with a RED overlay where the two differ, over a dimmed
                base. Use for v1-vs-v2 of the SAME clip — subtle changes pop.
                (the "red diff" trick from the qckfx demo)

Usage:
  ab_diff.py A B [--mode side|diff] [--n 6] [--tile-w 360]
                 [--thresh 28] [--label-a A] [--label-b B] [--out PATH]
"""
import argparse, os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _util import ffprobe_duration, extract_frame, load_font, fmt_ts
from PIL import Image, ImageDraw
import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("--mode", choices=["side", "diff"], default="side")
    ap.add_argument("--n", type=int, default=6)
    ap.add_argument("--tile-w", type=int, default=360)
    ap.add_argument("--thresh", type=int, default=28, help="diff: per-channel change threshold")
    ap.add_argument("--label-a", default="A")
    ap.add_argument("--label-b", default="B")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    da, db = ffprobe_duration(a.a), ffprobe_duration(a.b)
    tmp = tempfile.mkdtemp(prefix="ab_")
    pairs = []
    for i in range(a.n):
        ta, tb = da * (i + 0.5) / a.n, db * (i + 0.5) / a.n  # proportional match
        pa, pb = os.path.join(tmp, f"a{i}.jpg"), os.path.join(tmp, f"b{i}.jpg")
        extract_frame(a.a, ta, pa, width=a.tile_w)
        extract_frame(a.b, tb, pb, width=a.tile_w)
        if os.path.exists(pa) and os.path.exists(pb):
            pairs.append((ta, tb, pa, pb))
    if not pairs:
        print("ERROR: no frames", file=sys.stderr)
        sys.exit(1)

    tw, th = Image.open(pairs[0][2]).size
    lbl, pad = 22, 6
    font = load_font(15)

    if a.mode == "side":
        cellw = tw * 2 + pad
        cellh = th + lbl
        sheet = Image.new("RGB", (cellw + 2 * pad, len(pairs) * (cellh + pad) + pad), (18, 18, 20))
        d = ImageDraw.Draw(sheet)
        for i, (ta, tb, pa, pb) in enumerate(pairs):
            y = pad + i * (cellh + pad)
            sheet.paste(Image.open(pa).resize((tw, th)), (pad, y))
            sheet.paste(Image.open(pb).resize((tw, th)), (pad + tw + pad, y))
            d.rectangle([pad, y + th, pad + cellw, y + th + lbl], fill=(0, 0, 0))
            d.text((pad + 4, y + th + 3),
                   f"{a.label_a} {fmt_ts(ta)}      |      {a.label_b} {fmt_ts(tb)}",
                   fill=(0, 220, 120), font=font)
        out = a.out or "ab_side.png"
    else:
        cols = 3
        rows = (len(pairs) + cols - 1) // cols
        cellh = th + lbl
        sheet = Image.new("RGB", (cols * tw + pad * (cols + 1), rows * (cellh + pad) + pad), (18, 18, 20))
        d = ImageDraw.Draw(sheet)
        for i, (ta, tb, pa, pb) in enumerate(pairs):
            A = Image.open(pa).convert("RGB").resize((tw, th))
            B = Image.open(pb).convert("RGB").resize((tw, th))
            na, nb = np.asarray(A).astype(np.int16), np.asarray(B).astype(np.int16)
            mask = np.abs(na - nb).max(axis=2) > a.thresh
            base = (np.asarray(A).astype(np.float32) * 0.45).astype(np.uint8)
            base[mask] = [255, 40, 40]
            r, c = divmod(i, cols)
            x = pad + c * (tw + pad)
            y = pad + r * (cellh + pad)
            sheet.paste(Image.fromarray(base), (x, y))
            d.rectangle([x, y + th, x + tw, y + th + lbl], fill=(0, 0, 0))
            d.text((x + 4, y + th + 3), f"{fmt_ts(ta)}  d{round(100*mask.mean(),1)}%",
                   fill=(255, 80, 80), font=font)
        out = a.out or "ab_diff.png"

    sheet.save(out)
    print(out)


if __name__ == "__main__":
    main()
