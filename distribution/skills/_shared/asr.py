#!/usr/bin/env python3
"""asr.py — shared transcription for editorial ingest and audit gates.

Why this exists: the Groq key died 2026-08-03 and three audit gates (audit-audio,
audit-captions, audit-script) silently PASSED their transcript-dependent checks when
transcription failed — word-clipping, caption-accuracy, timing and gap checks all
"skipped" as green. Compounding standard: a gate that cannot run must fail LOUD.

Profiles:

``audit`` keeps the established Groq -> local MLX chain.

``editorial_ingest`` uses AssemblyAI Universal-3 Pro first, with disfluencies
and speaker labels enabled, then degrades to Groq -> local MLX.  The fallback
is explicitly marked PARTIAL because Whisper-family output can normalize away
fillers and does not provide equivalent speaker evidence.
Callers convert AsrUnavailable into verdict UNKNOWN + non-zero exit — never a PASS.

    from asr import transcribe, AsrUnavailable
    res = transcribe(clip_path)           # word granularity
    res["words"]    -> [{"word","start","end"}, ...]
    res["segments"] -> verbose_json-style segments (text,start,end)
    res["text"], res["engine"] ("groq"|"mlx")
"""
from __future__ import annotations

import os
import re
import subprocess
import tempfile
import time
from pathlib import Path

GROQ_MODEL = "whisper-large-v3"
MLX_MODEL = "mlx-community/whisper-large-v3-mlx"
AAI_BASE = "https://api.assemblyai.com"
AAI_MODELS = ["universal-3-5-pro", "universal-2"]


class AsrUnavailable(RuntimeError):
    """No transcription engine could produce a result. Gates must go UNKNOWN, not PASS."""


def api_key(name: str, config_path: str | None = None) -> str | None:
    k = os.environ.get(name)
    if k:
        return k
    paths = [Path.home() / ".zshrc"]
    if config_path:
        paths.append(Path.home() / config_path)
    for p in paths:
        try:
            if p.exists():
                if p.name == "api_key":
                    return p.read_text().strip() or None
                m = re.search(rf'{re.escape(name)}=["\']?([^"\'\s]+)', p.read_text())
                if m:
                    return m.group(1)
        except Exception:
            pass
    return None


def groq_key() -> str | None:
    return api_key("GROQ_API_KEY", ".config/groq/api_key")


def assemblyai_key() -> str | None:
    # A saved key rotation must supersede stale environment inherited by a running agent.
    saved = Path.home() / ".config/assemblyai/api_key"
    if saved.is_file():
        key = saved.read_text().strip()
        if key:
            return key
    return api_key("ASSEMBLYAI_API_KEY", ".config/assemblyai/api_key")


def assemblyai_keys() -> list[str]:
    """Primary key, then ~/.config/assemblyai/backup_keys (one per line, # comments)."""
    keys = [assemblyai_key()]
    backups = Path.home() / ".config/assemblyai/backup_keys"
    if backups.is_file():
        keys += [l.strip() for l in backups.read_text().splitlines()
                 if l.strip() and not l.strip().startswith("#")]
    return list(dict.fromkeys(k for k in keys if k))


_LAST_AAI_ERROR = ""
# Only account-level refusals rotate keys; a retry after a timeout could bill a running job twice.
_AAI_ACCOUNT_ERROR = re.compile(r"balance|top up|401|403|unauthori[sz]ed|invalid api key|authentication", re.I)


def _wav16(clip_path: str) -> str:
    wav = tempfile.mktemp(suffix=".wav")
    r = subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", clip_path, "-vn", "-ac", "1", "-ar", "16000", wav],
        capture_output=True,
    )
    if r.returncode != 0 or not os.path.exists(wav):
        raise AsrUnavailable(f"ffmpeg audio extract failed: {r.stderr.decode()[:200]}")
    return wav


def _groq(wav: str, key: str) -> dict | None:
    try:
        import httpx
        with open(wav, "rb") as f:
            resp = httpx.post(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                # Groq behind Cloudflare 403s non-browser UAs (error 1010)
                headers={"Authorization": f"Bearer {key}",
                         "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"},
                files={"file": ("audio.wav", f, "audio/wav")},
                data={"model": GROQ_MODEL, "response_format": "verbose_json",
                      "timestamp_granularities[]": "word"},
                timeout=120,
            )
        resp.raise_for_status()
        out = resp.json()
        words = out.get("words") or []
        if not words:
            for s in out.get("segments", []):
                words.extend(s.get("words", []))
        return {"text": out.get("text", ""), "words": words,
                "segments": out.get("segments", []), "engine": "groq"}
    except Exception as e:
        print(f"[asr] groq failed ({type(e).__name__}: {e}) — falling back to local mlx_whisper", flush=True)
        return None


def _assemblyai(wav: str, key: str, prompt: str | None,
                keyterms: list[str] | None) -> dict | None:
    """Return provider-native word evidence normalized to the shared shape."""
    try:
        import httpx
        headers = {"authorization": key}
        with open(wav, "rb") as f:
            upload = httpx.post(f"{AAI_BASE}/v2/upload", headers=headers,
                                content=f, timeout=180)
        upload.raise_for_status()
        body: dict = {
            "audio_url": upload.json()["upload_url"],
            "speech_models": AAI_MODELS,
            "language_code": "en",
            "disfluencies": True,
            "speaker_labels": True,
        }
        if prompt:
            body["prompt"] = prompt
        if keyterms:
            body["keyterms_prompt"] = [str(x) for x in keyterms if str(x).strip()][:900]
        submitted = httpx.post(f"{AAI_BASE}/v2/transcript", headers=headers,
                               json=body, timeout=60)
        submitted.raise_for_status()
        transcript_id = submitted.json().get("id")
        if not transcript_id:
            raise RuntimeError("submit response did not include transcript id")
        deadline = time.time() + 900
        data = None
        while time.time() < deadline:
            response = httpx.get(f"{AAI_BASE}/v2/transcript/{transcript_id}",
                                 headers=headers, timeout=60)
            response.raise_for_status()
            data = response.json()
            if data.get("status") == "completed":
                break
            if data.get("status") == "error":
                raise RuntimeError(data.get("error") or "unknown transcription error")
            time.sleep(2)
        if not data or data.get("status") != "completed":
            raise RuntimeError("transcription poll timed out")
        words = [{
            "word": w.get("text", "").strip(),
            "start": w.get("start", 0) / 1000.0,
            "end": w.get("end", 0) / 1000.0,
            "confidence": w.get("confidence"),
            "speaker": w.get("speaker"),
        } for w in data.get("words") or []]
        utterances = [{
            "text": u.get("text", ""),
            "start": u.get("start", 0) / 1000.0,
            "end": u.get("end", 0) / 1000.0,
            "speaker": u.get("speaker"),
            "confidence": u.get("confidence"),
        } for u in data.get("utterances") or []]
        return {
            "text": data.get("text", ""),
            "words": words,
            "segments": utterances,
            "utterances": utterances,
            "engine": "assemblyai",
            "model": data.get("speech_model") or AAI_MODELS[0],
            "evidence_status": "FULL",
            "provider_transcript_id": transcript_id,
            "provider_response": data,
        }
    except Exception as e:
        global _LAST_AAI_ERROR
        body = getattr(getattr(e, "response", None), "text", "") or ""
        _LAST_AAI_ERROR = f"{type(e).__name__}: {e} {body[:200]}"
        print(f"[asr] assemblyai failed ({_LAST_AAI_ERROR}) — falling back", flush=True)
        return None


def _mlx(wav: str) -> dict | None:
    try:
        import mlx_whisper
        out = mlx_whisper.transcribe(wav, path_or_hf_repo=MLX_MODEL, word_timestamps=True)
        words, segments = [], []
        for seg in out.get("segments", []):
            segments.append({"text": seg.get("text", ""),
                             "start": seg.get("start"), "end": seg.get("end")})
            for w in seg.get("words", []):
                words.append({"word": w.get("word", "").strip(),
                              "start": w.get("start"), "end": w.get("end")})
        return {"text": out.get("text", ""), "words": words,
                "segments": segments, "engine": "mlx"}
    except Exception as e:
        print(f"[asr] mlx_whisper failed ({type(e).__name__}: {e})", flush=True)
        return None


def _cache_path(clip_path: str, profile: str) -> Path:
    """Cache key = clip path + size + mtime, so a re-render invalidates it."""
    import hashlib
    st = os.stat(clip_path)
    h = hashlib.sha256(
        f"{os.path.abspath(clip_path)}|{st.st_size}|{int(st.st_mtime)}|{profile}".encode()
    ).hexdigest()[:16]
    d = Path(os.environ.get("ACQ_ASR_CACHE", "/tmp/acq_asr_cache"))
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{h}.json"


def transcribe(clip_path: str, use_cache: bool = True, *, profile: str = "audit",
               prompt: str | None = None, keyterms: list[str] | None = None) -> dict:
    """Transcribe with word timestamps. Raises AsrUnavailable when no engine works.

    CACHED by (path, size, mtime): the step-9 audit fan-out runs audit-audio,
    audit-captions and audit-script on the SAME delivered file, and each used to
    transcribe it independently — 3 identical ASR calls per clip. First caller pays,
    the rest hit the cache. A re-render changes mtime/size, so the cache self-invalidates.
    Set ACQ_ASR_CACHE to relocate; use_cache=False to force a fresh call.
    """
    if profile not in {"audit", "editorial_ingest"}:
        raise ValueError(f"unknown ASR profile: {profile}")
    cp = _cache_path(clip_path, profile) if use_cache else None
    if cp and cp.exists():
        try:
            import json
            res = json.loads(cp.read_text())
            print(f"[asr] cache HIT ({res.get('engine')}, {len(res.get('words', []))} words)", flush=True)
            return res
        except Exception:
            pass                                     # corrupt cache -> re-transcribe
    wav = _wav16(clip_path)
    try:
        res = None
        if profile == "editorial_ingest":
            for n, aai_key in enumerate(assemblyai_keys()):
                global _LAST_AAI_ERROR
                _LAST_AAI_ERROR = ""
                res = _assemblyai(wav, aai_key, prompt, keyterms)
                if res is not None or not _AAI_ACCOUNT_ERROR.search(_LAST_AAI_ERROR):
                    break
                print(f"[asr] assemblyai key #{n + 1} refused by account; trying next key", flush=True)
        key = groq_key()
        if res is None and key:
            res = _groq(wav, key)
        if res is None:
            res = _mlx(wav)
        if res is None:
            raise AsrUnavailable(
                "no ASR engine available for profile " + profile
                + ". Gate must report UNKNOWN, not PASS."
            )
        if profile == "editorial_ingest" and res.get("engine") != "assemblyai":
            res["evidence_status"] = "PARTIAL"
            res["limitations"] = [
                "disfluencies may have been normalized away",
                "speaker attribution is not equivalent to AssemblyAI diarization",
            ]
        else:
            res.setdefault("evidence_status", "FULL")
        res["profile"] = profile
        if cp:
            try:
                import json
                cp.write_text(json.dumps(res))
            except Exception:
                pass                                 # cache write is best-effort
        return res
    finally:
        if os.path.exists(wav):
            os.unlink(wav)


if __name__ == "__main__":
    import json
    import sys
    r = transcribe(sys.argv[1])
    print(json.dumps({"engine": r["engine"], "n_words": len(r["words"]),
                      "text": r["text"][:200]}, indent=1))
