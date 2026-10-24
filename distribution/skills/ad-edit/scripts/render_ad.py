#!/usr/bin/env python3
"""render_ad.py — paid-ad house style renderer (config-driven).

Structure (default "chip" mode, measured 2026-08-21 off a real shipped Hunter ad,
f.io/G4BFDgKa — supersedes the older "headline"/"hybrid" modes kept below for
backward compat only):
  whole clip      small solid-black caption chip, x-centred, y 68.9-74.9% of H
                  (NO separate big hook headline — same chip from frame 1)
  mid             product card push-in / VFX overlays on their beats
  end             purple/glass CTA pill, y 56-65% of H — the chip caption keeps
                  running underneath it; it never stops for the close
  whole clip      plain-text disclaimer, sits below the chip band

/edit rules applied to caption text: $ / K / M normalisation, <=3 words &
<=18 chars per line, no trailing stub words, safe box right edge 860.
"""
import json, math, pathlib, re, shutil, subprocess
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops
import sys
from pathlib import Path
HERE = pathlib.Path(__file__).resolve().parent
CFG = json.load(open(sys.argv[1]))

SRC = CFG["source"]
# Canvas defaults to the locked 9:16 vertical size; a config may override for a
# native square/16:9 export instead of pillarboxing the vertical cut (added
# 2026-08-27 for 1:1/16:9 aspect-ratio deliverables). Every position value
# elsewhere (chip_cy, cta_y, card_y, disclaimer_y, ...) is already config-driven,
# so it just needs re-picking per canvas — nothing else in this file hardcodes
# 1080/1920.
W, H = CFG.get("canvas_w", 1080), CFG.get("canvas_h", 1920)
FPS = 24
OUT = CFG["out"]
FONT = CFG.get("font")
if not isinstance(FONT, str) or not Path(FONT).expanduser().is_file():
    raise SystemExit("Config font must name an existing licensed font file")
FONT = str(Path(FONT).expanduser().resolve())
ImageFont.truetype(FONT, 12)  # validate before rendering or creating output

WHITE = (247, 247, 253, 255)
P_TOP, P_BOT = (168, 110, 255), (126, 48, 254)
PILL_FILL = (86, 65, 176, 214)          # measured #5641B0
GOLD = (214, 155, 35, 255)
CTA_FILL = (89, 25, 203, 226)
BORDER = (136, 122, 179, 255)

HOOK_END = CFG.get("hook_end", 5.4)
HEAD_Y1 = CFG.get("head_y1", 96)
HEAD_Y2 = CFG.get("head_y2", 244)
HEAD_SZ = CFG.get("head_size", 130)
PILL_CX = 483                            # measured (legacy "hybrid" purple pill, pre-2026-08-21)
PILL_CY = CFG.get("pill_cy", 1443)
PILL_MAXW = 700                          # keeps right edge < 860 safe line

# CHIP caption — Hunter's actual house style, measured 2026-08-21 off a real shipped ad
# (f.io/G4BFDgKa, "Leads Problem / Offer Problem"). Small solid-black rounded box, centered
# on X (not left-of-center like the old purple pill), runs from frame 1 with NO separate big
# hook headline, and — critically — keeps running underneath the CTA pill instead of
# stopping. Measured bbox on a 1080x1920 frame: x 330-749, y 1322-1438 (68.9%-74.9% of H),
# centered at x=540 (canvas center). This is now the default caption system.
CHIP_FILL = (13, 13, 17, 235)
CHIP_CX = W/2
CHIP_CY = CFG.get("chip_cy", 1380)
CARD_IN, CARD_OUT = CFG.get("card_in", 1e9), CFG.get("card_out", 1e9)
# Optional written hook headline, e.g. ["WHAT YOU AVOID", "CONTROLS YOU"]. When absent the
# renderer falls back to deriving headline cards from the first transcript chunks.
HEADLINE = [str(s).upper() for s in CFG.get("headline", [])][:2]
BANNER_IN = None   # resolved in main()


def ease(t): return t*t*(3-2*t)


# ---------------------------------------------------------------- /edit rules
def normalise(t):
    t = re.sub(r"\b(\d[\d,\.]*)\s*(dollars|bucks)\b", r"$\1", t, flags=re.I)
    t = re.sub(r"\b(per ?cent(?:age)?s?)\b", "%", t, flags=re.I)
    def money(m):
        v = float(m.group(1).replace(",", ""))
        if v >= 1e9: return f"${v/1e9:g}B"
        if v >= 1e6: return f"${v/1e6:g}M"
        if v >= 1e3: return f"${v/1e3:g}K"
        return f"${v:g}"
    t = re.sub(r"\$([\d,]+(?:\.\d+)?)", money, t)
    t = re.sub(r"\b(\d[\d,]*)\s*thousand\b", lambda m: f"{m.group(1)}K", t, flags=re.I)
    return re.sub(r"\s+", " ", t).strip()


STUB = {"and", "but", "so", "or", "the", "a", "of", "to"}


def glue_numbers(words):
    """Whisper emits "10,000" as TWO word tokens: " 10" then ",000".

    Left un-glued they can land in different caption cards and the chunk's
    trailing .strip(" ,.") then eats the leading comma — a shipped CTA once read
    "BASED ON 10" / "000 BUSINESSES". Weld any ",ddd"/".ddd" continuation back on
    so the number is a single caption word. Same for 1,000,000.
    """
    out = []
    for w in words:
        tok = w["word"].strip()
        if out and re.match(r"^[,.]\d", tok):
            out[-1] = {**out[-1], "word": out[-1]["word"] + tok, "end": w["end"]}
        else:
            out.append(dict(w))
    return out


def chunk(words, max_words=3, max_chars=18):
    words = glue_numbers(words)
    out, cur = [], []
    for w in words:
        tok = w["word"].strip()
        cand = cur + [w]
        if cur and (len(cand) > max_words or
                    len(" ".join(x["word"].strip() for x in cand)) > max_chars):
            out.append(cur); cur = [w]
        else:
            cur = cand
        if tok and tok[-1] in ".?!":
            out.append(cur); cur = []
    if cur: out.append(cur)
    res = []
    for c in out:
        if not c: continue
        # no trailing stub word
        while len(c) > 1 and c[-1]["word"].strip().lower().strip(",.") in STUB:
            c = c[:-1]
        txt = normalise(" ".join(x["word"].strip() for x in c)).strip(" ,.").upper()
        if txt:
            res.append({"t": txt, "s": c[0]["start"], "e": c[-1]["end"]})
    return res


def chip_chunks(words, max_words=4, max_chars=24):
    """Flat per-line chunks for CHIP captions — like `chunk()` but WITHOUT the
    sentence-punctuation reset. That reset is what fragmented chip pairs unpredictably
    (a sentence boundary landing mid-pair produced a stray one-line card mid-ad instead
    of a clean two-line one) — dropping it makes every pair but possibly the very last
    a full two-liner."""
    words = glue_numbers(words)
    out, cur = [], []
    for w in words:
        cand = cur + [w]
        if cur and (len(cand) > max_words or
                    len(" ".join(x["word"].strip() for x in cand)) > max_chars):
            out.append(cur); cur = [w]
        else:
            cur = cand
    if cur: out.append(cur)
    res = []
    for c in out:
        if not c: continue
        while len(c) > 1 and c[-1]["word"].strip().lower().strip(",.") in STUB:
            c = c[:-1]
        txt = normalise(" ".join(x["word"].strip() for x in c)).strip(" ,.").upper()
        if txt:
            res.append({"t": txt, "s": c[0]["start"], "e": c[-1]["end"]})
    return res


def resolve_time(v, words):
    """Beat times may be a number OR a phrase from the VO.

    Phrase-anchored beats survive a re-cut: trim an "um" out of the master and the
    graphics still land on the right words instead of drifting.
    """
    if isinstance(v, (int, float)):
        return float(v)
    toks = [re.sub(r"[^a-z0-9]", "", w["word"].lower()) for w in words]
    want = [re.sub(r"[^a-z0-9]", "", x) for x in str(v).lower().split() if x]
    want = [x for x in want if x]
    for i in range(len(toks)-len(want)+1):
        if toks[i:i+len(want)] == want:
            return float(words[i]["start"])
    raise SystemExit(f'beat phrase not found in VO: "{v}"')


def to_final_time(t_orig, speed, segs):
    """Convert a point on the ORIGINAL (pre-speed) timeline to where it lands on the
    FINAL (post speed-change) timeline — same conversion `speed`/`speed_segments`
    apply to the whole render, needed here because `audio_fade_out`'s "at" is resolved
    against the original transcript like every other beat, but must fire at the right
    moment in the already-sped-up output."""
    if segs:
        acc, prev_end = 0.0, 0.0
        for sg in segs:
            end = sg.get("end")
            s = sg["speed"]
            seg_end = end if end is not None else t_orig
            if t_orig <= seg_end or end is None:
                return acc + (t_orig - prev_end)/s
            acc += (seg_end - prev_end)/s
            prev_end = seg_end
        return acc
    return t_orig / (speed or 1.0)


def wrap(text, font, d, maxw):
    words, lines, line = text.split(), [], ""
    for w in words:
        c = (line+" "+w).strip()
        if d.textlength(c, font=font) > maxw and line:
            lines.append(line); line = w
        else:
            line = c
    if line: lines.append(line)
    return lines[:2]


def draw_pill(fr, text, font):
    d = ImageDraw.Draw(fr)
    lines = wrap(text, font, d, PILL_MAXW-56)
    lw = [d.textlength(l, font=font) for l in lines]
    tw, lh = max(lw), font.size + 12
    bw, bh = tw+56, lh*len(lines)+30
    x0, y0 = PILL_CX-bw/2, PILL_CY-bh/2
    body = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(body).rounded_rectangle([x0, y0, x0+bw, y0+bh], radius=18, fill=PILL_FILL)
    fr.alpha_composite(body)
    y = y0+15
    for l, w_ in zip(lines, lw):
        d.text((PILL_CX-w_/2, y), l, font=font, fill=(255, 255, 255, 255))
        y += lh


def glass_box(fr, x0, y0, bw, bh, radius=16):
    """'Liquid black glass' card — soft dark outer glow, a top-to-bottom gradient fill
    (not flat matte black), a thin glass-rim highlight along the top edge, and a subtle
    border. Same construction family as the purple CTA/badge glass, just dark-toned."""
    gl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(gl).rounded_rectangle([x0, y0, x0+bw, y0+bh], radius=radius, fill=(10, 10, 14, 160))
    fr.alpha_composite(gl.filter(ImageFilter.GaussianBlur(10)))
    grad = Image.new("RGBA", (int(bw), int(bh)), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    top, bot = (36, 36, 42, 222), (10, 10, 13, 236)
    for yy in range(int(bh)):
        k = yy/max(1, bh-1)
        gd.line([(0, yy), (bw, yy)], fill=tuple(int(top[i]+(bot[i]-top[i])*k) for i in range(4)))
    mask = Image.new("L", (int(bw), int(bh)), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, bw-1, bh-1], radius=radius, fill=255)
    grad.putalpha(ImageChops.multiply(grad.getchannel("A"), mask))
    body = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    body.paste(grad, (int(x0), int(y0)), grad)
    fr.alpha_composite(body)
    hi = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    hd = ImageDraw.Draw(hi)
    hd.rounded_rectangle([x0, y0, x0+bw, y0+bh], radius=radius, outline=(255, 255, 255, 40), width=1)
    hd.line([(x0+radius, y0+1.5), (x0+bw-radius, y0+1.5)], fill=(255, 255, 255, 70), width=2)
    fr.alpha_composite(hi)
    bd = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(bd).rounded_rectangle([x0, y0, x0+bw, y0+bh], radius=radius, outline=(60, 60, 70, 180), width=2)
    fr.alpha_composite(bd)


def draw_chip_pair(fr, pr, font):
    """Hunter's real caption: a 'liquid black glass' box, centered on X, runs the whole
    ad including under the CTA — continuously, no gaps (the caller hands every frame a
    pair to show). Always TWO lines, revealed TOGETHER — never a top-then-bottom stagger."""
    d = ImageDraw.Draw(fr)
    texts = [c["t"] for c in pr]
    lw = [d.textlength(tx, font=font) for tx in texts]
    tw, lh = max(lw) if lw else 0, font.size + 12
    bw, bh = tw+64, lh*len(texts)+30
    x0, y0 = CHIP_CX-bw/2, CHIP_CY-bh/2
    glass_box(fr, x0, y0, bw, bh, radius=14)
    y = y0+15
    for tx, w_ in zip(texts, lw):
        d.text((CHIP_CX-w_/2, y), tx, font=font, fill=(255, 255, 255, 255))
        y += lh


_FIT = {}
def fit(text, maxw, start):
    k = (text, maxw, start)
    if k in _FIT: return _FIT[k]
    d = ImageDraw.Draw(Image.new("RGBA", (8, 8)))
    sz = start
    while sz > 44 and d.textlength(text, font=ImageFont.truetype(FONT, sz)) > maxw:
        sz -= 2
    _FIT[k] = ImageFont.truetype(FONT, sz)
    return _FIT[k]


def draw_head(fr, text, y, grad):
    font = fit(text, W-96, HEAD_SZ)
    d = ImageDraw.Draw(fr)
    x = (W-d.textlength(text, font=font))/2
    tmp = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(tmp).text((x, y), text, font=font, fill=(255, 255, 255, 255))
    gl = tmp.filter(ImageFilter.GaussianBlur(24))
    fr.alpha_composite(Image.merge("RGBA", (*[c.point(lambda v: int(v*(0.6 if grad else 0.85)))
                                              for c in Image.new("RGB", (W, H),
                                              (150, 80, 255) if grad else (215, 222, 255)).split()],
                                            gl.getchannel("A").point(lambda a: int(a*0.55)))))
    if grad:
        bb = tmp.getbbox()
        g = Image.new("RGBA", (W, H), (0, 0, 0, 0)); gd = ImageDraw.Draw(g)
        for yy in range(bb[1], bb[3]):
            k = (yy-bb[1])/max(1, bb[3]-bb[1])
            gd.line([(0, yy), (W, yy)], fill=tuple(int(P_TOP[i]+(P_BOT[i]-P_TOP[i])*k)
                                                   for i in range(3))+(255,))
        g.putalpha(tmp.getchannel("A")); fr.alpha_composite(g)
    else:
        fr.alpha_composite(tmp)


MATTE_H = 520          # band the headline can occupy


def extract_band(src, cx, cw, cy, ch, n, outdir):
    """Pre-pass: the top MATTE_H px of the reframed video (luma-key path)."""
    outdir.mkdir(exist_ok=True)
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", src,
        "-vf", f"crop={cw}:{ch}:{cx}:{cy},scale={W}:{H}:flags=lanczos,"
               f"crop={W}:{MATTE_H}:0:0,format=gray",
        "-r", str(FPS), "-frames:v", str(n), str(outdir/"b%05d.png")], check=True)


def extract_alpha_band(pha, n, outdir):
    """Pre-pass from a pre-computed alpha video (MatAnyone `*_pha.mp4`).
    Already aligned to the reframed video, so just rescale + take the top band."""
    outdir.mkdir(exist_ok=True)
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", pha,
        "-vf", f"scale={W}:{H}:flags=lanczos,crop={W}:{MATTE_H}:0:0,format=gray",
        "-r", str(FPS), "-frames:v", str(n), str(outdir/"b%05d.png")], check=True)


def subject_matte(path, thresh, feather, precomputed=False):
    """Alpha for the subject: 255 = subject, 0 = background.

    precomputed=True  -> band came from a real matting model (MatAnyone); use as-is.
    precomputed=False -> luma key, only valid on a dark set.
    """
    from PIL import Image as _I
    g = _I.open(path).convert("L")
    if precomputed:
        return g.filter(ImageFilter.GaussianBlur(feather))
    m = g.point(lambda v: 0 if v < thresh else min(255, int((v-thresh)*255/max(1, 42-thresh))))
    m = m.filter(ImageFilter.MaxFilter(5))            # close pin-holes in hair
    return m.filter(ImageFilter.GaussianBlur(feather))


def load_overlays(specs, n, workroot):
    """Prepare timed overlays. type=png (static) | broll (video in the glow frame,
    or full=true for a full-bleed cutaway replacing the talking head entirely)."""
    out = []
    for k, o in enumerate(specs):
        rec = dict(o)
        if o["type"] == "seq":
            rec["frames"] = sorted(pathlib.Path(o["src"]).glob("*.png"))
        elif o["type"] == "broll" and o.get("full"):
            d = pathlib.Path(f"{workroot}_brf{k}")
            shutil.rmtree(d, ignore_errors=True); d.mkdir(parents=True)
            probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                "-show_entries", "stream=width,height", "-of", "csv=p=0", o["src"]],
                capture_output=True, text=True).stdout.strip().split(",")
            sw, sh = int(probe[0]), int(probe[1])
            cw = round(sh * W / H)
            cx = o.get("crop_x_src", (sw - cw) // 2)
            # a plain center crop can miss the subject in an off-center wide shot;
            # crop_x_src lets a specific clip override where the 9:16 window sits.
            subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", o["src"],
                "-vf", f"crop={cw}:{sh}:{cx}:0,scale={W}:{H}:flags=lanczos",
                "-r", str(FPS), str(d/"f%05d.png")], check=True)
            rec["frames"] = sorted(d.glob("*.png"))
        elif o["type"] == "broll":
            d = pathlib.Path(f"{workroot}_bro{k}")
            shutil.rmtree(d, ignore_errors=True); d.mkdir(parents=True)
            subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", o["src"],
                            "-r", str(FPS), str(d/"f%05d.png")], check=True)
            rec["frames"] = sorted(d.glob("*.png"))
            rec["chrome"] = (Image.open(o["chrome"]).convert("RGBA")
                             if o.get("chrome") else None)
        elif o["type"] == "cutaway":
            # Hunter's real full-bleed cutaway: blurred/darkened backdrop (added at render
            # time from the live source, see BG_FRAMES) + a big rounded video card + a
            # labeled glass-purple badge above it. Just extract the card's own video frames
            # here; the backdrop blur is handled once per-render, not per-overlay.
            d = pathlib.Path(f"{workroot}_cut{k}")
            shutil.rmtree(d, ignore_errors=True); d.mkdir(parents=True)
            subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", o["src"],
                            "-r", str(FPS), str(d/"f%05d.png")], check=True)
            rec["frames"] = sorted(d.glob("*.png"))
        else:
            im = Image.open(o["src"]).convert("RGBA")
            if o.get("scale", 1) != 1:
                im = im.resize((int(im.width*o["scale"]), int(im.height*o["scale"])))
            rec["img"] = im
        out.append(rec)
    return out


def place(o, img):
    x = o.get("x", "center")
    x = int(W/2-img.width/2) if x == "center" else int(x)
    return x, int(o.get("y", 0))


def extract_bg_frames(src, cx, cw, cy, ch, n, outdir):
    """The main talking-head video, cropped/scaled to the same 1080x1920 window the
    final composite uses — extracted once so `cutaway` overlays can blur/darken the
    LIVE background instead of cutting to plain black (Hunter freezes+blurs the current
    frame behind the video card, he never cuts to black)."""
    outdir.mkdir(exist_ok=True)
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", src,
        "-vf", f"crop={cw}:{ch}:{cx}:{cy},scale={W}:{H}:flags=lanczos,"
               f"gblur=sigma=30,eq=brightness=-0.22",
        "-r", str(FPS), "-frames:v", str(n), str(outdir/"g%05d.png")], check=True)


def badge_img(lines, icon=True):
    """Label badge above a `cutaway` video card, naming the segment (e.g. "OFFERS
    WORKSHOP"). Colors measured 2026-08-21 directly off the real reference frame
    (hi_phonemockup2.png) — the fill is a MUTED, desaturated slate-purple glass
    (roughly rgb 55-95, 40-90, 100-135), not a vivid saturated purple like the CTA
    pill — the two are a different, darker material. Flat fill read as cheap/cartoonish
    in review; this uses a gradient + soft glow + a thin top highlight instead, same
    construction family as `glass_box`."""
    lines = lines if isinstance(lines, list) else [lines]
    font = ImageFont.truetype(FONT, 40)
    pad_x, pad_y, R = 34, 22, 30
    d0 = ImageDraw.Draw(Image.new("RGBA", (8, 8)))
    # icon sits at x0+pad_x+30 with radius 30, so its right edge is at x0+pad_x+60
    # (x0+94 given pad_x=34) — icon_w must clear that plus a real gap before text
    # starts, or the text overlaps the icon (measured bug: 84 left a 10px overlap).
    icon_w = pad_x+60+22 if icon else 0
    lw = [d0.textlength(l.upper(), font=font) for l in lines]
    tw = max(lw) if lw else 0
    bw = tw + pad_x*2 + icon_w
    bh = max(len(lines)*(font.size+10) + pad_y*2, 100)
    img = Image.new("RGBA", (int(bw)+40, int(bh)+40), (0, 0, 0, 0))
    x0, y0 = 20, 20
    gl = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(gl).rounded_rectangle([x0, y0, x0+bw, y0+bh], radius=R, fill=(40, 30, 70, 110))
    img.alpha_composite(gl.filter(ImageFilter.GaussianBlur(16)))
    grad = Image.new("RGBA", (int(bw), int(bh)), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    top, bot = (92, 80, 128, 232), (58, 48, 92, 238)
    for yy in range(int(bh)):
        k = yy/max(1, bh-1)
        gd.line([(0, yy), (bw, yy)], fill=tuple(int(top[i]+(bot[i]-top[i])*k) for i in range(4)))
    mask = Image.new("L", (int(bw), int(bh)), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, bw-1, bh-1], radius=R, fill=255)
    grad.putalpha(ImageChops.multiply(grad.getchannel("A"), mask))
    body = Image.new("RGBA", img.size, (0, 0, 0, 0))
    body.paste(grad, (int(x0), int(y0)), grad)
    img.alpha_composite(body)
    hi = Image.new("RGBA", img.size, (0, 0, 0, 0))
    hd = ImageDraw.Draw(hi)
    hd.rounded_rectangle([x0, y0, x0+bw, y0+bh], radius=R, outline=(255, 255, 255, 35), width=1)
    hd.line([(x0+R, y0+1.5), (x0+bw-R, y0+1.5)], fill=(255, 255, 255, 60), width=2)
    img.alpha_composite(hi)
    tx = x0+pad_x
    if icon:
        cx, cy, r = x0+pad_x+30, y0+bh/2, 30
        ImageDraw.Draw(img).ellipse([cx-r, cy-r, cx+r, cy+r], fill=(24, 18, 40, 200))
        ImageDraw.Draw(img).ellipse([cx-r, cy-r, cx+r, cy+r], outline=(255, 255, 255, 45), width=1)
        try:
            lg = Image.open(CFG.get("brand_icon", str(HERE.parent/"assets/brand_icon.png"))).convert("RGBA")
            a = lg.getchannel("A"); lg = Image.new("RGBA", lg.size, (255,)*4); lg.putalpha(a)
            lg.thumbnail((44, 44), Image.LANCZOS)
            lg.putalpha(lg.getchannel("A").point(lambda v: min(255, int(v*3.2))))
            img.alpha_composite(lg, (int(cx-lg.width/2), int(cy-lg.height/2)))
        except Exception: pass
        tx = x0+icon_w
    d = ImageDraw.Draw(img)
    y = y0+pad_y
    for l, w_ in zip(lines, lw):
        d.text((tx, y), l.upper(), font=font, fill=(225, 222, 232, 255))
        y += font.size+10
    return img


def draw_cutaway(fr, cutaways, t, bg_frames):
    """Full-bleed cutaway: blurred/darkened live backdrop + a big rounded video card +
    a labeled badge above it. Runs instead of the talking head for the beat, exactly
    like the real ad's 'OFFERS WORKSHOP' cutaway (measured 2026-08-21).

    Fade-in/out at each cutaway's OWN edge is independent by default (0.3s) — fine when
    neighboring cutaways are well apart, but when two are scheduled close together (the
    common case for a high-broll-coverage ad) the two independent fades don't overlap
    enough to keep combined opacity at 1 the whole time: cutaway A ends fading down,
    cutaway B hasn't ramped up yet, and the live talking head flashes through for a few
    frames in between (caught 2026-08-21, ad review). Fix: when the gap to a neighbor is
    under 0.6s, that SPECIFIC edge hard-cuts (~1 frame) instead of fading — only a real,
    deliberate gap (a genuine beat of Alex between broll sections) still gets a fade."""
    cuts = sorted(cutaways, key=lambda c: c["at"])
    # Evaluate EVERY candidate whose window contains t and keep the most-opaque one —
    # NOT just the first match in sort order. During the short overlap between two
    # adjacent hard-cut cutaways, the outgoing one is fading DOWN while the incoming one
    # is fading UP at the same time; picking "first in order" always means "outgoing",
    # so for the 1-2 frames of overlap the displayed opacity dips toward the outgoing
    # cutaway's near-zero tail instead of jumping to the incoming cutaway's near-full
    # head — a real, visible flash of the live talking head (caught 2026-08-26, ad
    # review, traced past the fps/encoder theory that turned out to be a red herring:
    # the raw per-frame PNGs already show the fade math is right, this is purely a
    # "which candidate wins the overlap" selection bug).
    best = None
    for i, c in enumerate(cuts):
        a0c, durc = c["at"], c.get("dur", 3.0)
        prev = cuts[i-1] if i > 0 else None
        nxt = cuts[i+1] if i+1 < len(cuts) else None
        # For a small (but nonzero) gap, each side's fade must cover exactly HALF the
        # gap so the two meet with no dead zone in between — a fixed 0.03s "hard cut"
        # fade only works when the gap truly is ~0; for e.g. a genuine 0.16s gap, two
        # fixed 0.03s fades leave a real ~0.1s hole where NEITHER cutaway's window
        # covers t at all, and the live talking head flashes through (caught
        # 2026-08-26, ad review — a second, distinct bug from the overlap-selection
        # one above, in the same neighborhood of the timeline).
        # Splitting the gap exactly in half makes the two fades meet at a single
        # shared instant where BOTH sit at precisely 0 opacity at once — a real,
        # if single-frame, flash of the live talking head (caught 2026-08-26, ad
        # review, frame-exact scan at 23.00s: frame 552 came back pure bare face
        # even though 551 and 553 on either side were correctly ghosted). Padding
        # each half by one extra frame makes the two fade windows overlap instead
        # of touching, so every instant in the gap has at least one cutaway above
        # zero opacity — "meet in the middle" becomes "overlap in the middle."
        gap_before = (a0c - (prev["at"]+prev.get("dur", 3.0))) if prev else None
        gap_after = (nxt["at"] - (a0c+durc)) if nxt else None
        fi = max(0.02, gap_before/2 + 1/FPS) if (gap_before is not None and gap_before < 0.6) else c.get("fade", 0.3)
        fo = max(0.02, gap_after/2 + 1/FPS) if (gap_after is not None and gap_after < 0.6) else c.get("fade", 0.3)
        if not (a0c - fi <= t <= a0c + durc + fo):
            continue
        # Fade-in must ramp across [a0c-fi, a0c] (0 at the pre-roll edge, 1 by the
        # beat's own timestamp) — an earlier version ramped across [a0c, a0c+fi]
        # instead, so the cutaway sat at pure 0 opacity for the entire intended
        # fade-in window and only started appearing AFTER its beat had already
        # passed. Harmless for a lone cutaway with a big fade, but for the
        # gap-midpoint fix above (small fi) this reproduced the exact "flash of
        # talking head" bug it was meant to close: cutaway A's fade-out correctly
        # hit 0 at the gap midpoint, but cutaway B stayed at 0 for another `fi`
        # seconds past that (caught 2026-08-26, ad review, frame-exact scan at ~23s).
        p = ((t-(a0c-fi))/fi if t < a0c else
             (1-(t-(a0c+durc))/fo if t > a0c+durc else 1.0))
        ec = ease(min(1, max(0, p)))
        if best is None or ec > best[1]:
            best = (c, ec)
    if best is None:
        return
    o, e = best
    a0, dur = o["at"], o.get("dur", 3.0)
    if e <= 0.01:
        return
    idx = min(max(int(t*FPS), 0), len(bg_frames)-1)
    bg = Image.open(bg_frames[idx]).convert("RGBA")
    bg.putalpha(int(255*e))
    fr.alpha_composite(bg, (0, 0))
    frames = o["frames"]
    if not frames:
        return
    cidx = min(max(int((t-a0)*FPS), 0), len(frames)-1)
    clip = Image.open(frames[cidx]).convert("RGBA")
    cw = o.get("w", 918)
    ch = o.get("h", round(cw*clip.height/clip.width))
    clip = clip.resize((cw, ch))
    r = o.get("radius", 28)
    mask = Image.new("L", (cw, ch), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, cw-1, ch-1], radius=r, fill=255)
    clip.putalpha(mask.point(lambda a: int(a*e)))
    cx0 = int(W/2-cw/2)
    cy0 = int(o.get("card_y", 690)-(1-e)*18)
    d2 = ImageDraw.Draw(fr)
    fr.alpha_composite(clip, (cx0, cy0))
    d2.rounded_rectangle([cx0, cy0, cx0+cw, cy0+ch], radius=r, outline=(60, 60, 66, int(230*e)), width=3)
    badge = badge_img(o.get("badge", ["LABEL"]))
    badge.putalpha(badge.getchannel("A").point(lambda a: int(a*e)))
    bx0 = int(W/2-badge.width/2)
    by0 = cy0 - badge.height + 28
    fr.alpha_composite(badge, (bx0, int(by0-(1-e)*18)))


def draw_broll_full(fr, ovs_full, t):
    """Full-bleed b-roll cutaway — replaces the talking head entirely for the beat.
    Composited BEFORE the pill track (caller's job) so captions still read on top,
    matching the spec's 'pill caption runs the whole ad' rule even through a cutaway."""
    o = next((o for o in ovs_full if o["at"]-0.2 <= t <= o["at"]+o.get("dur", 3.0)+0.2), None)
    if o is None:
        return
    a0, dur = o["at"], o.get("dur", 3.0)
    fade = o.get("fade", 0.2)
    p = ((t-a0)/fade if t < a0+fade else
         (1-(t-(a0+dur))/fade if t > a0+dur else 1.0))
    e = min(1, max(0, p))
    if e <= 0.01:
        return
    frames = o["frames"]
    if not frames:
        return
    idx = min(max(int((t-a0)*FPS), 0), len(frames)-1)
    im = Image.open(frames[idx]).convert("RGBA")
    if e < 1:
        im.putalpha(im.getchannel("A").point(lambda a: int(a*e)))
    fr.alpha_composite(im, (0, 0))


def draw_overlays(fr, ovs, t):
    for o in ovs:
        a0, dur = o["at"], o.get("dur", 3.0)
        if not (a0-0.45 <= t <= a0+dur+0.45):
            continue
        p = ((t-a0)/0.45 if t < a0+0.45 else
             (1-(t-(a0+dur))/0.45 if t > a0+dur else 1.0))
        e = ease(min(1, max(0, p)))
        if e <= 0.01:
            continue
        if o["type"] == "seq":
            idx = int((t-a0)*FPS)
            fs = o["frames"]
            if fs:
                im = Image.open(fs[min(max(idx, 0), len(fs)-1)]).convert("RGBA")
                if o.get("scale", 1) != 1:
                    im = im.resize((int(im.width*o["scale"]), int(im.height*o["scale"])))
                if e < 1:
                    im.putalpha(im.getchannel("A").point(lambda a: int(a*e)))
                x, y = place(o, im)
                fr.alpha_composite(im, (x, int(y)))
            continue

        if o["type"] == "seq":
            fs = o["frames"]
            if fs:
                raw = int((t-a0)*FPS)
                if raw >= len(fs) and not o.get("hold", False):
                    continue
                idx = min(max(raw, 0), len(fs)-1)
                im = Image.open(fs[idx]).convert("RGBA")
                if o.get("scale", 1) != 1:
                    im = im.resize((int(im.width*o["scale"]), int(im.height*o["scale"])))
                if e < 1:
                    im.putalpha(im.getchannel("A").point(lambda a: int(a*e)))
                x, y = place(o, im)
                fr.alpha_composite(im, (x, int(y)))
            continue

        if o["type"] == "broll":
            idx = int((t-a0)*FPS)
            if 0 <= idx < len(o["frames"]):
                bw, bh = o.get("w", 938), o.get("h", 528)
                r = o.get("radius", 34)
                v = Image.open(o["frames"][idx]).convert("RGBA").resize((bw, bh))
                mask = Image.new("L", (bw, bh), 0)
                ImageDraw.Draw(mask).rounded_rectangle([0, 0, bw-1, bh-1], radius=r, fill=255)
                v.putalpha(mask.point(lambda a: int(a*e)))
                bx = int(W/2-bw/2) if o.get("x", "center") == "center" else int(o["x"])
                by = int(o.get("y", 560) - (1-e)*18)
                # purple glow + border, drawn to fit the card
                gl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                ImageDraw.Draw(gl).rounded_rectangle(
                    [bx, by, bx+bw, by+bh], radius=r,
                    outline=(150, 90, 255, int(225*e)), width=12)
                fr.alpha_composite(gl.filter(ImageFilter.GaussianBlur(22)))
                fr.alpha_composite(v, (bx, by))
                d2 = ImageDraw.Draw(fr)
                d2.rounded_rectangle([bx, by, bx+bw, by+bh], radius=r,
                                     outline=(178, 140, 255, int(235*e)), width=4)
        else:
            im = o["img"].copy()
            sc = 0.94+0.06*e
            im2 = im.resize((int(im.width*sc), int(im.height*sc)))
            im2.putalpha(im2.getchannel("A").point(lambda a: int(a*e)))
            x, y = place(o, im2)
            fr.alpha_composite(im2, (x, int(y-(1-e)*18)))


DISCLAIMER = ("Information not typical. These are examples not guarantees. "
              "Results may vary.")


def disclaimer_layer():
    """Mandatory on every ad (export SOP). Small, bottom, above the platform zone."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(FONT, 25)
    words, lines, line = DISCLAIMER.split(), [], ""
    for w_ in words:
        c = (line+" "+w_).strip()
        if d.textlength(c, font=f) > W-160 and line:
            lines.append(line); line = w_
        else:
            line = c
    if line: lines.append(line)
    # 1630 (measured 2026-08-21 off a real shipped ad) sits below the CHIP caption band
    # (y 1322-1438) with a clear gap — the old 1496 default overlapped it.
    y = CFG.get("disclaimer_y", 1630) - len(lines)*30
    for l in lines:
        lw = d.textlength(l, font=f)
        d.text(((W-lw)/2+2, y+2), l, font=f, fill=(0, 0, 0, 150))
        d.text(((W-lw)/2, y), l, font=f, fill=(228, 228, 238, 205))
        y += 30
    return img


def cta_pill():
    PW, PH, R, pad = 900, 128, 38, 30
    img = Image.new("RGBA", (PW+pad*2, PH+pad*2), (0, 0, 0, 0))
    x0, y0 = pad, pad
    gl = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(gl).rounded_rectangle([x0, y0, x0+PW, y0+PH], radius=R, fill=(120, 70, 255, 140))
    img.alpha_composite(gl.filter(ImageFilter.GaussianBlur(20)))
    b = Image.new("RGBA", img.size, (0, 0, 0, 0)); bd = ImageDraw.Draw(b)
    bd.rounded_rectangle([x0, y0, x0+PW, y0+PH], radius=R, fill=CTA_FILL)
    bd.rounded_rectangle([x0, y0, x0+PW, y0+PH], radius=R, outline=BORDER, width=3)
    img.alpha_composite(b)
    cx, cy, r = x0+70, y0+PH/2, 44
    bg = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(bg).ellipse([cx-r, cy-r, cx+r, cy+r], fill=(28, 12, 70, 210))
    img.alpha_composite(bg)
    try:
        # assets/ sits at the skill root, one level above scripts/ (HERE). The old
        # HERE/"assets" default pointed inside scripts/, so the icon silently never loaded.
        lg = Image.open(CFG.get("brand_icon", str(HERE.parent/"assets/brand_icon.png"))).convert("RGBA")
        a = lg.getchannel("A"); lg = Image.new("RGBA", lg.size, (255,)*4); lg.putalpha(a)
        # thin-stroke marks (like the ACQ triangle mark) lose most of their alpha coverage
        # when thumbnailed down to badge size — boost alpha post-resize or the badge just
        # reads as an empty circle (real bug, caught 2026-08-14: rendered invisible in every
        # CTA pill despite the asset itself being correct at full res).
        # 56px + 2.6x boost still read as an empty circle at phone size (user-confirmed,
        # 2026-08-14) - the mark is thin-stroke. Bigger mark, alpha driven to full.
        lg.thumbnail((72, 72), Image.LANCZOS)
        lg.putalpha(lg.getchannel("A").point(lambda v: min(255, int(v*4.0))))
        img.alpha_composite(lg, (int(cx-lg.width/2), int(cy-lg.height/2)))
    except Exception: pass
    def shrink_to_fit(text, maxw, start, floor=22):
        sz = start
        while sz > floor and d.textlength(text, font=ImageFont.truetype(FONT, sz)) > maxw:
            sz -= 2
        return ImageFont.truetype(FONT, sz)

    d = ImageDraw.Draw(img)
    text_maxw = PW-126-30   # leaves the pill's right-hand padding clear, never crosses x=860
    l1 = CFG.get("cta_line1", "GET IT FREE").upper()
    l2 = CFG.get("cta_line2", "CLICK THE LINK BELOW").upper()
    f1, f2 = shrink_to_fit(l1, text_maxw, 42), shrink_to_fit(l2, text_maxw, 38)
    d.text((x0+126, y0+22), l1, font=f1, fill=GOLD)
    d.text((x0+126, y0+72), l2, font=f2, fill=(255, 255, 255, 255))
    return img


def cta_fullscreen_card(elapsed):
    """Full-screen CTA end-card (`"cta_fullscreen": true`) — replaces the talking head
    entirely for the close instead of just overlaying a small pill on top of it. Fully
    opaque top-to-bottom, so compositing it over the live frame in the main loop covers
    the video completely (matches the `draw_broll_full` full-bleed pattern).

    Regenerated EVERY FRAME (not built once) so each element can stagger in on its own
    timing instead of the whole card just cross-fading as one flat image: icon pops in
    first, headline and instruction slide-up-and-fade in behind it, then the arrow fades
    in and settles into a slow bounce. `elapsed` is seconds since the CTA moment began
    (t - BANNER_IN) — negative/zero is valid (pre-entrance), just yields all-zero stagger.
    Layout is intentionally compact (2026-08-26: the original spacing between icon/
    headline/instruction/arrow read as too loose in review)."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    top, bot = (52, 20, 104), (10, 5, 22)
    grad = Image.new("RGB", (1, H))
    for y in range(H):
        k = y/(H-1)
        grad.putpixel((0, y), tuple(int(top[i]+(bot[i]-top[i])*k) for i in range(3)))
    img.paste(grad.resize((W, H)), (0, 0))
    d = ImageDraw.Draw(img)

    def stagger(start, dur=0.3):
        return ease(min(1, max(0, (elapsed-start)/dur)))

    e_icon = stagger(0.0, 0.3)
    if e_icon > 0.01:
        try:
            lg = Image.open(CFG.get("brand_icon", str(HERE.parent/"assets/brand_icon.png"))).convert("RGBA")
            a = lg.getchannel("A"); lg = Image.new("RGBA", lg.size, (255,)*4); lg.putalpha(a)
            lg.thumbnail((150, 150), Image.LANCZOS)
            lg.putalpha(lg.getchannel("A").point(lambda v: min(255, int(v*3.0))))
            sc = 0.5 + 0.5*e_icon
            lg2 = lg.resize((max(1, int(lg.width*sc)), max(1, int(lg.height*sc))))
            lg2.putalpha(lg2.getchannel("A").point(lambda v: int(v*e_icon)))
            icon_y = 420 + int(lg.height*(1-sc)/2)
            img.alpha_composite(lg2, (int(W/2-lg2.width/2), icon_y))
        except Exception: pass

    e_l1 = stagger(0.15, 0.3)
    if e_l1 > 0.01:
        l1 = CFG.get("cta_line1", "GET IT FREE").upper()
        f1 = fit(l1, W-140, 76)
        w1 = d.textlength(l1, font=f1)
        y1 = 600 + int((1-e_l1)*20)
        l1img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(l1img).text(((W-w1)/2, y1), l1, font=f1, fill=GOLD)
        l1img.putalpha(l1img.getchannel("A").point(lambda v: int(v*e_l1)))
        img.alpha_composite(l1img)

    e_l2 = stagger(0.3, 0.3)
    if e_l2 > 0.01:
        l2 = CFG.get("cta_line2", "CLICK THE LINK BELOW").upper()
        f2 = fit(l2, W-140, 50)
        w2 = d.textlength(l2, font=f2)
        y2 = 696 + int((1-e_l2)*20)
        l2img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(l2img).text(((W-w2)/2, y2), l2, font=f2, fill=(255, 255, 255, 255))
        l2img.putalpha(l2img.getchannel("A").point(lambda v: int(v*e_l2)))
        img.alpha_composite(l2img)

    e_ar = stagger(0.5, 0.25)
    if e_ar > 0.01:
        bounce = 6*math.sin(max(0.0, elapsed-0.5)*3.0)
        ay = 776 + int(bounce)
        arimg = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(arimg).polygon([(W/2-22, ay), (W/2+22, ay), (W/2, ay+32)], fill=(255, 255, 255, 190))
        arimg.putalpha(arimg.getchannel("A").point(lambda v: int(v*e_ar)))
        img.alpha_composite(arimg)
    return img


def main():
    r = json.load(open(CFG["transcript"]))
    words = [w for s in r["segments"] for w in s.get("words", [])]
    dur = float(subprocess.run(["ffprobe","-v","error","-show_entries","format=duration",
                                "-of","csv=p=0",SRC],capture_output=True,text=True).stdout)
    n = int(dur*FPS)
    cxc, cwc = CFG.get("crop_x", 1912), CFG.get("crop_w", 1215)
    cyc, chc = CFG.get("crop_y", 0), CFG.get("crop_h", 2160)
    ch = chunk(words)
    # chip (default, 2026-08-21) = Hunter's real style: small black-box caption, no
    # separate hook headline, runs the whole ad incl. under the CTA.
    # headline = big captions all the way (legacy); hybrid = old purple-pill + hook (legacy,
    # stops the caption at the CTA — kept only for pre-existing configs that rely on it).
    global BANNER_IN, HOOK_END
    BANNER_IN = resolve_time(CFG.get("cta_at", 24.2), words)
    HOOK_END = resolve_time(CFG.get("hook_end", 5.4), words)
    print(f"    cta    @ {BANNER_IN:6.2f}s")
    # optional: stop the chip caption track from a beat onward (e.g. a custom overlay,
    # like a "link in description" button, is taking over that same screen position and
    # should fully replace the caption rather than have it show/bleed through underneath).
    # None (default) preserves the original behaviour: chip never stops.
    CHIP_STOP_AT = (resolve_time(CFG["chip_stop_at"], words)
                    if CFG.get("chip_stop_at") is not None else None)
    MODE = CFG.get("caption_mode", "chip")
    src_chunks = ch if MODE == "headline" else [c for c in ch if c["s"] < HOOK_END]
    pairs = [src_chunks[i:i+2] for i in range(0, len(src_chunks), 2)]
    print(f"  mode={MODE} | {len(ch)} chunks -> {len(pairs)} headline cards")

    # CHIP mode: always pairs two chunks into one 2-line card — matches the real ad,
    # where every caption card is two lines, both revealed together, never one.
    chip_ch = (chip_chunks(words, CFG.get("chip_max_words", 4), CFG.get("chip_max_chars", 24))
               if MODE == "chip" else [])
    chip_pairs = [chip_ch[i:i+2] for i in range(0, len(chip_ch), 2)]
    # continuous, gap-free display windows: each card runs until the NEXT card starts
    # (not until its own words end) so there is never a moment with no caption on screen.
    chip_windows = []
    for i, pr in enumerate(chip_pairs):
        s = 0.0 if i == 0 else pr[0]["s"]
        e = chip_pairs[i+1][0]["s"] if i+1 < len(chip_pairs) else dur
        chip_windows.append((s, e))

    pfont = ImageFont.truetype(FONT, 46)
    cfont = ImageFont.truetype(FONT, CFG.get("chip_font_size", 40))
    card = Image.open(CFG["card"]).convert("RGBA") if CFG.get("card") else None
    if card: card = card.resize((int(card.width*.92), int(card.height*.92)))
    pill = cta_pill()
    USE_CTA_CARD = bool(CFG.get("cta_fullscreen"))
    DISC = disclaimer_layer() if CFG.get("disclaimer", True) else None
    if DISC is None:
        print("  !! disclaimer DISABLED — export SOP requires it on every ad")

    specs = []
    for o in CFG.get("overlays", []):
        o = dict(o); o["at"] = resolve_time(o["at"], words); specs.append(o)
    OVS = load_overlays(specs, n, CFG.get("work", "_ovr"))
    OVS_FULL = [o for o in OVS if o.get("type") == "broll" and o.get("full")]
    OVS_CUT = [o for o in OVS if o.get("type") == "cutaway"]
    OVS = [o for o in OVS if o not in OVS_FULL and o not in OVS_CUT]
    for o in specs:
        print(f"    beat {o['type']:<6}{' full' if o.get('full') else '':<5} @ {o['at']:6.2f}s")
    if OVS or OVS_FULL or OVS_CUT:
        print(f"  {len(OVS)} inset overlays, {len(OVS_FULL)} full-bleed cutaways, {len(OVS_CUT)} labeled cutaways")
    BG_FRAMES = []
    if OVS_CUT:
        bgdir = pathlib.Path(CFG.get("work", "_ovr")+"_cutbg")
        shutil.rmtree(bgdir, ignore_errors=True)
        extract_bg_frames(SRC, cxc, cwc, cyc, chc, n, bgdir)
        BG_FRAMES = sorted(bgdir.glob("*.png"))

    global MATTE, MATTE_TH, MATTE_FEATHER, band_dir
    MATTE = bool(CFG.get("matte", False))
    MATTE_TH = CFG.get("matte_threshold", 24)
    MATTE_FEATHER = CFG.get("matte_feather", 1.6)
    band_dir = pathlib.Path(CFG.get("work", "_ovr")+"_band")
    global MATTE_PRE
    MATTE_PRE = bool(CFG.get("matte_video"))
    if MATTE:
        shutil.rmtree(band_dir, ignore_errors=True)
        if MATTE_PRE:
            print("  matte: using precomputed alpha ->", CFG["matte_video"])
            extract_alpha_band(CFG["matte_video"], n, band_dir)
        else:
            print("  matte: luma key (dark set only)...")
            extract_band(SRC, cxc, cwc, cyc, chc, n, band_dir)

    seq = pathlib.Path(CFG.get("work","_ovr")); shutil.rmtree(seq, ignore_errors=True); seq.mkdir()
    for i in range(n):
        t = i/FPS
        fr = Image.new("RGBA", (W, H), (0, 0, 0, 0))

        head_until = (1e9 if MODE == "headline" else HOOK_END + 0.4)
        if MODE != "chip" and t < head_until:
            hl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            if HEADLINE:
                # A WRITTEN hook, held for the whole hook window. Auto-chunking the VO gives
                # lines like "THIS, BUT WHAT" - the reference ads use a crafted two-liner.
                draw_head(hl, HEADLINE[0], HEAD_Y1, False)
                if len(HEADLINE) > 1 and t >= CFG.get("headline_l2_at", 0.55):
                    draw_head(hl, HEADLINE[1], HEAD_Y2, True)
            for pr in ([] if HEADLINE else pairs):
                if pr[0]["s"]-0.08 <= t <= pr[-1]["e"]+0.28:
                    draw_head(hl, pr[0]["t"], HEAD_Y1, False)
                    if len(pr) > 1 and t >= pr[1]["s"]-0.05:
                        draw_head(hl, pr[1]["t"], HEAD_Y2, True)
                    break
            if MATTE and hl.getbbox():
                bp = band_dir/f"b{i+1:05d}.png"
                if bp.exists():
                    # punch the subject out of the headline: alpha *= (1 - matte)
                    inv = subject_matte(bp, MATTE_TH, MATTE_FEATHER, MATTE_PRE).point(lambda v: 255-v)
                    keep = Image.new("L", (W, H), 255)
                    keep.paste(inv, (0, 0))
                    hl.putalpha(ImageChops.multiply(hl.getchannel("A"), keep))
            fr.alpha_composite(hl)

        if OVS_FULL:
            draw_broll_full(fr, OVS_FULL, t)

        if OVS_CUT:
            draw_cutaway(fr, OVS_CUT, t, BG_FRAMES)

        # pill track: only in hybrid mode, and it stops for the CTA (legacy)
        if MODE == "hybrid" and t < BANNER_IN - 0.15:
            cur = next((c for c in ch if c["s"]-0.06 <= t <= c["e"]+0.22), None)
            if cur: draw_pill(fr, cur["t"], pfont)

        # chip track (default): runs the ENTIRE ad, including underneath the CTA —
        # matches Hunter's real ad, where the caption never stops for the close.
        # Windows are contiguous (chip_windows), so there is always exactly one active
        # pair — no gaps, and both its lines render together, no stagger.
        if (MODE == "chip" and not (USE_CTA_CARD and t >= BANNER_IN)
                and (CHIP_STOP_AT is None or t < CHIP_STOP_AT)):
            pr = next((pr for pr, (s, e) in zip(chip_pairs, chip_windows) if s <= t < e), None)
            if pr: draw_chip_pair(fr, pr, cfont)

        if card and CARD_IN-0.5 <= t <= CARD_OUT+0.45:
            p = ((t-CARD_IN)/0.5 if t < CARD_IN+0.5
                 else (1-(t-CARD_OUT)/0.45 if t > CARD_OUT else 1.0))
            e = ease(min(1, max(0, p)))
            sc = 0.94+0.06*e
            c2 = card.resize((int(card.width*sc), int(card.height*sc)))
            c2.putalpha(c2.getchannel("A").point(lambda a: int(a*e)))
            fr.alpha_composite(c2, (int(W/2-c2.width/2), int(400-(1-e)*24)))

        draw_overlays(fr, OVS, t)

        if USE_CTA_CARD and t >= BANNER_IN:
            # Full-screen end-card: replaces the talking head entirely (opaque top to
            # bottom) instead of a small pill on top of the live video. Regenerated
            # every frame (not built once + cross-faded flat) so icon/headline/
            # instruction/arrow can each stagger in on their own timing — see
            # cta_fullscreen_card(). The background itself still cross-fades in from
            # the live video over 0.4s so the cut from footage to card isn't instant.
            elapsed = t - BANNER_IN
            e = ease(min(1, elapsed/0.4))
            card_img = cta_fullscreen_card(elapsed)
            if e < 1:
                card_img.putalpha(card_img.getchannel("A").point(lambda a: int(a*e)))
            fr.alpha_composite(card_img, (0, 0))
        elif CFG.get("cta_builtin", True) and t >= BANNER_IN:
            e = ease(min(1, (t-BANNER_IN)/0.45))
            pl = pill.copy()
            # shine sweep: a soft white band travels across once, ~0.45-1.25s after entry
            g = (t-BANNER_IN-0.45)/0.8
            if 0 <= g <= 1:
                sh = Image.new("RGBA", pl.size, (0, 0, 0, 0))
                sd = ImageDraw.Draw(sh)
                sx = int(-pl.width*0.5 + g*pl.width*1.6)
                for k in range(-70, 71):
                    a = int(120*(1-abs(k)/70))
                    sd.line([(sx+k, 0), (sx+k-90, pl.height)], fill=(255, 255, 255, a), width=3)
                sh.putalpha(ImageChops.multiply(sh.getchannel("A"), pl.getchannel("A")))
                pl.alpha_composite(sh)
            # 1048 (measured 2026-08-21 off a real shipped ad) puts the pill's visual top
            # at ~1078 (56% of H) — well above the chip caption band (1322) and disclaimer.
            fr.alpha_composite(pl, (int(W/2-pl.width/2), int(CFG.get("cta_y", 1048)+(1-e)*260)))

        if DISC is not None:
            fr.alpha_composite(DISC)

        fr.save(seq/f"f{i:05d}.png")
        if i % 150 == 0: print(f"    {i}/{n}", flush=True)

    cx, cw = cxc, cwc

    # Music bed + SFX: extra audio inputs mixed with the voice (0:a). Music loops/trims
    # to the ad's own length and sits well under the voice; each SFX is a one-shot
    # delayed to its beat. `amix ... normalize=0` keeps amix from quietly turning the
    # voice down just because more inputs joined the mix.
    audio_inputs, filters, mix_labels = [], [], ["0:a"]
    extra_i = 2
    music_path = CFG.get("music")
    if music_path:
        audio_inputs += ["-stream_loop", "-1", "-i", music_path]
        gain = 10 ** (CFG.get("music_db", -20)/20)
        filters.append(f"[{extra_i}:a]atrim=0:{dur},volume={gain}[music]")
        mix_labels.append("music"); extra_i += 1
    for k, sx in enumerate(CFG.get("sfx", [])):
        at = resolve_time(sx["at"], words)
        audio_inputs += ["-i", sx["src"]]
        gain = 10 ** (sx.get("db", -6)/20)
        lbl = f"sfx{k}"
        filters.append(f"[{extra_i}:a]adelay=delays={int(at*1000)}:all=1,volume={gain}[{lbl}]")
        mix_labels.append(lbl); extra_i += 1

    # fps={FPS} on the LIVE source before the overlay is required, not cosmetic: SRC is
    # whatever the camera/reframe left it at (often ~29.97, sometimes 30) while the
    # overlay PNG sequence is generated at exactly FPS=24. Compositing two streams at
    # different frame rates leaves their frame PAIRING ambiguous — `overlay` picks
    # whichever overlay frame is current for the main stream's PTS, and the later
    # `-r 24` conversion on the encoder can then drop/duplicate across that seam,
    # occasionally pairing a live-source frame with the WRONG overlay frame for a single
    # output frame. Symptom: a one-frame flash back to the live talking head in the
    # middle of an otherwise continuous cutaway (caught 2026-08-26, ad review — traced
    # past the cutaway timing logic itself, which tested correct frame-by-frame in the
    # raw PNG sequence). Fix: resample SRC to the SAME 24fps before it ever reaches
    # `overlay`, so both streams have identical, aligned frame timing.
    fc = (f"[0:v]crop={cwc}:{chc}:{cxc}:{cyc},scale={W}:{H}:flags=lanczos,setsar=1,fps={FPS}[b];"
          f"[b][1:v]overlay=0:0:format=auto[v]")
    if len(mix_labels) > 1:
        fc += ";" + ";".join(filters)
        fc += ";" + "".join(f"[{m}]" for m in mix_labels) + \
              f"amix=inputs={len(mix_labels)}:duration=first:normalize=0[aout]"
        audio_map = ["-map", "[aout]"]
    else:
        audio_map = ["-map", "0:a"]

    subprocess.run(["ffmpeg","-nostdin","-v","error","-y","-i",SRC,
        "-framerate",str(FPS),"-i",str(seq/"f%05d.png"), *audio_inputs,
        "-filter_complex", fc,
        "-map","[v]", *audio_map, "-c:v","libx264","-preset","slow","-crf","18",
        "-pix_fmt","yuv420p","-c:a","aac","-b:a","192k","-r",str(FPS),"-shortest",OUT], check=True)

    # Optional speed change — applied as a POST pass on the fully composited output, not
    # the source before rendering. Speeding up the raw source first would desync every
    # phrase-anchored caption/overlay from the (now faster) words; retiming video+audio
    # TOGETHER after everything is already burned in keeps captions/CTA/cutaways locked
    # to the voice, just uniformly compressed with it.
    #
    # Two forms:
    #   "speed": 1.15                                             — uniform, whole clip
    #   "speed_segments": [{"end": 2.0, "speed": 1.0},             — a ramp: each segment
    #                       {"end": null, "speed": 1.08}]            covers [prev.end, end)
    #                                                                 of the ORIGINAL (pre-
    #                                                                 speed) timeline; the
    #                                                                 last segment's "end"
    #                                                                 must be null/omitted
    #                                                                 (runs to the clip's
    #                                                                 actual end).
    segs = CFG.get("speed_segments")
    speed = CFG.get("speed", 1.0)
    if segs or (speed and speed != 1.0):
        tmp = OUT + ".prespeed.mp4"
        shutil.move(OUT, tmp)
        if not segs:
            segs = [{"end": None, "speed": speed}]
        vparts, aparts, labels = [], [], []
        prev_end = 0.0
        for i, sg in enumerate(segs):
            s = sg["speed"]
            end = sg.get("end")
            trim_v = f"trim=start={prev_end}" + (f":end={end}" if end is not None else "")
            trim_a = f"atrim=start={prev_end}" + (f":end={end}" if end is not None else "")
            vparts.append(f"[0:v]{trim_v},setpts=(PTS-STARTPTS)/{s}[v{i}]")
            aparts.append(f"[0:a]{trim_a},asetpts=PTS-STARTPTS,atempo={s}[a{i}]")
            labels.append(i)
            prev_end = end if end is not None else prev_end
        vcat = "".join(f"[v{i}]" for i in labels) + f"concat=n={len(labels)}:v=1:a=0[v]"
        acat = "".join(f"[a{i}]" for i in labels) + f"concat=n={len(labels)}:v=0:a=1[a]"
        fc2 = ";".join(vparts + aparts + [vcat, acat])
        # -r after the filter forces a clean CFR output at the ORIGINAL fps: without it
        # the encoder was left to infer timing from the compressed PTS values on its
        # own, and produced a ghosted/double-exposed blend at some frames instead of a
        # clean cut — visually identical to a leftover cross-fade, but actually an
        # encoder timing artifact (caught 2026-08-21, traced past the cutaway-transition
        # logic itself, which tested correct at 1.0x).
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", tmp,
            "-filter_complex", fc2,
            "-map", "[v]", "-map", "[a]", "-r", str(FPS), "-c:v", "libx264",
            "-preset", "slow", "-crf", "18",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", OUT], check=True)
        pathlib.Path(tmp).unlink()
        print(f"  speed segments {segs} ->", OUT)

    # Optional short audio fade-out (`"audio_fade_out": 0.25`) — softens a hard plosive/
    # consonant on the last spoken word (e.g. the "T" in "fit.") that otherwise cuts off
    # abruptly. Two forms:
    #   0.25                                          — legacy: last 0.25s of the FILE.
    #                                                     Only correct if speech runs to
    #                                                     the very last frame — most clips
    #                                                     have trailing silence/tail after
    #                                                     the last word, and this form
    #                                                     fades the silence, not the word
    #                                                     (caught 2026-08-26: "fit." ended
    #                                                     0.5s before the clip did, so a
    #                                                     from-file-end fade missed it
    #                                                     completely).
    #   {"at": "fit", "pre_roll": 0.09, "duration": 0.25} — targeted: "at" resolves against
    #                                                     the transcript (phrase or seconds,
    #                                                     ORIGINAL pre-speed timeline, same
    #                                                     as every other beat), converted to
    #                                                     the FINAL sped-up timeline, minus
    #                                                     "pre_roll" seconds so the fade
    #                                                     starts just before the target
    #                                                     word/syllable rather than after it.
    fade_out = CFG.get("audio_fade_out")
    if fade_out:
        tmp = OUT + ".prefade.mp4"
        shutil.move(OUT, tmp)
        dur_out = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries",
            "format=duration", "-of", "csv=p=0", tmp], capture_output=True, text=True).stdout)
        if isinstance(fade_out, dict):
            t_orig = resolve_time(fade_out["at"], words)
            t_final = to_final_time(t_orig, CFG.get("speed", 1.0), CFG.get("speed_segments"))
            st = max(0.0, t_final - fade_out.get("pre_roll", 0.0))
            d = fade_out.get("duration", 0.25)
        else:
            d = fade_out
            st = max(0.0, dur_out - d)
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", tmp,
            "-filter_complex", f"[0:a]afade=t=out:st={st}:d={d}[a]",
            "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", OUT],
            check=True)
        pathlib.Path(tmp).unlink()
        print(f"  audio fade-out st={st:.2f} d={d} ->", OUT)

    print("  ->", OUT)


if __name__ == "__main__":
    main()
