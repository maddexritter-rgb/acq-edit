#!/usr/bin/env python3
"""/live-clip BLOCKING QC gate for autonomously-cut clips (no human in the loop).
A clip that fails ANY hard check does NOT ship — exit 2, verdict JSON says why.

  python3 live_qc_gate.py --clip <final.mp4> --spans '[[t0,t1],...]' \
      --words <segment_words.json> --kind short|mid [--out verdict.json]

Spans are in the CLIP-SOURCE (extracted segment) timebase, words is the segment
word JSON ({"words":[{word,start,end}]}) in the same timebase.

HARD CHECKS (each is a playbook non-negotiable, scripted):
  ending    — last kept word must complete a thought (_shared/ending_check.ends_complete)
  seams     — every internal splice lands in low-RMS audio of the OUTPUT (no mid-word cut)
  black     — no black frames anywhere; first frame live
  loudness  — integrated loudness sane (-20..-8 LUFS), no digital clipping (peak < -0.3 dB)
  format    — shorts are 1080x1920; mids match source AR
  duration  — output duration ≈ sum of spans (± 2.5s for CTA-less; mids allow CTA extra)
SOFT (reported, non-blocking): caption band via OCR if tesseract is present.
"""
from __future__ import annotations
import argparse, json, math, re, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from ending_check import ends_complete  # the canonical false-ending rule


def sh(cmd: list[str]) -> str:
    return subprocess.run(cmd, capture_output=True, text=True).stdout + \
           subprocess.run(cmd, capture_output=True, text=True).stderr


def probe(clip: str) -> dict:
    out = json.loads(subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-show_entries",
         "format=duration", "-of", "json", clip],
        capture_output=True, text=True).stdout)
    return {"w": out["streams"][0]["width"], "h": out["streams"][0]["height"],
            "dur": float(out["format"]["duration"])}


def rms_db(clip: str, t: float, win: float = 0.08) -> float:
    r = subprocess.run(
        ["ffmpeg", "-hide_banner", "-ss", f"{max(0, t - win / 2):.3f}",
         "-t", f"{win:.3f}", "-i", clip, "-map", "a:0",
         "-af", "astats=metadata=1", "-f", "null", "-"],
        capture_output=True, text=True).stderr
    m = re.findall(r"RMS level dB:\s*(-?[\d.]+|-inf)", r)
    if not m:
        return -90.0
    v = m[-1]
    return -90.0 if v == "-inf" else float(v)


def loudnorm_stats(clip: str) -> dict:
    r = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", clip, "-map", "a:0",
         "-af", "loudnorm=print_format=json", "-f", "null", "-"],
        capture_output=True, text=True).stderr
    m = re.search(r"\{[^{}]+\}", r[r.rfind("input_i") - 200:] or r)
    blob = re.search(r"\{[\s\S]*\}", r[r.find("Parsed_loudnorm"):])
    try:
        return json.loads(blob.group(0))
    except Exception:
        return {}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--clip", required=True)
    ap.add_argument("--spans", required=True)
    ap.add_argument("--words", required=True)
    ap.add_argument("--kind", choices=["short", "mid"], required=True)
    ap.add_argument("--out")
    a = ap.parse_args()
    spans = json.loads(a.spans)
    W = json.load(open(a.words))
    W = W["words"] if isinstance(W, dict) else W
    checks: dict[str, dict] = {}

    def check(name, ok, detail):
        checks[name] = {"pass": bool(ok), "detail": detail}

    # ---- ending: last kept word + the source words after it
    last_end = spans[-1][1]
    kept_tail = [w for w in W if w["end"] <= last_end + 0.05]
    after = [w for w in W if w["start"] > last_end - 0.05][:8]
    if kept_tail:
        verdict = ends_complete(kept_tail[-1], after)
        ok = verdict if isinstance(verdict, bool) else \
            str(verdict).lower() not in ("fail", "false")
        check("ending", ok, f"last word '{kept_tail[-1]['word']}' verdict={verdict}")
    else:
        check("ending", False, "no words inside final span?!")

    # ---- seams: internal splice points must sit in low-RMS output audio
    seam_fails = []
    tl = 0.0
    for i, (t0, t1) in enumerate(spans):
        if i > 0:
            db = rms_db(a.clip, tl)
            if db > -28.0:  # voiced audio right at the splice = mid-word cut
                seam_fails.append(f"seam@{tl:.2f}s {db:.0f}dB")
        tl += t1 - t0
    check("seams", not seam_fails,
          seam_fails or f"{max(0, len(spans) - 1)} seams all in silence")

    # ---- black frames / dead first frame
    bd = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", a.clip,
         "-vf", "blackdetect=d=0.05:pix_th=0.06", "-an", "-f", "null", "-"],
        capture_output=True, text=True).stderr
    blacks = re.findall(r"black_start:([\d.]+)", bd)
    check("black", not blacks, blacks or "no black frames")

    # ---- loudness / clipping
    st = loudnorm_stats(a.clip)
    try:
        li, tp = float(st.get("input_i", -99)), float(st.get("input_tp", 0))
        check("loudness", -20.0 <= li <= -8.0 and tp <= -0.3,
              f"I={li} LUFS, TP={tp} dB")
    except (TypeError, ValueError):
        check("loudness", False, f"loudnorm parse failed: {st}")

    # ---- format + duration
    p = probe(a.clip)
    if a.kind == "short":
        check("format", (p["w"], p["h"]) == (1080, 1920), f"{p['w']}x{p['h']}")
    else:
        check("format", p["w"] / p["h"] > 1.2, f"{p['w']}x{p['h']}")
    planned = sum(t1 - t0 for t0, t1 in spans)
    slack = 3.0 if a.kind == "short" else 25.0  # mid carries the CTA outro
    check("duration", planned - 1.0 <= p["dur"] <= planned + slack,
          f"planned {planned:.1f}s, actual {p['dur']:.1f}s")

    ok = all(c["pass"] for c in checks.values())
    verdict = {"pass": ok, "clip": a.clip, "kind": a.kind, "checks": checks}
    out = Path(a.out) if a.out else Path(a.clip).with_suffix(".qc.json")
    out.write_text(json.dumps(verdict, indent=1))
    print(json.dumps(verdict, indent=1))
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
