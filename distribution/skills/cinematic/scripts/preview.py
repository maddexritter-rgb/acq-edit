#!/usr/bin/env python3
"""Fast preview of the V7 timeline — ffmpeg segments + one caption-overlay pass."""
import numpy as np
import glob
import json, os, subprocess, sys, tempfile, math, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image, ImageDraw
import plan_v2 as P
D=os.path.dirname(os.path.abspath(__file__)); A=f"{D}/premiere/assets"
LIB=os.path.expanduser("__ACQ_ASSETS__/assets/broll_lib/pp")
# 🛑 SCALE ROUNDING: int() truncates, so int(1388*(980/1388)) == 979 and the final 980 crop
# fails with 'Invalid too big or non positive size'. Round, and floor at CARD.
W,H,CARD=1080,1920,980; FPS=24000/1001   # match the source master
off=json.load(open(f"{A}/media_offsets.json"))["items"]
fr={round(x["t0"],2):x for x in json.load(open(f"{D}/cut/aroll_framing.json"))}
man=json.load(open(f"{A}/captions_v2/manifest.json"))
AR=f"{A}/AROLL_window.mp4"
# 🛑 THE BED IS PER CLIP AND MUST BE SET DELIBERATELY. It used to be a hardcoded path, so a new
# clip silently inherited the previous clip's music on every re-render. Point MUSIC at the chosen
# track (pick it with the /edit MUSIC 4-step chain) or the render fails LOUDLY rather than lying.
MUS=os.environ.get("CINEMATIC_BED") or os.path.join(D,"MUSIC_BED.txt")
if MUS.endswith(".txt"):
    if not os.path.exists(MUS):
        raise SystemExit("NO MUSIC BED SET. Write the chosen track's path into MUSIC_BED.txt "
                         "(or export CINEMATIC_BED=...). Never inherit the last clip's bed.")
    MUS=open(MUS).read().strip()
tmp=tempfile.mkdtemp(prefix="pv_")
PRE=0.5

def sh(c):
    r=subprocess.run(c,capture_output=True,text=True)
    if r.returncode: sys.exit(r.stderr[-1500:])
def rr(w,h,p,bands=None):
    m=Image.new("L",(w,h),0); d=ImageDraw.Draw(m)
    if bands:
        for y0,y1 in bands: d.rounded_rectangle([0,y0,w-1,y1],48,fill=255)
    else: d.rounded_rectangle([0,0,w-1,h-1],48,fill=255)
    m.save(p); return p
mask=rr(CARD,CARD,f"{tmp}/m.png")
enc=["-c:v","libx264","-crf","16","-preset","veryfast","-pix_fmt","yuv420p"]
def wt(t):
    for it in off:
        if it["tl"]-0.02<=t<it["tl"]+(it["out"]-it["in"])+0.02: return it["in"]+(t-it["tl"])
    return off[-1]["in"]
segs=[]
def _nf(t0,t1):
    return int(round(t1*FPS))-int(round(t0*FPS))
for i,s in enumerate(P.SHOTS):
    NF=_nf(s["t0"],s["t1"]); d=NF/FPS+0.25          # pull extra, then take exactly NF frames
    o=f"{tmp}/s{i:02d}.mp4"
    card_fc=("[0:v]{VF},fps=%f,format=yuva420p[c];[1:v]format=gray[m];[c][m]alphamerge[cd];"
             "color=c=black:s=%dx%d:r=%f[bg];[bg][cd]overlay=50:470:shortest=1,format=yuv420p[v]")%(FPS,W,H,FPS)
    if s["k"]=="a":
        f=fr[round(s["t0"],2)]; S=f["scale"]/100
        sw=max(int(round(1920*S)),CARD); shh=max(int(round(1080*S)),CARD)
        x0=f["px"]*W-sw/2.0; y0=f["py"]*H-shh/2.0
        cxp=max(int(round(50-x0)),0); cyp=max(int(round(470-y0)),0)
        cxp=min(cxp,max(sw-CARD,0)); cyp=min(cyp,max(shh-CARD,0))
        vf=f"scale={sw}:{shh},crop={CARD}:{CARD}:{cxp}:{cyp}"
        sh(["ffmpeg","-v","error","-y","-ss",f"{wt(s['t0']):.4f}","-t",str(d),"-i",AR,"-i",mask,
            "-filter_complex",card_fc.replace("{VF}",vf),"-map","[v]","-frames:v",str(NF),"-an"]+enc+[o])
    elif s["k"]=="b":
        cw,ch,cx,cy=P.CROP[s["src"]]; S=CARD/ch
        vf=f"crop={cw}:{ch}:{cx}:{cy},scale={max(CARD,int(round(cw*S)))}:{max(CARD,int(round(ch*S)))},crop={CARD}:{CARD}"
        sh(["ffmpeg","-v","error","-y","-ss",str(s["ss"]),"-t",str(d),"-i",f"{LIB}/{s['src']}.mp4","-i",mask,
            "-filter_complex",card_fc.replace("{VF}",vf),"-map","[v]","-frames:v",str(NF),"-an"]+enc+[o])
    elif s["k"]=="split":
        SH_=696; m2=rr(CARD,SH_,f"{tmp}/ms.png")
        fc=""
        for j,(nm,ss) in enumerate([(s["top"],s["tss"]),(s["bot"],s["bss"])]):
            cw,ch,cx,cy=P.CROP[nm]; S=SH_/ch
            fc+=f"[{j}:v]crop={cw}:{ch}:{cx}:{cy},scale={max(CARD,int(round(cw*S)))}:{max(CARD,int(round(ch*S)))},crop={CARD}:{SH_},fps={FPS},format=yuva420p[p{j}];"
        fc+=(f"[2:v]format=gray,split=2[m0][m1];[p0][m0]alphamerge[c0];[p1][m1]alphamerge[c1];"
             f"color=c=black:s={W}x{H}:r={FPS}[bg];[bg][c0]overlay=50:258[t1];"
             f"[t1][c1]overlay=50:983:shortest=1,format=yuv420p[v]")
        sh(["ffmpeg","-v","error","-y","-ss",str(s["tss"]),"-t",str(d),"-i",f"{LIB}/{s['top']}.mp4",
            "-ss",str(s["bss"]),"-t",str(d),"-i",f"{LIB}/{s['bot']}.mp4","-i",m2,
            "-filter_complex",fc,"-map","[v]","-frames:v",str(NF),"-an"]+enc+[o])
    else:
        col=(255,255,255) if s["k"]=="dot" or s.get("fill")=="white" else (8,8,8)
        c=Image.new("RGB",(CARD,CARD),col)
        if s["k"]=="dot": ImageDraw.Draw(c).ellipse([CARD//2-26,300,CARD//2+26,352],fill=(12,12,12))
        p=f"{tmp}/c{i}.png"; c.save(p)
        sh(["ffmpeg","-v","error","-y","-loop","1","-t",str(d),"-i",p,"-i",mask,
            "-filter_complex",card_fc.replace("{VF}",f"scale={CARD}:{CARD}"),"-map","[v]","-frames:v",str(NF),"-an"]+enc+[o])
    segs.append(o)
with open(f"{tmp}/l.txt","w") as fh:
    for p in segs: fh.write(f"file '{p}'\n")
pic0=f"{tmp}/pic0.mp4"
sh(["ffmpeg","-v","error","-y","-f","concat","-safe","0","-i",f"{tmp}/l.txt","-vsync","cfr","-r",f"{FPS:.6f}"]+enc+[pic0])
# 🛑 PREVIEW-ONLY REPAIR. Concatenating per-shot segments leaves an occasional black frame at a
# boundary (a seek/keyframe artifact). It does NOT exist in the Premiere timeline, which uses real
# clipitems with in/out points. Replace any all-black card frame with its neighbour.
import numpy as _np
fr=f"{tmp}/fr"; os.makedirs(fr, exist_ok=True)
sh(["ffmpeg","-v","error","-i",pic0,"-vsync","0",f"{fr}/f%05d.png"])
_fs=sorted(glob.glob(f"{fr}/*.png")); _fixed=0
# 🛑 PROTECT INTENTIONAL DARK SHOTS. A black `card` IS a dark card by design — the repair pass
# cannot tell it from a concat artifact and will happily overwrite it with a neighbouring shot,
# silently deleting a beat. (This ate a 1.08s "BEFORE YOU FAIL" card whole.) Exclude every frame
# that falls inside a card/dot shot before repairing anything.
_protected=set()
for _s in P.SHOTS:
    if _s["k"] in ("card","dot"):
        for _k in range(int(round(_s["t0"]*FPS)), int(round(_s["t1"]*FPS))+1):
            _protected.add(_k)
for _i,_p in enumerate(_fs):
    if _i in _protected: continue
    _im=Image.open(_p); _a=_np.asarray(_im.convert("L"))[470:1450,50:1030]
    if _a.mean()<8:
        _src=None
        for _j in range(_i-1,-1,-1):
            if _np.asarray(Image.open(_fs[_j]).convert("L"))[470:1450,50:1030].mean()>=8: _src=_fs[_j]; break
        if _src is None:
            for _j in range(_i+1,len(_fs)):
                if _np.asarray(Image.open(_fs[_j]).convert("L"))[470:1450,50:1030].mean()>=8: _src=_fs[_j]; break
        if _src: Image.open(_src).save(_p); _fixed+=1
print(f"  repaired {_fixed} black boundary frames (preview artifact)")
pic=f"{tmp}/pic.mp4"
sh(["ffmpeg","-v","error","-y","-framerate",f"{FPS:.6f}","-i",f"{fr}/f%05d.png"]+enc+[pic])

# ── MATTED VARIANT: subject matte per PICTURE frame ─────────────────────────────────────────
# Matting the COMPOSITED picture (not the raw A-roll) means the matte is already in canvas space
# — no scale/position maths to get wrong — and it also mattes the B-ROLL subject, which is what
# the reference does (a face on a film clip passes in front of the word too).
MATTE = os.environ.get("CINEMATIC_MATTE", "1") != "0"
_mattes = {}
if MATTE:
    import onnxruntime as _ort
    _MODEL = os.path.expanduser("~/.u2net/u2net_human_seg.onnx")
    if not os.path.exists(_MODEL):
        raise SystemExit("matted variant needs ~/.u2net/u2net_human_seg.onnx")
    _sess = _ort.InferenceSession(_MODEL, providers=["CPUExecutionProvider"])
    _mdir = f"{tmp}/matte"; os.makedirs(_mdir, exist_ok=True)
    _MEAN = _np.array([0.485,0.456,0.406],dtype=_np.float32); _STD = _np.array([0.229,0.224,0.225],dtype=_np.float32)
    from PIL import ImageFilter as _IF
    # 🛑 STRIDE THE MATTE. The model costs ~2s/frame, so every frame is ~24min for a 23s clip.
    # This variant is built on SLOW HELD SHOTS — the subject moves a few px between frames at
    # 30fps — so matting every Nth frame and holding is visually identical and N times faster.
    # Raise MATTE_STRIDE only if the subject is moving fast.
    MATTE_STRIDE = int(os.environ.get("CINEMATIC_MATTE_STRIDE", "3"))
    print(f"  matting {len(_fs)} frames, stride {MATTE_STRIDE} (captions render BEHIND the subject)...")
    _last = None
    for _i,_p in enumerate(_fs):
        if _i % MATTE_STRIDE and _last is not None:
            os.link(_last, f"{_mdir}/m{_i:05d}.png") if not os.path.exists(f"{_mdir}/m{_i:05d}.png") else None
            _mattes[_i] = 1
            continue
        _im = Image.open(_p).convert("RGB")
        _x = _np.asarray(_im.resize((320,320), Image.BILINEAR),dtype=_np.float32)/255.0
        _x = ((_x-_MEAN)/_STD).transpose(2,0,1)[None].astype(_np.float32)
        _o = _sess.run(None, {_sess.get_inputs()[0].name: _x})[0][0,0]
        _o = (_o-_o.min())/(_o.max()-_o.min()+1e-8)
        # 🛑 DO THE EXPENSIVE WORK SMALL. Blurring and PNG-encoding at full 1080x1920 cost ~10s
        # per frame (2h for a 23s clip). The matte is soft by nature, so blur at model resolution
        # and store at HALF size — upscaled on use, visually identical, ~20x faster.
        _m = Image.fromarray((_o*255).astype(_np.uint8)).filter(_IF.GaussianBlur(1.2)).resize((W//2,H//2), Image.BILINEAR)
        # 🛑 WRITE TO DISK, DO NOT HOLD IN RAM. Keeping 590 full-res float32 mattes resident is
        # ~4.9GB and the render crawls on memory pressure rather than compute.
        _m.save(f"{_mdir}/m{_i:05d}.png")
        _last = f"{_mdir}/m{_i:05d}.png"
        _mattes[_i] = 1
        if _i % 120 == 0: print(f"    {_i}/{len(_fs)}", flush=True)
    print(f"  matte built for {len(_mattes)} frames -> disk")
# caption frames — every ACTIVE word is its own layer with its own entrance
cd=f"{tmp}/cap"; os.makedirs(cd)
blank=Image.new("RGBA",(W,H),(0,0,0,0)); blank.save(f"{cd}/_b.png")
cache={c["file"]:Image.open(f"{A}/captions_v2/{c['file']}").convert("RGBA") for c in man}
AN={"right":(-1,0),"left":(1,0),"down":(0,-1),"up":(0,1),"none":(0,0)}
TRAVEL=36.0
OPACITY_FLOOR=0.28   # start part-visible, never at 0
SUBS=6               # motion-blur sub-samples per frame
SHUTTER=1.0          # 360deg. The author is explicit: uncheck 'use composition shutter' and
                     # 'throw this all the way up to 360'. 360deg = the blur samples the WHOLE
                     # frame interval; 180deg (0.5) only smears half of it and still steps.
N=int(round((P.DUR+P.TAIL)*FPS))
for i in range(N):
    t=i/FPS
    active=[c for c in man if c["t0"]<=t<min(c["t1"], P.DUR)]
    if not active:
        shutil.copy(f"{cd}/_b.png", f"{cd}/f{i:05d}.png"); continue
    comp=Image.new("RGBA",(W,H),(0,0,0,0))
    for c in active:
        im=cache[c["file"]]
        el=t-c["t0"]
        anim_s=min(9/FPS, max(c["t1"]-c["t0"]-1/FPS, 1/FPS))
        fade_s=min(c.get("fade_in",2)*2/FPS, anim_s)
        ux,uy=AN.get(c.get("anim","none"),(0,0)); mag=c.get("anim_mag",1.0)
        cur=im
        if el < max(anim_s,fade_s):
            cur=im.copy()
            if el < fade_s:
                # 🛑 OPACITY RAMPS FROM ~28%, NOT FROM ZERO. The author, building the slide from
                # scratch: "make this like about like 30 or 25%, NOT from zero." Starting at 0
                # makes a word blink into being; starting part-visible makes it arrive.
                a0=OPACITY_FLOOR
                f=a0+(1.0-a0)*min(el/fade_s,1.0)
                cur.putalpha(cur.split()[3].point(lambda v:int(v*f)))
            if el < anim_s and (ux or uy):
                # 🛑 MOTION BLUR. His recipe uses the TRANSFORM effect precisely because Motion
                # cannot blur: "turn the shutter angle up -- if this isn't checked the motion blur
                # won't take effect." A hard-edged step per frame is what reads as stepping/glitch.
                # Averaging SUBS sub-positions across the frame's shutter is the same thing.
                def off(e):
                    u=max(0.0,min(e/anim_s,1.0))
                    # 🛑 EASE OUT, not smoothstep. The creator is explicit: "the FIRST keyframe
                    # must be set to ease out." Smoothstep eases in AND out, so it starts slow —
                    # his move starts at full speed and decelerates into its destination, which is
                    # what makes it read as arriving rather than drifting.
                    k = 1-(1-u)**3
                    return (int(round(ux*TRAVEL*mag*(1-k))), int(round(uy*TRAVEL*mag*(1-k))))
                # Blur ONLY inside the word's bbox padded by the travel — averaging six FULL
                # 1080x1920 float canvases per frame was ~300MB/frame and stalled the render.
                bb=cur.split()[3].getbbox()
                if bb:
                    pad=int(TRAVEL*mag)+4
                    x0=max(0,bb[0]-pad); y0=max(0,bb[1]-pad)
                    x1=min(W,bb[2]+pad); y1=min(H,bb[3]+pad)
                    crop=cur.crop((x0,y0,x1,y1)); cw,ch=crop.size
                    acc=np.zeros((ch,cw,4),dtype=np.float32)
                    for si in range(SUBS):
                        e=el+(si/SUBS)*SHUTTER/FPS
                        ox,oy=off(e)
                        sub=Image.new("RGBA",(cw,ch),(0,0,0,0)); sub.paste(crop,(ox,oy))
                        acc+=np.asarray(sub,dtype=np.float32)
                    blurred=Image.fromarray((acc/SUBS).astype(np.uint8),"RGBA")
                    cur=Image.new("RGBA",(W,H),(0,0,0,0)); cur.paste(blurred,(x0,y0))
        # phrase-end fade on the final item
        if c.get("fade"):
            rem=c["t1"]-t
            if rem < 4/FPS:
                cur=cur.copy()
                cur.putalpha(cur.split()[3].point(lambda v:int(v*max(rem/(4/FPS),0))))
        comp=Image.alpha_composite(comp,cur)
    if MATTE and i in _mattes:
        # 🛑 THE WHOLE POINT: erase the caption where the subject is, so he passes IN FRONT of it.
        # Cheaper and more robust than re-compositing the subject on top — same result.
        _mp = f"{_mdir}/m{i:05d}.png"
        if os.path.exists(_mp):
            _mm = _np.asarray(Image.open(_mp).resize((W,H), Image.BILINEAR),dtype=_np.float32)/255.0
            # 🛑 PARTIAL KNOCKOUT, NOT A HARD CUT-OUT. Erasing 100% where the subject is reads as
            # a blunt mask and eats the word. Knocking it back to ~30% leaves the letters visible
            # THROUGH him — which is both softer and closer to the glassy read of the reference.
            _STRENGTH = float(os.environ.get("CINEMATIC_MATTE_STRENGTH", "0.70"))
            _ca = _np.asarray(comp.split()[3],dtype=_np.float32) * (1.0 - _mm * _STRENGTH)
            comp.putalpha(Image.fromarray(_ca.astype(_np.uint8)))
    comp.save(f"{cd}/f{i:05d}.png")
import glob,re as _re
os.makedirs(f"{D}/build",exist_ok=True)
_n=[int(m.group(1)) for f in glob.glob(f"{D}/build/V*_preview.mp4") if (m:=_re.search(r"V(\d+)_preview",f))]
out=f"{D}/build/V{(max(_n)+1) if _n else 1}_preview.mp4"   # AUTO-INCREMENT: never clobber a prior version
total=P.DUR+P.TAIL
sh(["ffmpeg","-v","error","-y","-i",pic,"-framerate",f"{FPS:.6f}","-i",f"{cd}/f%05d.png",
    "-i",f"{A}/VOICE_cut.wav",
    "-stream_loop","-1","-i",MUS,
    "-filter_complex",
    f"[0:v]tpad=stop_mode=clone:stop_duration=0.25,trim=0:{P.DUR:.4f},setpts=PTS-STARTPTS,"
    f"tpad=stop_mode=add:stop_duration={P.TAIL}:color=black[vv];"
    f"[1:v]format=rgba[cap];[vv][cap]overlay=0:0[v];"
    "[2:a]highpass=f=80,loudnorm=I=-16:TP=-1.5:LRA=11[vo];"
    f"[3:a]volume=0.20,afade=t=in:st=0:d=1.0,afade=t=out:st={total-1.5:.2f}:d=1.5[mu];"
    "[vo][mu]amix=inputs=2:duration=first:dropout_transition=0,loudnorm=I=-14:TP=-1.0:LRA=11[a]",
    "-map","[v]","-map","[a]","-t",str(total),
    "-c:v","libx264","-crf","17","-preset","medium","-pix_fmt","yuv420p","-c:a","aac","-b:a","192k",out])
print(out)
