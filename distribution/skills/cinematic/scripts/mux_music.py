#!/usr/bin/env python3
"""mux_music.py — lay the lyric-timed bed onto each rendered clip.

Recipe from assets/music_approved/_APPROVED.md:
  1. IN-POINT = (measured lyric time - 0.30s) so the line lands just after the clip opens.
  2. LIFT the bed for the first ~5s or the lyric is inaudible under the VO, then decay to a
     normal bed.
  3. TUNE the lift by measuring the music STEM against the loudnorm'd VO STEM -> about -3 dB.
     🛑 Never judge from the mixed file: the final loudnorm hides the change (full mix moved 1dB
     while the bed moved 8dB).
"""
import subprocess, sys, os, wave
import numpy as np

CLIPS = {  # slug: (in-point = measured lyric time - 0.30s, the lyric it lands on)
 "Coward":         ( 11.70, "When you try your best but you don't succeed"),   # Fix You
 "BoyDied":        ( 58.96, "Take me back to the night we met"),               # The Night We Met
 "LonelyByDesign": ( 99.00, "From the dawn of time to the end of days"),       # Iron
 "DieTrying":      (137.70, "So live a life you will remember"),               # The Nights
}
TARGET_DB = -3.0

def rms_db(p, t0, t1):
    w = wave.open(p); a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32)/32768
    seg = a[int(t0*16000):int(t1*16000)]
    return 20*np.log10(max(np.sqrt((seg**2).mean()), 1e-6))

def run(c): subprocess.run(c, check=True, capture_output=True)

for slug,(ss,lyric) in CLIPS.items():
    d = f"clips/{slug}"
    import glob, re
    # take the NEWEST render, not V1 — a re-render for a framing fix auto-increments the version
    _v = sorted(glob.glob(f"{d}/build/V*_preview.mp4"),
                key=lambda x: int(re.search(r"V(\d+)_", x).group(1)))
    vid = _v[-1] if _v else f"{d}/build/V1_preview.mp4"
    if not os.path.exists(vid): print(f"  {slug:16s} SKIP (not rendered)"); continue
    vo, mu = f"{d}/premiere/assets/VOICE_cut.wav", f"music/{slug}.mp3"
    dur = float(subprocess.run(["ffprobe","-v","error","-show_entries","format=duration",
                                "-of","csv=p=0",vid],capture_output=True,text=True).stdout.strip())
    run(["ffmpeg","-v","error","-y","-i",vo,"-af","highpass=f=80,loudnorm=I=-16:TP=-1.5:LRA=11",
         "-ac","1","-ar","16000","/tmp/_vo.wav"])
    vdb = rms_db("/tmp/_vo.wav", 0.5, 5.0)
    extra = 0.42
    for _ in range(6):                      # converge the lift onto TARGET_DB
        curve = f"volume=volume='0.20+{extra:.3f}*exp(-max(0\\,t-5.5)*1.5)':eval=frame"
        run(["ffmpeg","-v","error","-y","-ss",str(ss),"-stream_loop","-1","-i",mu,"-t",str(dur),
             "-af",f"{curve},afade=t=in:st=0:d=0.25","-ac","1","-ar","16000","/tmp/_mu.wav"])
        mdb = rms_db("/tmp/_mu.wav", 0.5, 5.0)
        diff = (mdb - vdb) - TARGET_DB
        if abs(diff) < 0.4: break
        extra = max(0.05, min(1.6, extra * (10 ** (-diff/20))))
    curve = f"volume=volume='0.20+{extra:.3f}*exp(-max(0\\,t-5.5)*1.5)':eval=frame"
    out = f"{d}/build/{slug}_FINAL.mp4"
    run(["ffmpeg","-v","error","-y","-i",vid,"-i",vo,"-ss",str(ss),"-stream_loop","-1","-i",mu,
         "-filter_complex",
         f"[1:a]highpass=f=80,loudnorm=I=-16:TP=-1.5:LRA=11[vo];"
         f"[2:a]{curve},afade=t=in:st=0:d=0.25,afade=t=out:st={dur-1.5:.2f}:d=1.5[mu];"
         f"[vo][mu]amix=inputs=2:duration=first:dropout_transition=0,loudnorm=I=-14:TP=-1.0:LRA=11[a]",
         "-map","0:v","-map","[a]","-c:v","copy","-c:a","aac","-b:a","192k","-shortest",out])
    print(f"  {slug:16s} in@{ss:7.2f}s  lift {extra:.2f}  bed {mdb-vdb:+.1f}dB vs VO   \"{lyric}\"")
