#!/usr/bin/env python3
"""Caption chain for testimonial glass captions (editor spec 2026-07-14):
whisper.cpp DTW json -> words -> normalize_transcript -> normalize_simple ->
spice_normalize -> generate_spice chunker (.ass) -> glass props:
NO punctuation, ALL CAPS, NO gaps (extend to next cue, capped hold),
3-5 frame lead, hard-clipped around question-card windows."""
import json, re, subprocess, sys, os
from pathlib import Path

W = os.path.expanduser("~/Downloads/alex/2026-07-13_L3Testimonials/10_WORK/2026.02.17_Stetson")
SK = str(Path(__file__).resolve().parents[3] / "caption-clips/scripts")
FPS = 24000 / 1001
LEAD = 4 / FPS            # ~4-frame caption lead (Oliver standard 3-5)
MAX_HOLD = 1.2            # max seconds a cue may extend past its natural end
CARDS = [(4.505, 7.508), (147.439, 150.442), (192.651, 195.654), (252.127, 255.130)]

# 1. whisper.cpp tokens -> {"words":[...]}
d = json.load(open(f"{W}/_staging/master_dtw.json"))
words = []
cur = None
for seg in d["transcription"]:
    for tok in seg["tokens"]:
        txt = tok["text"]
        if txt.startswith("[_") or txt.strip() == "":
            continue
        start = tok["offsets"]["from"] / 1000.0
        if tok.get("t_dtw", -1) >= 0:
            start = min(start, tok["t_dtw"] / 100.0) if tok["t_dtw"] > 0 else start
        end = tok["offsets"]["to"] / 1000.0
        if txt.startswith(" ") or cur is None:
            if cur: words.append(cur)
            cur = {"word": txt.strip(), "start": round(start, 3), "end": round(end, 3)}
        else:
            cur["word"] += txt
            cur["end"] = round(end, 3)
if cur: words.append(cur)
json.dump({"words": words}, open(f"{W}/_staging/w0.json", "w"))
print(f"{len(words)} words from DTW")

# 2. canonical normalizers
subprocess.run(f'python3 "{SK}/normalize_transcript.py" --in "{W}/_staging/w0.json" --out "{W}/_staging/w1.json"', shell=True, check=True)
subprocess.run(f'python3 "{SK}/normalize_simple.py" "{W}/_staging/w1.json" "{W}/_staging/w2.json"', shell=True, check=True)
subprocess.run(f'python3 "{SK}/spice_normalize.py" "{W}/_staging/w2.json" "{W}/_staging/w3.json"', shell=True, check=True)

# 3. the locked chunker
r = subprocess.run(f'python3 "{SK}/generate_spice.py" "{W}/_staging/w3.json" '
                   f'--preset "{os.path.dirname(SK)}/presets/spice_longform.json" --out "{W}/_staging/spice_cues.ass"',
                   shell=True, capture_output=True, text=True)
if r.returncode != 0:
    sys.exit("generate_spice failed:\n" + r.stderr[-2000:] + r.stdout[-500:])

# 4. parse .ass cues
def ass_t(s):
    h, m, rest = s.split(":")
    return int(h) * 3600 + int(m) * 60 + float(rest)
cues = []
for line in open(f"{W}/_staging/spice_cues.ass"):
    if not line.startswith("Dialogue:"):
        continue
    parts = line.split(",", 9)
    st, en, txt = ass_t(parts[1]), ass_t(parts[2]), parts[9].strip()
    txt = re.sub(r"\{[^}]*\}", "", txt)          # strip ASS override tags
    txt = txt.replace("\\N", " ")
    raw = re.sub(r"\s+", " ", txt).strip()
    txt = re.sub(r"[^\w$%#&' ]+", "", raw)        # NO punctuation (keep $ % # & ')
    txt = re.sub(r"\s+", " ", txt).strip().upper()
    if txt:
        cues.append({"text": txt, "raw": raw, "start": st, "end": en})
cues.sort(key=lambda c: (c["start"], c["end"]))
# dedupe layered .ass events (shadow layer duplicates the text layer)
seen=set(); dedup=[]
for c in cues:
    k=(round(c["start"],2), round(c["end"],2), c["text"])
    if k in seen: continue
    seen.add(k); dedup.append(c)
cues = dedup

# 4b. LONG-FORM MERGE (editor 2026-07-14: ~20-30 chars/line vs short-form 18) —
# combine adjacent cues while <=28 chars, no real pause (<=0.30s) and no sentence
# end at the seam. Runs on raw text BEFORE punctuation strip so sentence ends count.
MERGE_MAX, MERGE_GAP = 28, 0.30
merged = []
for c in cues:
    if merged:
        prev = merged[-1]
        no_sentence_end = not prev["raw"].rstrip().endswith((".", "?", "!"))
        if (no_sentence_end and c["start"] - prev["end"] <= MERGE_GAP
                and len(prev["text"]) + 1 + len(c["text"]) <= MERGE_MAX):
            prev["text"] += " " + c["text"]
            prev["raw"] += " " + c["raw"]
            prev["end"] = c["end"]
            continue
    merged.append(dict(c))
cues = merged

# 5. post-process: lead, no gaps (capped), card-window clipping
def in_card(t):
    return any(a - 0.01 <= t <= b + 0.01 for a, b in CARDS)
out = []
for i, c in enumerate(cues):
    st = c["start"] - LEAD
    en = c["end"]
    nxt = cues[i + 1]["start"] - LEAD if i + 1 < len(cues) else None
    if nxt is not None:
        en = min(nxt, max(en, c["end"]) + MAX_HOLD)
        if nxt - c["end"] <= MAX_HOLD:
            en = nxt                              # butt-joined: no gap
    if out:
        st = max(st, out[-1]["end"])
    for a, b in CARDS:                            # never overlap a question card
        if st < a < en: en = a
        if a <= st < b: st = b
    if en - st < 0.05:
        continue
    out.append({"text": c["text"], "start": round(st, 3), "end": round(en, 3)})

props_path = f"{W}/../remotion/props/stetson.json"
props = json.load(open(props_path))
props["captions"] = out
json.dump(props, open(props_path, "w"), indent=1)
gaps = sum(1 for i in range(len(out) - 1)
           if out[i + 1]["start"] - out[i]["end"] > 0.05
           and not any(abs(out[i]["end"] - a) < 0.1 for a, b in CARDS))
print(f"{len(out)} cues -> props; non-card gaps >50ms: {gaps}")
