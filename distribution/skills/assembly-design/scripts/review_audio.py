#!/usr/bin/env python3
"""Send actual audio to Gemini and preserve evidence; never grants acoustic approval."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_MODEL = "gemini-3.1-pro-preview"
PROMPT = (
    "Listen to the entire supplied audio. Review sound only, not editorial selection. "
    "Inspect clipped consonants and word releases, intrusive syllables from excluded "
    "words, clicks, repeated sounds, unnatural splice cadence and unnecessary pauses. "
    "Do not reconstruct missing sounds merely because you understand the sentence. "
    "Distinguish defects from normal speech. Report uncertainty and specific timestamps. "
    "Return JSON with observations and issues; no issue invented to fill the list. "
)


def credential(slot):
    folder = Path.home() / ".config/assembly-design"
    if slot in ("paid", "fallback"):
        path = folder / ("gemini-paid-key" if slot == "paid" else "gemini-fallback-key")
        if path.stat().st_mode & 0o077:
            raise ValueError("Credential file must have owner-only permissions")
        key = path.read_text().strip()
    else:
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
        from asr import api_key
        key = api_key("GEMINI_API_KEY")
    if not key:
        raise ValueError("Selected credential is unavailable")
    return key


def save(path, value):
    with path.open("x") as f:
        json.dump(value, f, indent=2, allow_nan=False)
        f.write("\n")


def run(args):
    key = credential(args.credential)
    audio = args.audio.resolve()
    mime = {".wav": "audio/wav", ".flac": "audio/flac", ".mp3": "audio/mpeg"}.get(audio.suffix.lower())
    if not mime:
        raise ValueError("Use WAV, FLAC or MP3 audio")
    raw = audio.read_bytes()
    if not raw or len(raw) > 14_000_000:
        raise ValueError("Inline audio must be nonempty and at most 14 MB; use bounded review regions")
    prompt = PROMPT + (args.prompt_file.read_text() if args.prompt_file else "")
    body = {
        "contents": [{"role": "user", "parts": [
            {"inlineData": {"mimeType": mime, "data": base64.b64encode(raw).decode()}},
            {"text": prompt},
        ]}],
        "generationConfig": {"responseMimeType": "application/json", "maxOutputTokens": 8192},
    }
    args.out.mkdir(parents=True, exist_ok=False)
    save(args.out / "request.json", {
        "model": args.model, "credential_slot": args.credential,
        "audio": {"path": str(audio), "sha256": hashlib.sha256(raw).hexdigest()},
        "prompt": prompt, "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "generation_config": body["generationConfig"],
        "scope": "Audio model evidence only; qualification and seam review remain separate.",
    })
    url = "https://generativelanguage.googleapis.com/v1beta/models/" + urllib.parse.quote(args.model, safe="") + ":generateContent"
    request = urllib.request.Request(url, data=json.dumps(body).encode(), headers={
        "Content-Type": "application/json", "x-goog-api-key": key,
    })
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            payload = json.loads(response.read())
    except urllib.error.HTTPError as error:
        detail = error.read().decode(errors="replace").replace(key, "[REDACTED]")
        save(args.out / "error.json", {"http_status": error.code, "detail": detail})
        print(json.dumps({"status": "API_ERROR", "http_status": error.code, "evidence": str(args.out)}))
        return 2
    except (urllib.error.URLError, TimeoutError) as error:
        save(args.out / "error.json", {"type": type(error).__name__, "detail": str(error).replace(key, "[REDACTED]"), "outcome": "unknown; do not automatically replay"})
        print(json.dumps({"status": "TRANSPORT_ERROR", "evidence": str(args.out)}))
        return 2
    # Preserve the original response, including token usage and finish reason.
    save(args.out / "response.raw.json", payload)
    candidates = payload.get("candidates", [])
    if not candidates or candidates[0].get("finishReason") != "STOP":
        print(json.dumps({"status": "INCOMPLETE_RESPONSE", "evidence": str(args.out)}))
        return 2
    text = "".join(p.get("text", "") for p in candidates[0].get("content", {}).get("parts", []) if not p.get("thought"))
    try:
        review = json.loads(text)
    except json.JSONDecodeError:
        print(json.dumps({"status": "INVALID_REVIEW_JSON", "evidence": str(args.out)}))
        return 2
    save(args.out / "review.json", review)
    print(json.dumps({"status": "RESPONSE_SAVED_NOT_QUALIFICATION", "evidence": str(args.out), "usage": payload.get("usageMetadata")}))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--audio", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True, help="New evidence directory; never overwritten")
    ap.add_argument("--prompt-file", type=Path)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--credential", choices=("paid", "legacy", "fallback"), default="paid")
    args = ap.parse_args()
    try:
        return run(args)
    except (OSError, ValueError) as error:
        print(json.dumps({"status": "INPUT_ERROR", "type": type(error).__name__}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
