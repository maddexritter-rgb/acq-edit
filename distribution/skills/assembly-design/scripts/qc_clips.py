#!/usr/bin/env python3
"""EAR TEST #2 on the RENDERED clip -- clipped words + ending payoff.
A cut that 'clips' a word ends while the word is still at full energy (HOT, delta ~ 0 or +).
A clean cut tapers into silence (delta very negative). The clip should END on a tapering payoff,
not a hot-cut word.
  --clip        rendered mp4
  --spec        cut_spec.json that produced it
  --transcript  the render's OWN word transcript (ground truth of what it actually says), to label cuts.
                NB: ASR re-reads a clipped word as whole, so trust this ENERGY test for clipping, not the words."""
import argparse, json, subprocess
import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("--clip", required=True)
ap.add_argument("--spec", required=True)
ap.add_argument("--transcript", required=True, help="render's own word-transcript json ({words:[...]} or {segments:[{words}]})")
A = ap.parse_args()

spec = json.load(open(A.spec))["segments"]
durs = [float(s["out"]) - float(s["in"]) for s in spec]
seams = np.cumsum(durs)
raw = subprocess.run(["ffmpeg","-v","error","-i",A.clip,"-ac","1","-ar","16000","-f","f32le","-"],
                     capture_output=True).stdout
x = np.frombuffer(raw, np.float32); sr = 16000
def db(a,b):
    s = x[int(a*sr):int(b*sr)]; return float(20*np.log10(np.sqrt(np.mean(s**2))+1e-9)) if len(s)>40 else -120

d = json.load(open(A.transcript))
tw = d["words"] if isinstance(d, dict) and "words" in d else \
     [w for s in d.get("segments", []) for w in s.get("words", [])] if isinstance(d, dict) else []
def word_at(t):
    p = [w for w in tw if float(w.get("start",0)) <= t <= float(w.get("end",0))+0.05]
    if p: return (p[-1].get("word") or "").strip()
    pr = [w for w in tw if float(w.get("end",0)) <= t]
    return (pr[-1].get("word") or "").strip() if pr else ""

print(f"render {len(x)/sr:.2f}s   CLIP-RISK per cut (delta>-4dB = still loud at cut = clipped):", flush=True)
rows = []
for i,t in enumerate(seams[:-1]):
    rows.append((db(t-0.045,t)-db(t-0.22,t-0.06), i, t, word_at(t-0.03)))
hot = [r for r in sorted(rows, reverse=True) if r[0] > -4]
if not hot: print("  none -- all cuts taper cleanly", flush=True)
for dlt,i,t,wd in hot[:8]: print(f"  seam{i:2d} @{t:5.2f}s  delta={dlt:+5.1f}  last='{wd}'  <<< CLIP", flush=True)

T = len(x)/sr
tail = [db(T-k*0.05, T-k*0.05+0.05) for k in range(8,0,-1)]
ok = tail[-1] < tail[0]-8 or tail[-1] < -32
print(f"\nENDING last 0.4s dB: {[round(v,1) for v in tail]}", flush=True)
print(f"  final word '{word_at(T-0.05)}' -> {'TAPERS (good landing)' if ok else 'ends HOT (clipped payoff)'}", flush=True)
