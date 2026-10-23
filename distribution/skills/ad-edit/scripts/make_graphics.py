#!/usr/bin/env python3
"""make_graphics.py — on-brand overlay graphics for paid ads.

  python3 make_graphics.py <outdir> [font.ttf]

Produces transparent PNGs sized for the 1080x1920 canvas:
  g_stat.png    big-number proof card      (sits below the chin)
  g_chips.png   NEW / FREE / FAST chip row
  g_frame.png   purple-glow B-roll frame chrome (938x1667 window at 70,126)

Palette + geometry come from references/ad_style_spec.md.
"""
import sys, pathlib
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from pathlib import Path

W, H = 1080, 1920
PURPLE = (109, 32, 224, 255)
P_LIGHT = (168, 110, 255, 255)
CARD_BG = (17, 19, 32, 238)
GOLD = (214, 155, 35, 255)
FONT = sys.argv[2] if len(sys.argv) > 2 else \
    "__ACQ_LEGACY_HOME__/Library/Fonts/ProximaNova-Extrabold.ttf"
OUT = pathlib.Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
f = lambda s: ImageFont.truetype(FONT, s)


def shadowed(size, draw_fn, blur=20, alpha=130):
    """draw once into a shadow layer, blur it, then draw the real thing on top"""
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    sh = Image.new("RGBA", size, (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(sh), True)
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(blur)))
    draw_fn(ImageDraw.Draw(img), False)
    return img


def stat_card(number="10,000+", label="BUSINESSES ANALYZED", out="g_stat.png"):
    CW, CH, R = 660, 250, 34
    pad = 40
    def body(d, shadow):
        box = [pad, pad+10 if shadow else pad, pad+CW, pad+CH+(10 if shadow else 0)]
        d.rounded_rectangle(box, radius=R, fill=(0, 0, 0, 150) if shadow else CARD_BG)
        if not shadow:
            d.rounded_rectangle(box, radius=R, outline=(140, 110, 235, 170), width=2)
    img = shadowed((CW+pad*2, CH+pad*2), body)
    d = ImageDraw.Draw(img)
    fn, fl = f(112), f(34)
    nw = d.textlength(number, font=fn)
    d.text((pad+(CW-nw)/2, pad+34), number, font=fn, fill=P_LIGHT)
    lw = sum(d.textlength(c, font=fl) for c in label) + 2.2*(len(label)-1)
    x = pad+(CW-lw)/2
    for c in label:
        d.text((x, pad+176), c, font=fl, fill=(215, 215, 230, 255))
        x += d.textlength(c, font=fl) + 2.2
    img.save(OUT/out); print("  ", out, img.size)


def chips(words=("NEW", "FREE", "FAST"), out="g_chips.png"):
    fw = f(52)
    pad, gap, ph = 34, 22, 104
    probe = ImageDraw.Draw(Image.new("RGBA", (8, 8)))
    ws = [probe.textlength(w, font=fw)+72 for w in words]
    total = sum(ws) + gap*(len(words)-1)
    img = Image.new("RGBA", (int(total)+pad*2, ph+pad*2), (0, 0, 0, 0))
    gl = Image.new("RGBA", img.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(gl)
    x = pad
    for w_, wd in zip(ws, words):
        gd.rounded_rectangle([x, pad, x+w_, pad+ph], radius=ph//2, fill=(120, 60, 255, 150))
        x += w_+gap
    img.alpha_composite(gl.filter(ImageFilter.GaussianBlur(18)))
    d = ImageDraw.Draw(img)
    x = pad
    for w_, wd in zip(ws, words):
        d.rounded_rectangle([x, pad, x+w_, pad+ph], radius=ph//2, fill=PURPLE)
        d.rounded_rectangle([x, pad, x+w_, pad+ph], radius=ph//2,
                            outline=(190, 160, 255, 190), width=2)
        tw = d.textlength(wd, font=fw)
        d.text((x+(w_-tw)/2, pad+22), wd, font=fw, fill=(255, 255, 255, 255))
        x += w_+gap
    img.save(OUT/out); print("  ", out, img.size)


def broll_frame(out="g_frame.png"):
    """Chrome for the B-roll window: purple glow + border. Video goes behind it."""
    X0, Y0, X1, Y1, R = 70, 126, 1008, 1793, 40
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(gl).rounded_rectangle([X0, Y0, X1, Y1], radius=R,
                                         outline=(150, 90, 255, 230), width=14)
    img.alpha_composite(gl.filter(ImageFilter.GaussianBlur(26)))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([X0, Y0, X1, Y1], radius=R, outline=(178, 140, 255, 235), width=4)
    d.rounded_rectangle([X0+4, Y0+4, X1-4, Y1-4], radius=R-4,
                        outline=(255, 255, 255, 40), width=2)
    img.save(OUT/out); print("  ", out, img.size)


if __name__ == "__main__":
    stat_card(); chips(); broll_frame()
