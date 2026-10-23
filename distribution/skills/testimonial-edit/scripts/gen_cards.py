#!/usr/bin/env python3
"""gen_cards.py <project_root> — render all unique question-card PNGs referenced by the plans
(reference style: centered Poppins-800 white + soft shadow, transparent 3840x2160) into
<project_root>/10_WORK/_cards2/<card_png>. Dedupes by content-hash filename (card_png)."""
import glob, json, os, sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter
args=[a for a in sys.argv[1:] if not a.startswith("--")]
opts={a.split("=",1)[0][2:]:a.split("=",1)[1] for a in sys.argv[1:] if a.startswith("--") and "=" in a}
root=os.path.abspath(args[0]); WORK=f"{root}/10_WORK"
events=set(e.strip() for e in opts.get("events","").split(",") if e.strip())
FD=f"{WORK}/fonts"; OUT=f"{WORK}/_cards2"; os.makedirs(OUT,exist_ok=True)
W,H,FS,PITCH=3840,2160,184,292
font=ImageFont.truetype(f"{FD}/Poppins-800.ttf",FS)
uniq={}
_pp=glob.glob(f"{WORK}/*/*/premiere_plan.json")
if events: _pp=[p for p in _pp if os.path.basename(os.path.dirname(os.path.dirname(p))) in events]
for pp in _pp:
    for s in json.load(open(pp)).get("segments",[]):
        if s.get("kind")=="card": uniq[s["card_png"]]=s["lines"]
for png,lines in uniq.items():
    txt=Image.new("RGBA",(W,H),(0,0,0,0)); d=ImageDraw.Draw(txt)
    y0=H//2-(PITCH*(len(lines)-1)+FS)//2
    for i,l in enumerate(lines):
        bb=d.textbbox((0,0),l,font=font); d.text(((W-(bb[2]-bb[0]))//2-bb[0],y0+i*PITCH),l,font=font,fill=(255,255,255,255))
    sh=Image.new("RGBA",(W,H),(0,0,0,0)); sh.paste((0,0,0,150),(0,16),txt.split()[3]); sh=sh.filter(ImageFilter.GaussianBlur(22))
    Image.alpha_composite(sh,txt).save(f"{OUT}/{png}")
print(f"rendered {len(uniq)} unique cards")
