#!/usr/bin/env python3
"""Readable 15fps watch sheets — EVERY frame, tiles big enough to READ THE TYPE.

  python3 watchsheets.py <frames_dir> [out_dir]

These are for STRUCTURE (cuts, order, layout). They are downsampled — never measure colour or
size off them (SKILL.md rule 3).
"""
import glob, math, os, sys
from PIL import Image, ImageDraw, ImageFont
src=sys.argv[1].rstrip("/"); reel=os.path.basename(src)
COLS=6; ROWS=4; TW=236
frames=sorted(glob.glob(f"{src}/*.png"))
out=sys.argv[2] if len(sys.argv)>2 else f"{os.path.dirname(src)}/../watch/{reel}"
os.makedirs(out,exist_ok=True)
f=lambda s: ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf",s)
th=int(TW*1920/1080); per=COLS*ROWS; n=math.ceil(len(frames)/per)
for s in range(n):
    ch=frames[s*per:(s+1)*per]
    r_=math.ceil(len(ch)/COLS); pad=4; lbl=15
    W=COLS*(TW+pad)+pad; H=r_*(th+lbl+pad)+pad+20
    sheet=Image.new("RGB",(W,H),(10,10,12)); d=ImageDraw.Draw(sheet)
    t0=s*per/15; t1=min((s+1)*per,len(frames))/15
    d.text((pad,4),f"{reel}  WATCH {s+1}/{n}   {t0:.2f}s -> {t1:.2f}s   @15fps  EVERY FRAME",
           fill=(255,220,90),font=f(13))
    for i,p in enumerate(ch):
        rr,cc=divmod(i,COLS); x=pad+cc*(TW+pad); y=20+pad+rr*(th+lbl+pad)
        sheet.paste(Image.open(p).resize((TW,th)),(x,y))
        d.text((x+2,y+th+1),f"{(s*per+i)/15:06.2f}",fill=(150,205,255),font=f(12))
    sheet.save(f"{out}/W_{s+1:02d}.png")
print(f"{reel}: {n} sheets, {len(frames)} frames, {TW}px tiles")
