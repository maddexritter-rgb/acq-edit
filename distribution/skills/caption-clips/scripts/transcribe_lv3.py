#!/usr/bin/env python3
"""Per-clip Whisper-Large-v3 transcription via Groq.

Why per-clip + lv3 (not boundaries-mode + turbo):
- Boundaries-mode (one Whisper call over whole source) drops the first/last
  words of each clip because Whisper's VAD skips quiet starts when surrounded
  by silence/black.
- Turbo model occasionally mis-hears proper nouns and contractions
  (e.g. "who were" → "we were", missing "We" at the very start).

Per-clip lv3 fixes both. Cost is one Groq API call per clip + audio extraction.

Usage:
    python3 transcribe_lv3.py <source.mp4> <boundaries.json> --out transcripts/

    # Or single clip:
    python3 transcribe_lv3.py <source.mp4> --start 15.75 --end 62.20 \
        --out transcripts/clip_00.json

Output JSON per clip:
    { "clip_index": int, "source_start": float, "source_end": float,
      "duration": float,
      "words": [ {"word": str, "start": float, "end": float, "prob": float}, ... ] }
"""
from __future__ import annotations
import argparse, json, os, re, subprocess, sys, time
from pathlib import Path


def load_zshrc_api_keys() -> None:
    """Lift API_KEY/TOKEN exports from ~/.zshrc into os.environ."""
    zshrc = Path.home() / ".zshrc"
    if not zshrc.exists():
        return
    for line in zshrc.read_text().splitlines():
        m = re.match(r'^\s*export\s+([A-Z_][A-Z0-9_]*)=(.*)$', line)
        if m and ("API_KEY" in m.group(1) or "TOKEN" in m.group(1)):
            val = m.group(2).strip().strip('"').strip("'")
            os.environ.setdefault(m.group(1), val)


def transcribe_clip(source: str, start: float, end: float,
                     api_key: str, model: str = 'whisper-large-v3') -> list[dict]:
    """Extract audio for [start, end] from source, send to Groq, return words."""
    import requests, os
    # Unique temp per PROCESS (+ start for multi-chunk within one) so PARALLEL clips never clobber
    # each other's extracted audio. A fixed path keyed only by start (=0 for every clip) caused
    # cross-contaminated captions when clips transcribed concurrently — never again.
    audio = f'/tmp/_transcribe_lv3_{os.getpid()}_{int(start*1000)}.mp3'
    subprocess.run([
        'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
        '-ss', f'{start:.3f}', '-to', f'{end:.3f}', '-i', source,
        '-vn', '-ac', '1', '-ar', '16000',
        '-c:a', 'libmp3lame', '-b:a', '64k', audio,
    ], check=True)
    with open(audio, 'rb') as f:
        r = requests.post(
            'https://api.groq.com/openai/v1/audio/transcriptions',
            headers={'Authorization': f'Bearer {api_key}'},
            files={'file': (Path(audio).name, f, 'audio/mpeg')},
            data={
                'model': model,
                'response_format': 'verbose_json',
                'timestamp_granularities[]': 'word',
                'language': 'en',
            },
        )
    Path(audio).unlink(missing_ok=True)
    if r.status_code == 429:
        raise RuntimeError(f'rate limited: {r.text[:200]}')
    if r.status_code != 200:
        raise RuntimeError(f'groq error {r.status_code}: {r.text[:300]}')
    j = r.json()
    return [
        {
            'word': w['word'].strip(),
            'start': round(w['start'], 3),
            'end': round(w['end'], 3),
            'prob': 1.0,
        }
        for w in j.get('words', [])
    ]


def _window_rms(source: str, start: float, end: float) -> float | None:
    """Overall RMS (dB) of source audio in [start, end], or None on probe failure."""
    try:
        out = subprocess.run(
            ['ffmpeg', '-ss', f'{start:.3f}', '-t', f'{end - start:.3f}', '-i', source,
             '-af', 'astats=metadata=1,ametadata=print:key=lavfi.astats.Overall.RMS_level',
             '-f', 'null', '-'],
            capture_output=True, text=True).stderr
        vals = re.findall(r'RMS_level=(-?[\d.]+)', out)
        return float(vals[-1]) if vals else None
    except Exception:
        return None


def heal_coverage_holes(source: str, start: float, end: float, words: list[dict],
                        api_key: str, model: str) -> list[dict]:
    """COVERAGE GATE: Whisper can deterministically drop a long span after an
    opening line + pause (seen 2026-07-08: two Q&A clips lost 2.9s→30.0s — the
    entire first answer chunk — while audio was healthy speech). Word times here
    are RELATIVE to the extracted [start, end] window.

    For every internal gap >3s whose audio is speech-level (RMS > -38dB),
    re-transcribe JUST that span as a fresh window (fresh window = Whisper
    recovers) and merge. If a speech-level hole survives healing, HARD FAIL —
    never ship a partially-captioned clip as done."""
    dur = end - start

    def find_gaps(ws: list[dict]) -> list[tuple[float, float]]:
        out, prev = [], 0.0
        for w in ws:
            if w['start'] - prev > 3.0:
                out.append((prev, w['start']))
            prev = max(prev, w['end'])
        if dur - prev > 3.0:
            out.append((prev, dur))
        return out

    for g0, g1 in find_gaps(words):
        rms = _window_rms(source, start + g0, start + g1)
        if rms is None or rms < -38.0:
            continue  # genuinely quiet (room tone / music tail) — not a hole
        sub = transcribe_clip(source, start + g0, start + g1, api_key, model)
        sub = [{**w, 'start': round(w['start'] + g0, 3), 'end': round(w['end'] + g0, 3)}
               for w in sub]
        words = sorted(words + sub, key=lambda w: w['start'])
        print(f'  coverage-heal: gap {g0:.1f}-{g1:.1f}s had speech (RMS {rms:.0f}dB) '
              f'→ re-transcribed, +{len(sub)} words', flush=True)

    remaining = [g for g in find_gaps(words)
                 if (_window_rms(source, start + g[0], start + g[1]) or -99.0) >= -38.0]
    if remaining:
        sys.exit(f'TRANSCRIPT COVERAGE GATE FAILED: speech-level holes remain after '
                 f'healing: {[(round(a,1), round(b,1)) for a, b in remaining]} — refusing '
                 f'to emit a partial transcript.')
    return words


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('source', type=str)
    ap.add_argument('boundaries', type=Path, nargs='?')
    ap.add_argument('--start', type=float)
    ap.add_argument('--end', type=float)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--model', default='whisper-large-v3',
                    choices=['whisper-large-v3', 'whisper-large-v3-turbo'])
    ap.add_argument('--rate-limit-cushion', type=float, default=3.5,
                    help='Seconds between Groq calls (20 RPM = 3s min)')
    args = ap.parse_args()

    load_zshrc_api_keys()
    api_key = os.environ.get('GROQ_API_KEY')
    if not api_key:
        sys.exit('GROQ_API_KEY not set')

    # Single-clip mode
    if args.boundaries is None:
        if args.start is None or args.end is None:
            sys.exit('Need either boundaries.json or --start/--end')
        words = transcribe_clip(args.source, args.start, args.end,
                                api_key, args.model)
        words = heal_coverage_holes(args.source, args.start, args.end, words,
                                    api_key, args.model)
        out = {
            'clip_index': 0, 'source_start': args.start, 'source_end': args.end,
            'duration': round(args.end - args.start, 3), 'words': words,
        }
        args.out.write_text(json.dumps(out, indent=2))
        print(f'{len(words)} words → {args.out}')
        return 0

    # Batch mode
    args.out.mkdir(parents=True, exist_ok=True)
    b = json.loads(args.boundaries.read_text())
    last_call = 0.0
    for clip in b['clips']:
        i, s, e = clip['index'], clip['start'], clip['end']
        out_path = args.out / f'clip_{i:02d}.json'
        # Skip if already transcribed with the same boundary (resume support)
        if out_path.exists():
            try:
                existing = json.loads(out_path.read_text())
                if abs(existing.get('source_start', -1) - s) < 0.01 and \
                   abs(existing.get('source_end', -1) - e) < 0.01:
                    print(f'clip {i:02d}: already transcribed → skip')
                    continue
            except Exception:
                pass  # corrupt or stale — re-do
        # Rate-limit guard (Groq free tier = 20 RPM)
        wait = args.rate_limit_cushion - (time.time() - last_call)
        if wait > 0:
            time.sleep(wait)
        for attempt in range(5):
            try:
                words = transcribe_clip(args.source, s, e, api_key, args.model)
                break
            except RuntimeError as ex:
                if 'rate limited' in str(ex) and attempt < 4:
                    print(f'  clip {i:02d} rate-limited, sleep 8s…')
                    time.sleep(8); continue
                raise
        last_call = time.time()
        words = heal_coverage_holes(args.source, s, e, words, api_key, args.model)
        out_path = args.out / f'clip_{i:02d}.json'
        out_path.write_text(json.dumps({
            'clip_index': i, 'source_start': s, 'source_end': e,
            'duration': round(e - s, 3), 'words': words,
        }, indent=2))
        preview = ' '.join(w['word'] for w in words[:8])
        print(f'clip {i:02d}: {len(words)} words | {preview}…')
    return 0


if __name__ == '__main__':
    sys.exit(main())
