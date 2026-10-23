#!/usr/bin/env python3
"""Find caption frames whose TEXT sits on a clean, low-variance plate — the only frames where
glyph shapes can be extracted without background contamination."""
import numpy as np, subprocess, glob, tempfile, shutil, sys, os, json
from PIL import Image
from scipy.ndimage import minimum_filter, binary_dilation
def hunt(reel, want=6, fps=30):
    tmp=tempfile.mkdtemp()
    subprocess.run(["ffmpeg","-v","error","-i",f"00_SOURCE/{reel}.mp4","-vf",f"fps={fps}","-vsync","0",f"{tmp}/f%05d.png"],check=True)
    out=[]
    for p in sorted(glob.glob(f"{tmp}/*.png")):
        a=np.asarray(Image.open(p).convert("RGB")).astype(np.int16)
        card=a[470:1450,50:1030]; g=card.mean(2)
        br=(card[:,:,0]>200)&(card[:,:,1]>200)&(card[:,:,2]>200)
        txt=br&(minimum_filter(g,size=17)<110)
        if txt.sum()<600: continue
        ys,xs=np.where(txt)
        y0,y1,x0,x1=ys.min(),ys.max(),xs.min(),xs.max()
        if y1-y0>200 or x1-x0>900: continue           # skip contaminated giant boxes
        # background = the box minus a dilated glyph mask; want it DARK and FLAT
        box=g[y0:y1+1, x0:x1+1]
        mask=binary_dilation(txt[y0:y1+1, x0:x1+1], iterations=4)
        bg=box[~mask]
        if bg.size<400: continue
        score=bg.std() + abs(bg.mean()-30)*0.5        # low variance, dark
        out.append((score, p, int(x0),int(y0),int(x1),int(y1)))
    out.sort()
    keep=[]
    for sc,p,x0,y0,x1,y1 in out:
        if len(keep)>=want: break
        if any(abs(int(p.split('f')[-1].split('.')[0])-int(k[1].split('f')[-1].split('.')[0]))<20 for k in keep): continue
        keep.append((sc,p,x0,y0,x1,y1))
    res=[]
    for i,(sc,p,x0,y0,x1,y1) in enumerate(keep):
        im=Image.open(p).convert("RGB").crop((50+x0-8,470+y0-8,50+x1+9,470+y1+9))
        o=f"10_WORK/glyphs/{reel}_{i}.png"; os.makedirs("10_WORK/glyphs",exist_ok=True); im.save(o)
        res.append((o, round(sc,1), im.size))
    shutil.rmtree(tmp)
    return res
if __name__=="__main__":
    for r in sys.argv[1:]:
        for o,sc,sz in hunt(r):
            print(f"  {o}  bgscore {sc:6.1f}  {sz[0]}x{sz[1]}")
