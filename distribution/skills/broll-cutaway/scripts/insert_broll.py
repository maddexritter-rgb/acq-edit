#!/usr/bin/env python3
"""Insert full-screen B-roll cutaways (with a flash/glare transition) into a vertical clip.

Each insert replaces the WHOLE frame with cropped-to-fill B-roll footage for a couple seconds,
bracketed by a white flash-in -> glare-sweep -> flash-out so the cut reads as intentional. The
base clip's audio is preserved. Captions are NOT added here -- burn them AFTER, on the output
(2-pass), via caption-clips (a subtitles filter as the last node eats the overlay pad).

  insert_broll.py --base BASE.mp4 --out OUT.mp4 --spec inserts.json
  insert_broll.py --base BASE.mp4 --out OUT.mp4 \
      --insert src=code.mp4,at=4.8,in=7.0,dur=2.0 --insert src=money.mp4,at=37.3,in=23.0

inserts.json: [{"src": "...", "at": 4.8, "in": 7.0, "dur": 2.0}, ...]
  src : B-roll source file (any aspect/res; auto-cropped to fill the base frame)
  at  : start time on the BASE timeline (seconds)
  in  : in-point inside src (seconds, default 0)
  dur : insert length (seconds, default 2.0)

ACQ standard: encodes via _shared/fast_encode.py (VideoToolbox). Never hand-writes libx264.
"""
import os
import sys
import json
import argparse
import subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from gen_transition import gen_transition  # noqa: E402
from pathlib import Path
try:
    from fast_encode import encoder_args_for  # noqa: E402
except Exception:
    encoder_args_for = None

CACHE = os.path.expanduser("~/.cache/broll-cutaway")


def _ffprobe_bin(ffmpeg):
    b = os.path.basename(ffmpeg)
    if "ffmpeg" in b:
        return os.path.join(os.path.dirname(ffmpeg), b.replace("ffmpeg", "ffprobe"))
    return "ffprobe"


def probe(path, ffmpeg="ffmpeg"):
    """Return (width, height, duration) of path's first video stream (sane 9:16 fallback)."""
    ffprobe = _ffprobe_bin(ffmpeg)

    def q(args):
        return subprocess.run([ffprobe, "-v", "error", *args, path],
                              capture_output=True, text=True).stdout.strip()
    wh = q(["-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=s=x:p=0"])
    dur = q(["-show_entries", "format=duration", "-of", "csv=p=0"])
    try:
        w, h = (int(x) for x in wh.split("x")[:2])
    except Exception:
        w, h = 1080, 1920
    try:
        d = float(dur)
    except Exception:
        d = 0.0
    return w, h, d


def transition_for(dur, fps, w, h, ffmpeg):
    """Cached flash/glare overlay for a given duration/size (regenerated only if missing)."""
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, f"xn_{w}x{h}_{fps}_{dur:.2f}.mov")
    if not os.path.exists(path) or os.path.getsize(path) < 1000:
        gen_transition(path, dur=dur, fps=fps, w=w, h=h, ffmpeg=ffmpeg)
    return path


def parse_insert(s):
    d = {}
    for kv in s.split(","):
        k, _, v = kv.partition("=")
        d[k.strip()] = v.strip()
    if "src" not in d or "at" not in d:
        sys.exit(f"--insert needs at least src= and at=: {s!r}")
    return {"src": os.path.expanduser(d["src"]), "at": float(d["at"]),
            "in": float(d.get("in", 0)), "dur": float(d.get("dur", 2.0))}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--base", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--spec", help="JSON file: [{src, at, in, dur}, ...]")
    p.add_argument("--insert", action="append", default=[], help="src=..,at=..,in=..,dur=.. (repeatable)")
    p.add_argument("--no-transition", action="store_true", help="hard cuts, no flash/glare")
    p.add_argument("--fps", type=int, default=30)
    p.add_argument("--ffmpeg", default="ffmpeg")
    a = p.parse_args()

    inserts = []
    if a.spec:
        with open(a.spec) as f:
            for i in json.load(f):
                inserts.append({"src": os.path.expanduser(i["src"]), "at": float(i["at"]),
                                "in": float(i.get("in", 0)), "dur": float(i.get("dur", 2.0))})
    inserts += [parse_insert(s) for s in a.insert]
    if not inserts:
        sys.exit("no inserts (use --spec or --insert)")
    inserts.sort(key=lambda i: i["at"])

    base = os.path.expanduser(a.base)
    W, H, BD = probe(base, a.ffmpeg)
    if W <= 0:
        W, H = 1080, 1920

    for i in inserts:
        if not os.path.exists(i["src"]):
            sys.exit(f"missing src: {i['src']}")
        _, _, sd = probe(i["src"], a.ffmpeg)
        if sd and sd < i["in"] + i["dur"] - 0.05:
            print(f"WARN: {os.path.basename(i['src'])} is {sd:.1f}s but insert needs "
                  f"in+dur={i['in'] + i['dur']:.1f}s -- it will run short", file=sys.stderr)
        if BD and i["at"] + i["dur"] > BD + 0.05:
            print(f"WARN: insert at {i['at']:.1f}+{i['dur']:.1f}s runs past base ({BD:.1f}s)", file=sys.stderr)

    n = len(inserts)
    inputs = ["-i", base]
    for i in inserts:
        inputs += ["-i", i["src"]]
    if not a.no_transition:
        for i in inserts:
            inputs += ["-i", transition_for(i["dur"], a.fps, W, H, a.ffmpeg)]

    fc = []
    # crop each B-roll to fill the base frame + place it on the timeline
    for k, i in enumerate(inserts, start=1):
        fc.append(
            f"[{k}:v]trim=start={i['in']:.3f}:duration={i['dur']:.3f},"
            f"setpts=PTS-STARTPTS+{i['at']:.3f}/TB,"
            f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1[b{k}]"
        )
    cur = "0:v"
    for k, i in enumerate(inserts, start=1):
        nxt = f"v{k}"
        fc.append(f"[{cur}][b{k}]overlay=0:0:enable='between(t,{i['at']:.3f},{i['at'] + i['dur']:.3f})'[{nxt}]")
        cur = nxt
    # flash/glare on top of each insert
    if not a.no_transition:
        for k, i in enumerate(inserts, start=1):
            ti = n + k  # this insert's transition input index
            fc.append(f"[{ti}:v]setpts=PTS-STARTPTS+{i['at']:.3f}/TB[t{k}]")
            nxt = f"w{k}"
            fc.append(f"[{cur}][t{k}]overlay=0:0:enable='between(t,{i['at']:.3f},{i['at'] + i['dur']:.3f})'[{nxt}]")
            cur = nxt

    venc = (list(encoder_args_for(base, a.ffmpeg, tier="delivery")) if encoder_args_for
            else ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p"])
    cmd = [a.ffmpeg, "-y", *inputs, "-filter_complex", ";".join(fc),
           "-map", f"[{cur}]", "-map", "0:a?", *venc, "-c:a", "copy",
           "-movflags", "+faststart", os.path.expanduser(a.out)]
    print(f"inserts: {n} | base {W}x{H} {BD:.1f}s | transition: {'no' if a.no_transition else 'yes'}",
          file=sys.stderr)
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.stderr.write(r.stderr[-2500:])
        sys.exit(r.returncode)
    print(os.path.expanduser(a.out))


if __name__ == "__main__":
    main()
