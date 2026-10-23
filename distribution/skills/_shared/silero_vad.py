#!/usr/bin/env python3
"""THE Silero VAD engine — the single owner of neural voice-activity detection.

Why this file exists: Silero VAD is a trained speech detector. It beats ffmpeg
`silencedetect` (a dumb dB threshold) at telling speech from silence — it catches
breathy/soft pauses a threshold misses and does NOT flag quiet-but-voiced tails as
silence. Bake-off vs 13 editor ground-truth cuts (2026-07-07): Silero 10 clean
detections incl. a breathy pause silencedetect missed; silencedetect 28 noisy ones.

ONE engine, one home. Every silence-removal consumer (jumpcut.py, ...) calls
`silence_spans()` here — nobody imports silero directly. This keeps Silero's heavy
torch dependency isolated in its own venv and gives every caller the same behavior +
the same graceful fallback.

Design: silero lives in its own venv (`~/.local/share/silero-vad/venv`) with torch,
separate from the skills' python. So this file runs the model in a SUBPROCESS under
that venv (re-executing itself in `--_worker` mode) and returns plain JSON. Any caller
in any python gets speech/silence spans without importing torch.

Public API (import from any python):
    silence_spans(src, min_silence=0.18, speech_pad_ms=30, threshold=0.5)
        -> list[(start, end)] silence spans in seconds, OR None if Silero is unavailable
           (caller MUST fall back loudly — never ship a silent regression to silencedetect).
    speech_spans(src, ...) -> list[(start, end)] speech spans, OR None.

CLI (standalone / bake-off):
    python3 silero_vad.py <audio_or_video> [--min-silence 0.18] [--pad-ms 30] [--threshold 0.5]
        prints JSON {"engine","duration","speech":[[s,e]...],"silence":[[s,e]...]}
"""
from __future__ import annotations
import argparse, json, os, subprocess, sys, tempfile, wave
from pathlib import Path

# The venv Silero + torch live in (installed 2026-07-07). Override with SILERO_VENV.
VENV = Path(os.environ.get("SILERO_VENV", os.path.expanduser("~/.local/share/silero-vad/venv")))
VENV_PY = VENV / "bin" / "python"


def _probe_dur(path: str) -> float:
    return float(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", path]).decode().strip())


def _extract_wav(src: str, wav_path: str) -> None:
    """16 kHz mono PCM — what Silero expects, and readable by the stdlib `wave` module
    (we avoid torchaudio's loader: it needs torchcodec and is broken in this venv)."""
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
         "-i", src, "-ac", "1", "-ar", "16000", "-vn",
         "-c:a", "pcm_s16le", wav_path],
        check=True)


def _worker(wav_path: str, threshold: float, min_silence_ms: int, pad_ms: int) -> int:
    """Runs INSIDE the silero venv. Loads audio via stdlib wave (no torchaudio),
    runs the model, prints speech spans as JSON."""
    # This file is named silero_vad.py; its own dir on sys.path[0] would shadow the
    # installed `silero_vad` package. Drop the script dir so the real package wins.
    _here = os.path.dirname(os.path.abspath(__file__))
    sys.path[:] = [p for p in sys.path if p not in ("", ".", _here)]
    import numpy as np, torch
    from silero_vad import load_silero_vad, get_speech_timestamps

    with wave.open(wav_path, "rb") as w:
        sr = w.getframerate()
        raw = w.readframes(w.getnframes())
    audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    tensor = torch.from_numpy(audio)

    model = load_silero_vad()
    ts = get_speech_timestamps(
        tensor, model,
        sampling_rate=sr,
        threshold=threshold,
        min_silence_duration_ms=min_silence_ms,
        speech_pad_ms=pad_ms,
        # The package defaults to 0.1-second rounding in seconds mode. Preserve
        # sample positions: rounded gaps can create or erase a legal video frame.
        return_seconds=False,
    )
    print(json.dumps([[t["start"] / sr, t["end"] / sr] for t in ts]))
    return 0


def speech_spans(src, min_silence: float = 0.18, speech_pad_ms: int = 30,
                 threshold: float = 0.5):
    """Speech spans (seconds) via Silero, or None if Silero is unavailable.
    None means the caller MUST fall back — and should say so out loud."""
    src = str(src)
    if not VENV_PY.exists():
        return None
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    try:
        _extract_wav(src, tmp.name)
        r = subprocess.run(
            [str(VENV_PY), os.path.abspath(__file__), "--_worker", tmp.name,
             "--threshold", str(threshold),
             "--min-silence-ms", str(int(min_silence * 1000)),
             "--pad-ms", str(int(speech_pad_ms))],
            capture_output=True, text=True)
        if r.returncode != 0:
            return None
        return [(float(s), float(e)) for s, e in json.loads(r.stdout.strip())]
    except Exception:
        return None
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


def silence_spans(src, min_silence: float = 0.18, speech_pad_ms: int = 30,
                  threshold: float = 0.5):
    """Silence spans (seconds) = the complement of speech within [0, duration].
    Same shape as jumpcut's silencedetect output. None if Silero is unavailable."""
    sp = speech_spans(src, min_silence=min_silence, speech_pad_ms=speech_pad_ms,
                      threshold=threshold)
    if sp is None:
        return None
    dur = _probe_dur(str(src))
    sp = sorted(sp)
    sils, cursor = [], 0.0
    for s, e in sp:
        if s - cursor >= min_silence:
            sils.append((cursor, s))
        cursor = max(cursor, e)
    if dur - cursor >= min_silence:
        sils.append((cursor, dur))
    return sils


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    # hidden worker mode (runs under the silero venv)
    ap.add_argument("--_worker", dest="worker")
    ap.add_argument("--threshold", type=float, default=0.5)
    ap.add_argument("--min-silence-ms", type=int, default=180)
    ap.add_argument("--pad-ms", type=int, default=30)
    # standalone / bake-off mode
    ap.add_argument("src", nargs="?")
    ap.add_argument("--min-silence", type=float, default=0.18)
    args = ap.parse_args()

    if args.worker:
        return _worker(args.worker, args.threshold, args.min_silence_ms, args.pad_ms)

    if not args.src:
        ap.error("src required (audio or video file)")
    sils = silence_spans(args.src, min_silence=args.min_silence,
                         speech_pad_ms=args.pad_ms, threshold=args.threshold)
    if sils is None:
        print(json.dumps({"engine": "unavailable", "silence": None}))
        return 1
    sp = speech_spans(args.src, min_silence=args.min_silence,
                      speech_pad_ms=args.pad_ms, threshold=args.threshold)
    print(json.dumps({
        "engine": "silero-vad",
        "duration": _probe_dur(args.src),
        "speech": sp,
        "silence": sils,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
