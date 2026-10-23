#!/usr/bin/env python3
"""plate_at(t) — the card content at timeline time t, as the caption will see it.
Used so the caption engine can measure luminance UNDER THE GLYPHS and flip to dark type
when white would be invisible (e.g. the Matrix white-void b-roll)."""
import json, os, subprocess, sys
from PIL import Image, ImageDraw
D=os.path.dirname(os.path.abspath(__file__))
A=f"{D}/premiere/assets"
sys.path.insert(0,D)
import plan_v2 as P
# 🛑 LIB COMES FROM THE PLAN. It was a hardcoded constant, so a clip whose b-roll lives in a
# DIFFERENT library (pp/ vs pp5/) silently resolved every source against the wrong folder.
# Same bug class as check_plan's hardcoded pp/: a path constant that the plan already owns.
# 🛑 Must come AFTER `import plan_v2 as P` — putting it above was a NameError on import.
LIB=getattr(P,"LIB",os.path.expanduser("__ACQ_ASSETS__/assets/broll_lib/pp"))
W,H,CARD=1080,1920,980
_off=json.load(open(f"{A}/media_offsets.json"))["items"]
_fr={round(x["t0"],2):x for x in json.load(open(f"{D}/cut/aroll_framing.json"))}
_mask=Image.new("L",(W,H),0); ImageDraw.Draw(_mask).rounded_rectangle([50,470,1029,1449],48,fill=255)
def _win(t):
    for it in _off:
        if it["tl"]-0.02<=t<it["tl"]+(it["out"]-it["in"])+0.02: return it["in"]+(t-it["tl"])
    return _off[-1]["in"]
def _shot(t):
    for s in P.SHOTS:
        if s["t0"]<=t<s["t1"]: return s
    return P.SHOTS[-1]
def plate_at(t, tmp="/tmp/_plate.png"):
    s=_shot(t); cv=Image.new("RGB",(W,H),(0,0,0))
    if s["k"]=="a":
        f=_fr[round(s["t0"],2)]; S=f["scale"]/100
        sw=max(int(round(1920*S)),CARD); shh=max(int(round(1080*S)),CARD)
        x0=f["px"]*W-sw/2.0; y0=f["py"]*H-shh/2.0
        cx=min(max(int(round(50-x0)),0),max(sw-CARD,0)); cy=min(max(int(round(470-y0)),0),max(shh-CARD,0))
        subprocess.run(["ffmpeg","-v","error","-ss",f"{_win(t):.3f}","-i",f"{A}/AROLL_window.mp4",
            "-frames:v","1","-vf",f"scale={sw}:{shh},crop={CARD}:{CARD}:{cx}:{cy}","-y",tmp],check=True)
        cv.paste(Image.open(tmp).convert("RGB"),(50,470))
    elif s["k"]=="b":
        cw,ch,cx0,cy0=P.CROP[s["src"]]; S=CARD/ch
        subprocess.run(["ffmpeg","-v","error","-ss",f"{s['ss']+(t-s['t0']):.3f}","-i",f"{LIB}/{s['src']}.mp4",
            "-frames:v","1","-vf",f"crop={cw}:{ch}:{cx0}:{cy0},scale={int(round(cw*S))}:{max(int(round(ch*S)),CARD)},crop={CARD}:{CARD}",
            "-y",tmp],check=True)
        cv.paste(Image.open(tmp).convert("RGB"),(50,470))
    elif s["k"]=="split":
        SH_=696
        for nm,ss,yc in [(s["top"],s["tss"],258),(s["bot"],s["bss"],258+SH_+29)]:
            cw,ch,cx0,cy0=P.CROP[nm]; S=SH_/ch
            subprocess.run(["ffmpeg","-v","error","-ss",f"{ss+(t-s['t0']):.3f}","-i",f"{LIB}/{nm}.mp4",
                "-frames:v","1","-vf",f"crop={cw}:{ch}:{cx0}:{cy0},scale={int(round(cw*S))}:{max(int(round(ch*S)),SH_)},crop={CARD}:{SH_}",
                "-y",tmp],check=True)
            cv.paste(Image.open(tmp).convert("RGB"),(50,yc))
    else:
        col=(255,255,255) if s["k"]=="dot" or s.get("fill")=="white" else (8,8,8)
        c=Image.new("RGB",(CARD,CARD),col)
        if s["k"]=="dot": ImageDraw.Draw(c).ellipse([CARD//2-26,300,CARD//2+26,352],fill=(12,12,12))
        cv.paste(c,(50,470))
    return Image.composite(cv, Image.new("RGB",(W,H),(0,0,0)), _mask)
