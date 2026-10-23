#!/usr/bin/env python3
"""THE single-face 16:9 -> 9:16 reframer (locked house style, 2026-06-08).

Y-LOCK (eyeline fixed at clip median, only X keyframes) + face-BOX center (steadier than nose tip).
Use --preset to fire a locked template; explicit args override. Split-screen = run twice + stack
via make_splitscreen.py (or use edit/qa_assembly.py for the full Q&A pipeline).

PRESETS (locked):
  alex-listicle  : Alex talking-head from a desk, 4K master source. zoom 1.6, eye-y 0.25, lock-y,
                   xcenter box. PROVED 2026-06-08 on StayInAGreatMood batch.
  alex-stage     : Alex on Q&A stage with audience in foreground. zoom 1.6, eye-y 0.18, tight
                   upper-left ROI to exclude audience. Used by qa_assembly.py for Alex's cam.
  alex-split-top : Alex in the TOP half of a split-screen stack. zoom 1.4, eye-y 0.22.
  guest          : Guest cam, single-face (NOT the static split-bottom crop). zoom 1.4, eye-y 0.24.
  podcast        : YouTube/podcast source already tightly framed (chest-up). FULL-BLEED full-height
                   crop (subject edge-to-edge), eye-y 0.22, auto scene-split. Use for ANY pre-produced
                   interview/podcast from YouTube. NOTE: the --pullback blur-fill zoom-out was tried and
                   REJECTED 2026-06-10 — the darkened blurred border read as an ugly shadow. Keep
                   full-bleed. PROVED 2026-06-10 on George Janko x Alex Hormozi (PeaceOrPower).

SCENE-SPLIT (--scene-split):
  For multi-angle source (podcasts/interviews with camera switches): detects the camera cuts IN the
  same cv2 read loop used for cropping (mean abs frame-to-frame difference on a 64x36 thumbnail), then
  resets the face tracker at each cut — single pass, per-segment Y-lock + X-smoothing. Detecting in the
  cv2 loop is the whole point: the OLD code detected cuts with ffmpeg and applied them in cv2, and the
  two tools count frames differently, so the boundary landed 1 frame late and the first frame of the
  NEW angle got cropped with the PREVIOUS angle's position (a 1-frame background "flash" at every cut).
  --min-seg debounces multi-frame dissolves into one cut (else a 1-frame micro-segment flashes), and a
  faceless transition frame at a cut holds the previous crop. Auto-enabled for --preset podcast.
  GLITCH FIXED 2026-06-10 on PeaceOrPower (the "plant flash" at camera switches).
  NOTE for assembled/thread clips: concat segments with a RE-ENCODE (concat filter), never `-c copy`,
  and trim ~2 frames off each INTERNAL seam — a stray transition frame at a seam reframes as a flash.
"""
import cv2, numpy as np, subprocess, argparse, sys, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared")); from fast_encode import encoder_args

PRESETS = {
    "alex-listicle":  {"zoom": 1.6, "eye_y": 0.25, "roi": [0.20, 0.05, 0.80, 0.70],
                       "lock_y": True, "xcenter": "box"},   # LOCKED 2026-06-08 (StayInAGreatMood)
    "alex-stage":     {"zoom": 1.6, "eye_y": 0.18, "roi": [0.05, 0.05, 0.82, 0.55],
                       "lock_y": True, "xcenter": "box"},   # Q&A stage cam (qa_assembly default)
    "alex-split-top": {"zoom": 1.4, "eye_y": 0.22, "roi": [0.05, 0.05, 0.82, 0.55],
                       "lock_y": True, "xcenter": "box"},
    "guest":          {"zoom": 1.4, "eye_y": 0.24, "roi": [0.25, 0.15, 0.58, 0.48],
                       "lock_y": True, "xcenter": "box"},
    "podcast":        {"zoom": 1.0, "eye_y": 0.22, "roi": [0.10, 0.05, 0.80, 0.70],
                       "lock_y": True, "lock_x": True, "xcenter": "box"},   # lock_x DEFAULT-ON (2026-06-12): seated talking-head = static frame per angle, NO follow-pan. zoom 1.0 = NO zoom (source already chest-up; any zoom crops the head). full-bleed (pullback REJECTED 2026-06-10).
}

ap = argparse.ArgumentParser()
ap.add_argument("inp"); ap.add_argument("out")
ap.add_argument("--preset", choices=sorted(PRESETS),
                help="Apply a locked template. Explicit args override individual values.")
ap.add_argument("--res", default="1080", choices=["1080", "4k"])
ap.add_argument("--zoom", type=float, default=None)
ap.add_argument("--eye-y", type=float, default=None, dest="eye_y")
ap.add_argument("--roi", type=float, nargs=4, default=None)
ap.add_argument("--detw", type=int, default=1280)
ap.add_argument("--score", type=float, default=0.3)
ap.add_argument("--face-conf", type=float, default=0.5, dest="face_conf",
                help="Minimum face confidence to be a tracking candidate. The detector returns weak "
                     "(0.3-0.5) false positives on plants/shadows; if a big low-conf blob beats the real "
                     "face on size, the crop locks onto background (the 'plant' on a wide profile shot). "
                     "0.5 drops the junk; real faces here are 0.85+. Lower only if a real face is missed.")
ap.add_argument("--robust-profile", action="store_true", dest="robust_profile",
                help="Recover SIDE-PROFILE faces. YuNet is frontal-biased: when the subject turns to "
                     "the side it stops detecting, the crop freezes at the last frontal position and "
                     "the subject walks out of frame (Maddex 2026-08-10: 'whenever Alex turns to the "
                     "side the keyframing stops... it picks back up when he faces the camera'). "
                     "On a miss this retries the frame HORIZONTALLY FLIPPED (YuNet is asymmetric on "
                     "profiles) and then at a lowered confidence, and extrapolates with the last known "
                     "VELOCITY across gaps instead of holding a frozen position.")
ap.add_argument("--smooth", type=int, default=41)
ap.add_argument("--pullback", type=float, default=None,
                help="Zoom OUT past full-height crop: scale the subject to (1-pullback) of the canvas "
                     "and fill the edges with a soft-blurred copy. 0=full-bleed. 0.10 = a subtle "
                     "pull-back (subject at 90 pct). Preset 'podcast' defaults to 0.10; pass --pullback 0 "
                     "for full-bleed. Use when a full-height crop feels too tight.")
ap.add_argument("--lock-y", action="store_true", dest="lock_y", default=None)
ap.add_argument("--lock-x", action="store_true", dest="lock_x", default=None,   # None -> take preset's lock_x (podcast=True). store_true forces ON.
                help="Lock X to the per-segment median (static frame per camera angle) instead of "
                     "smoothing/following the face. Use for SEATED talking-heads where the subject "
                     "shifts/gestures and X-following reads as an unwanted horizontal pan across angles. "
                     "Pairs with scene-split so each angle still gets its own locked X.")
ap.add_argument("--xcenter", default=None, choices=["nose", "box"])
ap.add_argument("--model", default=str(Path(__file__).resolve().parents[2] / "horizontal-to-vertical/scripts/yunet.onnx"))
ap.add_argument("--scene-split", action="store_true", dest="scene_split", default=None,
                help="Detect camera angle switches and reset the face tracker at each one (single pass). "
                     "Auto-enabled for --preset podcast. Disable with --no-scene-split.")
ap.add_argument("--no-scene-split", action="store_false", dest="scene_split")
ap.add_argument("--scene-threshold", type=float, default=0.085,
                help="Cut sensitivity = mean abs frame-to-frame difference (0-1) above which a camera "
                     "switch is declared. Default 0.085. Lower = more sensitive. Detected IN the cv2 "
                     "read loop so the boundary lands on the EXACT frame the new angle begins.")
ap.add_argument("--min-seg", type=int, default=4,
                help="Minimum frames between camera cuts. A dissolve spans 2-3 frames and would "
                     "otherwise register as several cuts, making a 1-frame segment that falls back to "
                     "ROI-center (a background flash). Debouncing to >=4 frames collapses it to one cut.")
ap.add_argument("--cut-frames", default=None,
                help="Comma-separated cv2 frame indices of EXPLICIT cut boundaries (e.g. the content "
                     "seams of an assembled cut, where each cut comes from a different source time on "
                     "the SAME camera angle). When set, the tracker resets at exactly these frames — "
                     "per-cut single-pass tracking (per-segment Y-lock + X-smoothing, ONE render pass, "
                     "no concat) — instead of visual scene auto-detection (which can't see a same-angle "
                     "seam). This is what the render pipeline passes from cut.meta.segments.")
ap.add_argument("--global-y", action="store_true", default=False,
                help="ONE Y-lock for the WHOLE clip (clip-wide eyeline median) even when segments/cut "
                     "frames are present. REQUIRED for same-angle assembled cuts (single locked camera): "
                     "per-segment Y medians differ by a few px per segment, so every seam visibly bumps "
                     "the subject up/down ('jumpy cuts', Maddex 2026-06-12). X stays per-segment. "
                     "Leave OFF for true multicam, where each angle needs its own eyeline.")
a = ap.parse_args()
# Apply preset where not explicitly overridden; otherwise fall back to legacy defaults.
_p = PRESETS[a.preset] if a.preset else {}
if a.zoom    is None: a.zoom    = _p.get("zoom", 1.4)
if a.eye_y   is None: a.eye_y   = _p.get("eye_y", 0.30)
if a.roi     is None: a.roi     = _p.get("roi", [0.05, 0.08, 0.50, 0.45])
if a.lock_y  is None: a.lock_y  = _p.get("lock_y", False)
if a.lock_x  is None: a.lock_x  = _p.get("lock_x", False)   # podcast preset -> lock_x True by default (no follow-pan)
if a.xcenter is None: a.xcenter = _p.get("xcenter", "nose")
if a.pullback is None: a.pullback = _p.get("pullback", 0.0)
if a.scene_split is None: a.scene_split = (a.preset == "podcast")
# Explicit cut boundaries (from an assembled cut) take precedence over visual scene auto-detect:
# reset the tracker at exactly these frames so each cut is framed independently in ONE pass.
_explicit_cuts = None
if a.cut_frames:
    _explicit_cuts = set(int(x) for x in a.cut_frames.replace(" ", "").split(",") if x != "")
    a.scene_split = True  # engage the single-pass per-segment machinery (reset at explicit frames)

# ── SCENE-SPLIT: detect angle switches INSIDE the cv2 read loop (single pass) ──
# Detecting cuts in the SAME frame iterator we crop from guarantees the segment boundary lands on
# the EXACT frame the new angle begins. The old approach detected cuts with ffmpeg (one frame
# indexing) and applied them in cv2 (a different one) — the off-by-one cropped a new-angle frame
# with the PREVIOUS angle's X position (the "plant flash" at every cut). Metric = mean absolute
# frame-to-frame difference on a 64x36 grayscale thumbnail (a spatial-difference measure like
# ffmpeg's `scene`, robust to same-room cuts where color histograms barely change). Fixed 2026-06-10.

cap = cv2.VideoCapture(a.inp); W = int(cap.get(3)); H = int(cap.get(4)); fps = cap.get(5) or 30.0
dw = min(a.detw, W); sc = dw / W; dh = int(H * sc)
det = cv2.FaceDetectorYN.create(a.model, "", (dw, dh), a.score, 0.3, 5000)
rx0, ry0, rx1, ry1 = a.roi
R = (rx0 * dw, ry0 * dh, rx1 * dw, ry1 * dh)

xs, ys, last, hits, n = [], [], None, 0, 0
seg_ids = []  # which segment each frame belongs to (for per-segment Y-lock + smoothing)
cur_seg = 0
_cut_frames = []          # cv2 frame indices where a camera switch begins
_prev_thumb = None        # previous 64x36 grayscale thumbnail for cut detection

# ---- STATIC-FACE (decoy) REJECTION -------------------------------------------------
# A face that never moves is not a person: a projected slide, a poster, a portrait on the
# wall. It is lethal here because the picker prefers CONTINUITY (nearest x to the last
# pick) — so the instant the tracker touches a motionless face it stays locked to it
# forever, since |x - last| == 0 can never be beaten. That is the "keyframing stops and
# Alex walks out of frame" failure, and no ROI can fix it: on this shoot the projected
# face sits at x 0.095 while the subject walks to x 0.015, and elsewhere they are 0.003
# apart. Geometry cannot separate them; motion can.
#
# Online, not a pre-pass: quantize each candidate's position and count it. Once a position
# has been seen STATIC_N times at the SAME quantized spot, treat it as furniture and drop
# it from then on. Opt-in via ACQ_REJECT_STATIC=1 so existing renders are unaffected.
_reject_static = os.environ.get("ACQ_REJECT_STATIC") == "1"
_static_seen = {}
STATIC_N = 6              # hits at one spot before it is called furniture
STATIC_Q = 0.004          # quantization: ~4 px at dw=960. A real head jitters more than this.
STATIC_R = 0.012          # neighbourhood radius (~12px at dw=960) around a confirmed static
                          # centre. Must exceed the sub-pixel wobble of a projected face but
                          # stay well under how far a real person moves between frames.


_static_zones = []        # [(x, y)] normalized centres of confirmed furniture


def _static_hit(f, dw_):
    """True if this candidate is furniture.

    Matching on an exact quantized key was too brittle: a projected face wobbles by a
    sub-pixel amount and crosses bucket boundaries, and every NEW bucket starts its count
    at zero — so the decoy was re-admitted for several frames each time it drifted, which
    is how it still dragged the crop off Alex after the blacklist "fired" (16 positions
    blacklisted, yet the tail of the range still panned to the slide). Test a NEIGHBOURHOOD
    instead: anything within STATIC_R of a confirmed static centre is the same furniture.
    """
    x = float(f[0]) / dw_
    y = float(f[1]) / dw_
    for zx, zy in _static_zones:
        if abs(x - zx) <= STATIC_R and abs(y - zy) <= STATIC_R:
            return True
    k = (round(x / STATIC_Q), round(y / STATIC_Q))
    _static_seen[k] = _static_seen.get(k, 0) + 1
    if _static_seen[k] > STATIC_N:
        _static_zones.append((x, y))
        return True
    return False


def _prescan_statics():
    """Find the motionless faces BEFORE tracking starts.

    Building the blacklist online is too late: the tracker locks onto the decoy for the
    first STATIC_N frames and then slides off it, which reads as an unmotivated pan at the
    head of the segment. A cheap pre-pass (grab() to skip, retrieve() only on sampled
    frames) means the furniture is already known at frame 1.

    Measured on ContentVolume: the projected face sat at EXACTLY x0.107 y0.259 in every
    sample while Alex moved 0.516->0.598, so 'never moves' separates them cleanly where
    no ROI could — the decoy's centre was inside the box by 0.008.
    """
    cap2 = cv2.VideoCapture(a.inp)
    seen, i = {}, 0
    while True:
        if not cap2.grab():
            break
        if i % PRESCAN_EVERY == 0:
            ok, fr = cap2.retrieve()
            if ok:
                _, fs = det.detect(cv2.resize(fr, (dw, dh)))
                if fs is not None:
                    for f in fs:
                        k = (round(float(f[0]) / dw / STATIC_Q),
                             round(float(f[1]) / dw / STATIC_Q))
                        seen[k] = seen.get(k, 0) + 1
        i += 1
    cap2.release()
    hard = {k: STATIC_N * 100 for k, v in seen.items() if v >= PRESCAN_MIN}
    _static_seen.update(hard)
    # seed the neighbourhood zones too — a counter alone only blocks the exact bucket
    for (kx, ky) in hard:
        _static_zones.append((kx * STATIC_Q, ky * STATIC_Q))
    return len(hard), i


PRESCAN_EVERY = 12        # sample ~2x/second at 24fps; enough to prove a face never moves
PRESCAN_MIN = 4           # same quantized spot this many times in the pre-pass = furniture
if _reject_static:
    _nblk, _nfr = _prescan_statics()
    print(f"  [reframe] pre-scan: {_nblk} motionless face position(s) blacklisted before "
          f"tracking ({_nfr} frames scanned)", flush=True)

while True:
    ok, fr = cap.read()
    if not ok: break
    small = cv2.resize(fr, (dw, dh))
    if _explicit_cuts is not None:
        # EXPLICIT cut boundaries: reset the tracker at exactly these frames (per-cut, single pass).
        if n in _explicit_cuts and n > 0:
            last = None
            cur_seg += 1
            if not _cut_frames or _cut_frames[-1] != n:
                _cut_frames.append(n)
    elif a.scene_split:
        thumb = cv2.resize(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY), (64, 36)).astype(np.float32)
        if _prev_thumb is not None and n > 0:
            diff = float(np.mean(np.abs(thumb - _prev_thumb))) / 255.0
            if diff > a.scene_threshold and (not _cut_frames or n - _cut_frames[-1] >= a.min_seg):
                last = None      # new camera angle — start fresh, don't follow the previous speaker
                cur_seg += 1
                _cut_frames.append(n)   # debounced: a multi-frame dissolve = ONE cut, no micro-segment
        _prev_thumb = thumb
    seg_ids.append(cur_seg)
    n += 1
    _, faces = det.detect(small)
    cand = []
    if faces is not None:
        for f in faces:
            cx, cy = f[0] + f[2] / 2, f[1] + f[3] / 2
            if R[0] <= cx <= R[2] and R[1] <= cy <= R[3] and f[-1] >= a.face_conf:
                cand.append(f)
    if not cand and a.robust_profile:
        # RETRY 1: horizontally flipped — YuNet detects a left-facing profile far better than
        # the mirrored right-facing one (and vice versa), so flipping recovers half the misses.
        _fl = cv2.flip(small, 1)
        _, ff = det.detect(_fl)
        if ff is not None:
            for f in ff:
                f = f.copy()
                f[0] = dw - f[0] - f[2]                      # mirror the box back
                for _k in (4, 6, 8, 10, 12):                 # mirror the landmark x's
                    if _k < len(f) - 1: f[_k] = dw - f[_k]
                cx, cy = f[0] + f[2] / 2, f[1] + f[3] / 2
                if R[0] <= cx <= R[2] and R[1] <= cy <= R[3] and f[-1] >= a.face_conf * 0.72:
                    cand.append(f)
        # RETRY 2: same frame, lowered bar — a true profile scores well under a frontal face.
        if not cand and faces is not None:
            for f in faces:
                cx, cy = f[0] + f[2] / 2, f[1] + f[3] / 2
                if R[0] <= cx <= R[2] and R[1] <= cy <= R[3] and f[-1] >= a.face_conf * 0.55:
                    cand.append(f)
    # After the profile retries, so a lowered-bar pass cannot re-admit the furniture.
    if _reject_static and cand:
        _live = [f for f in cand if not _static_hit(f, dw)]
        if _live:
            cand = _live      # keep the static one only if it is genuinely all we have
    pick = None
    if cand:
        if last is not None:
            pick = min(cand, key=lambda f: abs(f[8] - last))
            if abs(pick[8] - last) > 0.15 * dw:
                pick = max(cand, key=lambda f: f[2] * f[3] * f[-1])   # area x confidence: a big low-conf false blob can't beat the real face
        else:
            pick = max(cand, key=lambda f: f[2] * f[3] * f[-1])
    if pick is not None:
        xc = (pick[0] + pick[2] / 2) if a.xcenter == "box" else float(pick[8])
        xs.append(xc / sc); ys.append(float(pick[5] + pick[7]) / 2 / sc)
        last = float(pick[8]); hits += 1
    else:
        xs.append(np.nan); ys.append(np.nan)
cap.release()
if a.scene_split:
    print(f"scene-split: {len(_cut_frames)+1} segments, cuts at frames {_cut_frames}", flush=True)
seg_ids = np.array(seg_ids)
n_segs_actual = int(seg_ids.max()) + 1 if len(seg_ids) else 1
def _fill(idx, good, vals, limit):
    """Interpolate detection gaps; EXTRAPOLATE the leading/trailing gaps with the last known
    velocity instead of numpy's flat hold. A frozen hold is what lets a walking subject leave
    the frame while the tracker waits for his face to come back (side-profile dropout)."""
    gi = idx[good]; gv = vals[good]
    if len(gi) == 0: return vals
    out = np.interp(idx, gi, gv)
    if len(gi) >= 2 and not bool(np.asarray(good).all()):
        SPAN, CAP = 8, 0.45          # frames used to estimate velocity; cap the drift
        head = idx < gi[0]
        if head.any():
            k = min(SPAN, len(gi) - 1)
            v = (gv[k] - gv[0]) / max(1e-6, (gi[k] - gi[0]))
            ext = gv[0] + v * (idx[head] - gi[0])
            out[head] = np.clip(ext, gv[0] - CAP * limit, gv[0] + CAP * limit)
        tail = idx > gi[-1]
        if tail.any():
            k = min(SPAN, len(gi) - 1)
            v = (gv[-1] - gv[-1 - k]) / max(1e-6, (gi[-1] - gi[-1 - k]))
            ext = gv[-1] + v * (idx[tail] - gi[-1])
            out[tail] = np.clip(ext, gv[-1] - CAP * limit, gv[-1] + CAP * limit)
    return np.clip(out, 0, limit)


xs, ys = np.array(xs, float), np.array(ys, float)
idx = np.arange(n); good = ~np.isnan(xs)
if good.sum() == 0:
    fx, fy = (rx0 + rx1) / 2 * W, (ry0 + ry1) / 2 * H
    xs[:] = fx; ys[:] = fy
    print(f"  no face in ROI -> static ROI-center fallback ({fx/W:.2f},{fy/H:.2f})", flush=True)
elif n_segs_actual > 1:
    # Per-segment interpolation: don't interpolate across scene boundaries
    for s in range(n_segs_actual):
        mask = seg_ids == s
        seg_idx = np.where(mask)[0]
        seg_good = good[mask]
        if seg_good.sum() == 0:
            fx, fy = (rx0 + rx1) / 2 * W, (ry0 + ry1) / 2 * H
            xs[mask] = fx; ys[mask] = fy
        elif seg_good.sum() < mask.sum():
            xs[mask] = _fill(seg_idx, seg_good, xs[mask], W)
            ys[mask] = _fill(seg_idx, seg_good, ys[mask], H)
else:
    xs = _fill(idx, good, xs, W); ys = _fill(idx, good, ys, H)


def smooth(arr, win):
    win = max(3, win | 1); m = arr.copy()
    for i in range(len(arr)):
        m[i] = np.median(arr[max(0, i - 2):i + 3])
    pad = np.pad(m, (win // 2, win // 2), mode="edge")
    return np.convolve(pad, np.ones(win) / win, mode="valid")[:len(arr)]


# Per-segment smoothing: don't smooth X across scene boundaries (that causes the slide)
if n_segs_actual > 1:
    xss = np.zeros_like(xs); yss = np.zeros_like(ys)
    for s in range(n_segs_actual):
        mask = seg_ids == s
        if mask.sum() == 0: continue
        xss[mask] = smooth(xs[mask], a.smooth)
        yss[mask] = smooth(ys[mask], a.smooth)
else:
    xss, yss = smooth(xs, a.smooth), smooth(ys, a.smooth)
# X-LOCK: pin X to the per-segment median so a seated subject's shifts/gestures don't read as a
# horizontal pan across camera angles (mirrors the Y-lock). Each scene segment keeps its own static X.
if a.lock_x:
    if n_segs_actual > 1:
        for s in range(n_segs_actual):
            mask = seg_ids == s
            if mask.sum(): xss[mask] = float(np.median(xss[mask]))
    else:
        xss[:] = float(np.median(xss))
OW, OH = (2160, 3840) if a.res == "4k" else (1080, 1920)
cropH = min(H, int(round(H / a.zoom))); cropW = min(W, int(round(cropH * 9 / 16)))
# Per-segment Y-lock: each camera angle gets its own eyeline median.
# --global-y overrides: same-angle assembled cuts keep ONE clip-wide eyeline (no per-seam Y bumps).
if n_segs_actual > 1 and a.lock_y and not a.global_y:
    y_lock_per_seg = {}
    for s in range(n_segs_actual):
        mask = seg_ids == s
        seg_y = yss[mask]
        y_lock_per_seg[s] = float(np.median(seg_y)) if len(seg_y) else float(np.median(yss))
    y_lock = None  # signal to use per-seg in the render loop
    print(f"{W}x{H} {fps:.1f}fps {n}f | hits {hits} ({100*hits//max(1,n)}%) | "
          f"x {xss.min()/W:.2f}-{xss.max()/W:.2f} | y LOCKED per-seg "
          f"{{{', '.join(f'{s}:@{v/H:.2f}' for s,v in y_lock_per_seg.items())}}} | "
          f"center={a.xcenter} | {n_segs_actual} segments", flush=True)
else:
    y_lock = float(np.median(yss))
    y_lock_per_seg = None
    if _reject_static:
        _bl = sum(1 for v in _static_seen.values() if v > STATIC_N)
        print(f"  [reframe] static-face rejection ON — {_bl} motionless position(s) blacklisted "
              f"(projected slides / posters cannot capture the tracker)", flush=True)
    print(f"{W}x{H} {fps:.1f}fps {n}f | hits {hits} ({100*hits//max(1,n)}%) | x {xss.min()/W:.2f}-{xss.max()/W:.2f} | "
          f"y {'LOCKED@%.2f' % (y_lock/H) if a.lock_y else 'tracked~%.2f' % (yss.mean()/H)} | center={a.xcenter}", flush=True)
# Frames at/just after a cut where NO face was detected = the dissolve/transition frame. Holding the
# previous good crop for that 1 frame is invisible at a hard cut; showing its interpolated/fallback
# crop is the background flash. Build the boundary set once.
_cut_set = set(_cut_frames) | {c + 1 for c in _cut_frames}
ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr24",
    "-s", f"{OW}x{OH}", "-r", f"{fps}", "-i", "-", "-i", a.inp, "-map", "0:v", "-map", "1:a?",
    *encoder_args(OW, OH, "ffmpeg", tier="intermediate"),
    "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", a.out], stdin=subprocess.PIPE)
cap = cv2.VideoCapture(a.inp)
prev_crop, prev_cm, _held = None, 255.0, 0
for i in range(n):
    ok, fr = cap.read()
    if not ok: break
    x0 = max(0, min(W - cropW, int(round(xss[i] - cropW / 2))))
    if y_lock_per_seg is not None:
        yc = y_lock_per_seg[seg_ids[i]]
    elif a.lock_y:
        yc = y_lock
    else:
        yc = yss[i]
    y0 = max(0, min(H - cropH, int(round(yc - a.eye_y * cropH))))
    crop = fr[y0:y0 + cropH, x0:x0 + cropW]
    cm = float(crop[::8, ::8].mean())                      # brightness of the CROP, not the full frame
    # Hold the last good crop ONLY for a transient dark grab (tracker briefly caught a dark foreground),
    # NEVER at a scene cut and never for more than 1 frame. At a camera switch the per-segment interpolated
    # position IS the correct new angle; holding the previous crop there shows the OLD angle for a frame =
    # the "dead frame" between shots (the bug Maddex caught 2026-06-11). Let the new-angle crop through.
    if prev_crop is not None and cm < 50.0 < prev_cm and _held < 1 and i not in _cut_set:
        crop = prev_crop; _held += 1
    else:
        prev_crop, prev_cm, _held = crop.copy(), cm, 0
    if a.pullback > 0:                                     # zoom out: subject at (1-pullback), soft-blurred fill behind
        fgw = int(round(OW * (1 - a.pullback))); fgh = int(round(OH * (1 - a.pullback)))
        fg = cv2.resize(crop, (fgw, fgh), interpolation=cv2.INTER_LANCZOS4)
        bg = cv2.resize(crop, (OW, OH), interpolation=cv2.INTER_LANCZOS4)
        bg = cv2.GaussianBlur(bg, (0, 0), sigmaX=OW * 0.025)
        bg = (bg.astype(np.float32) * 0.62).astype(np.uint8)   # darken so the subject pops
        yoff = int(round((OH - fgh) * 0.42)); xoff = (OW - fgw) // 2   # bias slightly high for headroom
        bg[yoff:yoff + fgh, xoff:xoff + fgw] = fg
        ff.stdin.write(bg.tobytes())
    else:
        ff.stdin.write(cv2.resize(crop, (OW, OH), interpolation=cv2.INTER_LANCZOS4).tobytes())
ff.stdin.close(); ff.wait(); cap.release()
print("_reframe_v2 ->", a.out)
