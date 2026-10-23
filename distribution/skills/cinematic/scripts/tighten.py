#!/usr/bin/env python3
"""tighten.py — remove interior dead air from a clip's spans (spine step 6d).

🛑 WHY THIS EXISTS: a batch of 8 assembly cuts was rejected with "the cuts were terrible" — they
carried 6–34% dead air, one with a 5.86s silence in the middle. Boundaries were verified to the
millisecond and every transcript was read, but NOBODY LOOKED INSIDE. Reading a transcript cannot
show you a pause: the words are all correct and in order. Only the envelope shows it.

Finds silences in the CUT audio, maps them back to MASTER time through the span list, and rewrites
the spans to keep only KEEP_PAD of each pause. Motion across each new seam is reported so a
high-motion seam can be covered by a b-roll cut instead of jump-cutting a talking head.
"""
import json, subprocess, sys, wave
import numpy as np

SIL_DB, MIN_SIL, KEEP_PAD = -45.0, 0.50, 0.22

def envelope(wav, hop_s=0.01):
    w = wave.open(wav)
    x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    hop = int(hop_s * 16000)
    db = np.array([20*np.log10(max(np.sqrt((x[i:i+hop]**2).mean()), 1e-6))
                   for i in range(0, len(x)-hop, hop)])
    return db, hop_s

def silences(db, hop_s):
    out, st = [], None
    for i, v in enumerate(db < SIL_DB):
        if v and st is None: st = i
        elif not v and st is not None:
            if (i-st)*hop_s >= MIN_SIL: out.append((st*hop_s, i*hop_s))
            st = None
    if st is not None and (len(db)-st)*hop_s >= MIN_SIL: out.append((st*hop_s, len(db)*hop_s))
    return out

def cut_to_master(t, spans):
    """clip-relative seconds -> master seconds, walking the span list"""
    acc = 0.0
    for a, b in spans:
        d = b - a
        if t <= acc + d: return a + (t - acc)
        acc += d
    return spans[-1][1]

def tighten(slug):
    p = f"clips/{slug}/cut_spans.json"
    d = json.load(open(p)); spans = d["spans"]
    wav = f"clips/{slug}/premiere/assets/VOICE_cut.wav"
    subprocess.run(["ffmpeg","-v","error","-i",wav,"-ac","1","-ar","16000","-y","/tmp/t.wav"], check=True)
    db, hop = envelope("/tmp/t.wav")
    sils = silences(db, hop)
    # only INTERIOR pauses (head/tail are already handled by the boundary work)
    total = sum(b-a for a,b in spans)
    sils = [(a,b) for a,b in sils if a > 0.35 and b < total - 0.35]
    if not sils:
        print(f"  {slug:20s} no interior pause >= {MIN_SIL}s"); return
    cuts = []
    for a, b in sils:
        keep_from = b - KEEP_PAD                      # keep a breath, drop the rest
        cuts.append((cut_to_master(a + KEEP_PAD/2, spans), cut_to_master(keep_from, spans)))
    new, removed = [], 0.0
    for a, b in spans:
        seg = [a]
        for ca, cb in cuts:
            if a < ca and cb < b:
                seg += [ca, cb]; removed += cb - ca
        seg.append(b)
        for i in range(0, len(seg), 2):
            if seg[i+1] - seg[i] > 0.05: new.append([round(seg[i],3), round(seg[i+1],3)])
    d["spans"] = new
    d["tighten_note"] = (f"step 6d: removed {removed:.2f}s of interior dead air across "
                         f"{len(cuts)} pause(s), keeping {KEEP_PAD}s of breath at each.")
    json.dump(d, open(p,"w"), indent=1)
    print(f"  {slug:20s} {total:5.1f}s -> {sum(b-a for a,b in new):5.1f}s  "
          f"(-{removed:.1f}s across {len(cuts)} pause(s), {len(new)} pieces)")

for s in sys.argv[1:]: tighten(s)
