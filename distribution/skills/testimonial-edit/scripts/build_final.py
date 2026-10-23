#!/usr/bin/env python3
"""build_final.py <workdir> — produce the FINAL cutlist (cutlist_v3.json) + cards_final.json:
snap every cutlist_v2 boundary to real inter-word silence, then apply opening.json
(keep|replace|prepend). Idempotent: always derives from pristine cutlist_v2.json + cards.json.
"""
import json, os, re, subprocess, sys
def sh(c): return subprocess.run(c, shell=True, capture_output=True, text=True)
def main(wd):
    wd=os.path.abspath(wd)
    cl=json.load(open(f"{wd}/cutlist_v2.json"))
    if cl.get("empty"): print("empty"); return
    src=cl["source"]
    mv=sh(f'ffmpeg -v info -i "{src}" -af volumedetect -vn -f null - 2>&1'); t=mv.stdout+mv.stderr
    m=re.search(r"mean_volume:\s*(-?[\d.]+) dB",t); mean=float(m.group(1)) if m else -30.0
    floor=round(mean-6,1)
    sd=sh(f'ffmpeg -v info -i "{src}" -af silencedetect=noise={floor}dB:d=0.10 -vn -f null - 2>&1'); tt=sd.stdout+sd.stderr
    sil=[]; cur=None
    for ln in tt.splitlines():
        a=re.search(r"silence_start:\s*(-?[\d.]+)",ln); b=re.search(r"silence_end:\s*(-?[\d.]+)",ln)
        if a: cur=float(a.group(1))
        if b and cur is not None: sil.append((cur,float(b.group(1)))); cur=None
    W=0.35
    def snin(x):
        # only move the IN earlier (into the silence just BEFORE the first word) — never skip a word
        c=[e for (s,e) in sil if x-W <= e <= x+0.06]
        return round(max(c)-0.04,3) if c else None
    def snout(x):
        # only move the OUT later (into the silence just AFTER the last word) — never clip a word
        c=[s for (s,e) in sil if x-0.06 <= s <= x+W]
        return round(min(c)+0.06,3) if c else None
    for sp in cl["spans"]:
        ni=snin(sp["in"]); no=snout(sp["out"])
        if ni is not None: sp["in"]=ni
        if no is not None and no>sp["in"]+0.3: sp["out"]=no
    # opening
    op=json.load(open(f"{wd}/opening.json")) if os.path.exists(f"{wd}/opening.json") else {"mode":"keep"}
    cards=json.load(open(f"{wd}/cards.json")) if os.path.exists(f"{wd}/cards.json") else {"cards":[]}
    mode=op.get("mode","keep")
    if mode=="replace" and op.get("intro"):
        intro=op["intro"]; intro["n"]=0
        # snap the intro boundaries too
        ni=snin(intro["in"]); no=snout(intro["out"])
        if ni is not None: intro["in"]=ni
        if no is not None and no>intro["in"]+0.3: intro["out"]=no
        cl["spans"][0]=intro  # cards indices unchanged
    elif mode=="prepend" and op.get("intro"):
        intro=op["intro"]; intro["n"]=0
        ni=snin(intro["in"]); no=snout(intro["out"])
        if ni is not None: intro["in"]=ni
        if no is not None and no>intro["in"]+0.3: intro["out"]=no
        cl["spans"]=[intro]+cl["spans"]
        for c in cards.get("cards",[]): c["span"]+=1   # shift card refs
    # per-span sanity only (spans need NOT be increasing in source time — timeline order
    # is span-list order; a prepended intro may come from anywhere in the source)
    for sp in cl["spans"]:
        if sp["out"] <= sp["in"] + 0.2:  # snap collapsed it -> keep a safe min length
            sp["out"] = round(sp["in"] + 0.3, 3)
    json.dump(cl,open(f"{wd}/cutlist_v3.json","w"),indent=1)
    json.dump(cards,open(f"{wd}/cards_final.json","w"),indent=1)
    print(f'{cl["person"]}: mode={mode}, {len(cl["spans"])} spans, {len(cards.get("cards",[]))} cards')
if __name__=="__main__": main(sys.argv[1])
