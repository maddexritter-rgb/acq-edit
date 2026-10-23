#!/usr/bin/env python3
"""matte.py — per-frame subject matte, so captions can sit BEHIND the person.

  python3 matte.py <in.mp4> <out_dir> [--every N] [--feather 2] [--thresh 0.5]

The signature of the "matted big-word" variant (references/VARIANT_matted_bigword.md): the caption
is composited UNDER the subject, so a shoulder or a strand of hair passes in front of a huge word.
Verified at pixel level on the reference — letterforms are interrupted by a hard-edged shape with
a light rim, which an overlay can never produce.

Uses u2net_human_seg via onnxruntime (already on disk at ~/.u2net/) — no download, no rembg.
Writes one 8-bit PNG matte per frame, same numbering as the frame extract.

🛑 The matte is only as good as its EDGES. Check them before trusting a render: a hard-thresholded
mask gives a cut-out-with-scissors look that reads worse than no matte at all. `--feather` blurs
the alpha; raise it if hair looks chopped, lower it if the subject looks haloed.
"""
import argparse, os, subprocess, sys
import numpy as np
import onnxruntime as ort
from PIL import Image

MODEL = os.path.expanduser("~/.u2net/u2net_human_seg.onnx")
MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


def load_session():
    if not os.path.exists(MODEL):
        raise SystemExit(f"missing {MODEL} — u2net_human_seg is required for matting")
    return ort.InferenceSession(MODEL, providers=["CPUExecutionProvider"])


def matte_one(sess, img: Image.Image, feather: float):
    w, h = img.size
    x = np.asarray(img.convert("RGB").resize((320, 320), Image.BILINEAR), dtype=np.float32) / 255.0
    x = (x - MEAN) / STD
    x = x.transpose(2, 0, 1)[None].astype(np.float32)
    out = sess.run(None, {sess.get_inputs()[0].name: x})[0][0, 0]
    out = (out - out.min()) / (out.max() - out.min() + 1e-8)
    m = Image.fromarray((out * 255).astype(np.uint8)).resize((w, h), Image.BILINEAR)
    if feather > 0:
        from PIL import ImageFilter
        m = m.filter(ImageFilter.GaussianBlur(feather))
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("outdir")
    ap.add_argument("--fps", default="24000/1001")
    ap.add_argument("--feather", type=float, default=2.0)
    a = ap.parse_args()

    frames = os.path.join(a.outdir, "_frames")
    os.makedirs(frames, exist_ok=True); os.makedirs(a.outdir, exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", a.src, "-vf", f"fps={a.fps}",
                    "-vsync", "0", f"{frames}/f%05d.png"], check=True)
    fs = sorted(f for f in os.listdir(frames) if f.endswith(".png"))
    print(f"  {len(fs)} frames")

    sess = load_session()
    cov = []
    for i, f in enumerate(fs):
        im = Image.open(os.path.join(frames, f))
        m = matte_one(sess, im, a.feather)
        m.save(os.path.join(a.outdir, f))
        if i % 25 == 0:
            arr = np.asarray(m, dtype=float) / 255.0
            cov.append(arr.mean())
            print(f"    {i}/{len(fs)}  subject covers {arr.mean()*100:4.1f}% of frame", flush=True)
    print(f"\n  wrote {len(fs)} mattes -> {a.outdir}")
    if cov:
        print(f"  subject coverage: min {min(cov)*100:.1f}%  max {max(cov)*100:.1f}%")
        if max(cov) < 0.05:
            print("  !! coverage very low — the model may not be finding a person", file=sys.stderr)


if __name__ == "__main__":
    main()
