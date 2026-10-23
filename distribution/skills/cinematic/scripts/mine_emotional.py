#!/usr/bin/env python3
"""mine_emotional.py — find EMOTIONALLY CHARGED passages in this podcast, not teaching moments.

Adapted from 2026-08-11_CinematicMine2 (which was hardcoded to another source). Two changes for a
2-SPEAKER podcast: the charge is scored on the SUBJECT's words only (the host asking "how did that
feel" must not score), and a window must be >=70% subject speech or it is a dialogue, not a
confession.

🛑 The 25 locked /edit clips from this source were mined for a DIFFERENT objective — clean teaching
arcs. The cinematic look needs stakes, loss, fear, defiance, mortality, shame. A purely
informational moment cannot be scored into chills.
"""
import json, os, re, sys
# 🛑 per-run: point these at the source. Kept as argv so the file is never hardcoded to one job.
import sys
WORDS_JSON = sys.argv[1] if len(sys.argv)>1 else None
if not WORDS_JSON: raise SystemExit("usage: mine_emotional.py <words.json> [subject_speaker=A]")
W=json.load(open(WORDS_JSON))
WS=W["words"] if isinstance(W,dict) else W
SUBJ=sys.argv[2] if len(sys.argv)>2 else "A"   # the subject; the other speaker is the host
EX=json.load(open("excluded_spans.json")) if os.path.exists("excluded_spans.json") else []

CHARGE={"die":3,"died":3,"dies":3,"death":3,"dead":3,"kill":2,"lose":2,"lost":2,"losing":2,
 "fail":2,"failed":2,"failure":2,"afraid":3,"fear":3,"scared":3,"terrified":3,"terror":3,
 "regret":3,"alone":2,"lonely":3,"pain":2,"hurt":2,"suffer":2,"suffering":3,"sacrifice":3,
 "shame":3,"ashamed":3,"embarrassed":2,"humiliated":3,"coward":3,"weak":2,"broke":2,
 "cry":3,"cried":3,"tears":3,"grief":3,"mourn":3,"funeral":3,"betrayed":3,"abandoned":3,
 "worthless":3,"empty":2,"hollow":2,"desperate":2,"quit":2,"gave up":3,"nightmare":3,
 "haunt":3,"forever":2,"last time":2,"cancer":3,"hospital":2,"buried":3,"loved":2,"love":1}
CONFESS=("i was","i felt","i remember","i thought i","i used to","i had to","i couldn't",
         "i didn't","my dad","my father","my mom","my mother","my wife","for me it","i cried",
         "i almost","i never")
LECTURE=("number one","number two","first thing","second thing","the framework","step one",
         "three things","couple things","in other words","for example","let's say","so the way")

def excluded(a,b): return any(a<y and b>x for x,y in EX)

win,hop=40.0,5.0
t0=WS[0]["start"]; tend=WS[-1]["end"]; rows=[]
while t0+win<tend:
    a,b=t0,t0+win
    if not excluded(a,b):
        seg=[w for w in WS if w["start"]>=a and w["end"]<=b]
        if len(seg)>60:
            sub=[w for w in seg if w.get("spk")==SUBJ]
            frac=len(sub)/len(seg)
            if frac>=0.70:
                txt=" ".join(w["word"] for w in sub).lower()
                ch=sum(v*txt.count(k) for k,v in CHARGE.items())
                cf=sum(txt.count(k) for k in CONFESS)
                lec=sum(txt.count(k) for k in LECTURE)
                rows.append((round(ch+2.2*cf-3.0*lec,1),round(a,1),round(b,1),len(seg),round(frac,2)))
    t0+=hop
rows.sort(reverse=True)
picked=[]
for r in rows:
    if all(abs(r[1]-p[1])>70 for p in picked): picked.append(r)
    if len(picked)>=20: break
json.dump(picked,open("emotional_windows.json","w"),indent=1)
print(f"{len(rows)} windows scanned (>=70% subject) · top {len(picked)} neighbourhoods:")
for s,a,b,n,f in picked: print(f"  score {s:6.1f}  {a:8.1f}-{b:8.1f}s  ({a/60:5.1f} min)  subj {f:.2f}")
