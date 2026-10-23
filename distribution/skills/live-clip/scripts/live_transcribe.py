#!/usr/bin/env python3
"""/live-clip rolling transcription — keep a word-level transcript growing as
chunks close.

  python3 live_transcribe.py --work <dir> [--watch] [--overlap 4] \
      [--engine assemblyai|groq] [--prompt "..."] [--keyterms-file vocab.txt]

For each newly-closed chunk: build an audio window = last <overlap>s of the
previous chunk + this chunk (so words split across a chunk boundary are heard
whole), transcribe it, keep only the words whose MIDPOINT falls inside this
chunk's span (the previous pass already emitted everything before it), offset
to absolute stream time, append.

Default engine = AssemblyAI universal-3-5-pro with disfluencies:true — fillers
("um", "uh") stay IN the transcript, which is what makes downstream cut
boundaries honest (Whisper-family ASR silently erases them and hides the filler
audio inside a stretched neighbor word — proven trap, see cut/SKILL.md).
Groq whisper-large-v3 is the fallback engine (no fillers).

Outputs in <work>/:
  rolling_words.json  [{"w","s","e"}, ...] absolute stream seconds
  rolling.txt         [mm:ss] utterance lines — feed THIS to the miner
  transcribe_state.json

--once (default) processes what's new and exits — the orchestrating session
calls it every cycle. --watch loops until INGEST_DONE and all chunks are done.
"""
from __future__ import annotations
import argparse, json, os, subprocess, sys, tempfile, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from live_common import update_manifest

GROQ_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
AAI_BASE = "https://api.assemblyai.com"


def env_key(name: str) -> str:
    k = os.environ.get(name)
    if not k:  # login shells have it via ~/.zshrc; cron/detached may not
        r = subprocess.run(["zsh", "-ic", f"echo -n ${name}"],
                           capture_output=True, text=True)
        k = r.stdout.strip()
    if not k:
        sys.exit(f"{name} not available")
    return k


def make_window_audio(work: Path, chunk: dict, prev: dict | None,
                      overlap: float, out_wav: Path) -> float:
    """Extract mono 16k audio for [chunk.t0 - overlap, chunk.t1]. Returns the
    absolute time of the window start."""
    cd = work / "chunks"
    if prev is None or overlap <= 0:
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                        "-i", str(cd / chunk["file"]),
                        "-ac", "1", "-ar", "16000", str(out_wav)], check=True)
        return chunk["t0"]
    prev_dur = prev["t1"] - prev["t0"]
    ss = max(0.0, prev_dur - overlap)
    lst = out_wav.with_suffix(".txt")
    lst.write_text(f"file '{cd / prev['file']}'\nfile '{cd / chunk['file']}'\n")
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-ss", f"{ss:.3f}",
                    "-ac", "1", "-ar", "16000", str(out_wav)], check=True)
    lst.unlink()
    return prev["t0"] + ss


def transcribe_groq(wav: Path, key: str, _cfg: dict) -> list[dict]:
    r = subprocess.run(
        ["curl", "-s", "--max-time", "120", GROQ_URL,
         "-H", f"Authorization: Bearer {key}",
         "-F", f"file=@{wav}",
         "-F", "model=whisper-large-v3",
         "-F", "response_format=verbose_json",
         "-F", "timestamp_granularities[]=word",
         "-F", "language=en"],
        capture_output=True, text=True, check=True)
    data = json.loads(r.stdout)
    if "words" not in data:
        raise RuntimeError(f"Groq response missing words: {r.stdout[:300]}")
    return [{"word": w["word"], "start": w["start"], "end": w["end"]}
            for w in data["words"]]


def transcribe_assemblyai(wav: Path, key: str, cfg: dict) -> list[dict]:
    """Async /v2/transcript flow. Auth header is the RAW key (no Bearer).
    disfluencies:true keeps fillers — the whole reason this engine exists."""
    up = subprocess.run(
        ["curl", "-s", "--max-time", "120", f"{AAI_BASE}/v2/upload",
         "-H", f"Authorization: {key}", "--data-binary", f"@{wav}"],
        capture_output=True, text=True, check=True)
    upload_url = json.loads(up.stdout)["upload_url"]

    body = {"audio_url": upload_url,
            "speech_models": ["universal-3-5-pro", "universal-2"],
            "disfluencies": True,
            "language_code": "en"}
    if cfg.get("prompt"):
        body["prompt"] = cfg["prompt"]
    if cfg.get("keyterms"):
        body["keyterms_prompt"] = cfg["keyterms"]
    sub = subprocess.run(
        ["curl", "-s", f"{AAI_BASE}/v2/transcript",
         "-H", f"Authorization: {key}", "-H", "Content-Type: application/json",
         "-d", json.dumps(body)],
        capture_output=True, text=True, check=True)
    sub_j = json.loads(sub.stdout)
    tid = sub_j.get("id")
    if not tid:
        raise RuntimeError(f"AAI submit failed: {sub.stdout[:300]}")

    deadline = time.time() + 300
    while time.time() < deadline:
        res = json.loads(subprocess.run(
            ["curl", "-s", f"{AAI_BASE}/v2/transcript/{tid}",
             "-H", f"Authorization: {key}"],
            capture_output=True, text=True, check=True).stdout)
        if res["status"] == "completed":
            return [{"word": w["text"], "start": w["start"] / 1000.0,
                     "end": w["end"] / 1000.0} for w in res.get("words") or []]
        if res["status"] == "error":
            raise RuntimeError(f"AAI transcript error: {res.get('error')}")
        time.sleep(2)
    raise RuntimeError("AAI transcript poll timed out (300s)")


ENGINES = {"assemblyai": ("ASSEMBLYAI_API_KEY", transcribe_assemblyai),
           "groq": ("GROQ_API_KEY", transcribe_groq)}


def rebuild_rolling_txt(words: list[dict], out: Path) -> None:
    """Utterance lines broken on >=0.9s gaps, stamped [mm:ss]."""
    lines, cur, cur_start = [], [], None
    for w in words:
        if cur and w["s"] - cur[-1]["e"] >= 0.9:
            lines.append((cur_start, " ".join(x["w"] for x in cur)))
            cur, cur_start = [], None
        if cur_start is None:
            cur_start = w["s"]
        cur.append(w)
    if cur:
        lines.append((cur_start, " ".join(x["w"] for x in cur)))
    out.write_text("\n".join(
        f"[{int(t // 60):02d}:{int(t % 60):02d}] {txt}" for t, txt in lines) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True)
    ap.add_argument("--watch", action="store_true")
    ap.add_argument("--overlap", type=float, default=4.0)
    ap.add_argument("--engine", choices=list(ENGINES), default="assemblyai")
    ap.add_argument("--prompt", default="Business livestream. The host answers "
                    "audience questions and takes hotline calls about business, "
                    "sales, marketing, money, and scaling companies.")
    ap.add_argument("--keyterms-file", help="one bias term per line (brand vocab "
                    "loads by path — never baked into the skill)")
    a = ap.parse_args()
    work = Path(a.work).expanduser()
    key_name, engine_fn = ENGINES[a.engine]
    key = env_key(key_name)
    cfg = {"prompt": a.prompt}
    if a.keyterms_file:
        cfg["keyterms"] = [t.strip() for t in
                           Path(a.keyterms_file).read_text().splitlines()
                           if t.strip()][:900]

    state_f = work / "transcribe_state.json"
    words_f = work / "rolling_words.json"
    state = json.loads(state_f.read_text()) if state_f.exists() else {"done": []}
    words: list[dict] = json.loads(words_f.read_text()) if words_f.exists() else []

    while True:
        man = update_manifest(work)
        todo = [c for c in man["chunks"] if c["file"] not in state["done"]]
        for c in todo:
            prev = next((p for p in man["chunks"] if p["i"] == c["i"] - 1), None)
            with tempfile.TemporaryDirectory() as td:
                wav = Path(td) / "win.wav"
                win_t0 = make_window_audio(work, c, prev, a.overlap, wav)
                raw = engine_fn(wav, key, cfg)
            new = 0
            for w in raw:
                s, e = win_t0 + w["start"], win_t0 + w["end"]
                if (s + e) / 2 < c["t0"] or (s + e) / 2 >= c["t1"]:
                    continue  # previous / next pass owns it
                words.append({"w": w["word"].strip(), "s": round(s, 3),
                              "e": round(e, 3)})
                new += 1
            state["done"].append(c["file"])
            print(f"chunk {c['file']} [{c['t0']:.0f}-{c['t1']:.0f}s] +{new} words")
        if todo:
            words.sort(key=lambda w: w["s"])
            words_f.write_text(json.dumps(words))
            rebuild_rolling_txt(words, work / "rolling.txt")
            state_f.write_text(json.dumps(state))
        ingest_done = (work / "chunks" / "INGEST_DONE").exists()
        if not a.watch or (ingest_done and not todo):
            break
        if not todo:
            time.sleep(10)
    return 0


if __name__ == "__main__":
    sys.exit(main())
