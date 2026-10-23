#!/usr/bin/env python3
"""disfluency_gate.py — ACOUSTIC um/ah + long-pause detector. Closes the blind spot of the transcript-based
filler/pause gates: ASR (even whisper large-v3) DROPS 'um/uh/ah' and SWALLOWS pauses inside inflated word
labels, so a perfectly CLEAN transcript can still have audible fillers + a too-long pause. (Proven on
ThreeFunctions V6, 2026-06-22: transcript clean, gauntlet green, but the audio had ums @17/36/53s + a 1.13s
pause @58.6s that Maddex heard.) This gate LISTENS to the audio instead of trusting the words.

Two checks on the delivered clip's audio:
  PAUSES  — ffmpeg silencedetect: a silence >= --max-pause (default 0.8s) FAILS; 0.55-0.8s = advisory.
  FILLERS — VOICED energy (>= --voiced-db) that falls OUTSIDE any transcribed word span (needs --words
            w_norm.json), 0.12-0.55s long = a dropped 'um/uh/ah' or an audible breath. Reported with
            timestamps; EAR-VERIFY each (a breath is fine, an 'um' gets cut).
Usage: disfluency_gate.py --clip CLIP.mp4 [--words w_norm.json] [--max-pause 0.8] [--voiced-db -28]
Exit 0 = clean / advisory only · 1 = a too-long pause (or, with --strict, any filler candidate).
"""
import argparse, subprocess, re, json, sys
import numpy as np
from pathlib import Path

def audio(clip, sr=16000):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", clip, "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"],
                         capture_output=True).stdout
    return np.frombuffer(raw, dtype="<f4"), sr

def pauses(clip, floor_db):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", clip,
                        "-af", f"silencedetect=noise={floor_db}dB:d=0.45", "-f", "null", "-"],
                       capture_output=True, text=True).stderr
    out = []
    cur = None
    for ln in r.splitlines():
        m = re.search(r"silence_start: ([0-9.]+)", ln)
        if m: cur = float(m.group(1))
        d = re.search(r"silence_duration: ([0-9.]+)", ln)
        if d and cur is not None: out.append((round(cur, 2), round(float(d.group(1)), 2))); cur = None
    return out

def fillers(a, sr, words, voiced_db):
    hop = int(sr * 0.02)
    rms = np.array([20*np.log10(np.sqrt(np.mean(a[i:i+hop]**2)+1e-12)+1e-9) for i in range(0, len(a)-hop, hop)])
    def covered(t): return any(w["start"]-0.04 <= t <= w["end"]+0.04 for w in words)
    runs = []; cur = None
    for i, db in enumerate(rms):
        t = i*0.02
        if db > voiced_db and not covered(t):
            cur = [t, t] if cur is None else [cur[0], t]
        else:
            if cur and 0.12 <= cur[1]-cur[0] <= 0.55: runs.append((round(cur[0], 2), round(cur[1]-cur[0], 2)))
            cur = None
    return runs

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clip", required=True)
    ap.add_argument("--words")
    ap.add_argument("--max-pause", type=float, default=0.8)
    ap.add_argument("--voiced-db", type=float, default=-28.0)
    ap.add_argument("--strict", action="store_true", help="also FAIL on filler candidates (default: advisory)")
    a = ap.parse_args()
    # measure mean to set a sensible silence floor (~mean-13dB, clamped)
    md = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", a.clip, "-af", "volumedetect", "-f", "null", "-"],
                        capture_output=True, text=True).stderr
    mm = re.search(r"mean_volume:\s*(-?\d+\.?\d*)", md)
    floor = min(-28.0, (float(mm.group(1)) - 13.0)) if mm else -32.0

    print(f"=== disfluency_gate ({Path(a.clip).name}) ===")
    fails = []
    pz = pauses(a.clip, round(floor))
    longp = [(t, d) for t, d in pz if d >= a.max_pause]
    advp = [(t, d) for t, d in pz if a.max_pause > d >= 0.55]
    for t, d in longp:
        print(f"  ✗ PAUSE {d:.2f}s @ {t}s — too long (>= {a.max_pause}s); tighten to a clean beat")
        fails.append(f"pause {d}s@{t}s")
    for t, d in advp:
        print(f"  ⚠ pause {d:.2f}s @ {t}s — borderline; tighten if it drags")

    if a.words and Path(a.words).exists():
        ws = json.loads(Path(a.words).read_text()); ws = ws.get("words", ws)
        a_arr, sr = audio(a.clip)
        fl = fillers(a_arr, sr, ws, a.voiced_db)
        for t, d in fl:
            tag = "✗" if a.strict else "⚠"
            print(f"  {tag} FILLER candidate @ {t}s ({d:.2f}s voiced, no transcribed word) — EAR-VERIFY: cut if it's an um/ah, keep if a breath")
            if a.strict: fails.append(f"filler@{t}s")
        if not fl: print("  ✓ no voiced filler outside transcribed words")
    else:
        print("  · filler check skipped (pass --words w_norm.json)")

    if not fails and not longp:
        print("  ✓ no too-long pauses")
    print(f"\n{'BLOCK — fix before delivery' if fails else 'PASS (review any ⚠ by ear)'}")
    return 1 if fails else 0

if __name__ == "__main__":
    sys.exit(main())
