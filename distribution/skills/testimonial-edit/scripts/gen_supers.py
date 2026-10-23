#!/usr/bin/env python3
"""gen_supers.py <project_root> — render plain reference-style super PNGs (transparent 3840x2160,
Poppins ExtraBold white + soft shadow, top-left) for every premiere_plan.json under
<project_root>/10_WORK, into <project_root>/10_WORK/_supers/<SEQ>.png. SEQ name comes from
_batch_manifest.json (seq->workdir). Fonts in 10_WORK/fonts (Poppins-800.ttf)."""
import glob, json, os, sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter
args=[a for a in sys.argv[1:] if not a.startswith("--")]
opts={a.split("=",1)[0][2:]:a.split("=",1)[1] for a in sys.argv[1:] if a.startswith("--") and "=" in a}
root=os.path.abspath(args[0]); WORK=f"{root}/10_WORK"
suffix=("_"+opts["out"]) if opts.get("out") else ""
FD=f"{WORK}/fonts"; OUT=f"{WORK}/_supers"; os.makedirs(OUT,exist_ok=True)
W,H=3840,2160
f1=ImageFont.truetype(f"{FD}/Poppins-800.ttf",88); f2=ImageFont.truetype(f"{FD}/Poppins-800.ttf",52)
man={m['workdir']:m['seq'] for m in json.load(open(f"{WORK}/_batch_manifest{suffix}.json"))}
for plan_path in glob.glob(f"{WORK}/*/*/premiere_plan.json"):
    plan=json.load(open(plan_path)); d=os.path.dirname(plan_path)
    seq=man.get(d); 
    if not seq: continue
    txt=Image.new("RGBA",(W,H),(0,0,0,0)); dr=ImageDraw.Draw(txt)
    dr.text((160,128),plan["super_line1"],font=f1,fill=(255,255,255,255))
    dr.text((160,232),plan["super_line2"],font=f2,fill=(255,255,255,255))
    sh=Image.new("RGBA",(W,H),(0,0,0,0)); sh.paste((0,0,0,150),(0,6),txt.split()[3])
    sh=sh.filter(ImageFilter.GaussianBlur(10))
    Image.alpha_composite(sh,txt).save(f"{OUT}/{seq}.png")
    print("super:",seq)
