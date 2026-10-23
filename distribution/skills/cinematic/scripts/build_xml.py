#!/usr/bin/env python3
"""make_xml.py — build the 9:16 card-style timeline as xmeml (FCP7 XML) for Premiere.

RUNBOOK route 8B / EDITABILITY INVARIANT: every cut is a real clipitem referencing its SOURCE
media at in/out points (razor-able), the card mask is a matte item on its own track, captions
are transparent overlay items, audio is its own lane. Nothing is baked.

xmeml rules that matter (learned the hard way, RUNBOOK STEP 8):
  · full <file> definition inline on the FIRST clipitem that uses it; later ones reference by id
  · absolute file://localhost pathurls
  · NO standalone audio file defs (silently rejected) -> music is laid post-import
"""
import json, os, sys, urllib.parse, importlib.util

# usage:  python3 build_xml.py <project_10_WORK_dir> [seq_name]
# the project dir must contain:  plan.py · cut/ · premiere/assets/
D = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.getcwd()
SEQ = sys.argv[2] if len(sys.argv) > 2 else "CINEMATIC_9x16"
A = f"{D}/premiere/assets"
LIB = os.path.expanduser("__ACQ_ASSETS__/assets/broll_lib/pp")   # ALWAYS the H.264 transcodes
sys.path.insert(0, D)
_spec = importlib.util.spec_from_file_location("plan", f"{D}/plan.py")
P = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(P)

FPS = 24000 / 1001.0
TB, NTSC = 24, "TRUE"
W, H = 1080, 1920
CARD = 980

def f(t):            # seconds -> frames
    return int(round(t * FPS))

def url(p):
    return "file://localhost" + urllib.parse.quote(os.path.abspath(p))

_seen = {}
def filedef(path, dur_f, has_audio=False, w=1920, h=1080, audio_only=False):
    """full def first time, id-reference after.
    🛑 An AUDIO-ONLY file must NOT carry a <video> block. Emitting <video><width>0</width> made
    Premiere link the music as video and the sequence played SILENT."""
    fid = "f" + str(abs(hash(path)) % 10**9)
    if fid in _seen:
        return f'<file id="{fid}"/>'
    _seen[fid] = True
    a = ""
    if has_audio:
        a = ('<audio><samplecharacteristics><depth>16</depth>'
             '<samplerate>48000</samplerate></samplecharacteristics>'
             '<channelcount>2</channelcount></audio>')
    head = (f'<file id="{fid}"><name>{os.path.basename(path)}</name>'
            f'<pathurl>{url(path)}</pathurl>'
            f'<rate><timebase>{TB}</timebase><ntsc>{NTSC}</ntsc></rate>'
            f'<duration>{dur_f}</duration>')
    if audio_only:
        return head + f'<media>{a}</media></file>'
    return (head + f'<media><video><samplecharacteristics><width>{w}</width>'
            f'<height>{h}</height></samplecharacteristics></video>{a}</media></file>')

AR = H / W          # 1920/1080 = 1.7778

def pos_to_xml(px, py):
    """Premiere normalised position -> xmeml centre offsets.
    MEASURED: premiere_x = 0.5 + xml_horiz * (H/W).  The xmeml horizontal centre is in
    FRAME-HEIGHT units, not width — passing (px-0.5) straight through lands the crop in
    the wrong place (that is what put Alex off the edge of the card)."""
    return ((px - 0.5) / AR, (py - 0.5))


def motion(scale, x=0.0, y=0.0):
    """Basic Motion — scale % and centre offset (xmeml units, see pos_to_xml)."""
    return (
      '<filter><effect><name>Basic Motion</name><effectid>basic</effectid>'
      '<effectcategory>motion</effectcategory><effecttype>motion</effecttype>'
      '<mediatype>video</mediatype>'
      '<parameter authoringApp="PremierePro"><parameterid>scale</parameterid>'
      f'<name>Scale</name><valuemin>0</valuemin><valuemax>1000</valuemax><value>{scale:.3f}</value></parameter>'
      '<parameter authoringApp="PremierePro"><parameterid>center</parameterid>'
      f'<name>Center</name><value><horiz>{x:.5f}</horiz><vert>{y:.5f}</vert></value></parameter>'
      '</effect></filter>')

def crop_filter(top, bottom):
    return (
      '<filter><effect><name>Crop</name><effectid>AE.ADBE Crop</effectid>'
      '<effectcategory>Transform</effectcategory><effecttype>filter</effecttype>'
      '<mediatype>video</mediatype>'
      '<parameter authoringApp="PremierePro"><parameterid>Top</parameterid><name>Top</name>'
      f'<valuemin>0</valuemin><valuemax>100</valuemax><value>{top:.3f}</value></parameter>'
      '<parameter authoringApp="PremierePro"><parameterid>Bottom</parameterid><name>Bottom</name>'
      f'<valuemin>0</valuemin><valuemax>100</valuemax><value>{bottom:.3f}</value></parameter>'
      '</effect></filter>')

# Reverse-engineered from "Text Down Small (Alex Shorts Default Text Animation).prfpset":
#   Position 0.49609375 -> 0.5 over 12 frames = the caption EASES DOWN 7.5px of 1920 and settles.
# Our states are much shorter than the preset's 0.5s (82% are under it), so the move is scaled to
# the state and kept subtle. Only the FIRST state of a phrase animates — animating every
# accumulating word would jitter.
# MEASURED across all three reference reels (58 caption entrances, probed at native 30fps):
#   fade-in 39-56% (fast, 1-3 frames) · slide 63% · of slides 71% are HORIZONTAL
#   direction mix: RIGHT 28% · LEFT 17% · DOWN 13% · UP 6% · no move 37%
#   travel: median 36px = 3.7% of the 980 card (p75 78px)
# The editor does not want the "settle down" look — it is also the RAREST in the reference (6%).
ANIM = {                      # unit direction the caption travels FROM, in frame-height fractions
    "right": (-1.0, 0.0),     # enters from the left, moves right   (most common)
    "left":  ( 1.0, 0.0),     # enters from the right, moves left
    "down":  (0.0, -1.0),
    "up":    (0.0,  1.0),
    "none":  (0.0, 0.0),
}
TRAVEL = 36.0 / 1920.0        # 36px of 1920 = the measured median

def motion_anim(kind, dur_f, mag=1.0, anim_f=5):
    """Keyframed centre: start offset -> settle. xmeml centre is in FRAME-HEIGHT units."""
    ux, uy = ANIM.get(kind, ANIM["none"])
    dx = ux * TRAVEL * mag; dy = uy * TRAVEL * mag
    if dx == 0 and dy == 0:
        return ""
    n = max(1, min(anim_f, dur_f - 1))
    return (
      '<filter><effect><name>Basic Motion</name><effectid>basic</effectid>'
      '<effectcategory>motion</effectcategory><effecttype>motion</effecttype>'
      '<mediatype>video</mediatype>'
      '<parameter authoringApp="PremierePro"><parameterid>center</parameterid><name>Center</name>'
      f'<keyframe><when>0</when><value><horiz>{dx:.8f}</horiz><vert>{dy:.8f}</vert></value></keyframe>'
      f'<keyframe><when>{n}</when><value><horiz>0.00000000</horiz><vert>0.00000000</vert></value></keyframe>'
      '</parameter></effect></filter>')


def opacity_in(dur_f, in_f=2):
    """Fast fade-in — measured 1-3 frames in the reference."""
    n = max(1, min(in_f, dur_f - 1))
    return ('<filter><effect><name>Opacity</name><effectid>opacity</effectid>'
            '<effectcategory>motion</effectcategory><effecttype>motion</effecttype>'
            '<mediatype>video</mediatype>'
            '<parameter authoringApp="PremierePro"><parameterid>opacity</parameterid>'
            '<name>opacity</name><valuemin>0</valuemin><valuemax>100</valuemax>'
            '<keyframe><when>0</when><value>0</value></keyframe>'
            f'<keyframe><when>{n}</when><value>100</value></keyframe>'
            '</parameter></effect></filter>')


def opacity_fade(dur_f, fade_f):
    """Native keyframed Opacity — the reference fades a completed phrase out before it clears."""
    a = max(dur_f - fade_f, 0)
    return ('<filter><effect><name>Opacity</name><effectid>opacity</effectid>'
            '<effectcategory>motion</effectcategory><effecttype>motion</effecttype>'
            '<mediatype>video</mediatype>'
            '<parameter authoringApp="PremierePro"><parameterid>opacity</parameterid>'
            '<name>opacity</name><valuemin>0</valuemin><valuemax>100</valuemax>'
            f'<keyframe><when>{a}</when><value>100</value></keyframe>'
            f'<keyframe><when>{dur_f}</when><value>0</value></keyframe>'
            '</parameter></effect></filter>')


def clipitem(cid, name, fdef, start, end, inp, outp, filters="", enabled=True):
    return (f'<clipitem id="{cid}"><name>{name}</name>'
            f'<enabled>{"TRUE" if enabled else "FALSE"}</enabled>'
            f'<duration>{outp-inp}</duration>'
            f'<rate><timebase>{TB}</timebase><ntsc>{NTSC}</ntsc></rate>'
            f'<start>{start}</start><end>{end}</end><in>{inp}</in><out>{outp}</out>'
            f'{fdef}{filters}</clipitem>')


def build():
    off = json.load(open(f"{A}/media_offsets.json"))
    FR = {round(x["t0"],2): x for x in json.load(open(f"{D}/cut/aroll_framing.json"))}
    AROLL = f"{A}/AROLL_window.mp4"          # UNGRADED — the editor does the colour grade
    aroll_dur_f = f(48.006)
    TOTAL = f(P.DUR + P.TAIL)

    NCAP = 5                                   # max words in a chunk -> one track per slot
    v1, v2, v3, a1 = [], [], [], []             # V1 picture · V2 split-bottom · V3 matte
    vcap = [[] for _ in range(NCAP)]            # V4..V8 — one caption WORD per item
    n = [0]
    def nid():
        n[0] += 1; return f"ci{n[0]}"

    # ---- V1 picture ------------------------------------------------------
    aroll_items = off["items"]
    ai = 0
    for s in P.SHOTS:
        st, en = f(s["t0"]), f(s["t1"])
        k = s["k"]
        if k == "a":
            it = aroll_items[ai] if ai < len(aroll_items) else aroll_items[-1]
            # which A-roll cut item covers this shot
            for cand in aroll_items:
                if cand["tl"] - 0.02 <= s["t0"] < cand["tl"] + (cand["out"] - cand["in"]) + 0.02:
                    it = cand; break
            src_in = f(it["in"] + (s["t0"] - it["tl"]))
            src_out = src_in + (en - st)
            fr = FR[round(s["t0"], 2)]                 # YuNet face-tracked, per shot
            sc = fr["scale"]
            # xmeml centre is offset-from-centre in frame widths; convert from normalised pos
            v1.append(clipitem(nid(), "AROLL", filedef(AROLL, aroll_dur_f, True),
                               st, en, src_in, src_out,
                               motion(sc, *pos_to_xml(fr["px"], fr["py"]))))
        elif k == "b":
            src = f"{LIB}/{s['src']}.mp4"
            cw, ch, cx, cy = P.CROP[s["src"]]
            # source native height (pre-crop) — needed for both the crop % and the fill scale
            nat_h = {"wolf_party": 534, "social_network_coding": 800}.get(s["src"], 1080)
            top = bot = (cy / nat_h * 100) if cy else 0.0
            vis_h = ch
            sc = CARD / vis_h * 100
            filt = motion(sc) + (crop_filter(top, bot) if cy else "")
            si = f(s["ss"]); so = si + (en - st)
            v1.append(clipitem(nid(), s["src"], filedef(src, f(600), False, cw, nat_h),
                               st, en, si, so, filt))
        elif k == "split":
            for which, (nm, ss, ypos) in enumerate(
                    [(s["top"], s["tss"], (258 + 696/2)/H - 0.5),
                     (s["bot"], s["bss"], (258 + 696 + 29 + 696/2)/H - 0.5)]):
                src = f"{LIB}/{nm}.mp4"
                cw, ch, cx, cy = P.CROP[nm]
                nat_h = {"wolf_party": 534, "social_network_coding": 800}.get(nm, 1080)
                top = bot = (cy / nat_h * 100) if cy else 0.0
                sc = 696 / ch * 100
                filt = motion(sc, 0.0, ypos) + (crop_filter(top, bot) if cy else "")
                si = f(ss); so = si + (en - st)
                lst = v1 if which == 0 else v2
                lst.append(clipitem(nid(), nm + "_split", filedef(src, f(600), False, cw, nat_h),
                                    st, en, si, so, filt))
        else:  # card / dot
            png = {"dot": "CARD_white_dot.png"}.get(k,
                   "CARD_white.png" if s.get("fill") == "white" else "CARD_black.png")
            p = f"{A}/{png}"
            v1.append(clipitem(nid(), png, filedef(p, TOTAL, False, W, H),
                               st, en, 0, en - st))

    # ---- A1 continuous voice: the 3 cut spans, contiguous (audio never follows picture) ----
    for it in aroll_items:
        st_ = f(it["tl"]); en_ = st_ + (f(it["out"]) - f(it["in"]))
        a1.append(clipitem(nid(), "VOICE", filedef(AROLL, aroll_dur_f, True),
                           st_, en_, f(it["in"]), f(it["out"])))

    # ---- V3 the rounded-card matte (above picture; swaps to the split matte) ----
    frame_end = f(P.DUR)
    sp = [x for x in P.SHOTS if x["k"] == "split"]
    segs = []
    if sp:
        a_, b_ = f(sp[0]["t0"]), f(sp[0]["t1"])
        segs = [("FRAME_card980.png", 0, a_), ("FRAME_split.png", a_, b_),
                ("FRAME_card980.png", b_, frame_end)]
    else:
        segs = [("FRAME_card980.png", 0, frame_end)]
    for png, a_, b_ in segs:
        if b_ <= a_: continue
        v3.append(clipitem(nid(), png, filedef(f"{A}/{png}", TOTAL, False, W, H),
                           a_, b_, 0, b_ - a_))

    # ---- V3 captions ------------------------------------------------------
    man = json.load(open(f"{A}/captions_v2/manifest.json"))
    FADE_F = 4                      # ~0.17s at 23.976
    for c in man:
        st, en = f(c["t0"]), f(min(c["t1"], P.DUR))
        if en <= st: continue
        p = f"{A}/captions_v2/{c['file']}"
        dur = en - st
        filt = ""
        if c.get("anim"):
            filt += motion_anim(c["anim"], dur, mag=c.get("anim_mag", 1.0))
        if c.get("fade_in"):
            filt += opacity_in(dur, c["fade_in"])
        elif c.get("fade"):
            filt += opacity_fade(dur, min(FADE_F, max(dur - 1, 1)))
        slot = c.get("slot", 0) % NCAP
        vcap[slot].append(clipitem(nid(), c.get("word", c["file"]),
                                   filedef(p, TOTAL, False, W, H), st, en, 0, dur, filt))

    MUS = f"{A}/MUSIC_bed.wav"   # prenormalised, -vn (cover art stripped), fades baked
    a2 = [clipitem(nid(), "MUSIC", filedef(MUS, TOTAL, True, audio_only=True), 0, TOTAL, 0, TOTAL)]

    def track(items, kind="video"):
        return (f"<track>{''.join(items)}<enabled>TRUE</enabled><locked>FALSE</locked></track>")

    CAPTRACKS = "\n".join(track(t) for t in vcap)
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE xmeml>
<xmeml version="4">
<sequence id="{SEQ}">
<name>{SEQ}</name>
<duration>{TOTAL}</duration>
<rate><timebase>{TB}</timebase><ntsc>{NTSC}</ntsc></rate>
<media>
<video>
<format><samplecharacteristics>
<rate><timebase>{TB}</timebase><ntsc>{NTSC}</ntsc></rate>
<width>{W}</width><height>{H}</height>
<pixelaspectratio>square</pixelaspectratio>
</samplecharacteristics></format>
{track(v1)}
{track(v2)}
{track(v3)}
{CAPTRACKS}
</video>
<audio>
<format><samplecharacteristics><depth>16</depth><samplerate>48000</samplerate></samplecharacteristics></format>
{track(a1)}
{track(a2)}
</audio>
</media>
</sequence>
</xmeml>"""
    out = f"{D}/premiere/{SEQ}.xml"
    open(out, "w").write(xml)
    print(f"V1 picture {len(v1)} · V2 split {len(v2)} · V3 matte {len(v3)} · caption tracks "
          f"{[len(t) for t in vcap]} = {sum(len(t) for t in vcap)} word items · A1 {len(a1)}")
    print(out)
    return out


if __name__ == "__main__":
    build()
