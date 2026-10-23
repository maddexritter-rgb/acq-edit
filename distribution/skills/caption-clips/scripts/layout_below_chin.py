#!/usr/bin/env python3
"""layout_below_chin.py — per-shot caption-Y that sits BELOW the chin/beard, using the
CANONICAL layout_analyze for cut-accurate shot boundaries (so Y snaps only at real camera
cuts — no mid-cue pop, no per-shot bounce).

Pipeline:
  1. Run caption-app/worker/layout_analyze.py → per-frame faces + hard-cut frames.
  2. Segment the timeline at the hard cuts (frame-accurate).
  3. Per segment, set Y just below the BEARD (face_box_bottom + BEARD*face_height), median
     over the segment — scales per angle (tight CU = lower; wide = higher).
  4. ANTI-JUMP (per Maddex's note): hold the previous Y when a segment's Y is within ~30px
     of it (smallest move that clears the face; no few-pixel bounce at every cut).

Output: generate_spice --layout schema {"meta":{"fps":F},"segments":[{start_i,end_i,safe_y_pct}]}.
Usage: layout_below_chin.py IN.mp4 OUT.json [--beard 0.45] [--margin 0.03]
       [--region-plan camera_layout.json]

An optional region plan is the authoritative handoff from the camera stage. Its
segments use frame-inclusive ``start_i``/``end_i`` and ``layout`` values such as
``split`` or ``full``. Split regions use the approved 50% seam anchor; full-frame
regions retain the face-clearance calculation. This prevents the largest-face
analyzer from mistaking the lower participant in a split for a full-screen face.
"""
import subprocess, sys, json, re, argparse, statistics, os

from layout_region_plan import bounds_with_regions, is_split, layout_for_region, load_regions

LAYOUT_ANALYZE = os.path.expanduser("__ACQ_ASSETS__/caption-app/worker/layout_analyze.py")

ap = argparse.ArgumentParser()
ap.add_argument("inp"); ap.add_argument("out")
ap.add_argument("--beard", type=float, default=0.45)   # fraction of face height below the jaw to clear (beard)
ap.add_argument("--margin", type=float, default=0.03)
ap.add_argument("--lo", type=float, default=0.56)      # clamp (never above ~chest)
ap.add_argument("--hi", type=float, default=0.84)      # clamp (never off the bottom)
ap.add_argument("--hold-px", type=float, default=30.0) # sub-this Y diff between shots → hold previous
ap.add_argument("--region-plan", default=None,
                help="Optional camera-stage frame-region JSON; split regions force the 50%% seam anchor")
a = ap.parse_args()

# 1. run canonical layout_analyze (cut-accurate frames + per-frame faces)
tmp = a.out + ".la.json"
p = subprocess.run(["python3", LAYOUT_ANALYZE, a.inp, tmp, "--sample-every", "2"],
                   capture_output=True, text=True)
if p.returncode != 0:
    sys.stderr.write(p.stderr[-800:]); sys.exit(1)
la = json.loads(open(tmp).read())
H = la["meta"]["h"]; FPS = la["meta"]["fps"]; N = la["meta"]["n_frames"]
frames = {f["i"]: f for f in la["frames"]}

# hard-cut frames: parse from layout_analyze's stdout ("hard cuts at frames [a, b, c]")
m = re.search(r"hard cuts at frames \[([0-9,\s]*)\]", p.stdout + p.stderr)
cuts = [int(x) for x in m.group(1).split(",") if x.strip()] if m else []

try:
    planned_regions = load_regions(a.region_plan, N)
except ValueError as exc:
    raise SystemExit(str(exc)) from exc
bounds = bounds_with_regions(cuts, planned_regions, N)

def seg_y(lo_i, hi_i):
    ys = []
    for i in range(lo_i, hi_i):
        f = frames.get(i) or frames.get(i - (i % 2))   # sample-every 2 → use nearest sampled frame
        if not f or not f.get("faces"):
            continue
        big = max(f["faces"], key=lambda r: r["w"] * r["h"])
        ys.append((big["y"] + big["h"] + a.beard * big["h"]) / H + a.margin)
    if not ys:
        return None
    return min(a.hi, max(a.lo, statistics.median(ys)))

segs = []
prev_y = None
for k in range(len(bounds) - 1):
    lo_i, hi_i = bounds[k], bounds[k + 1]
    layout = layout_for_region(planned_regions, lo_i, hi_i)
    y = 0.50 if is_split(layout) else seg_y(lo_i, hi_i)
    if y is None:
        y = prev_y if prev_y is not None else 0.62
    # ANTI-JUMP: hold previous Y if the move is < hold-px
    if not is_split(layout) and prev_y is not None and abs(y - prev_y) * H < a.hold_px:
        y = prev_y
    segment = {"start_i": int(lo_i), "end_i": int(hi_i - 1),
               "safe_y_pct": round(float(y), 3)}
    if layout:
        segment["layout"] = layout
        segment["layout_source"] = "camera_region_plan"
    segs.append(segment)
    prev_y = y

json.dump({"meta": {"fps": FPS,
                    "region_plan": os.path.abspath(a.region_plan) if a.region_plan else None},
           "segments": segs}, open(a.out, "w"))
os.remove(tmp)
print(f"layout_below_chin: {len(segs)} shots (cuts at {cuts}), "
      f"Y {min(s['safe_y_pct'] for s in segs):.2f}-{max(s['safe_y_pct'] for s in segs):.2f}, "
      f"explicit regions={len(planned_regions)}")
