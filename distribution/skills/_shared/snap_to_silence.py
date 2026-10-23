#!/usr/bin/env python3
"""Snap cut boundaries to inter-word SILENCE (CLIP_CUTTING_PLAYBOOK law:
never cut at an ASR label — land every cut on the quietest moment).

For each removal boundary, finds the quietest frame-width (~33ms) RMS window
within +/-0.07s and moves the boundary there. Removals that collapse below
0.06s after snapping revert to their original values.

Usage:
  snap_to_silence.py <removals.json> <source_media> <out.json>
removals.json: {"removals":[{"a":<sec>,"b":<sec>,...},...]}  (source seconds)
out json:      same, with a_snapped/b_snapped added per removal.

Locked 2026-07-07 (DeskQA polish pass, 63 cuts, zero clipped words).
"""
import json, subprocess, sys
import numpy as np

SR = 16000
WIN = int(SR * 0.0334)   # one 29.97fps frame of audio
SEARCH = 0.07

def envelope_snap(src, t):
    t0 = max(0, t - 0.25)
    r = subprocess.run(["ffmpeg","-v","error","-ss",str(t0),"-t","0.5","-i",src,
                        "-vn","-ac","1","-ar",str(SR),"-f","s16le","-"], capture_output=True)
    pcm = np.frombuffer(r.stdout, dtype=np.int16).astype(np.float32) / 32768.0
    if len(pcm) < WIN * 3:
        return t
    hop = int(SR * 0.005)
    n = (len(pcm) - WIN) // hop
    rms = np.array([np.sqrt(np.mean(pcm[i*hop:i*hop+WIN]**2)) for i in range(n)])
    times = t0 + (np.arange(n) * hop + WIN / 2) / SR
    mask = np.abs(times - t) <= SEARCH
    if not mask.any():
        return t
    k = np.argmin(np.where(mask, rms, np.inf))
    return float(times[k])

def main():
    inp, src, outp = sys.argv[1], sys.argv[2], sys.argv[3]
    d = json.load(open(inp))
    for r in d["removals"]:
        a2, b2 = envelope_snap(src, r["a"]), envelope_snap(src, r["b"])
        if b2 - a2 >= 0.06:
            r["a_snapped"], r["b_snapped"] = round(a2, 4), round(b2, 4)
        else:
            r["a_snapped"], r["b_snapped"] = r["a"], r["b"]
    json.dump(d, open(outp, "w"), indent=1)
    print(f"{len(d['removals'])} boundaries snapped -> {outp}")

if __name__ == "__main__":
    main()
