#!/usr/bin/env python3
"""make_plan.py <slug> — build plan_v2.py for a cinematic-card clip.

🛑 EVERY SHOT BOUNDARY MUST BE A CAPTION CUE BOUNDARY (check_plan enforces it), so the shot list
is derived FROM the cues rather than from round numbers. Cinematic variant = SLOW cuts: it targets
~3.0s shots (~3 cuts/10s), because long holds are what give the matte room to read.
"""
import importlib.util, json, os, sys

slug = sys.argv[1]; D = f"clips/{slug}"
spec = importlib.util.spec_from_file_location("gg", f"{D}/generated_groups.py")
gg = importlib.util.module_from_spec(spec); spec.loader.exec_module(gg)
W = json.load(open(f"{D}/cut/timeline_words.json"))
DUR = float(sys.argv[2])
BROLL = sys.argv[3].split(",")            # b-roll keys, in order
CROP  = json.loads(sys.argv[4])
BDUR  = json.loads(sys.argv[5])      # {broll_key: clip duration in seconds}
SS    = 0.2                          # skip the first moments of a b-roll clip, not a full second
# 🛑 A B-ROLL SHOT CANNOT BE LONGER THAN ITS CLIP. Most of the library is 1.4-7.0s; a 3.5s shot
# cut from a 1.8s file freezes on the last frame for the remainder. Match each slot to a clip
# that actually covers it, and fall back to A-roll when none does.
TARGET = 3.0

# cue boundaries = the start time of each group
bounds = [0.0] + [W[g["i0"]]["t0"] for g in gg.GROUPS[1:]] + [DUR]
bounds = sorted(set(round(b, 3) for b in bounds if 0 <= b <= DUR))

cuts, last = [0.0], 0.0
for b in bounds[1:-1]:
    if b - last >= TARGET:
        cuts.append(b); last = b
cuts.append(DUR)
if cuts[-1] - cuts[-2] < 1.2 and len(cuts) > 2:   # never leave a stub final shot
    cuts.pop(-2)

shots, bi = [], 0
used, last_b = {}, None
for i in range(len(cuts) - 1):
    t0, t1 = cuts[i], cuts[i + 1]
    need = t1 - t0
    if i % 2 == 1:                                # alternate: A-roll, b-roll, A-roll...
        # A long clip may serve more than one slot at a DIFFERENT offset — the library is mostly
        # short files, and consuming each one once starved the edit of b-roll. Never the same clip
        # twice in a row, and never past the end of the file.
        opts = [b for b in BROLL if b != last_b and BDUR[b] - used.get(b, SS) >= need]
        repeat = False
        if not opts:
            # Forced to reuse a clip. 🛑 Do NOT restart it at the same offset — that puts the
            # IDENTICAL footage on screen twice in one clip, which reads as a mistake. Take the
            # LAST `need` seconds instead, so at least the frames differ.
            opts = [b for b in BROLL if BDUR[b] - SS >= need]
            repeat = True
        if opts:
            pick = max(opts, key=lambda b: BDUR[b] - used.get(b, SS))
            ss = max(SS, BDUR[pick] - need - 0.05) if repeat else used.get(pick, SS)
            used[pick] = ss + need
            last_b = pick
            shots.append(dict(t0=t0, t1=t1, k="b", src=pick, ss=round(ss, 2)))
        else:
            print(f"    (no b-roll covers {need:.2f}s — A-roll instead)")
            shots.append(dict(t0=t0, t1=t1, k="a", ss=t0))
    else:
        shots.append(dict(t0=t0, t1=t1, k="a", ss=t0))

body = ['#!/usr/bin/env python3',
        f'"""plan_v2.py — {slug} (cinematic matted variant). Shot cuts land on caption cue',
        'boundaries; CROP values are cropdetect-MEASURED, never assumed."""',
        'import json, os',
        'D = os.path.dirname(os.path.abspath(__file__))',
        'LIB = os.path.expanduser("__ACQ_ASSETS__/assets/broll_lib/pp5")',
        'B = lambda n: f"{LIB}/{n}.mp4"', '',
        f'DUR, TAIL = {DUR:.3f}, 1.70', '',
        'CROP = ' + json.dumps(CROP, indent=4).replace('[', '(').replace(']', ')'), '',
        'SHOTS = [']
for s in shots:
    if s["k"] == "b":
        body.append(f'  dict(t0={s["t0"]:.3f}, t1={s["t1"]:.3f}, k="b", src="{s["src"]}", ss={s["ss"]}),')
    else:
        body.append(f'  dict(t0={s["t0"]:.3f}, t1={s["t1"]:.3f}, k="a", ss={s["ss"]:.3f}),')
body += [']', '',
         'FLASH = ' + repr([round(s["t0"], 2) for s in shots if s["k"] == "b"][:2]), '',
         'def words():', '    return json.load(open(f"{D}/cut/timeline_words.json"))', '']
open(f"{D}/plan_v2.py", "w").write("\n".join(body) + "\n")
print(f"  {slug:16s} {len(shots)} shots, {len(shots)/DUR*10:.1f} cuts/10s, "
      f"median {sorted(s['t1']-s['t0'] for s in shots)[len(shots)//2]:.2f}s")
