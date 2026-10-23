#!/usr/bin/env python3
"""chin_layout.py — per-ANGLE caption Y for a reframed 9:16 clip.

Replaces the (missing) layout_analyze: samples the video, detects the largest face per
sample with YuNet, and sets the caption safe-Y just BELOW that shot's chin. Tight CUs
(face fills frame, low chin) -> low caption; wide/medium shots (chin high) -> higher
caption. Emits the layout.json schema generate_spice consumes:
  {"meta":{"fps":F},"segments":[{"start_i":frame,"end_i":frame,"safe_y_pct":0.xx}]}

Usage: chin_layout.py IN.mp4 OUT.json [--margin 0.035] [--every 0.33]
"""
import cv2, sys, json, argparse

MODEL="__ACQ_SKILLS__/horizontal-to-vertical/scripts/yunet.onnx"

ap=argparse.ArgumentParser()
ap.add_argument("inp"); ap.add_argument("out")
ap.add_argument("--margin", type=float, default=0.03)
ap.add_argument("--beard", type=float, default=0.45)  # fraction of face height to clear (beard)
ap.add_argument("--every", type=float, default=0.33)    # sample interval (s)
ap.add_argument("--lo", type=float, default=0.56)       # clamp: never above this
ap.add_argument("--hi", type=float, default=0.84)       # clamp: never below this
a=ap.parse_args()

cap=cv2.VideoCapture(a.inp)
W=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)); H=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
FPS=cap.get(cv2.CAP_PROP_FPS) or 30.0
N=int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
det=cv2.FaceDetectorYN.create(MODEL,"",(W,H),score_threshold=0.6)
det.setInputSize((W,H))

step=max(1,int(FPS*a.every))
raw=[]  # (frame_idx, chin_y_or_None)
f=0
while f < N:
    cap.set(cv2.CAP_PROP_POS_FRAMES, f)
    ok,fr=cap.read()
    if not ok: break
    _,faces=det.detect(fr)
    y=None
    if faces is not None and len(faces):
        big=max(faces, key=lambda r:r[2]*r[3])
        # YuNet box ends at the JAW; a beard extends below it ~proportional to face height.
        # Place caption below the beard: box_bottom + BEARD*box_height. Scales per angle
        # (tight CU = tall box = lower caption; wide = short box = higher).
        box_bottom=float(big[1]+big[3]); box_h=float(big[3])
        y=(box_bottom + a.beard*box_h)/H + a.margin
    raw.append([f, y])
    f+=step
cap.release()

# fill gaps (B-roll/no face) by holding nearest neighbour
vals=[v for _,v in raw if v is not None]
fill=vals[0] if vals else 0.74
for r in raw:
    if r[1] is None: r[1]=fill
    else: fill=r[1]

# median-smooth over a ~1.5s window to kill per-frame jitter
import statistics
win=max(1,int(1.5/a.every))
sm=[]
for i in range(len(raw)):
    lo=max(0,i-win//2); hi=min(len(raw),i+win//2+1)
    sm.append(min(a.hi,max(a.lo, statistics.median(raw[j][1] for j in range(lo,hi)))))

# build sections: new section only when smoothed Y shifts > 0.05 from the section anchor
segs=[]
for i,(idx,_) in enumerate(raw):
    y=round(sm[i],3)
    if segs and abs(segs[-1]["_y"]-y)<=0.05:
        segs[-1]["end_i"]=idx+step-1
    else:
        segs.append({"start_i":idx,"end_i":idx+step-1,"_y":y})
# merge any section shorter than ~1.0s into the previous (avoid bouncing)
minlen=int(FPS*1.0)
merged=[segs[0]]
for s in segs[1:]:
    if (s["end_i"]-s["start_i"])<minlen:
        merged[-1]["end_i"]=s["end_i"]
    else:
        merged.append(s)
out={"meta":{"fps":FPS},"segments":[{"start_i":int(s["start_i"]),"end_i":int(min(s["end_i"],N-1)),
       "safe_y_pct":round(float(s["_y"]),3)} for s in merged]}
json.dump(out, open(a.out,"w"))
print(f"chin_layout: {len(out['segments'])} sections, Y range "
      f"{min(s['safe_y_pct'] for s in out['segments']):.2f}-{max(s['safe_y_pct'] for s in out['segments']):.2f}")
