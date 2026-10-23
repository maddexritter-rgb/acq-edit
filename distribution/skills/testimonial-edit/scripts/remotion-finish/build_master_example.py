#!/usr/bin/env python3
"""Stetson master: exact replication of Maddex's approved Premiere timeline
(15 takes + 4 blurred question cards) -> 1080p23.976 master + 2-pass loudnorm."""
import json, math, subprocess, os

W = os.path.expanduser("~/Downloads/alex/2026-07-13_L3Testimonials/10_WORK/2026.02.17_Stetson")
SRC = os.path.expanduser("~/Downloads/alex/2026-07-13_L3Testimonials/00_SOURCE/2026.02.17_Stetson/StetsonWickers_L3_Renewal_Testimonial.mp4")
FPS = 24000 / 1001

# (type, srcIn, srcOut[, cardPng]) in timeline order — from the live sequence dump
SEGS = [
    ("clip", 27.819, 29.988),
    ("clip", 32.491, 34.326),
    ("card", 46.590, 49.593, "card1.png"),
    ("clip", 49.841, 77.077),
    ("clip", 89.798, 115.198),
    ("clip", 124.374, 140.641),
    ("clip", 143.727, 155.614),
    ("clip", 155.781, 173.173),
    ("clip", 173.173, 180.347),
    ("clip", 187.062, 199.408),
    ("clip", 207.582, 229.813),
    ("card", 231.567, 234.570, "card2.png"),
    ("clip", 234.943, 260.218),
    ("clip", 278.403, 295.337),
    ("card", 299.593, 302.596, "card3.png"),
    ("clip", 302.886, 332.582),
    ("clip", 336.753, 363.530),
    ("card", 366.005, 369.008, "card4.png"),
    ("clip", 369.286, 395.186),
]

def q(t):  # snap to frame grid
    return round(t * FPS) / FPS

inputs = [f'-i "{SRC}"']
cards = sorted(set(s[3] for s in SEGS if s[0] == "card"))
card_idx = {}
for i, png in enumerate(cards):
    inputs.append(f'-loop 1 -i "{W}/qcards/{png}"')
    card_idx[png] = i + 1

f = []
concat_refs = []
# 0.5s leader (black + silence)
f.append(f"color=c=black:s=1920x1080:r=24000/1001:d=0.5[v_lead];")
f.append(f"anullsrc=r=48000:cl=stereo,atrim=0:0.5[a_lead];")
concat_refs.append(("[v_lead]", "[a_lead]"))

timeline = [("lead", 0.0, 0.5)]
pos = 0.5
for n, seg in enumerate(SEGS):
    kind, a, b = seg[0], q(seg[1]), q(seg[2])
    dur = b - a
    if kind == "clip":
        f.append(f"[0:v]trim={a:.6f}:{b:.6f},setpts=PTS-STARTPTS,scale=1920:1080[v{n}];")
        f.append(f"[0:a]atrim={a:.6f}:{b:.6f},asetpts=PTS-STARTPTS[a{n}];")
    else:
        ci = card_idx[seg[3]]
        f.append(
            f"[0:v]trim={a:.6f}:{b:.6f},setpts=PTS-STARTPTS,scale=1920:1080,gblur=sigma=34[vb{n}];"
            f"[{ci}:v]scale=1920:1080,format=rgba[c{n}];"
            f"[vb{n}][c{n}]overlay=0:0:shortest=1[v{n}];"
        )
        f.append(f"anullsrc=r=48000:cl=stereo,atrim=0:{dur:.6f}[a{n}];")
    concat_refs.append((f"[v{n}]", f"[a{n}]"))
    timeline.append((kind, pos, pos + dur))
    pos += dur

chain = "".join(v + aa for v, aa in concat_refs)
f.append(f"{chain}concat=n={len(concat_refs)}:v=1:a=1[vout][aout]")
graph = "".join(f)
open(f"{W}/master_graph.txt", "w").write(graph)
json.dump(timeline, open(f"{W}/master_timeline.json", "w"), indent=1)

cmd = (f'ffmpeg -y -v warning -stats {" ".join(inputs)} '
       f'-filter_complex_script "{W}/master_graph.txt" '
       f'-map "[vout]" -map "[aout]" -r 24000/1001 '
       f'-c:v libx264 -preset fast -crf 18 -pix_fmt yuv420p -c:a aac -b:a 256k '
       f'"{W}/master_nolm.mp4"')
r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
if r.returncode != 0:
    raise SystemExit("render failed:\n" + r.stderr[-3000:])

# 2-pass loudnorm
m = subprocess.run(f'ffmpeg -y -i "{W}/master_nolm.mp4" -af loudnorm=I=-16:TP=-3:LRA=11:print_format=json -f null -',
                   shell=True, capture_output=True, text=True).stderr
j = json.loads(m[m.rfind("{"):m.rfind("}") + 1])
r = subprocess.run(
    f'ffmpeg -y -v warning -i "{W}/master_nolm.mp4" -af "loudnorm=I=-16:TP=-3:LRA=11:'
    f'measured_I={j["input_i"]}:measured_TP={j["input_tp"]}:measured_LRA={j["input_lra"]}:'
    f'measured_thresh={j["input_thresh"]}:offset={j["target_offset"]}:linear=true,'
    f'alimiter=limit=0.60:level=false" -c:v copy -c:a aac -b:a 256k "{W}/master_cut.mp4"',
    shell=True, capture_output=True, text=True)
if r.returncode != 0:
    raise SystemExit("loudnorm failed:\n" + r.stderr[-2000:])
d = subprocess.run(f'ffprobe -v quiet -show_entries format=duration -of csv=p=0 "{W}/master_cut.mp4"',
                   shell=True, capture_output=True, text=True).stdout.strip()
print(f"MASTER DONE {d}s -> {W}/master_cut.mp4")
