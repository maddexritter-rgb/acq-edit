#!/usr/bin/env python3
"""Ears + pacing probe — loudness, peaks, silence, black frames, scene cuts.

Self-contained (ffmpeg only). Complements the MCP's video_analyze; gives you raw
numbers against the Team Alex audio gate (peak ~-6 dB, true peak <= -6 dB,
music-not-drowning-dialogue) without needing the MCP up.

Usage: probe.py INPUT [--out JSON]
"""
import argparse, os, sys, re, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _util import run, ffprobe_duration


def grab(pattern, text, cast=float, default=None, last=False):
    # ebur128 prints running values then a final SUMMARY; take last= for the summary
    ms = re.findall(pattern, text)
    if not ms:
        return default
    return cast(ms[-1] if last else ms[0])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    dur = ffprobe_duration(a.input)
    res = {"input": a.input, "duration": round(dur, 2)}

    t = run(["ffmpeg", "-hide_banner", "-nostats", "-i", a.input,
             "-af", "ebur128=peak=true", "-f", "null", "-"]).stderr
    res["loudness_LUFS_integrated"] = grab(r"I:\s*(-?\d+\.?\d*)\s*LUFS", t, last=True)
    res["loudness_range_LU"] = grab(r"LRA:\s*(-?\d+\.?\d*)\s*LU", t, last=True)
    res["true_peak_dBFS"] = grab(r"Peak:\s*(-?\d+\.?\d*)\s*dBFS", t, last=True)

    t = run(["ffmpeg", "-hide_banner", "-nostats", "-i", a.input,
             "-af", "volumedetect", "-f", "null", "-"]).stderr
    res["max_volume_dB"] = grab(r"max_volume:\s*(-?\d+\.?\d*) dB", t)
    res["mean_volume_dB"] = grab(r"mean_volume:\s*(-?\d+\.?\d*) dB", t)

    t = run(["ffmpeg", "-hide_banner", "-nostats", "-i", a.input,
             "-af", "silencedetect=noise=-30dB:d=0.3", "-f", "null", "-"]).stderr
    sil = re.findall(r"silence_duration:\s*(\d+\.?\d*)", t)
    res["silence_total_s"] = round(sum(float(x) for x in sil), 2)
    res["silence_segments"] = len(sil)
    res["silence_pct"] = round(100 * res["silence_total_s"] / dur, 1) if dur else None

    t = run(["ffmpeg", "-hide_banner", "-nostats", "-i", a.input,
             "-vf", "blackdetect=d=0.05:pix_th=0.10", "-f", "null", "-"]).stderr
    res["black_segments"] = len(re.findall(r"black_start", t))

    t = run(["ffmpeg", "-hide_banner", "-nostats", "-i", a.input,
             "-vf", "select='gt(scene,0.4)',metadata=print", "-an", "-f", "null", "-"]).stderr
    res["scene_cuts"] = len(re.findall(r"scene_score", t))

    notes = []
    mv = res["max_volume_dB"]
    if mv is not None:
        if mv > -3:
            notes.append(f"max volume {mv} dB is HOT (>-3) — clipping risk")
        elif mv < -9:
            notes.append(f"max volume {mv} dB is quiet (<-9) — target peak ~-6 dB")
    tp = res["true_peak_dBFS"]
    if tp is not None and tp > -6:
        notes.append(f"true peak {tp} dBFS exceeds the -6 dB TP gate")
    if res["silence_pct"] is not None and res["silence_pct"] < 2:
        notes.append("almost no silence — music may be drowning dialogue (check #9), or it's wall-to-wall talk")
    res["notes"] = notes

    out = a.out or os.path.splitext(a.input)[0] + "_probe.json"
    json.dump(res, open(out, "w"), indent=2)
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
