#!/usr/bin/env python3
"""EAR TEST #1 on the RENDERED clip -- dead air + seam spectrograms.
I (Claude) run this; I do NOT ask the human to find the errors.
  --clip   rendered mp4
  --spec   the cut_spec.json that produced it (for seam positions)
Outputs: residual dead-air gaps, too-short (fragment) segments, and a contact sheet of every
cut seam's spectrogram (clipped consonant = high-freq energy chopped; stray syllable = a blob at the cut)."""
import argparse, json, subprocess, os
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

ap = argparse.ArgumentParser()
ap.add_argument("--clip", required=True)
ap.add_argument("--spec", required=True)
ap.add_argument("--out", default=None, help="contact sheet png (default: next to clip)")
A = ap.parse_args()

spec = json.load(open(A.spec))["segments"]
durs = [float(s["out"]) - float(s["in"]) for s in spec]
seams = np.cumsum(durs)[:-1]
raw = subprocess.run(["ffmpeg","-v","error","-i",A.clip,"-ac","1","-ar","16000","-f","f32le","-"],
                     capture_output=True).stdout
x = np.frombuffer(raw, np.float32); sr = 16000
print(f"render dur={len(x)/sr:.2f}s  segments={len(spec)}  seams={len(seams)}", flush=True)

wl, hop = 400, 160
env = np.array([20*np.log10(np.sqrt(np.mean(x[i:i+wl]**2)+1e-9)+1e-9) for i in range(0,max(1,len(x)-wl),hop)])
floor = np.percentile(env, 20) - 6
sil = env < floor; gaps = []; i = 0
while i < len(sil):
    if sil[i]:
        j = i
        while j < len(sil) and sil[j]: j += 1
        dur = (j-i)*hop/sr
        if dur >= 0.30: gaps.append((round(i*hop/sr,2), round(dur,2)))
        i = j
    else: i += 1
print(f"residual dead-air gaps >=0.30s: {len(gaps)} -> {gaps}", flush=True)
print(f"too-short segments (<0.25s): {[(i,round(d,2)) for i,d in enumerate(durs) if d<0.25]}", flush=True)

n = len(seams); cols = 4; rows = max(1,(n + cols - 1)//cols)
fig, axes = plt.subplots(rows, cols, figsize=(cols*3.2, rows*2.2)); axes = np.array(axes).reshape(-1)
for k, t in enumerate(seams):
    s0 = max(0, int((t-0.5)*sr)); s1 = min(len(x), int((t+0.5)*sr)); seg = x[s0:s1]; ax = axes[k]
    if len(seg) > 256:
        ax.specgram(seg, NFFT=512, Fs=sr, noverlap=400, cmap="magma"); ax.axvline(0.5, color="cyan", lw=1.2, ls="--")
    ax.set_title(f"seam{k} @{t:.1f}s", fontsize=7); ax.set_xticks([]); ax.set_yticks([])
for k in range(n, len(axes)): axes[k].axis("off")
plt.tight_layout()
out = A.out or os.path.splitext(A.clip)[0] + "_seams.png"
plt.savefig(out, dpi=85); print(f"contact sheet -> {out}", flush=True)
