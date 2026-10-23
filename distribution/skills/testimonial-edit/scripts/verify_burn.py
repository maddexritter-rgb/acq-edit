#!/usr/bin/env python3
"""verify_burn.py <workdir> — burn a verification MP4 from premiere_plan.json + captions.srt
(EDL of segments with card-beat blur + card PNG overlay + plain super + SRT caption burn).
For MY visual QA of the plan; the native Premiere sequence is built from the same plan.
"""
import json, os, subprocess, sys

CARDS = os.path.expanduser("~/Downloads/alex/2026-07-13_L3Testimonials/10_WORK/_cards2")
FONTS = os.path.expanduser("~/Downloads/alex/2026-07-13_L3Testimonials/10_WORK/fonts")

def main(workdir):
    workdir = os.path.abspath(workdir)
    plan = json.load(open(f"{workdir}/premiere_plan.json"))
    src = plan["source"]
    segs = plan["segments"]
    inputs = [f'-i "{src}"']
    cards = sorted(set(s["card_png"] for s in segs if s["kind"] == "card"))
    cidx = {}
    for i, c in enumerate(cards):
        inputs.append(f'-loop 1 -i "{CARDS}/{c}"')
        cidx[c] = i + 1
    f = []
    refs = []
    f.append("color=c=black:s=1920x1080:r=24000/1001:d=0.5[vL];anullsrc=r=48000:cl=stereo,atrim=0:0.5[aL];")
    refs.append(("[vL]", "[aL]"))
    for n, s in enumerate(segs):
        a, b, dur = s["src_in"], s["src_out"], s["dur"]
        if s["kind"] == "clip":
            f.append(f"[0:v]trim={a:.6f}:{b:.6f},setpts=PTS-STARTPTS,scale=1920:1080[v{n}];")
            f.append(f"[0:a]atrim={a:.6f}:{b:.6f},asetpts=PTS-STARTPTS[a{n}];")
        else:
            ci = cidx[s["card_png"]]
            f.append(f"[0:v]trim={a:.6f}:{b:.6f},setpts=PTS-STARTPTS,scale=1920:1080,gblur=sigma=34[vb{n}];"
                     f"[{ci}:v]scale=1920:1080,format=rgba[c{n}];[vb{n}][c{n}]overlay=0:0:shortest=1[v{n}];")
            f.append(f"anullsrc=r=48000:cl=stereo,atrim=0:{dur:.6f}[a{n}];")
        refs.append((f"[v{n}]", f"[a{n}]"))
    chain = "".join(v + aa for v, aa in refs)
    f.append(f"{chain}concat=n={len(refs)}:v=1:a=1[vc][aout];")
    # super drawtext (plain, top-left, 0.5-12s)
    open(f"{workdir}/_s1.txt", "w").write(plan["super_line1"])
    open(f"{workdir}/_s2.txt", "w").write(plan["super_line2"])
    srt = f"{workdir}/captions.srt".replace(":", "\\:")
    f.append(
        f"[vc]drawtext=fontfile={FONTS}/Poppins-800.ttf:textfile={workdir}/_s1.txt:fontsize=44:fontcolor=white:x=80:y=64:shadowcolor=black@0.6:shadowx=3:shadowy=3:enable='between(t,0.5,12)',"
        f"drawtext=fontfile={FONTS}/Poppins-800.ttf:textfile={workdir}/_s2.txt:fontsize=26:fontcolor=white:x=80:y=116:shadowcolor=black@0.6:shadowx=2:shadowy=2:enable='between(t,0.5,12)',"
        f"subtitles='{srt}':force_style='FontName=Poppins SemiBold,Fontsize=15,PrimaryColour=&H00FFFFFF,BorderStyle=3,BackColour=&HA0000000,Outline=8,Shadow=0,MarginV=60'[vout]"
    )
    graph = "".join(f)
    open(f"{workdir}/_burn_graph.txt", "w").write(graph)
    out = f"{workdir}/VERIFY_burn.mp4"
    cmd = (f'ffmpeg -y -v warning -stats {" ".join(inputs)} -filter_complex_script "{workdir}/_burn_graph.txt" '
           f'-map "[vout]" -map "[aout]" -r 24000/1001 -c:v libx264 -preset veryfast -crf 20 -pix_fmt yuv420p '
           f'-c:a aac -b:a 192k "{out}"')
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit("burn failed:\n" + r.stderr[-2500:])
    print(f"DONE {out}")

if __name__ == "__main__":
    main(sys.argv[1])
