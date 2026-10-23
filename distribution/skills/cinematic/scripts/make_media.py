#!/usr/bin/env python3
"""make_media.py — build the A-roll window, the cut voice, and the offset files. ONE command.

  python3 make_media.py <MASTER.mp4> <cut_spans.json> <project/10_WORK>

Was three hand-written ffmpeg invocations per clip; that is exactly the kind of step that drifts.
Emits, into <10_WORK>/premiere/assets/ :
    AROLL_window.mp4   the cut spans, concatenated, 1080-tall, 23.976
    VOICE_cut.wav      the SAME spans concatenated — never a continuous pull from the master
and writes media_offsets.json into BOTH cut/ and premiere/assets/ (face_frame reads one,
plate.py reads the other — a missing copy makes the dark-flip silently default every word white).
"""
import json, os, subprocess, sys, tempfile

FPS = "24000/1001"   # 🛑 MATCH THE SOURCE. The masters are 23.976; rendering 30 duplicates
                     # frames (judder) AND adds 25% more frames. 1080x1920 output is already
                     # the standard — we downscale from the 4K master on extraction, so a
                     # slow render is never "it is rendering in 4K".


def run(c):
    r = subprocess.run(c, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(f"ffmpeg failed:\n{' '.join(map(str,c))}\n{r.stderr[-800:]}")


def main():
    master, spansp, work = sys.argv[1:4]
    A = os.path.join(work, "premiere", "assets")
    os.makedirs(A, exist_ok=True)
    os.makedirs(os.path.join(work, "cut"), exist_ok=True)

    d = json.load(open(spansp))
    spans = d["spans"] if isinstance(d, dict) else d
    tmp = tempfile.mkdtemp(prefix="mm_")
    vs, ws = [], []
    for i, (a, b) in enumerate(spans):
        v, w = f"{tmp}/s{i}.mp4", f"{tmp}/s{i}.wav"
        run(["ffmpeg", "-v", "error", "-y", "-ss", f"{a:.3f}", "-i", master, "-t", f"{b-a:.3f}",
             "-vf", f"scale=-2:1080,fps={FPS}", "-an", "-c:v", "libx264", "-crf", "16",
             "-preset", "veryfast", v])
        run(["ffmpeg", "-v", "error", "-y", "-ss", f"{a:.3f}", "-i", master, "-t", f"{b-a:.3f}",
             "-vn", "-ac", "2", "-ar", "48000", "-c:a", "pcm_s16le", w])
        vs.append(v); ws.append(w)
        print(f"  span {i}: {a:.3f}-{b:.3f}  ({b-a:.2f}s)")

    for lst, out, codec in ((vs, f"{A}/AROLL_window.mp4", "copy"), (ws, f"{A}/VOICE_cut.wav", "copy")):
        lf = f"{tmp}/{os.path.basename(out)}.txt"
        open(lf, "w").write("".join(f"file '{p}'\n" for p in lst))
        run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lf, "-c", codec, out])

    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                "-of", "csv=p=0", f"{A}/AROLL_window.mp4"],
                               capture_output=True, text=True).stdout.strip())
    off = {"items": [{"tl": 0.0, "in": 0.0, "out": dur}]}     # the window IS the timeline
    for p in (f"{work}/cut/media_offsets.json", f"{A}/media_offsets.json"):
        json.dump(off, open(p, "w"), indent=1)

    print(f"\n  AROLL_window.mp4  {dur:.3f}s")
    print(f"  VOICE_cut.wav     written")
    print(f"  media_offsets.json written to BOTH cut/ and premiere/assets/")
    print(f"\n  -> set DUR = {dur:.3f} in plan_v2.py")


if __name__ == "__main__":
    main()
