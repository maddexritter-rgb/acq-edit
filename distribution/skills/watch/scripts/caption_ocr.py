#!/usr/bin/env python3
"""Caption placement + presence detector for burnt-in 9:16 captions (+ advisory OCR).

WHAT'S RELIABLE — placement & presence. From the brightness profile of the white
caption text it reports, per moment, whether a caption is on screen and its
vertical y-center (% of height). This powers audit #3 (lower-half / not covering
face) and #7 (safezone). Verified accurate (e.g. y-center 67.4% matched eye).

WHAT'S ADVISORY — the OCR text. Stylized captions over busy video OCR imperfectly;
tesseract gets some frames clean and mangles others. Treat the text as a hint.
For the EXACT caption text + spelling, read a contact_sheet.py PNG with your own
eyes (Claude reads stylized captions far better than tesseract) — that is the
intended primary path.

Usage:
  caption_ocr.py INPUT [--interval 0.5] [--start 0] [--end DUR]
                       [--band-lo 0.45] [--no-ocr] [--out JSON]
Writes temp frames next to --out (accessible path), cleaned up on exit.
"""
import argparse, os, sys, json, re, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _util import ffprobe_duration, ffprobe_dims, fmt_ts, run
from PIL import Image
import numpy as np


def detect_caption(arr, band_lo, band_hi=None):
    """arr: HxWx3 uint8 full frame. Returns (present, y_center_pct, (row0,row1))
    using the dominant run of bright, neutral (white) text rows in the band.
    band_hi (fraction) caps the search below the caption zone so lower set-dressing
    (a guest's white name-badge/lanyard, bottom UI) can't be mistaken for a caption."""
    H, W = arr.shape[:2]
    lo = int(H * band_lo)
    hi = int(H * band_hi) if band_hi else H
    band = arr[lo:hi]
    R, G, B = (band[:, :, i].astype(int) for i in range(3))
    mx = np.maximum(np.maximum(R, G), B)
    mn = np.minimum(np.minimum(R, G), B)
    white = (mn > 190) & ((mx - mn) < 35)          # near-white AND neutral
    rc = white.sum(axis=1)
    thr = 0.05 * W                                  # a caption line spans >5% of width
    if rc.size == 0 or rc.max() < thr:
        return False, None, None
    peak = int(rc.argmax())
    cutoff = max(rc[peak] * 0.4, thr)
    r0 = r1 = peak
    while r0 > 0 and rc[r0 - 1] >= cutoff:
        r0 -= 1
    while r1 < len(rc) - 1 and rc[r1 + 1] >= cutoff:
        r1 += 1
    yc = lo + (r0 + r1) / 2
    return True, round(100 * yc / H, 1), (lo + r0, lo + r1)


def ocr_line(frame_png, rowrange, W, workdir):
    """Advisory: crop the detected caption row, binarize + upscale, OCR."""
    r0, r1 = rowrange
    pad = 18
    y0 = max(r0 - pad, 0)
    h = (r1 - r0) + 2 * pad
    crop = os.path.join(workdir, "line.png")
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", frame_png,
         "-vf", f"crop={W}:{h}:0:{y0}", crop])
    if not os.path.exists(crop):
        return ""
    a = np.asarray(Image.open(crop).convert("L"))
    b = Image.fromarray(np.where(a > 200, 0, 255).astype("uint8"))
    b = b.resize((b.width * 2, b.height * 2), Image.LANCZOS)
    bp = os.path.join(workdir, "bin.png")
    b.save(bp)
    best = ""
    for psm in ("6", "7", "11"):
        txt = re.sub(r"\s+", " ", run(["tesseract", bp, "stdout", "-l", "eng", "--psm", psm]).stdout).strip()
        if len(re.findall(r"[A-Za-z]", txt)) > len(re.findall(r"[A-Za-z]", best)):
            best = txt
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("--interval", type=float, default=0.5)
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--end", type=float, default=None)
    ap.add_argument("--band-lo", type=float, default=0.45,
                    help="fraction of height to start searching for captions")
    ap.add_argument("--band-hi", type=float, default=None,
                    help="fraction of height to STOP searching (caps the band below the caption zone)")
    ap.add_argument("--no-ocr", action="store_true", help="skip advisory OCR (placement only, faster)")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    out = a.out or os.path.splitext(a.input)[0] + "_captions.json"
    workdir = os.path.join(os.path.dirname(os.path.abspath(out)) or ".", f".watch_tmp_{os.getpid()}")
    os.makedirs(workdir, exist_ok=True)
    try:
        W, H = ffprobe_dims(a.input)
        dur = ffprobe_duration(a.input)
        end = a.end or dur
        rows = []
        t = a.start
        while t <= end:
            fp = os.path.join(workdir, "f.png")
            run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t:.3f}", "-i", a.input,
                 "-frames:v", "1", fp])
            present, yc, text = False, None, ""
            if os.path.exists(fp):
                arr = np.asarray(Image.open(fp).convert("RGB"))
                present, yc, rr = detect_caption(arr, a.band_lo, a.band_hi)
                if present and not a.no_ocr:
                    text = ocr_line(fp, rr, W, workdir)
            rows.append({"t": round(t, 2), "present": present, "yc": yc, "text": text})
            t += a.interval

        spans, cur = [], None
        for r in rows:
            if r["present"]:
                if cur is None:
                    cur = {"start": r["t"], "end": r["t"], "_yc": [r["yc"]], "_tx": [r["text"]]}
                else:
                    cur["end"] = r["t"]; cur["_yc"].append(r["yc"]); cur["_tx"].append(r["text"])
            elif cur:
                spans.append(cur); cur = None
        if cur:
            spans.append(cur)
        for s in spans:
            ycs = [v for v in s.pop("_yc") if v is not None]
            s["y_center_pct"] = round(float(np.median(ycs)), 1) if ycs else None
            txs = [x for x in s.pop("_tx") if x]
            s["ocr_text"] = max(txs, key=lambda x: len(re.findall(r"[A-Za-z]", x))) if txs else ""

        ycs = [r["yc"] for r in rows if r["yc"] is not None]
        present_pct = round(100 * sum(r["present"] for r in rows) / len(rows), 0) if rows else 0
        placement = {
            "frames_with_caption_pct": present_pct,
            "y_center_min": min(ycs) if ycs else None,
            "y_center_max": max(ycs) if ycs else None,
            "y_center_median": round(float(np.median(ycs)), 1) if ycs else None,
        }
        flags = []
        if ycs and min(ycs) < 50:
            flags.append(f"caption rises above 50% height (min y-center {min(ycs)}%) — may cover the face (audit #3)")
        if ycs and max(ycs) > 92:
            flags.append(f"caption sits very low (max y-center {max(ycs)}%) — risk of bottom UI-safezone overlap (audit #7)")

        result = {"input": a.input, "dims": [W, H], "interval": a.interval,
                  "caption_spans": spans, "placement": placement, "flags": flags}
        json.dump(result, open(out, "w"), indent=2)

        print(f"# Captions: {os.path.basename(a.input)}  ({W}x{H}, {dur:.1f}s)")
        print(f"caption on screen {present_pct:.0f}% of sampled frames; {len(spans)} caption spans")
        print(f"placement y-center: median {placement['y_center_median']}%  "
              f"range {placement['y_center_min']}-{placement['y_center_max']}%  (SOP target ~65-80% = below chin)")
        for f in flags:
            print("  WARN " + f)
        print("---- timeline (ocr text is ADVISORY — read a contact sheet for exact text) ----")
        for s in spans:
            print(f"[{fmt_ts(s['start'])}-{fmt_ts(s['end'])}] y{s['y_center_pct']}%  ~{s['ocr_text']!r}")
        print("json:", out)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    main()
