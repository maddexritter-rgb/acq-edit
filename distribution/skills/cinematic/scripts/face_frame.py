#!/usr/bin/env python3
"""face_frame.py — per-shot face-tracked framing for the 980 card.

  python3 face_frame.py <aroll.mp4> <plan.py> <media_offsets.json> <out.json> [face_x] [face_frac]

Emits, per A-roll shot: {t0, t1, scale, px, py} where scale is Premiere Motion Scale (%) and
px/py are Premiere's normalised Position. Feed straight into build_xml.py.

🛑 RULE 5 (SKILL.md): PICK THE FACE BY CONFIDENCE, NEVER BY AREA. Selecting the largest box locked
onto a wall fixture (score 0.60) instead of the real face (score 0.93) and put the subject off the
edge of the card on the most important shot in the clip.

Composition, measured off the reference: the face fills ONE side of the card with the caption in
the OPPOSITE negative space, head in the TOP HALF. At fill-scale a 16:9 source usually already
puts the head in the top third, so no vertical shift is needed — and any vertical shift at
fill-scale opens a gap at the card edge (the asserts below catch that).
"""
import cv2, json, os, subprocess, sys

def _f(v):
    """numpy float32 is NOT json-serializable -- coerce every emitted number."""
    import numpy as _np
    return float(v) if isinstance(v, (_np.floating, _np.integer)) else v
import numpy as np
from pathlib import Path

MODEL = str(Path(__file__).resolve().parents[2] / "horizontal-to-vertical/scripts/yunet.onnx")
CARD_X, CARD_Y, CARD = 50, 470, 980
W, H = 1080, 1920
SRC_W, SRC_H = 1920, 1080
MIN_SCORE = 0.80
SAMPLES = 5


def load_plan(path):
    import importlib.util
    s = importlib.util.spec_from_file_location("plan", path)
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
    return m


def main():
    aroll, planp, offp, outp = sys.argv[1:5]
    face_x = float(sys.argv[5]) if len(sys.argv) > 5 else 0.62      # face centre, fraction of card
    face_frac = float(sys.argv[6]) if len(sys.argv) > 6 else 0.42   # face height, fraction of card
    face_y    = float(sys.argv[7]) if len(sys.argv) > 7 else 0.34   # face CENTRE, fraction down the card
    P = load_plan(planp)
    off = json.load(open(offp))["items"]

    def win_time(t):
        for it in off:
            if it["tl"] - 0.02 <= t < it["tl"] + (it["out"] - it["in"]) + 0.02:
                return it["in"] + (t - it["tl"])
        return off[-1]["in"]

    det = cv2.FaceDetectorYN.create(MODEL, "", (SRC_W, SRC_H), 0.5, 0.3, 5000)
    target_face = face_frac * CARD
    XT = CARD_X + face_x * CARD
    out = []
    for s in [x for x in P.SHOTS if x["k"] == "a"]:
        hits = []
        for t in np.linspace(s["t0"] + 0.05, s["t1"] - 0.05, SAMPLES):
            subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{win_time(float(t)):.3f}",
                            "-i", aroll, "-frames:v", "1", "-y", "/tmp/_ff.png"], check=True)
            img = cv2.imread("/tmp/_ff.png")
            det.setInputSize((img.shape[1], img.shape[0]))
            _, faces = det.detect(img)
            if faces is None or not len(faces):
                continue
            f = max(faces, key=lambda z: z[-1])          # CONFIDENCE, not area
            if f[-1] < MIN_SCORE:
                continue
            hits.append((f[0] + f[2] / 2, f[1] + f[3] / 2, f[2], f[3]))
        if not hits:
            print(f"  !! no confident face {s['t0']:.2f}-{s['t1']:.2f} — set this shot by hand")
            continue
        cx, cy, fw, fh = np.array(hits).mean(0)
        S = min(max(target_face / fh, CARD / SRC_H), 1.85)
        Px = (XT - (cx - SRC_W / 2) * S) / W
        # 🛑 Py WAS HARDCODED 0.5. Harmless at fill scale (a 16:9 source scaled to cover a 980 card
        # has NO vertical freedom), but the moment the shot punches in — Alex leaning back makes
        # the face small, so S climbs to ~1.44 — centring vertically shoves his head off the TOP
        # of the card. That is the "cropped funny" the editor caught. Place the face deliberately:
        # head in the TOP HALF, same as the horizontal rule, then clamp so the card stays covered.
        sw, sh = SRC_W * S, SRC_H * S
        YT = CARD_Y + face_y * CARD
        Py = (YT - (cy - SRC_H / 2) * S) / H
        lo = (CARD_Y + CARD - sh / 2) / H      # bottom edge must still reach the card bottom
        hi = (CARD_Y + sh / 2) / H             # top edge must still reach the card top
        Py = min(max(Py, lo), hi) if lo <= hi else 0.5
        # 🛑 0.5px TOLERANCE, AND A DIAGNOSTIC INSTEAD OF A BARE AssertionError.
        # A shot whose face is LARGE enough that target/fh falls below the fill floor gets S clamped
        # to exactly CARD/SRC_H, which makes the vertical clamp window [lo,hi] degenerate to a single
        # point — and then floating-point error on the re-check trips a "vertical gap" assert on a
        # framing that is correct to within a billionth of a pixel. Half a pixel of slack is not a
        # defect; a bare assert with no numbers cost real debugging time.
        EPS = 0.5
        gapx = not (Px * W - sw / 2 <= CARD_X + EPS and Px * W + sw / 2 >= CARD_X + CARD - EPS)
        gapy = not (Py * H - sh / 2 <= CARD_Y + EPS and Py * H + sh / 2 >= CARD_Y + CARD - EPS)
        if gapx or gapy:
            raise SystemExit(
                f"  🛑 the card is not covered on shot {s['t0']:.2f}-{s['t1']:.2f} "
                f"({'horizontal' if gapx else 'vertical'}):\n"
                f"     face cx {cx/SRC_W:.3f} cy {cy/SRC_H:.3f} height {fh:.0f}px · scale {S*100:.2f}% "
                f"(fill floor {100*CARD/SRC_H:.2f}%) · Px {Px:.4f} Py {Py:.4f}\n"
                f"     scaled source {sw:.0f}x{sh:.0f} vs card {CARD} at ({CARD_X},{CARD_Y})\n"
                f"     face_x {face_x} is unreachable at this scale: legal max is "
                f"{min(1.0,(cx*S)/CARD):.3f}. Lower face_x, or raise face_frac to zoom in further.")
        out.append(dict(t0=s["t0"], t1=s["t1"], scale=round(S * 100, 3), px=round(Px, 6), py=round(Py, 6),
                        _cx=round(cx / SRC_W, 4), _fh=round(float(fh), 1)))
        print(f"  {s['t0']:6.2f}-{s['t1']:6.2f}  cx {cx/SRC_W:.3f}  scale {S*100:6.2f}%  pos ({Px:.4f}, {Py})"
              f"  n={len(hits)}/{SAMPLES}")
    # 🛑 TWO-SPEAKER GUARD — FAIL LOUDLY WHEN THE TRACKER SWITCHES PERSON.
    # Confidence-picking fixed choosing a wall fixture over a face, but it cannot tell TWO REAL
    # faces apart. On a wide two-shot the host is often more front-facing than the subject (who is
    # in profile), so the host wins on confidence and that shot gets framed on the WRONG PERSON —
    # silently, with a plausible-looking scale. Caught on a real clip: 3 shots at cx 0.31-0.43 and
    # one at cx 0.697 with HALF the face height, scale clamped to 185%.
    # The subject is the person present in EVERY shot, so the median cx is the subject's side.
    if len(out) >= 3:
        med = sorted(r["_cx"] for r in out)[len(out) // 2]
        medfh = sorted(r["_fh"] for r in out)[len(out) // 2]
        bad = [r for r in out if abs(r["_cx"] - med) > 0.18 or r["_fh"] < 0.55 * medfh]
        if bad:
            print(f"\n  🛑 TRACKER SWITCHED PERSON (or the shot is a wide two-shot). "
                  f"median cx {med:.3f}, median face height {medfh:.0f}px:")
            for r in bad:
                print(f"      {r['t0']:6.2f}-{r['t1']:6.2f}  cx {r['_cx']:.3f}  face {r['_fh']:.0f}px  "
                      f"scale {r['scale']:.1f}%")
            raise SystemExit("  Fix the PLAN: a wide two-shot is a bad card image anyway — make that\n"
                             "  span b-roll, or split the shot so the subject is alone in frame.")
    json.dump([{k: _f(v) for k, v in r.items()} for r in out], open(outp, "w"), indent=1)
    print(f"\n{len(out)} shots -> {outp}")
    print("  per-shot table (a shot disagreeing with its neighbours by >15% is a tracker failure):")
    for r in out:
        print(f"      {r['t0']:6.2f}-{r['t1']:6.2f}  scale {r['scale']:7.2f}%  px {r['px']:.4f}  "
              f"py {r['py']:.4f}  cx {r['_cx']:.3f}  face {r['_fh']:.0f}px")


if __name__ == "__main__":
    main()
