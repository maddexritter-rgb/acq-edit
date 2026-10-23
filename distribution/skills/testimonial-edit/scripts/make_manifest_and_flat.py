#!/usr/bin/env python3
"""make_manifest_and_flat.py <project_root> [seq_order_csv] — build:
  10_WORK/_batch_manifest.json : [{seq,workdir,person,source,...}] (seq = FIRSTNAME_L3_V2, deduped)
  10_WORK/review_flat_plan.json: flat non-nested review layout (V1 clips, V2 cards, V3 supers)
Run AFTER prep_clip has produced premiere_plan.json for every clip. If seq_order_csv omitted,
uses event-folder/name sort order."""
import glob, json, os, sys
FPS=24000/1001
# optional --events=ev1,ev2 scopes to specific event folders (batches share one project);
# optional --out=NAME writes _batch_manifest_NAME.json / review_flat_plan_NAME.json
args=[a for a in sys.argv[1:] if not a.startswith("--")]
opts={a.split("=",1)[0][2:]:a.split("=",1)[1] for a in sys.argv[1:] if a.startswith("--") and "=" in a}
root=os.path.abspath(args[0]); WORK=f"{root}/10_WORK"
events=set(e.strip() for e in opts.get("events","").split(",") if e.strip())
suffix=("_"+opts["out"]) if opts.get("out") else ""
GAP=float(opts.get("gap","0"))  # seconds of empty timeline between people (review readability)
plans=sorted(glob.glob(f"{WORK}/*/*/premiere_plan.json"))
if events: plans=[p for p in plans if os.path.basename(os.path.dirname(os.path.dirname(p))) in events]
man=[]; seen={}
for pp in plans:
    p=json.load(open(pp)); d=os.path.dirname(pp)
    first="".join(ch for ch in p["super_line1"].split()[0].upper() if ch.isalnum())
    seq=first+"_L3_V2"
    if seq in seen: seen[seq]+=1; seq=f"{first}{seen[seq]}_L3_V2"
    else: seen[seq]=1
    man.append({"seq":seq,"workdir":d,"person":p["person"],"source":p["source"],"total":p["total"]})
json.dump(man,open(f"{WORK}/_batch_manifest{suffix}.json","w"),indent=1)
# flat plan (event order = plan sort unless override given)
order=[m["seq"] for m in man]
if len(args)>1: order=[s.strip() for s in args[1].split(",")]
byseq={m["seq"]:m for m in man}
def q(t): return round(t*FPS)/FPS
clips=[];cards=[];supers=[];cur=0.0
for seq in order:
    plan=json.load(open(f"{byseq[seq]['workdir']}/premiere_plan.json")); block=cur
    for s in plan["segments"]:
        dur=q(s["src_out"])-q(s["src_in"])
        clips.append({"source":plan["source"],"src_in":round(q(s["src_in"])+0.002,5),"src_out":round(q(s["src_out"])+0.002,5),"tl":round(cur,5),"dur":round(dur,5),"kind":s["kind"],"card_png":s.get("card_png")})
        if s["kind"]=="card": cards.append({"card_png":s["card_png"],"tl":round(cur,5),"dur":round(dur,5)})
        cur=round(cur+dur,5)
    supers.append({"seq":seq,"tl":round(block,5),"dur":11.5})
    cur=round(cur+GAP,5)  # gap before the next person (none trails the last visibly)
json.dump({"clips":clips,"cards":cards,"supers":supers,"total":round(cur,2),"gap":GAP},open(f"{WORK}/review_flat_plan{suffix}.json","w"))
print(f"manifest{suffix} {len(man)} | flat V1 {len(clips)} V2 {len(cards)} V3 {len(supers)} | {cur/60:.1f} min")
