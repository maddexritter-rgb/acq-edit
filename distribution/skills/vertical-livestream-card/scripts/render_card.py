#!/usr/bin/env python3
"""THE vertical-livestream card compositor (locked 2026-08-20, 3 bake-off rounds against a
reference reel, editor-approved: "that's it").

For raw footage that is ALREADY 9:16 (a phone livestream) — NOT a 16:9→9:16 reframe job
(that's horizontal-to-vertical's job). This takes the native-vertical frame and turns it
into a floating card over a blurred duplicate of itself:
  - CARD: a crop of the source, full canvas width, hard corners, headroom-anchored on the
    speaker's face (not a naive center-crop — a low card reads "too zoomed in").
  - BACKGROUND: the same frame, heavily blurred to near-tonal (no readable detail), pushed
    slightly darker so the card reads forward.
  - SHADOW: a PHYSICAL elevation model, not a painted vignette band. Two components:
      ambient  = a tight, low-opacity blur directly under the card silhouette (a whisper).
      key      = the card's own silhouette offset DOWNWARD and blurred WIDE — this is what
                 sells "the card is floating above the background, lit from above." Almost
                 nothing shows above the card; the visible weight is below it.
    (Painting a symmetric shadow BAND at each edge was tried first and rejected twice —
    it reads flat/pasted. The fix was modeling actual light + elevation, not more blur.)

Per-item face-anchoring: probe each cut item's own footage (median face-top over 5 frames)
rather than one fixed crop for the whole clip — a talking head drifts across a livestream.

Usage:
    render_card.py --source <9:16 source.mp4> --spans '[[a,b],[c,d],...]' --out out.mp4
    render_card.py --source <src.mp4> --cuts cuts.json --out out.mp4
        (cuts.json = {"spans": [[a,b],...]} or a bare [[a,b],...] list, SOURCE-time seconds)

Tunables (CLI flags, defaults = the approved look):
    --card-h      card height in the 1080-wide canvas (default 1350 = 4:5)
    --canvas-h    output canvas height (default 1920 = 9:16 at 1080 wide)
    --headroom    fraction of card height to leave above the face top (default 0.22)
"""
import argparse, json, os, pathlib, subprocess, sys
import numpy as np, cv2

YUNET_CANDIDATES = [
    # canonical sibling skill, resolved relative to THIS file so it works from either root
    str(pathlib.Path(__file__).resolve().parents[2] / "horizontal-to-vertical/scripts/yunet.onnx"),
]


def find_yunet():
    for p in YUNET_CANDIDATES:
        if os.path.exists(p):
            return p
    sys.exit("yunet.onnx not found — pass --yunet <path> or install horizontal-to-vertical's model")


def ensure_shadow(work_dir, canvas_h, card_h, wd, cy):
    """Physical elevation shadow: ambient halo (tight, no offset) + key shadow (card
    silhouette offset +30px down, wide blur). See module docstring for why."""
    p = f"{work_dir}/_card_shadow.png"
    ind = np.zeros(canvas_h, np.float32)
    ind[cy:cy + card_h] = 1.0
    amb = cv2.GaussianBlur(ind.reshape(-1, 1), (0, 0), 12).ravel() * 0.28
    ki = np.zeros(canvas_h, np.float32)
    ki[cy + 30:min(canvas_h, cy + card_h + 30)] = 1.0
    key = cv2.GaussianBlur(ki.reshape(-1, 1), (0, 0), 45).ravel() * 0.55
    a = np.clip(amb + key, 0, 1)
    rgba = np.zeros((canvas_h, wd, 4), np.uint8)
    rgba[..., 3] = (a[:, None] * 255).astype(np.uint8)
    cv2.imwrite(p, rgba)
    return p


def face_top(src, t0, t1, yunet_path):
    """Median face-box top (px) over 5 probe frames in [t0, t1] — per-item, not per-clip,
    since a livestreamer drifts across the frame over a long broadcast."""
    det, tops = None, []
    for t in np.linspace(t0 + 0.3, max(t0 + 0.4, t1 - 0.3), 5):
        r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t}", "-i", src, "-frames:v", "1",
                            "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True)
        img = cv2.imdecode(np.frombuffer(r.stdout, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            continue
        h, w = img.shape[:2]
        if det is None:
            det = cv2.FaceDetectorYN.create(yunet_path, "", (w, h), 0.6)
            det.setInputSize((w, h))
        _, faces = det.detect(img)
        if faces is not None and len(faces):
            tops.append(max(faces, key=lambda x: x[2] * x[3])[1])
    return float(np.median(tops)) if tops else canvas_default_top


canvas_default_top = 450.0  # fallback if face detection whiffs on every probe frame


def render(source, spans, out, work_dir, card_h=1350, canvas_h=1920, wd=1080,
           headroom=0.22, yunet_path=None):
    yunet_path = yunet_path or find_yunet()
    cy = (canvas_h - card_h) // 2
    shadow = ensure_shadow(work_dir, canvas_h, card_h, wd, cy)
    segs = []
    for i, (a, b) in enumerate(spans):
        y0 = int(min(max(face_top(source, a, b, yunet_path) - headroom * card_h, 0),
                      canvas_h - card_h))
        seg = f"{work_dir}/_card_seg_{i}.mp4"
        fc = (f"[0:v]split=2[bgs][fgs];"
              f"[bgs]scale=135:240,gblur=sigma=12,scale={wd}:{canvas_h},eq=brightness=-0.09[bg];"
              f"[bg][1:v]overlay=0:0[bgsh];"
              f"[fgs]crop={wd}:{card_h}:0:{y0}[fg];"
              f"[bgsh][fg]overlay=0:{cy}[outv]")
        subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{a}", "-to", f"{b}", "-i", source,
                        "-loop", "1", "-i", shadow,
                        "-filter_complex", fc, "-map", "[outv]", "-map", "0:a",
                        "-c:v", "h264_videotoolbox", "-b:v", "10000k", "-pix_fmt", "yuv420p", "-r", "30",
                        "-c:a", "aac", "-b:a", "256k", "-shortest", "-y", seg], check=True)
        segs.append(seg)
        print(f"  seg {i + 1}/{len(spans)} y0={y0}", flush=True)
    lst = f"{work_dir}/_card_seglist.txt"
    open(lst, "w").write("\n".join(f"file '{s}'" for s in segs))
    subprocess.run(["ffmpeg", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst,
                    "-c", "copy", "-y", out], check=True)
    for s in segs:
        os.remove(s)
    os.remove(lst)
    print("DONE", out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, help="native 9:16 source video")
    ap.add_argument("--spans", help="JSON list of [start,end] source-time seconds")
    ap.add_argument("--cuts", help="path to a cuts JSON ({'spans':[[a,b],...]} or a bare list)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--work-dir", default=None, help="scratch dir (default: alongside --out)")
    ap.add_argument("--card-h", type=int, default=1350)
    ap.add_argument("--canvas-h", type=int, default=1920)
    ap.add_argument("--canvas-w", type=int, default=1080)
    ap.add_argument("--headroom", type=float, default=0.22)
    ap.add_argument("--yunet", default=None)
    a = ap.parse_args()

    if a.spans:
        spans = json.loads(a.spans)
    elif a.cuts:
        d = json.load(open(a.cuts))
        spans = d["spans"] if isinstance(d, dict) else d
    else:
        sys.exit("need --spans or --cuts")

    work_dir = a.work_dir or os.path.dirname(os.path.abspath(a.out)) or "."
    render(a.source, spans, a.out, work_dir, card_h=a.card_h, canvas_h=a.canvas_h,
           wd=a.canvas_w, headroom=a.headroom, yunet_path=a.yunet)


if __name__ == "__main__":
    main()
