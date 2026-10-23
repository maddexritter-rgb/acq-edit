#!/usr/bin/env python3
"""gen_captions.py — render ONE PNG PER WORD + the manifest that preview/XML both consume.

This step existed only as an ad-hoc snippet and was never saved, so a type change could not be
re-rendered without rebuilding it from scratch. It is a real script now.

  generated_groups.py (chunks+styles)  +  blackdot_words.json (onsets)  +  plate.py (luma)
      -> premiere/assets/captions_v2/cap_%03d.png  +  manifest.json

Per word: its own item at its own onset, positioned in the FULL chunk layout (render(only=k)),
fill chosen from the luma of the plate BEHIND it, and a slide direction.
"""
import json, os, sys, importlib.util, collections
import numpy as np
from PIL import Image

D = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, D)
import caption_v2 as CT
import plan_v2 as P

OUT = f"{D}/premiere/assets/captions_v2"
os.makedirs(OUT, exist_ok=True)

spec = importlib.util.spec_from_file_location("gg", f"{D}/generated_groups.py")
gg = importlib.util.module_from_spec(spec); spec.loader.exec_module(gg)
GROUPS = gg.GROUPS

# cut/timeline_words.json is the AUTHORITATIVE post-/edit word list (t0/t1, timeline-relative).
# blackdot_words.json is a stale 94-word snapshot from before the final cut -- do not use it.
WORDS = json.load(open(f"{D}/cut/timeline_words.json"))
for w in WORDS: w.setdefault("start", w["t0"]); w.setdefault("end", w["t1"])
T0 = 0.0

# ── LAYOUT ────────────────────────────────────────────────────────────────────────────────────
# 🛑 THE REFERENCE CENTRES ITS CAPTIONS. Measured over 297 caption boxes across all six reels:
#     X centre  p25 0.47 · MED 0.50 · p75 0.51   (fraction of the 980 card)
#     Y centre  p25 0.47 · MED 0.50 · p75 0.57
# We were pinning every chunk to a fixed top-left corner (0.30, 0.13). That single fact — not the
# font, not the size — is what made our captions read wrong on every shot.
# X is nudged slightly left of centre because the subject sits right of frame in this source;
# that is a per-source adjustment, NOT a style rule. The style rule is: centre it.
# 🛑 MATTED VARIANT: the subject EATS whatever it covers, so a centred caption behind a subject
# who occupies the right half is unreadable ('YOURS OR THEIRS' rendered as 'YOURS'). Push the
# block into the empty side so only its TAIL passes behind him — occlusion as an accent, not a
# censor. Reference behaviour: the subject crosses PART of the word, never most of it.
# 🛑 PLACE THE CAPTION WHERE THE SUBJECT IS NARROWEST, not where the card centre is.
# Measured silhouette width by height on this framing: y0.14=33% · y0.21=37% · y0.50=64%.
# At mid-card Alex's torso+arm+mic blocked 64% of the line and ate the words. At head level
# he is a narrow vertical slice, which is exactly how the reference reads — the subject CROSSES
# the caption, it does not bury it. Re-measure this per source; it is framing-dependent.
CX_FRAC, CY_FRAC = 0.28, 0.50
ALIGN  = "left"                    # lines are left-aligned WITHIN a block that is centred
ANCHOR = (96, 620)                 # provisional; recentred per chunk in place_block()


def place_block(blk):
    """Move the block so its INK centre lands on the reference target. The anchor is the first
    baseline, so the offset can only be computed after measuring the rendered mask."""
    m, bb = CT._mask(blk, only=None)
    if bb is None:
        return blk
    tx = CT.CARD_X + CX_FRAC * CT.CARD
    ty = CT.CARD_Y + CY_FRAC * CT.CARD
    dx = tx - (bb[0] + bb[2]) / 2.0
    dy = ty - (bb[1] + bb[3]) / 2.0
    ax, ay = blk["anchor"]
    blk["anchor"] = (int(round(ax + dx)), int(round(ay + dy)))
    return blk

# 🛑 TRAVEL must stay smaller than the gap between neighbouring words. At 150px a sliding word
# crossed straight over its neighbour ("because"+"there" -> "becausehere"). 64px is proven.
# 🛑 DIRECTION IS PER CUE, NOT PER WORD. With DIRS[(gi+k)%4] a three-word cue had one word
# sliding left, the next up, the next right — read as jitter, not as motion. Same class of error
# as varying SIZE inside a line. The whole cue now enters together, one direction, and the
# variety the editor asked for lives ACROSS cues instead of inside them.
# Travel also comes down: the house spec's drop-in is 8px @1080. 64px with four directions was
# far past "smooth". 36px keeps the slide readable without throwing the word across the card.
TRAVEL = 36.0
MIN_WORD = 0.24      # a word shorter than this reads as a flicker, not a word
DIRS = ["right", "left", "up", "down"]


def block_for(g):
    return {"lines": [{"runs": [{"t": t, "style": st} for t, st in line]} for line in g["lines"]],
            "anchor": ANCHOR, "align": ALIGN,
            "cue_scale": g.get("cue_scale", 1.0)}     # size is PER CUE, never per word


_pc = {}
def P_plate(t):
    """The card content behind the captions at time t (FULL 1080x1920 canvas, same space as the
    glyph masks) -- so plate_luma can sample the actual glyph pixels with no offset maths."""
    k = round(t, 2)
    if k not in _pc:
        import plate
        _pc[k] = plate.plate_at(t)
    return _pc[k]


man = []
idx = 0
for gi, g in enumerate(GROUPS):
    blk = place_block(block_for(g))
    slots = CT._word_slots(blk)
    i0, i1 = g["i0"], g["i1"]
    gw = WORDS[i0:i1 + 1]
    g_t0 = gw[0]["start"] - T0
    # 🛑 HOLD THE FINAL CUE TO PICTURE-OUT. Every other cue is held until its SUCCESSOR takes over
    # (that is what keeps text on screen ~99% of the time as ONE run). The last cue has no
    # successor, so it alone was clipped to its own last word — leaving a textless flash of bare
    # picture before the black, on the PAYOFF word. Editor 2026-08-12: the ending "cuts to black
    # abruptly".
    g_t1 = (WORDS[GROUPS[gi + 1]["i0"]]["start"] - T0) if gi + 1 < len(GROUPS) else max(gw[-1]["end"] - T0, P.DUR)
    for k, (li, ri, wi, word) in enumerate(slots):
        # 🛑 map the k-th SHOWN word back to the word it actually came from. Captions
        # drop stutters/filler, so k-th shown != k-th spoken; without `keep` every
        # dropped word pulls the rest of the phrase early.
        _keep = g.get("keep")
        _src = _keep[k] if (_keep and k < len(_keep)) else k
        wtime = gw[min(_src, len(gw) - 1)]
        t0 = wtime["start"] - T0
        # A word that would flash for <MIN_WORD is pulled EARLIER (never held later, which would
        # cross the cue boundary). Bounded by the cue start, so it can only arrive a little ahead
        # of its onset -- imperceptible next to an 0.08s flicker.
        if g_t1 - t0 < MIN_WORD:
            t0 = max(g_t0, g_t1 - MIN_WORD)
        mask, bbox = CT._mask(blk, only=k)
        if bbox is None:
            continue
        # 🛑 DARK-FLIP: decide ink colour from the luma of the plate UNDER THIS WORD'S GLYPHS.
        # White-on-white is how "NOTHING" disappeared against the white-void b-roll.
        try:
            lum = CT.plate_luma(P_plate(t0 + 0.05), mask)
        except Exception as e:
            print(f"  !! plate failed at t={t0:.2f} ({e}) -- defaulting to white", file=sys.stderr)
            lum = 40.0
        # WHITE is the style; black only on a genuinely all-white plate (see caption_v2.WHITE_PLATE)
        ink = "black" if lum > CT.WHITE_PLATE else "white"
        f = f"cap_{idx:03d}.png"
        blk["fill"] = ink                       # explicit: never fall through to a default
        CT.render(blk, out=f"{OUT}/{f}", only=k)
        style = None
        for line in g["lines"]:
            for t_, st in line:
                if word in t_.split(): style = st
        man.append({
            # 🛑 A CUE IS ATOMIC: every word in it clears at the cue end, full stop.
            # A per-WORD minimum duration (max(cue_end, t0+0.35)) pushed late-starting words
            # straight through the boundary -- 24 of 100 words bled up to 0.27s into the next
            # cue, and since every cue is centred they landed ON TOP of each other.
            # Read-time is a CUE-level concern; enforce it by chunking, never by extending a word.
            "i": idx, "t0": round(t0, 3), "t1": round(g_t1, 3),
            "file": f, "word": word, "slot": k, "group": gi,
            "fill": ink,
            "style": style,
            # 🛑 ONE WORD PER CUE ANIMATES, NOT ALL OF THEM. From the course author, narrating
            # the exact move: "selecting the ONE WORD that you want to have a slide in effect on
            # -- you can do like a little slide in up." We were sliding EVERY word, which is what
            # made a 3-word cue look like three separate events firing. The stressed word moves;
            # the rest simply appear.
            "anim": DIRS[gi % 4] if style in ("emph", "peak") else "none",
            "anim_mag": 1.0,                       # uniform: a per-word magnitude read as jitter
            "fade_in": 2,
            "fade": False,
        })
        idx += 1

json.dump(man, open(f"{OUT}/manifest.json", "w"), indent=1)
c = collections.Counter(m["style"] for m in man)
fc = collections.Counter(m["fill"] for m in man)
print(f"wrote {len(man)} word PNGs -> {OUT}")
print("  style mix:", dict(c))
print("  fill mix :", dict(fc))
hs = []
for m in man:
    bb = Image.open(f"{OUT}/{m['file']}").split()[3].getbbox()
    if bb: hs.append(bb[3] - bb[1])
# ── GATE: nothing may sit outside the card ────────────────────────────────────────────────
CX0, CY0, CX1, CY1 = CT.CARD_X, CT.CARD_Y, CT.CARD_X + CT.CARD, CT.CARD_Y + CT.CARD
over = []
for m in man:
    bb = Image.open(f"{OUT}/{m['file']}").split()[3].getbbox()
    if not bb: continue
    d = []
    if bb[0] < CX0: d.append(f"left {CX0-bb[0]}")
    if bb[1] < CY0: d.append(f"top {CY0-bb[1]}")
    if bb[2] > CX1: d.append(f"right {bb[2]-CX1}")
    if bb[3] > CY1: d.append(f"bottom {bb[3]-CY1}")
    if d: over.append((m["word"], m["style"], d))
if over:
    print(f"  !! {len(over)} WORD(S) OUTSIDE THE CARD -- raise ANCHOR y or lower the tallest style:",
          file=sys.stderr)
    for w, st, d in over[:10]: print(f"       '{w}' ({st}) {', '.join(d)}", file=sys.stderr)
else:
    print("  card-bounds gate: PASS (0 words outside)")

# ── GATE: a cue must never straddle a shot cut that FLIPS the plate luma ───────────────────
# If it does, half the cue sits on a dark plate (wants white) and half on a bright one (wants
# black) and no single ink colour is right -- the "into" problem. The fix is always to move the
# CUT to the cue boundary, never to recolour mid-cue.
import plan_v2 as _P
cuts = sorted({round(sh["t0"], 3) for sh in _P.SHOTS if sh["t0"] > 0})
cue_span = {}
for m in man:
    a, b = cue_span.get(m["group"], (9e9, -9e9))
    cue_span[m["group"]] = (min(a, m["t0"]), max(b, m["t1"]))
straddle = []
for gi, (a, b) in sorted(cue_span.items()):
    for c in cuts:
        if a + 1e-6 < c < b - 1e-6:
            try:
                l0 = CT.plate_luma(P_plate(a + 0.02), CT._mask(block_for(GROUPS[gi]), only=0)[0])
                l1 = CT.plate_luma(P_plate(c + 0.02), CT._mask(block_for(GROUPS[gi]), only=0)[0])
            except Exception:
                continue
            if (l0 > CT.WHITE_PLATE) != (l1 > CT.WHITE_PLATE):
                straddle.append((gi, round(a, 2), round(b, 2), c, round(l0), round(l1)))
if straddle:
    print(f"  !! {len(straddle)} CUE(S) STRADDLE A LUMA FLIP -- move the CUT to the cue edge:", file=sys.stderr)
    for gi, a, b, c, l0, l1 in straddle:
        print(f"       cue {gi} {a}-{b} crosses cut @{c}  (luma {l0} -> {l1})", file=sys.stderr)
else:
    print("  luma-straddle gate: PASS (no cue crosses a plate flip)")
print(f"  glyph height: min={min(hs)} p25={int(np.percentile(hs,25))} MED={int(np.median(hs))} "
      f"p75={int(np.percentile(hs,75))} max={max(hs)}   (reference: 49/70/97, max 193)")
