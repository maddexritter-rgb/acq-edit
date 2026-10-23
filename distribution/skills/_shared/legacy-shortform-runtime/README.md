# legacy-shortform-runtime

Two runtime scripts lifted **byte-identical** from the retired `shortform` pipeline
(`__ACQ_ASSETS__/content-skill-system/shortform/scripts/`), so active skills stop
depending on a vault path or on a top-level skill that does not exist.

This is a **shared library, not a skill** — deliberately no `SKILL.md`, so no agent
loads or routes to it. The vault originals remain untouched.

| script | consumers | contract |
|---|---|---|
| `scripts/silence_map.py` | `transcript-edit` invokes it; `edit/scripts/detect_fillers.py` consumes its `silence_map.json` output | stdlib only (`argparse, json, re, subprocess, sys, pathlib`); shells out to **ffmpeg** `silencedetect`. No file or preset reads. |
| `scripts/transcribe_groq.py` | `caption-clips/training/extract_oliver_style.py`, `caption-clips/training/extract_caption_strips.py` | see runtime contract below |

## `transcribe_groq.py` runtime contract

Not self-contained — it has environmental dependencies that copying bytes cannot satisfy:

- **`GROQ_API_KEY`** (env) — required for the Groq path. Absent, it falls back.
- **fallback** — local `faster-whisper` when `GROQ_API_KEY` is unset.
- **`requests`** (optional) — preferred for multipart upload; otherwise `urllib`.
- **`FFMPEG`** (env, optional) — overrides ffmpeg discovery.

Callers must treat a missing key as "fallback engine ran", never as failure, and must
record which engine actually produced the transcript.

## Output contract — `silence_map.json`

`silence_map.py` writes a JSON list of silent intervals. `edit/scripts/detect_fillers.py`
reads it via `--silence-map` and snaps cut boundaries to those intervals. Changing the
shape of that file breaks `edit`, not just `transcript-edit`.
