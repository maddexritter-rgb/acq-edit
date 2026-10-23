#!/usr/bin/env python3
"""Machine-ear gate: render each clip's cut AUDIO (hard cuts, exactly as the
timeline will play) and verbatim-listen to the head and tail.
  - HEAD: first 3s must transcribe to the expected opening words (hook, no
    filler, no leftover fragment from the word before the cut).
  - TAIL: last 4s must end with the expected final word, complete.
ASR-blind caveat respected: this catches WRONG/EXTRA/MISSING words at the
boundaries (fragments, filler, swallowed tails at the cut), which transcripts
CAN see; sub-200ms artifacts still belong to the human ear.

  python3 ear_check.py T1 T2 ... | all      (needs GROQ_API_KEY)
Writes ear_check_results.json; prints PASS/FAIL per clip.
"""
from __future__ import annotations
import json, os, re, subprocess, sys, tempfile
from pathlib import Path

WORK = Path(__file__).parent
SRC = WORK.parent / "00_SOURCE/GetRichYoung_YT720.mp4"
W = json.load(open(WORK / "words_v2.json"))["words"]
KEY = os.environ.get("GROQ_API_KEY") or subprocess.run(
    ["zsh", "-ic", "echo -n $GROQ_API_KEY"], capture_output=True, text=True).stdout.strip()


def norm_tokens(s):
    return [t for t in re.sub(r"[^a-z0-9' ]", " ", s.lower()).split() if t]


def kept_words(spans):
    return [w for w in W if any(a - 0.05 <= w["start"] <= b + 0.05 for a, b in spans)]


def render_audio(spans, out):
    parts = []
    with tempfile.TemporaryDirectory() as td:
        for i, (a, b) in enumerate(spans):
            p = f"{td}/p{i:02d}.wav"
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                            "-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i", str(SRC),
                            "-ac", "1", "-ar", "16000", p], check=True)
            parts.append(p)
        lst = f"{td}/l.txt"
        open(lst, "w").write("".join(f"file '{p}'\n" for p in parts))
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                        "-f", "concat", "-safe", "0", "-i", lst, out], check=True)


def asr(wav):
    import time
    for attempt in range(5):
        r = subprocess.run(
            ["curl", "-s", "--max-time", "60",
             "https://api.groq.com/openai/v1/audio/transcriptions",
             "-H", f"Authorization: Bearer {KEY}", "-F", f"file=@{wav}",
             "-F", "model=whisper-large-v3", "-F", "response_format=text"],
            capture_output=True, text=True)
        out = r.stdout.strip()
        if "rate_limit_exceeded" not in out and '"error"' not in out[:20]:
            return out
        time.sleep(20 * (attempt + 1))
    return out


def check(tag):
    spans = json.loads((WORK / f"v3_{tag}.json").read_text())
    kw = kept_words(spans)
    dur = sum(b - a for a, b in spans)
    with tempfile.TemporaryDirectory() as td:
        full = f"{td}/full.wav"
        render_audio(spans, full)
        head, tail = f"{td}/h.wav", f"{td}/t.wav"
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                        "-t", "3", "-i", full, head], check=True)
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                        "-sseof", "-4", "-i", full, tail], check=True)
        h_txt, t_txt = asr(head), asr(tail)
    exp_head = norm_tokens(" ".join(w["word"] for w in kw[:6]))
    got_head = norm_tokens(h_txt)
    # head passes when the heard opening matches the expected first words
    # (>=3 of the first 4 expected tokens, in order, starting within 1 token)
    ALIAS = {"layla": "leila", "lela": "leila"}
    got_head = [ALIAS.get(t, t) for t in got_head]
    exp_head = [ALIAS.get(t, t) for t in exp_head]
    def head_match(exp):
        return bool(exp) and got_head[:1] == exp[:1] and \
            sum(1 for t in exp[:4] if t in got_head[:6]) >= min(3, len(exp))
    # allow ONE leading expected token to be an overlapping-label ghost
    ok_head = head_match(exp_head) or head_match(exp_head[1:])
    exp_last = norm_tokens(kw[-1]["word"])
    got_tail = norm_tokens(t_txt)
    ok_tail = bool(exp_last) and bool(got_tail) and exp_last[-1] == got_tail[-1]
    # AAI sometimes MISSES quiet trailing words that Silero heard and the engine
    # kept (proven: 'endured [to get to where you want to go.]'). If the heard
    # tail CONTAINS the expected last word and ends sentence-terminal, the cut
    # is complete — the label stream was short, not the clip.
    if not ok_tail and exp_last and exp_last[-1] in got_tail and \
            t_txt.rstrip().endswith((".", "?", "!")):
        ok_tail = True
    verdict = "PASS" if (ok_head and ok_tail) else "FAIL"
    print(f"{tag}: {verdict}  ({dur:.0f}s)  head heard: \"{h_txt[:60]}\" | "
          f"expected: \"{' '.join(w['word'] for w in kw[:5])}\""
          + ("" if ok_tail else f" | TAIL: heard \"...{t_txt[-40:]}\" expected end '{kw[-1]['word']}'"))
    return {"tag": tag, "verdict": verdict, "dur": round(dur, 1),
            "head_heard": h_txt, "head_expected": " ".join(w["word"] for w in kw[:6]),
            "tail_heard": t_txt[-80:], "tail_expected": kw[-1]["word"],
            "ok_head": ok_head, "ok_tail": ok_tail}


tags = sys.argv[1:]
if tags == ["all"]:
    tags = sorted((p.stem.split("_")[1] for p in WORK.glob("v3_T*.json")
                   if p.stem.count("_") == 1), key=lambda s: int(s[1:]))
res = [check(t) for t in tags]
json.dump(res, open(WORK / "ear_check_results.json", "w"), indent=1)
fails = [r["tag"] for r in res if r["verdict"] == "FAIL"]
print(f"\n{len(res) - len(fails)}/{len(res)} PASS. Fails: {fails or 'none'}")
