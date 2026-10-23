#!/usr/bin/env python3
"""Per-FRAME analysis of every 15fps frame — no sampling.

  python3 analyze15.py <frames_dir> [out.json]

Isolates caption glyphs by LOCAL CONTRAST (bright pixel with dark neighbours), which also
excludes flat white interstitial cards. NOTE: this detector also fires on a bright window with
dark mullions — see SKILL.md rule 4. Use it for colour, and treat width/size from a COMPOSITE as
unreliable; measure our own captions from their alpha masks instead.
"""
import numpy as np, glob, os, json, sys
from PIL import Image
from scipy.ndimage import minimum_filter, maximum_filter, label

CX0,CX1,CY0,CY1 = 50,1030,470,1450

def analyse(path):
    a = np.asarray(Image.open(path).convert("RGB")).astype(np.int16)
    card = a[CY0:CY1, CX0:CX1]
    g = card.mean(2)
    bright = (card[:,:,0]>195)&(card[:,:,1]>195)&(card[:,:,2]>195)
    if bright.sum() < 150:
        return None
    # text = bright AND has dark pixels nearby (kills flat white cards / bright skies)
    localmin = minimum_filter(g, size=17)
    text = bright & (localmin < 125)
    if text.sum() < 150:
        return None
    lab,n = label(text)
    if n == 0: return None
    px = card[text]
    ys,xs = np.where(text)
    return dict(file=os.path.basename(path),
                n=int(text.sum()),
                r=float(px[:,0].mean()), g=float(px[:,1].mean()), b=float(px[:,2].mean()),
                x0=int(xs.min()), x1=int(xs.max()), y0=int(ys.min()), y1=int(ys.max()),
                comps=int(n))

if __name__ == "__main__":
    d = sys.argv[1].rstrip("/")
    out=[]
    for p in sorted(glob.glob(f"{d}/*.png")):
        r = analyse(p)
        if r: out.append(r)
    dst = sys.argv[2] if len(sys.argv)>2 else f"{d}_text.json"
    json.dump(out, open(dst,"w"))
    print(f"{os.path.basename(d)}: {len(out)} frames containing caption text -> {dst}")
