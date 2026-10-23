#!/usr/bin/env python3
"""snap_boundaries.py <workdir> — snap every cutlist span in/out to real inter-word silence
on the SOURCE so no seam lands mid-word. Uses ffmpeg silencedetect (noise floor measured
from the clip's own mean volume). Writes cutlist_snapped.json (same schema) + reports moves.

IN  -> first sample of sustained speech at/after the chosen boundary (onset just after a
       silence), nudged 0.04s into the preceding silence.
OUT -> last sample of speech before the following silence (true acoustic end), +0.06s tail.
Only moves within a ±0.35s window of the original boundary; if no silence found, keeps original
but flags it.
"""
import json, os, re, subprocess, sys

def sh(c): return subprocess.run(c, shell=True, capture_output=True, text=True)

def main(workdir):
    workdir = os.path.abspath(workdir)
    cl = json.load(open(f"{workdir}/cutlist_v2.json"))
    if cl.get("empty"): print("empty"); return
    src = cl["source"]
    # mean volume for adaptive floor
    mv = sh(f'ffmpeg -v info -i "{src}" -af volumedetect -vn -f null - 2>&1')
    m = re.search(r"mean_volume:\s*(-?[\d.]+) dB", mv.stdout + mv.stderr)
    mean = float(m.group(1)) if m else -30.0
    floor = round(mean - 6, 1)  # silence = 6 dB below mean speech
    # global silencedetect once (min silence 0.10s)
    sd = sh(f'ffmpeg -v info -i "{src}" -af silencedetect=noise={floor}dB:d=0.10 -vn -f null - 2>&1')
    txt = sd.stdout + sd.stderr
    sil = []  # (start,end) of silences
    cur = None
    for line in txt.splitlines():
        a = re.search(r"silence_start:\s*(-?[\d.]+)", line)
        b = re.search(r"silence_end:\s*(-?[\d.]+)", line)
        if a: cur = float(a.group(1))
        if b and cur is not None: sil.append((cur, float(b.group(1)))); cur = None
    W = 0.35
    def snap_in(t):
        # want a silence->speech transition (silence_end) near t; use nearest silence_end within W
        cands = [e for (s, e) in sil if abs(e - t) <= W]
        if cands:
            e = min(cands, key=lambda x: abs(x - t))
            return round(e - 0.04, 3)  # start just before speech onset
        return None
    def snap_out(t):
        # want a speech->silence transition (silence_start) near t
        cands = [s for (s, e) in sil if abs(s - t) <= W]
        if cands:
            s = min(cands, key=lambda x: abs(x - t))
            return round(s + 0.06, 3)  # end just after speech ends
        return None
    moved = 0; flags = []
    for sp in cl["spans"]:
        ni = snap_in(sp["in"]); no = snap_out(sp["out"])
        if ni is not None and abs(ni - sp["in"]) > 0.005: sp["in"] = ni; moved += 1
        elif ni is None: flags.append(f"in@{sp['n']}")
        if no is not None and abs(no - sp["out"]) > 0.005 and no > sp["in"] + 0.3: sp["out"] = no; moved += 1
        elif no is None: flags.append(f"out@{sp['n']}")
    # ensure strictly increasing
    prev = 0
    for sp in cl["spans"]:
        if sp["in"] < prev: sp["in"] = prev + 0.02
        prev = sp["out"]
    json.dump(cl, open(f"{workdir}/cutlist_snapped.json", "w"), indent=1)
    print(f"{cl['person']}: floor {floor}dB, {len(sil)} silences, moved {moved} boundaries, "
          f"no-silence flags: {len(flags)}")

if __name__ == "__main__":
    main(sys.argv[1])
