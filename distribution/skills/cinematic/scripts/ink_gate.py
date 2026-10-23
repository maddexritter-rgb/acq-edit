#!/usr/bin/env python3
"""ink_gate.py — BLOCKING post-render check that every caption word is actually LEGIBLE
in the delivered pixels, at the contrast the manifest declared.

  python3 ink_gate.py <clip_dir> [--video build/V2_preview.mp4]

🛑 WHY THIS EXISTS. `gen_captions.py`'s three gates (card-bounds, luma-straddle, fill mix) all
read the manifest's DECLARED fill. None of them look at the rendered frame. So when the OVERLAY
BLEND recoloured the beat words on a bright plate — overlay for bd->1 returns 1 regardless of
source — a whole 1.08s "FUTURE IS A STRANGER" white card rendered as a faint white-on-white
outline while every gate printed PASS. The declared truth and the observed truth disagreed and
nothing was watching.

The rule this encodes: **a gate that checks what we asked for is not a gate on what we shipped.**
Measure the ink in the delivered frame, under the word's own alpha mask, never over a bbox
(a bbox mean averages in the plate and hides a white-on-white collision).

PASS condition, per caption word, measured under its glyph pixels in the delivered video:
  fill=black -> ink must be DARK   (mean luma <= 110) and at least 60 luma BELOW its plate
  fill=white -> ink must be LIGHT  (mean luma >= 150) and at least 40 luma ABOVE its plate
The asymmetry is deliberate: white ink legitimately sits on mid-bright footage and the matte
knocks it back where the subject crosses it, so it gets the looser floor. Black ink is only ever
used on a near-255 plate, so it has no excuse to be bright.
"""
import argparse, glob, json, os, subprocess, sys
import numpy as np
from PIL import Image

CARD, CARD_X, CARD_Y = 980, 50, 470
# a word thinner than this in the delivered frame is a sliver (matted almost entirely away by the
# subject) and cannot be judged fairly — report it, do not fail on it
MIN_PIX = 400


def frame(video, t, out):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", video,
                    "-frames:v", "1", out], check=True)
    return np.asarray(Image.open(out).convert("L"), dtype=np.float32)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("clip_dir")
    ap.add_argument("--video", default=None)
    ap.add_argument("--sample-frac", type=float, default=0.65,
                    help="where inside each item to sample (0.65 = after any entrance animation)")
    a = ap.parse_args()
    D = os.path.abspath(a.clip_dir)
    cap = f"{D}/premiere/assets/captions_v2"
    man = json.load(open(f"{cap}/manifest.json"))
    items = man["items"] if isinstance(man, dict) else man

    vid = a.video
    if vid and not os.path.isabs(vid):
        vid = os.path.join(D, vid)
    if not vid:
        vs = sorted(glob.glob(f"{D}/build/V*_preview.mp4"),
                    key=lambda p: int(os.path.basename(p).split("_")[0][1:]))
        if not vs:
            sys.exit("no build/V*_preview.mp4 — render first")
        vid = vs[-1]
    print(f"  video: {os.path.relpath(vid, D)}   {len(items)} caption words")

    fails, slivers = [], []
    for it in items:
        t = it["t0"] + (it["t1"] - it["t0"]) * a.sample_frac
        img = frame(vid, t, "/tmp/_ink.png")
        alpha = np.asarray(Image.open(f"{cap}/{it['file']}").split()[3], dtype=np.float32)
        core = alpha > 200                      # glyph BODY only — skip antialiased edges
        n = int(core.sum())
        if n < MIN_PIX:
            slivers.append((it["word"], n)); continue
        ink = float(img[core].mean())
        ring = (alpha > 4) & (alpha < 60)       # the plate immediately around the glyph
        plate = float(img[ring].mean()) if ring.sum() > 200 else float("nan")
        black = it.get("fill") == "black"
        ok = (ink <= 110 and (np.isnan(plate) or plate - ink >= 60)) if black else \
             (ink >= 150 and (np.isnan(plate) or ink - plate >= 40))
        if not ok:
            fails.append((it["word"], it["fill"], round(t, 2), round(ink, 1), round(plate, 1), n))

    if slivers:
        print(f"  ~ {len(slivers)} word(s) too matted to judge (<{MIN_PIX}px of glyph body): "
              f"{[w for w, _ in slivers[:6]]}")
    if fails:
        print(f"  ✗ {len(fails)} caption word(s) NOT legible in the delivered pixels:")
        for w, fl, t, ink, pl, n in fails:
            print(f"      {t:6.2f}s  {w!r:16s} declared {fl:5s}  ink luma {ink:5.1f}  plate {pl:5.1f}")
        print("\n  The declared fill and the rendered pixels disagree — suspect the compositor,\n"
              "  not the caption generator (overlay blend, matte strength, or a blend on black ink).")
        sys.exit(1)
    print(f"  ✓ every judgeable caption word is legible in the delivered frame")


if __name__ == "__main__":
    main()
