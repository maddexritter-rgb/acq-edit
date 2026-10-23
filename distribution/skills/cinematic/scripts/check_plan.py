#!/usr/bin/env python3
"""check_plan.py — validate the shot plan BEFORE spending four minutes on a render.

  python3 check_plan.py <project/10_WORK>

Every check here exists because the failure it catches actually shipped:
  1. a shot cut that is NOT on a caption cue boundary   -> cue straddles a plate flip, no ink
     colour is right for both halves ("into" half on Alex, half on the white void)
  2. gaps / overlaps between shots, or coverage != DUR
  3. b-roll declared at the wrong crop                  -> letterboxed inside the rounded card
  4. cut rate / shot length outside the shipped band
  5. punctuation in any cue                             -> editor ruling: never
"""
import importlib.util, json, os, subprocess, sys, re
import statistics as st

W = sys.argv[1] if len(sys.argv) > 1 else "."
sys.path.insert(0, W)


def load(name, path):
    s = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


P = load("plan_v2", f"{W}/plan_v2.py")
GG = load("gg", f"{W}/generated_groups.py")
WORDS = json.load(open(f"{W}/cut/timeline_words.json"))
fail = 0

# 1 — cuts on cue boundaries
bounds = {round(WORDS[g["i0"]]["t0"], 2) for g in GG.GROUPS} | {round(WORDS[-1]["t1"], 2)}
off = [s["t0"] for s in P.SHOTS if s["t0"] > 0 and round(s["t0"], 2) not in bounds]
if off:
    fail += 1
    sb = sorted(bounds)
    print(f"  ✗ {len(off)} cut(s) NOT on a cue boundary — move the CUT, never the colour:")
    for x in off:
        print(f"      {x}  nearest: {[y for y in sb if abs(y - x) < 1.2]}")
else:
    print("  ✓ every cut lands on a caption cue boundary")

# 2 — continuity
gaps = [(P.SHOTS[i]["t1"], P.SHOTS[i+1]["t0"]) for i in range(len(P.SHOTS) - 1)
        if abs(P.SHOTS[i]["t1"] - P.SHOTS[i+1]["t0"]) > 1e-6]
end = P.SHOTS[-1]["t1"]
if gaps or abs(end - P.DUR) > 0.02:
    fail += 1; print(f"  ✗ gaps/overlaps {gaps}   coverage ends {end} vs DUR {P.DUR}")
else:
    print(f"  ✓ shots are contiguous and cover 0 -> {P.DUR}")

# 3 — crops measured, not assumed
LIB = getattr(P, "LIB", os.path.expanduser("__ACQ_ASSETS__/assets/broll_lib/pp"))
missing = [n for n in getattr(P, "CROP", {}) if not os.path.exists(f"{LIB}/{n}.mp4")]
bad = []
for name, (cw, ch, cx, cy) in getattr(P, "CROP", {}).items():
    f = f"{LIB}/{name}.mp4"
    if not os.path.exists(f): continue
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                "-of", "csv=p=0", f], capture_output=True, text=True).stdout or 0)
    ss = max(0.5, min(12.0, dur * 0.25))
    r = subprocess.run(["ffmpeg", "-hide_banner", "-ss", f"{ss:.2f}", "-i", f,
                        "-t", f"{max(1.0, min(4.0, dur - ss - 0.2)):.2f}",
                        "-vf", "cropdetect=24:2:0", "-f", "null", "-"],
                       capture_output=True, text=True).stderr
    m = re.findall(r"crop=(\d+):(\d+):(\d+):(\d+)", r)
    if not m:
        bad.append((name, (cw, ch, cx, cy), "cropdetect returned NOTHING — unverified"))
    if m:
        dw, dh, dx, dy = map(int, m[-1])
        if abs(dh - ch) > 8 or abs(dy - cy) > 8:
            bad.append((name, (cw, ch, cx, cy), (dw, dh, dx, dy)))
if missing:
    fail += 1
    print(f"  ✗ CROP declared for files not in {LIB}: {missing} (check would have SKIPPED them)")
if bad:
    fail += 1
    print("  ✗ CROP disagrees with cropdetect (b-roll will sit letterboxed in the card):")
    for n, dec, det in bad: print(f"      {n}: declared {dec}  measured {det}")
else:
    print("  ✓ every declared CROP matches cropdetect")

# 3b — CAPTION-ZONE LEGIBILITY ON B-ROLL (pre-render, blocking)
# 🛑 WHY THIS IS A *PRE*-RENDER GATE. The matte knocks the caption back where the subject is, so a
# bright subject sitting under the caption block ERASES the glyphs — "it's typicall[y] / an
# immigra[nt]" vanished into Michael Jordan's white shirt. A post-render luma check CANNOT see it:
# erased white ink and a bright plate have the SAME luminance, so ink_gate measured 249 and passed.
# The only place to catch it is before the render, on the b-roll itself.
# Measured: the offending clip ran 11-12% of the caption zone above 195 luma; clean clips sit
# under 6%.
CARD = 980
ZONE = (0.45, 0.85, 0.00, 0.55)          # y0,y1,x0,x1 of the card — where the caption block sits
BRIGHT_PCT_MAX = 8.0
try:
    import numpy as _np
    from PIL import Image as _Im
    hot = []
    for sh in [x for x in P.SHOTS if x["k"] == "b"]:
        f = f"{LIB}/{sh['src']}.mp4"
        if not os.path.exists(f): continue
        ss, dur = float(sh.get("ss", 0)), sh["t1"] - sh["t0"]
        worst = 0.0; at = ss
        for k in range(5):
            t = ss + dur * k / 4.0
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", f, "-frames:v", "1",
                            "-vf", f"scale=-2:{CARD},crop={CARD}:{CARD}", "/tmp/_cz.png"], check=True)
            a = _np.asarray(_Im.open("/tmp/_cz.png").convert("L"), dtype=_np.float32)
            z = a[int(ZONE[0]*CARD):int(ZONE[1]*CARD), int(ZONE[2]*CARD):int(ZONE[3]*CARD)]
            v = 100.0 * (z > 195).mean()
            if v > worst: worst, at = v, t
        if worst > BRIGHT_PCT_MAX:
            hot.append((sh["src"], sh["t0"], sh["t1"], worst, at))
    if hot:
        fail += 1
        print(f"  ✗ {len(hot)} b-roll shot(s) will have captions ERASED by the matte "
              f"(caption zone >{BRIGHT_PCT_MAX:.0f}% above 195 luma):")
        for src, t0, t1, v, at in hot:
            print(f"      {t0:6.2f}-{t1:6.2f}  {src:12s} {v:4.1f}% bright at source t={at:.2f}s"
                  f"  -> move ss, or pick a clip whose lower-left is dark")
    else:
        print(f"  ✓ every b-roll shot keeps its caption zone dark enough to read")
except ImportError:
    print("  ~ caption-zone check SKIPPED (numpy/PIL unavailable) — this is NOT a pass")

# 4 — rhythm
durs = [s["t1"] - s["t0"] for s in P.SHOTS]
rate = len(P.SHOTS) / P.DUR * 10
med = st.median(durs)
ok = 5.5 <= rate <= 9.0 and 0.9 <= med <= 2.0
print(f"  {'✓' if ok else '⚠'} {len(P.SHOTS)} shots · {rate:.1f} cuts/10s · median {med:.2f}s "
      f"(shipped: 6.8–7.4 · 1.2–1.5s)")

# 5 — punctuation
punct = [" ".join(t for l in g["lines"] for t, _ in l) for g in GG.GROUPS]
badp = [c for c in punct if re.search(r"[.,?!;:]", c)]
if badp:
    fail += 1; print(f"  ✗ {len(badp)} cue(s) still carry punctuation: {badp[:4]}")
else:
    print(f"  ✓ no punctuation in any of {len(punct)} cues")

print(f"\n  {'READY TO RENDER' if not fail else f'{fail} BLOCKER(S) — fix before rendering'}")
sys.exit(1 if fail else 0)
