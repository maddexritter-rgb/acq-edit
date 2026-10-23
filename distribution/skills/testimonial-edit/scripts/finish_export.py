#!/usr/bin/env python3
"""finish_export.py <master.mp4> <ranges.json> <out_dir> — split a single native
Premiere export of a flat review timeline into per-person deliverables, caption each
one, and loudness-normalize.

Robust caption timing: we RE-TRANSCRIBE each person's exported audio (Groq
whisper-large-v3-turbo) so captions match the ACTUAL approved cut — never a stale
pre-edit SRT. Spice caption logic (editor spec): ALL CAPS, no punctuation, no gaps
(butt-joined within a run, capped hold), ~26-char lines, 4-frame lead. Muted
question-card beats are silent, so they naturally carry no caption.

ranges.json = [{"name": "JackHenderson", "start": 0.375, "end": 211.211,
                "out": "ALEX_TESTIMONIAL_L3_JackHenderson_Maddex_20260717_V1.mp4"}, ...]

Per person, ONE re-encode from the master (master gen + final gen = 2 generations):
  ffmpeg -ss start -i master -t dur  -> scale 1080 + burn SRT + loudnorm -16 LUFS.

Env: GROQ_API_KEY (falls back to nothing -> errors; source ~/.zshrc before running).
"""
import json, os, re, subprocess, sys, tempfile, urllib.request, urllib.error

FPS = 24000 / 1001
LEAD = 4 / FPS
MAX_HOLD = 1.2
MAXCHARS = 26
GAP_BREAK = 0.6
GROQ_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
MODEL = "whisper-large-v3-turbo"
# caption look (1080p) — clean, bold, all-caps, lower third. Editor styles further if needed.
FORCE_STYLE = ("FontName=Arial,Fontsize=15,Bold=1,PrimaryColour=&H00FFFFFF&,"
               "OutlineColour=&H00000000&,BorderStyle=1,Outline=2,Shadow=1,"
               "Alignment=2,MarginV=90")


def sh(cmd, **kw):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, **kw)


def transcribe(audio_path):
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        raise SystemExit("GROQ_API_KEY not set (source ~/.zshrc)")
    # curl multipart is more reliable than hand-rolled urllib bodies (Groq 403s malformed ones)
    r = subprocess.run([
        "curl", "-s", "--max-time", "300", GROQ_URL,
        "-H", "Authorization: Bearer " + key,
        "-F", "file=@" + audio_path,
        "-F", "model=" + MODEL,
        "-F", "response_format=verbose_json",
        "-F", "timestamp_granularities[]=word",
    ], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("curl failed: " + r.stderr[-300:])
    j = json.loads(r.stdout)
    if "words" not in j:
        raise RuntimeError("no words in response: " + r.stdout[:300])
    return j.get("words", [])


def cues_from_words(words):
    # chunk to <=MAXCHARS, break on gap>GAP_BREAK; then lead + butt-join + cap hold
    raw, cur = [], []
    for w in words:
        t = (w.get("word") or "").strip()
        if not t:
            continue
        ws, we = float(w["start"]), float(w["end"])
        if cur and (len(" ".join(x[0] for x in cur + [(t, ws, we)])) > MAXCHARS
                    or ws - cur[-1][2] > GAP_BREAK):
            raw.append(cur); cur = []
        cur.append((t, ws, we))
    if cur:
        raw.append(cur)
    cues = []
    for grp in raw:
        txt = " ".join(x[0] for x in grp)
        txt = re.sub(r"[^\w$%#&' ]+", "", txt)
        txt = re.sub(r"\s+", " ", txt).strip().upper()
        if txt:
            cues.append({"text": txt, "start": grp[0][1], "end": grp[-1][2]})
    out, prev = [], 0.0
    for i, c in enumerate(cues):
        st = max(c["start"] - LEAD, prev)
        en = c["end"]
        nxt = cues[i + 1]["start"] - LEAD if i + 1 < len(cues) else None
        if nxt is not None and 0 < nxt - en <= MAX_HOLD:
            en = nxt  # no gap within a run
        if en <= st:
            continue
        out.append({"text": c["text"], "start": round(st, 3), "end": round(en, 3)})
        prev = en
    return out


def fmt(t):
    h = int(t // 3600); m = int(t % 3600 // 60); s = int(t % 60); ms = int(round((t - int(t)) * 1000))
    if ms == 1000: ms = 0; s += 1
    return "%02d:%02d:%02d,%03d" % (h, m, s, ms)


def write_srt(cues, path):
    with open(path, "w") as f:
        for i, c in enumerate(cues, 1):
            f.write("%d\n%s --> %s\n%s\n\n" % (i, fmt(c["start"]), fmt(c["end"]), c["text"]))


def main(master, ranges_path, out_dir, srt_only=False):
    os.makedirs(out_dir, exist_ok=True)
    work = os.path.join(out_dir, "_finish_tmp")
    os.makedirs(work, exist_ok=True)
    ranges = json.load(open(ranges_path))
    log = []
    for idx, r in enumerate(ranges, 1):
        name, a, b = r["name"], float(r["start"]), float(r["end"])
        dur = round(b - a, 3)
        out_path = os.path.join(out_dir, r["out"])
        aud = os.path.join(work, name + ".mp3")
        srt = os.path.join(work, name + ".srt")
        print("[%d/%d] %s  %.3f-%.3f (%.1fs)" % (idx, len(ranges), name, a, b, dur), flush=True)
        if srt_only and os.path.exists(srt) and os.path.getsize(srt) > 20:
            print("  SKIP srt (exists)"); log.append((name, "ok")); continue
        if not srt_only and os.path.exists(out_path) and os.path.getsize(out_path) > 500000:
            print("  SKIP (already delivered)"); log.append((name, "ok")); continue
        # 1) audio for transcription (0-based)
        r1 = sh('ffmpeg -y -v error -ss %.3f -i "%s" -t %.3f -vn -ac 1 -ar 16000 -b:a 96k "%s"'
                % (a, master, dur, aud))
        if r1.returncode != 0:
            print("  AUDIO FAIL: " + r1.stderr[-400:]); log.append((name, "audio-fail")); continue
        # 2) transcribe -> spice cues -> srt
        try:
            words = transcribe(aud)
            cues = cues_from_words(words)
            write_srt(cues, srt)
        except Exception as e:
            print("  TRANSCRIBE FAIL: %s" % e); log.append((name, "transcribe-fail")); continue
        if srt_only:
            print("  SRT %d cues" % len(cues)); log.append((name, "ok")); continue
        # 3) final: 1080p + burn captions + loudnorm -16 LUFS, one re-encode from master
        srt_esc = srt.replace(":", "\\:").replace("'", "\\'")
        vf = "scale=-2:1080,subtitles='%s':force_style='%s'" % (srt_esc, FORCE_STYLE)
        r3 = sh('ffmpeg -y -v error -ss %.3f -i "%s" -t %.3f -vf "%s" '
                '-af "loudnorm=I=-16:TP=-1.5:LRA=11" '
                '-c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p -r 24000/1001 '
                '-c:a aac -b:a 256k -movflags +faststart "%s"'
                % (a, master, dur, vf, out_path))
        if r3.returncode != 0:
            print("  BURN FAIL: " + r3.stderr[-500:]); log.append((name, "burn-fail")); continue
        sz = os.path.getsize(out_path) / 1048576
        print("  OK -> %s (%.0f MB, %d cues)" % (r["out"], sz, len(cues)))
        log.append((name, "ok"))
    ok = sum(1 for _, s in log if s == "ok")
    print("\nDONE %d/%d ok" % (ok, len(ranges)))
    for n, s in log:
        if s != "ok":
            print("  FAILED: %s (%s)" % (n, s))


if __name__ == "__main__":
    pos = [a for a in sys.argv[1:] if not a.startswith("--")]
    main(pos[0], pos[1], pos[2], srt_only="--srt-only" in sys.argv)
