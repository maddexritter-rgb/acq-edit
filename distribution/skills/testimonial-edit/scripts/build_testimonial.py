#!/usr/bin/env python3
"""L3 testimonial finishing engine (locked from Stetson template 2026-07-14).

Input:  a work dir containing cutlist.json (+ clip_00.json word transcript)
Output: 20_DELIVER/ALEX_TESTIMONIAL_L3_<Person>_Maddex_<YYYYMMDD>_V1.mp4
        + captions SRT/ASS, premiere_spans.json, prelim render in the work dir.

Steps: frame-quantize spans -> captions (SRT + styled ASS) -> ffmpeg select cut
@1080p + ASS burn + name super + typicality disclaimer -> 2-pass loudnorm to
-16 LUFS / TP<=-3 (linear + limiter) -> QA probe printout.
"""
import json, math, os, subprocess, sys, datetime

# Job-agnostic: workdir is .../<project>/10_WORK/<event>/<person>; project root is
# derived by walking up to the folder that contains 10_WORK. Fonts: <project>/10_WORK/fonts
# (Poppins 600/700/regular — fetch via the fonts skill / Google Fonts API if absent).
def project_root(workdir):
    d = os.path.abspath(workdir)
    while d != "/":
        if os.path.basename(d) == "10_WORK":
            return os.path.dirname(d)
        d = os.path.dirname(d)
    raise SystemExit("workdir must live under <project>/10_WORK/")
DISC1 = ("Individual experiences presented here may not be typical. Their background, "
         "education, effort, and application affected their experience.")
DISC2 = ("The information shared here are for example purposes and not a guarantee of "
         "a rate of return or a specific result. Your results may vary.")

ASS_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: CAP,Poppins SemiBold,40,&H00FFFFFF,&H00FFFFFF,&H00000000,&HA0000000,-1,0,0,0,100,100,0,0,3,10,0,2,60,60,210,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

def sh(cmd, **kw):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, **kw)

def probe_fps_dur(src):
    out = sh(f'ffprobe -v quiet -print_format json -show_format -show_streams "{src}"').stdout
    d = json.loads(out)
    fps = None
    for s in d["streams"]:
        if s["codec_type"] == "video":
            a, b = s["avg_frame_rate"].split("/")
            fps = float(a) / float(b)
    return fps, float(d["format"]["duration"])

def fmt_srt(sec):
    h = int(sec // 3600); m = int(sec % 3600 // 60); s = int(sec % 60)
    ms = int(round((sec - int(sec)) * 1000))
    if ms == 1000: ms = 0; s += 1
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def fmt_ass(sec):
    h = int(sec // 3600); m = int(sec % 3600 // 60)
    return f"{h:d}:{m:02d}:{sec % 60:05.2f}"

def main(workdir):
    workdir = os.path.abspath(workdir)
    root = project_root(workdir)
    FONTS = f"{root}/10_WORK/fonts"
    DELIVER = f"{root}/20_DELIVER"
    cutfile = "cutlist_v2.json" if os.path.exists(f"{workdir}/cutlist_v2.json") else "cutlist.json"
    cl = json.load(open(f"{workdir}/{cutfile}"))
    words = json.load(open(f"{workdir}/clip_00.json"))["words"]
    src = cl["source"]
    person = cl["person"].replace(" ", "")
    fps, _ = probe_fps_dur(src)

    # frame-quantize
    q, cum = [], 0
    for sp in cl["spans"]:
        fa, fb = math.floor(sp["in"] * fps), math.floor(sp["out"] * fps)
        if fb <= fa: raise SystemExit(f"span {sp['n']} empty after quantize")
        q.append({"n": sp["n"], "fa": fa, "fb": fb,
                  "src_in": fa / fps, "src_out": fb / fps, "pos": cum / fps})
        cum += fb - fa
    total = cum / fps
    json.dump({"fps": fps, "total_s": total, "spans": q},
              open(f"{workdir}/premiere_spans.json", "w"), indent=1)

    # captions
    cards, prev_end = [], 0.0
    for sp in q:
        ws = [w for w in words if w["start"] >= sp["src_in"] - 0.05 and w["end"] <= sp["src_out"] + 0.05]
        cur = []
        for w in ws:
            if cur and (len(cur) >= 4 or w["start"] - cur[-1]["end"] > 0.8):
                cards.append((cur, sp)); cur = []
            cur.append(w)
        if cur: cards.append((cur, sp))
    srt, ass = [], []
    for i, (cw, sp) in enumerate(cards, 1):
        st = max(sp["pos"] + (cw[0]["start"] - sp["src_in"]), prev_end)
        en = sp["pos"] + min(cw[-1]["end"] - sp["src_in"], sp["src_out"] - sp["src_in"])
        if en <= st: en = st + 0.2
        txt = " ".join(w["word"].strip() for w in cw).upper()
        srt.append(f"{i}\n{fmt_srt(st)} --> {fmt_srt(en)}\n{txt}\n")
        ass.append(f"Dialogue: 0,{fmt_ass(st)},{fmt_ass(en)},CAP,,0,0,0,,{txt}")
        prev_end = en
    open(f"{workdir}/captions_timeline.srt", "w").write("\n".join(srt))
    open(f"{workdir}/captions_timeline.ass", "w").write(ASS_HEADER + "\n".join(ass) + "\n")

    # drawtext textfiles
    open(f"{workdir}/txt_name.txt", "w").write(cl["super_line1"])
    open(f"{workdir}/txt_co.txt", "w").write(cl["super_line2"])
    open(f"{workdir}/txt_disc1.txt", "w").write(DISC1)
    open(f"{workdir}/txt_disc2.txt", "w").write(DISC2)

    vsel = "+".join(f"between(n\\,{s['fa']}\\,{s['fb']-1})" for s in q)
    asel = "+".join(f"between(t\\,{s['src_in']:.6f}\\,{s['src_out']:.6f})" for s in q)
    vf = (f"select='{vsel}',setpts=N/FRAME_RATE/TB,scale=1920:1080,"
          f"ass={workdir}/captions_timeline.ass:fontsdir={FONTS},"
          f"drawtext=fontfile={FONTS}/Poppins-700.ttf:textfile={workdir}/txt_name.txt:fontsize=44:fontcolor=white:x=80:y=64:shadowcolor=black@0.6:shadowx=3:shadowy=3:enable='between(t,0.5,12)',"
          f"drawtext=fontfile={FONTS}/Poppins-600.ttf:textfile={workdir}/txt_co.txt:fontsize=26:fontcolor=white:x=80:y=118:shadowcolor=black@0.6:shadowx=2:shadowy=2:enable='between(t,0.5,12)',"
          f"drawtext=fontfile={FONTS}/Poppins-regular.ttf:textfile={workdir}/txt_disc1.txt:fontsize=17:fontcolor=white@0.85:x=(w-text_w)/2:y=1022:shadowcolor=black@0.7:shadowx=2:shadowy=2:enable='between(t,0.5,15.5)',"
          f"drawtext=fontfile={FONTS}/Poppins-regular.ttf:textfile={workdir}/txt_disc2.txt:fontsize=17:fontcolor=white@0.85:x=(w-text_w)/2:y=1046:shadowcolor=black@0.7:shadowx=2:shadowy=2:enable='between(t,0.5,15.5)'")
    af = f"aselect='{asel}',asetpts=N/SR/TB"
    prelim = f"{workdir}/prelim.mp4"
    r = sh(f'ffmpeg -y -v warning -hwaccel videotoolbox -i "{src}" -vf "{vf}" -af "{af}" '
           f'-c:v libx264 -preset fast -crf 18 -pix_fmt yuv420p -c:a aac -b:a 256k "{prelim}"')
    if r.returncode != 0: raise SystemExit("render failed:\n" + r.stderr[-2000:])

    # loudnorm 2-pass
    m = sh(f'ffmpeg -y -i "{prelim}" -af loudnorm=I=-16:TP=-3:LRA=11:print_format=json -f null -')
    j = json.loads(m.stderr[m.stderr.rfind("{"):m.stderr.rfind("}") + 1])
    os.makedirs(DELIVER, exist_ok=True)
    stamp = datetime.date.today().strftime("%Y%m%d")
    final = f"{DELIVER}/ALEX_TESTIMONIAL_L3_{person}_Maddex_{stamp}_V1.mp4"
    r = sh(f'ffmpeg -y -v warning -i "{prelim}" -af "loudnorm=I=-16:TP=-3:LRA=11:'
           f'measured_I={j["input_i"]}:measured_TP={j["input_tp"]}:measured_LRA={j["input_lra"]}:'
           f'measured_thresh={j["input_thresh"]}:offset={j["target_offset"]}:linear=true,'
           f'alimiter=limit=0.60:level=false" -c:v copy -c:a aac -b:a 256k "{final}"')
    if r.returncode != 0: raise SystemExit("loudnorm failed:\n" + r.stderr[-2000:])

    chk = sh(f'ffmpeg -v info -i "{final}" -af loudnorm=I=-16:TP=-3:print_format=summary -vn -f null -').stderr
    lufs = [l for l in chk.splitlines() if "Input Integrated" in l or "Input True Peak" in l]
    print(f"DONE {final}")
    print(f"  runtime {total:.1f}s | spans {len(q)} | cards {len(cards)}")
    for l in lufs: print("  " + l.strip())
    print(f"  notes: {cl.get('notes','')}")

if __name__ == "__main__":
    main(sys.argv[1])
