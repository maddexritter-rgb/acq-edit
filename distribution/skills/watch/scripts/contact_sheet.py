#!/usr/bin/env python3
"""Contact sheet — tile N evenly-spaced frames from a clip into ONE labeled PNG.

Gives Claude a single-image overview of a clip's whole arc (then drill into
specific timestamps with the MCP video_detail/video_watch, or re-run with a
narrow --start/--end). Read the output PNG to view it.

Usage:
  contact_sheet.py INPUT [--n 12] [--cols 4] [--start 0] [--end DUR]
                         [--tile-w 360] [--out PATH]
"""
import argparse, os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _util import ffprobe_duration, extract_frame, load_font, fmt_ts
from PIL import Image, ImageDraw


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("--n", type=int, default=12)
    ap.add_argument("--cols", type=int, default=4)
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--end", type=float, default=None)
    ap.add_argument("--tile-w", type=int, default=360)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    dur = ffprobe_duration(a.input)
    end = a.end if (a.end and a.end > a.start) else dur
    span = max(end - a.start, 0.01)
    times = [a.start + span * (i + 0.5) / a.n for i in range(a.n)]

    tmp = tempfile.mkdtemp(prefix="cs_")
    tiles = []
    for i, t in enumerate(times):
        p = os.path.join(tmp, f"f{i:03d}.jpg")
        if extract_frame(a.input, t, p, width=a.tile_w):
            tiles.append((t, p))
    if not tiles:
        print("ERROR: no frames extracted", file=sys.stderr)
        sys.exit(1)

    tw, th = Image.open(tiles[0][1]).size
    cols = a.cols
    rows = (len(tiles) + cols - 1) // cols
    pad, lbl = 6, 22
    cell_h = th + lbl
    sheet = Image.new("RGB", (cols * tw + pad * (cols + 1),
                              rows * (cell_h + pad) + pad), (18, 18, 20))
    d = ImageDraw.Draw(sheet)
    font = load_font(15)
    for idx, (t, p) in enumerate(tiles):
        r, c = divmod(idx, cols)
        x = pad + c * (tw + pad)
        y = pad + r * (cell_h + pad)
        try:
            sheet.paste(Image.open(p).resize((tw, th)), (x, y))
        except Exception:
            continue
        d.rectangle([x, y + th, x + tw, y + th + lbl], fill=(0, 0, 0))
        d.text((x + 4, y + th + 3), f"#{idx}  {fmt_ts(t)}", fill=(0, 220, 120), font=font)

    out = a.out or os.path.splitext(a.input)[0] + "_contact.png"
    sheet.save(out)
    print(out)


if __name__ == "__main__":
    main()
