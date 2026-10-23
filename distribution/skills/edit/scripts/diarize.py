#!/usr/bin/env python3
"""diarize.py --config <multicam_config.json>
Close-mic BLEED diarization. Each lav picks up BOTH speakers — label each word in the
HOST lav's Groq word-transcript by which mic was LOUDER at that moment (= the real speaker),
group into utterances, write per-episode `clean.json`.

Why louder-mic and not a clustering diarizer? With close lavs the level difference is huge
(~10-20 dB host:bleed), so a per-word RMS compare is dead-reliable and avoids the segment-
boundary artifacts of pyannote/etc. A diarize_bias multiplier (default 1.15) on `host` biases
toward the host so faint host coughs/agreements through the guest's mic don't flip ownership.

Inputs (under <project_root>/10_WORK/):
  - transcripts/{ep}_host.words.json     (Groq large-v3 verbose_json over the HOST's clean lav)
  - sync_map.json                        (run sync.py first; not used here but required downstream)
The Groq transcribe step itself runs from a main session (subagents are Bash-sandboxed) —
this skill consumes the existing transcript files.

Outputs:
  - transcripts/{ep}_clean.json   [{speaker:"host"|"guest", start, end, text}, ...]

Times = HOST_WAV time. Convert to wide-cam time with  wide_time = wav_time - Δ_host_wav
from sync_map.json when cutting (multicut.py does this for you)."""
import argparse, json, subprocess
from pathlib import Path
import numpy as np

SR, FR = 8000, 100


def env(path):
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-vn", "-i", str(path),
         "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
        capture_output=True).stdout
    a = np.frombuffer(raw, dtype=np.float32)
    n = SR // FR
    m = len(a) // n
    return np.sqrt((a[:m * n].reshape(m, n) ** 2).mean(axis=1) + 1e-9)   # 100 Hz RMS


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True, type=Path)
    args = ap.parse_args()
    cfg = json.loads(args.config.read_text())
    root = Path(cfg["project_root"]).expanduser()
    work = root / "10_WORK"
    tdir = work / "transcripts"
    tdir.mkdir(parents=True, exist_ok=True)

    host_bias = float(cfg.get("speakers", {}).get("host", {}).get("diarize_bias", 1.15))
    eps = cfg["episodes"]

    for ep, files in eps.items():
        if "host_wav" not in files or "guest_wav" not in files:
            print(f"⚠ {ep}: missing host_wav/guest_wav; skipping"); continue
        wpath = tdir / f"{ep}_host.words.json"
        if not wpath.exists():
            print(f"⚠ {ep}: {wpath.name} not found (transcribe HOST lav with Groq first); skipping")
            continue
        eg = env(root / files["host_wav"])
        et = env(root / files["guest_wav"])
        words = json.load(open(wpath))["words"]
        lab = []
        for w in words:
            i0 = int(w["start"] * FR)
            i1 = max(int(w["start"] * FR) + 1, int(w["end"] * FR))
            g = eg[i0:i1].mean() if i0 < len(eg) else 0.0
            t = et[i0:i1].mean() if i0 < len(et) else 0.0
            spk = "host" if g >= t * host_bias else "guest"
            lab.append({**w, "speaker": spk})
        utt, cur = [], None
        for w in lab:
            if cur and w["speaker"] == cur["speaker"] and w["start"] - cur["end"] < 0.7:
                cur["end"] = w["end"]
                cur["text"] += " " + w["word"]
            else:
                if cur:
                    utt.append(cur)
                cur = {"speaker": w["speaker"],
                       "start": round(w["start"], 2),
                       "end": round(w["end"], 2),
                       "text": w["word"]}
        if cur:
            utt.append(cur)
        json.dump(utt, open(tdir / f"{ep}_clean.json", "w"), indent=1)
        h_share = sum(1 for u in utt if u["speaker"] == "host") / max(1, len(utt))
        print(f"{ep}: {len(utt)} utterances, host {h_share:.0%} / guest {1 - h_share:.0%}")
        for u in utt[12:20]:
            print(f"  [{u['start']:.0f}] {u['speaker']}: {u['text'][:72]}")
        print()


if __name__ == "__main__":
    main()
