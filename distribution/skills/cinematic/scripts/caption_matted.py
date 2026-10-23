#!/usr/bin/env python3
"""caption_matted.py — THE caption engine for the MATTED variant. Copy this in as `caption_v2.py`.

🛑 THIS FILE EXISTED ONLY INSIDE PROJECT FOLDERS UNTIL 2026-08-12. `caption_type.py` beside it is
the HOUSE variant (flat 96pt ladder, OpenSauceSans). The matted variant needs Europa Grotesk, the
graduated size ladder, and the two-line `lead` lockup — and a batch built by copying
`caption_type.py` in as `caption_v2.py` died on `KeyError: 'lead'` for three clips and silently
rendered the other two in the WRONG FONT AND SIZE LADDER. A gate would not have caught it: the
captions were internally consistent, just not the approved look.

Pick ONE per clip and never mix:
  matted variant  -> this file            (Europa Grotesk, graduated ladder, lead lockup)
  house variant   -> caption_type.py      (OpenSauceSans, flat ladder)
"""
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from pathlib import Path

W, H = 1080, 1920
CARD_X, CARD_Y, CARD = 50, 470, 980

SANS = ("/System/Library/Fonts/HelveticaNeue.ttc", 1)      # index 1 = Bold (UPRIGHT; 2 is Italic)
# MEASURED off the new references ("2nd" on a white card): ink coverage 0.263, aspect 2.76.
# Snell Roundhand BLACK = 0.252 / 2.69.  Regular 0.141/2.30 · Bold 0.204/2.53 · Great Vibes 0.202.
# The secondary face is a BOLD ENGRAVER'S SCRIPT, not a Didone serif italic — that was the
# "secondary font I don't love". Ships with macOS.
SERIF = ("/System/Library/Fonts/Supplemental/SnellRoundhand.ttc", 2)   # index 2 = Black

# calibrated off the reference glyph heights on a 980px card
# MEASURED over 1,882 caption lines in reel 1 (card = 980px):
#   body 35-65px cap (3.6-6.6%) · emphasis ~104px (10.6%) · max emphasis ~155px (15.5%)
# My first pass was flat (43/53/80) — the reference range is much wider.
# Re-calibrated against reel 3 measured side-by-side with our own output:
#   REF cap height p50 43px (4.4% of card) p90 86px (8.8%);  ours was p50 50 p90 104 = ~1.2x over.
# Calibrated by measuring OUR caption alpha masks against the reference frames:
#   REF cap height p50 44px, p90 86px.  mid must land ~44px cap; hero ~86px; beats stay RARE.
# Calibrated against the reference FRAMES I read at 15fps (captions span 0.25-0.45 of card
# width, cap height ~40-45px at p50). NOTE: the aggregate width metric from frame analysis is
# CONTAMINATED on both sides (bright window + dark mullions trip the text detector), so the
# visual read is the ground truth here, not the 0.71 aggregate.
# Calibrated 2026-08-09 against 36 CLEAN reference specimens (glyph_hunt crops, native frame px,
# 6 reels): text-box height p25 49 · p50 70 · p75 97 · p90 121 · max 193. Measured on OUR side
# from the caption ALPHA MASKS -- the earlier "ours is 1.2x over" reading was taken off renders
# that still carried the glow, which inflated every box by ~70px and drove the ladder DOWN twice.
# WIDTH is the honest measure of visual weight, not glyph height: a short word and a long word
# at the same point size read completely differently. Caption-box width / card, 297 reference
# boxes vs ours: body matched (p25 .29/.28, med .39/.42) but our EMPHASIS tier was ~1.5x too
# wide (p75 .50 vs .79, p90 .63 vs .91) -- big words spanned nearly the whole card, which the
# reference never does. hero/mega scaled 0.65x; body left alone.
# MATTED VARIANT: type scaled up. Reference ink height is 8.8-13.9% of the card; the house
# style sits at 6.8%. Bigger works here because the subject crosses in front of it.
# Emphasis is SIZE + CAPS (he has one weight). Ink height targets from his reels: 8.8-13.9%.
SIZES = {"base": 108, "strong": 118, "emph": 132, "peak": 150,
         "sm": 108, "mid": 118, "tiny": 96, "hero": 132, "mega": 150,
         "serif": 104, "serif_sm": 76, "display": 128,
         # 🛑 THE TWO-LINE LOCKUP. Measured on DbzAXF5BqEw: the small lead line and the big
         # payload line run at a **2.24x** size ratio (49px vs 110px ink on a 909 card), and the
         # small line NESTS above the tail of the big one rather than sitting squarely on top.
         # It is the single most recognisable thing about that style. This is a per-LINE size,
         # which the locked house model allows ("a size bump lands on a single-word caption OR
         # the whole line") -- it is per-WORD size mixing that stays banned.
         "lead": 56}   # ~125/2.24; our overall type scale runs smaller than the reference's
SERIF_STYLES = {"serif", "serif_sm"}
# Letter spacing: the author gives the number outright -- "turn the letter spacing down, which
# makes everything look a lot more clean, about a value of like -40 or so". Premiere's units are
# 1/1000 em, so -40 = -4%. We were at -2.5%.
TRACK = -0.040        # -4% of em — measured value from the author, not a guess
# Word gap as a fraction of the em. NEGATIVE tracking tightens letters, which is the style, but
# it also drags WORDS together: at 0.21em a Bold word butting a Black one read as a single word
# ("was"+"nothing" -> "wasnothing"). Letters tight, words clearly apart.
WGAP = 0.30

# ── THE TYPE SYSTEM ────────────────────────────────────────────────────────────────────────
# Until now every word rendered in ONE face: the serif path required EVERY word in a chunk to be
# in a hand-listed set, so it never fired, and 42 of 121 words landed on the identical size.
# The reference reels are not that flat. Faces below are the ones the reference pack actually
# ships, ranked by glyph IoU against our clean 8-sample specimen:
#   HelveticaNeue Bold 0.788 · OpenSauceSans Black 0.763 · Helvetica Bold 0.751 · Inter 0.740
#   Akira Expanded 0.312  <- scores low BECAUSE it is a display face, never a caption face.
# Roles, not decoration: body carries the sentence, emphasis carries the beat word, display is
# for hooks and title cards only, script is the card accent.
FONTS = os.path.expanduser("__ACQ_ASSETS__/assets/fonts")
PROXIMA = str(Path(__file__).resolve().parents[2] / "caption-clips/fonts/proxima_full")

# 🛑 EMPHASIS IS **WEIGHT**, NOT SIZE. This is the house caption model, already locked in
# caption-clips/SKILL.md and proven on shipped work — do not reinvent it here:
#     "Weight = vocal stress. Proxima Nova ladder: Medium (base) -> Bold -> Extrabold -> Black.
#      Base weight is Medium, never Regular/Light."
#     "Size = intensity, subtle (10-15%). PER CUE only — a size bump lands on a single-word
#      caption OR the whole line, NEVER one word inside a multi-word line."
# We had it backwards: emphasis by SIZE, mixed inside a line. To make that fit, mixed sizes then
# had to be stacked onto separate lines — which is exactly the jumping/glitching the editor saw.
# Weight varies per WORD; size varies per CUE. Everything sits on ONE line at ONE size.
# FACE: Open Sauce Sans, not Proxima. The course author states it outright while styling a cue
# ("go to Open Sauce Sans Black -- that's looking way better to me"), and it independently won our
# own glyph IoU on one reel (0.763 overall, 0.84/0.88/0.86 on DbyOnB1O16q). Proxima is the house
# face for /edit's spice captions; this style uses the reference's face. We keep /edit's WEIGHT
# LOGIC and swap only the family -- Open Sauce ships the same 4-step ladder.
# 🛑 HIS ACTUAL FONTS, from the course asset pack — not our IoU guesses.
#   main   = Europa Grotesk SH Demi-Bold  ("ElitexVision Font")
#   second = Roundhand Bold               ("ElitexVision Second Font")
# He ships ONE weight of the main face, so his emphasis is SIZE + CAPS, not a weight ladder.
# Our four-step weight ladder was an invention; keep the names, point them all at Europa.
FACE_BASE    = (os.path.join(FONTS, "europa-grotesk-medium.ttf"), 0)
FACE_STRONG  = FACE_BASE
FACE_EMPH    = FACE_BASE
FACE_PEAK    = FACE_BASE
FACE_SCRIPT  = (os.path.join(FONTS, "Roundhand Bold.ttf"), 0)
FACE_DISPLAY = (os.path.join(FONTS, "Akira Expanded Demo.otf"), 0)

STYLE_FACE = {
    "base": FACE_BASE, "strong": FACE_STRONG, "emph": FACE_EMPH, "peak": FACE_PEAK,
    # legacy names kept so nothing breaks; they now map onto the weight ladder, NOT onto sizes
    "sm": FACE_BASE, "mid": FACE_STRONG, "tiny": FACE_BASE,
    "hero": FACE_EMPH, "mega": FACE_PEAK,
    "display": FACE_DISPLAY,
    "serif": FACE_SCRIPT, "serif_sm": FACE_SCRIPT,
}

# Per-CUE size multipliers, from the locked spec (emph 110 / strong 115 / peak 120).
CUE_SIZE = {"none": 1.00, "emph": 1.10, "strong": 1.15, "peak": 1.20}

# 🛑 A SLIDE MUST NEVER BE WIDER THAN THE GAP TO THE NEXT WORD.
# V21 shipped 150px travel; words in a chunk sit side by side with normal word-spacing, so a
# sliding word crossed straight over its neighbour ("because"+"there" -> "becausehere").
# Two words mid-slide at different elapsed times sit at different offsets, so they collide.
MAX_TRAVEL_FRAC = 0.55        # of the gap to the neighbouring word

# 🛑 WHITE IS THE STYLE. BLACK IS AN EXCEPTION, NOT A BALANCE.
# Editor: "I don't like that there's black text that you randomly use... it was just a one-off
# scenario when it went to an all-white background."
# A 128 threshold is the midpoint of the luma range, so it flipped on any merely BRIGHT plate —
# 24 of 100 words. Measured under the actual glyphs: p90 190, p95 255. The genuine all-white
# interstitials sit at a pin-clean 255; everything between 128 and 200 is just bright footage.
# 200 leaves black ONLY on the pure-white plates (9 words, every one of them luma 255).
WHITE_PLATE = 200

GRAD_TOP, GRAD_BOT = (251, 239, 200), (224, 138, 51)
GLOW = (255, 176, 84)
# Ceiling on line width, and it is a STYLE constant, not a safety margin. 90% of reference
# caption boxes sit under 0.63 of the card (617px); ours ran to 0.91 because MAXW was set to
# the card itself (900 = 0.92). A caption that spans the whole card reads as a subtitle, not
# as this style. 620px = the reference p90.
MAXW = 520        # matted variant: keep lines NARROW. A wide line pushed off-card the
                  # moment the block moved into the negative space.            # auto-shrink a line that would exceed this


# 🛑 LEGIBILITY FLOOR ON THE LEAD LINE. The 2.24x lockup ratio compounds with the MAXW clamp:
# a long payload line ("well-intentioned people") drags the whole cue's scale down, and the lead
# line then rendered at **17px ink — 1.7% of the card**, far under the reference's 5.4%. The
# ratio is the finding; an unreadable line is not. Floor the lead so it can never fall below a
# readable size, even if that means the ratio compresses on the longest cues.
LEAD_MIN_PT = 62          # ~44px ink on a 980 card ~= 4.5%, just under the reference's 5.4%

def _sz(style, scale):
    """Point size for a run. THE single place size is computed — _line_w, _line_metrics and
    _draw must all agree or the layout maths silently desyncs."""
    v = int(SIZES[style] * scale)
    if style == "lead":
        v = max(v, min(LEAD_MIN_PT, SIZES["lead"]))
    return v

_c = {}
def _font(style, size=None):
    sz = size or SIZES[style]
    key = (style, sz)
    if key not in _c:
        path, idx = STYLE_FACE.get(style, FACE_BASE)
        try:
            _c[key] = ImageFont.truetype(path, sz, index=idx)
        except OSError:                      # a vault font is missing -> fall back LOUDLY, never silently
            import sys
            print(f"  !! FONT MISSING for style '{style}': {path} -- falling back to body face", file=sys.stderr)
            _c[key] = ImageFont.truetype(FACE_BASE[0], sz, index=FACE_BASE[1])
    return _c[key]


def _adv(f, ch, sz):
    return f.getlength(ch) + TRACK * sz


def _line_w(runs, scale=1.0):
    """Must mirror _draw exactly: glyph advances per word + WGAP between words."""
    w = 0.0
    for r in runs:
        sz = _sz(r["style"], scale)
        f = _font(r["style"], sz)
        for word in r["t"].split():
            for ch in word:
                w += _adv(f, ch, sz)
            w += WGAP * sz
    last_sz = _sz(runs[-1]["style"], scale)
    return w - WGAP * last_sz


def _fit(lines, cue_scale=1.0):
    """Global scale: the per-CUE size bump, clamped so the widest line still fits MAXW."""
    widest = max(_line_w(l["runs"]) for l in lines)
    s = cue_scale
    if widest * s > MAXW:
        s = MAXW / widest
    return s


def _line_metrics(runs, scale):
    """max ascent above baseline and max descent below, in px, for one line."""
    asc = desc = 0
    for r in runs:
        sz = _sz(r["style"], scale)
        f = _font(r["style"], sz)
        # BASELINE-relative box: PIL's default getbbox is origin-relative, which returns
        # ascent 0 for every line and silently collapses the leading maths.
        x0, y0, x1, y1 = f.getbbox(r["t"], anchor="ls")
        asc = max(asc, -y0); desc = max(desc, max(y1, 0))
    return asc, desc


def _word_slots(block):
    """Every word's (line_index, run_index, word_index) in speaking order."""
    slots=[]
    for li, line in enumerate(block["lines"]):
        for ri, r in enumerate(line["runs"]):
            for wi, w in enumerate(r["t"].split()):
                slots.append((li, ri, wi, w))
    return slots


def _draw(block, draw_fn, only=None):
    lines = block["lines"]
    scale = _fit(lines, block.get("cue_scale", 1.0))
    # tight but NEVER overlapping: next baseline = prev descent + this ascent + a little air
    air = block.get("air", 0.26)
    met = [_line_metrics(l["runs"], scale) for l in lines]
    ys, y = [], 0
    for i, (asc, desc) in enumerate(met):
        if i: y += met[i-1][1] + asc + int(asc * air)
        ys.append(y)
    ax, ay = block["anchor"]
    align = block.get("align", "left")
    n = -1
    for li, line in enumerate(lines):
        lw = _line_w(line["runs"], scale)
        x = ax if align == "left" else (ax - lw / 2 if align == "center" else ax - lw)
        for ri, r in enumerate(line["runs"]):
            sz = _sz(r["style"], scale)
            f = _font(r["style"], sz)
            for wi, word in enumerate(r["t"].split()):
                n += 1
                draw_this = (only is None) or (n == only)
                for ch in word:
                    if draw_this:
                        draw_fn((x, ay + ys[li]), ch, f)
                    x += _adv(f, ch, sz)
                x += WGAP * sz            # keep the layout identical whether drawn or not
            # no extra run-boundary gap: WGAP already separated the last word of this run


def _mask(block, only=None):
    m = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(m)
    _draw(block, lambda xy, ch, f: d.text(xy, ch, font=f, fill=255, anchor="ls"), only=only)
    return m, m.getbbox()


def plate_luma(plate, mask):
    """Luminance of the backing plate UNDER THE GLYPH PIXELS (not the bbox — a bbox mean
    averages in dark background and hides a white-on-white collision)."""
    import numpy as np
    a = np.asarray(plate.convert("L"), dtype=float)
    m = np.asarray(mask, dtype=float) / 255.0
    tot = m.sum()
    return float((a * m).sum() / tot) if tot else 0.0


def render(block, out=None, plate=None, only=None):
    """only=k renders ONLY word k, at its position in the full block layout —
    so each word can be its own timeline item with its own entrance animation."""
    mask, bbox = _mask(block, only=only)
    if bbox is None:
        raise ValueError("empty block")
    # 🛑 DEFAULT IS WHITE, NEVER "gradient". The gold gradient + glow was fabricated from ONE frame
    # and rejected outright ("this looks absolutely terrible"); 97% of reference caption text is
    # flat neutral white. It used to be the default, so any caller that simply forgot to pass a
    # fill silently shipped the rejected look — which is exactly what happened once. Opting IN is
    # the only way to get it now.
    fill = block.get("fill", "white")
    # LEGIBILITY: white type on a near-white plate is unreadable no matter the shadow -> flip to dark
    # 🛑 TWO STATES ONLY — white or black. NEVER a shadow: the reference carries none
    # (ring test: 3-9px 149.8 = antialiasing, 9-17px 88.7, background 84.1) and the editor has
    # ruled it out outright for this style. Plate luma is strongly bimodal (p50 62, p75 181), so a
    # single threshold is clean.
    if plate is not None and fill == "white" and plate_luma(plate, mask) > WHITE_PLATE:
        fill = "black"
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    if fill == "gradient":
        y0, y1 = bbox[1], bbox[3]
        g = Image.new("RGB", (1, max(y1 - y0, 1))); gp = g.load()
        for i in range(g.size[1]):
            t = i / max(g.size[1] - 1, 1)
            gp[0, i] = tuple(int(GRAD_TOP[c] + (GRAD_BOT[c] - GRAD_TOP[c]) * t) for c in range(3))
        full = Image.new("RGB", (W, H), GRAD_BOT); full.paste(g.resize((W, g.size[1])), (0, y0))
        glow = mask.filter(ImageFilter.GaussianBlur(15)).point(lambda v: int(v * 0.42))
        gl = Image.new("RGBA", (W, H), GLOW + (0,)); gl.putalpha(glow)
        layer = Image.alpha_composite(layer, gl)
        t = full.convert("RGBA"); t.putalpha(mask)
        layer = Image.alpha_composite(layer, t)
    elif fill == "white":
        # MEASURED on the reference ('RELENTLESS', white type over movie b-roll): ring luminance
        # 3-9px = 149.8 (glyph antialiasing), 9-17px = 88.7, far background = 84.1. There is NO
        # darkening anywhere -> the reference carries NO drop shadow and NO glow. Flat white only.
        # Legibility on bright plates is handled by the dark-flip guard above, not by a shadow.
        t = Image.new("RGBA", (W, H), (253, 253, 253, 0)); t.putalpha(mask)
        layer = Image.alpha_composite(layer, t)
    else:
        t = Image.new("RGBA", (W, H), (12, 12, 12, 0)); t.putalpha(mask)
        layer = Image.alpha_composite(layer, t)

    if out:
        layer.save(out)
    return layer


# ---------------------------------------------------------------- word-timed states
def L(*runs):
    return {"runs": [{"t": t, "style": s} for t, s in runs]}


def blk(lines, x=70, y=430, align="left", fill="gradient", lead=0.80):
    return dict(lines=lines, anchor=(CARD_X + x, CARD_Y + y), align=align, fill=fill, leading=lead)


def states_from_groups(words, groups, per_word=True):
    """REFERENCE GRAMMAR (measured off 1,609 frames at 15fps):
    words appear ONE AT A TIME and accumulate within a phrase; a new LINE joins below when the
    emphasis word lands; the completed block then clears (with a fade — see make_xml).
    Returns [(t0, t1, block, is_phrase_end)].
    """
    st = []
    prev_units = []
    PAUSE = 0.25          # a real speech pause; only THERE does the reference let text drop out
    for gi, g in enumerate(groups):
        if gi + 1 < len(groups):
            nxt = words[groups[gi + 1]["i0"]]["t0"]
            hole = nxt - words[g["i1"]]["t1"]
            # back-to-back chunks must NOT fade — fading with nothing behind it blinks the caption
            # off. The reference holds text almost continuously (one 37.4s run; ours had 12 holes).
            gend = (words[g["i1"]]["t1"] + 0.15) if hole > PAUSE else nxt
            fade_here = hole > PAUSE
        else:
            gend = words[g["i1"]]["t1"] + 0.45
            fade_here = True
        lay = g.get("lay", {})
        # explode every run into individual WORDS, preserving line + style
        units = []
        for li, ln in enumerate(g["lines"]):
            for text, style in ln:
                for w in str(text).split():
                    units.append((li, w, style))
        if not per_word or not units:
            st.append((round(words[g["i0"]]["t0"], 3), round(gend, 3),
                       blk([L(*ln) for ln in g["lines"]], **lay), fade_here, True))
            continue
        span = list(range(g["i0"], g["i1"] + 1))
        n = len(units)
        # units carried over from the previous group are ALREADY on screen — they must appear
        # instantly at the group start, not re-build word by word (that stepped backwards).
        carried = 0
        if gi and prev_units:
            while carried < n and carried < len(prev_units) and units[carried] == prev_units[carried]:
                carried += 1
        fresh = max(n - carried, 1)
        onsets = []
        for k in range(n):
            if k < carried:
                onsets.append(words[g["i0"]]["t0"])
            else:
                j = k - carried
                wi = span[min(int(round(j * (len(span) - 1) / max(fresh - 1, 1))), len(span) - 1)]
                onsets.append(words[wi]["t0"])
        for k in range(n):
            if k < carried - 1:      # collapse the carried run into one state
                continue
            t0 = onsets[k]
            t1 = onsets[k + 1] if k + 1 < n else gend
            if t1 <= t0 + 0.02:
                continue
            shown = {}
            for li, w, style in units[:k + 1]:
                shown.setdefault(li, []).append((w, style))
            blines = []
            for li in sorted(shown):
                runs = []
                for w, style in shown[li]:
                    if runs and runs[-1][1] == style:
                        runs[-1] = (runs[-1][0] + " " + w, style)
                    else:
                        runs.append((w, style))
                blines.append(L(*runs))
            st.append((round(t0, 3), round(t1, 3), blk(blines, **lay),
                       (k == n - 1) and fade_here, k == carried or (carried == 0 and k == 0)))
        prev_units = units
    return st
