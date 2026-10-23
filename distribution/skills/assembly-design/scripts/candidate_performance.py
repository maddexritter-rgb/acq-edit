#!/usr/bin/env python3
"""Measure candidate speech/pause evidence before assembly design.

This is an inspection artifact, not a transcript correction, listening receipt, or
permission to cut. It reuses the shared Silero detector and leaves editorial
keep/remove decisions to assembly-design.
"""
from __future__ import annotations

import argparse
from array import array
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import wave


SCHEMA = "cut.candidate-performance/v2"
FILLER = {"uh", "um", "uhh", "umm", "ah", "er", "hmm", "mhm"}
SHORT_FUNCTION = {"a", "and", "because", "i", "is", "it", "of", "so", "that", "the", "this", "to", "was"}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def pin(path: Path) -> dict:
    path = path.resolve()
    return {"path": str(path), "sha256": sha256(path)}


def pinned_media(path: Path, identity_path: Path | None) -> dict:
    """Reuse a stable-copy digest already verified by ingest; do not rehash huge media."""
    if identity_path is None:
        return pin(path)
    identity = json.loads(identity_path.read_text())
    path = path.resolve()
    if identity.get('schema') != 'long-form-ingest.media-identity/v1' or \
            identity.get('identity_status') != 'SOURCE_AND_COPY_SHA256_MATCH' or \
            Path(identity.get('project_copy', '')).resolve() != path or \
            identity.get('size_bytes') != path.stat().st_size:
        raise ValueError('media identity does not match the stable project copy')
    digest = identity.get('project_copy_sha256')
    if not isinstance(digest, str) or len(digest) != 64 or \
            any(ch not in '0123456789abcdef' for ch in digest):
        raise ValueError('media identity lacks a valid SHA256')
    return {'path': str(path), 'sha256': digest,
            'identity_path': str(identity_path.resolve()),
            'identity_sha256': sha256(identity_path)}


def _clean(word: str) -> str:
    return "".join(ch for ch in word.lower() if ch.isalpha())


def _overlap(start: float, end: float, spans: list[list[float]]) -> float:
    return round(sum(max(0.0, min(end, b) - max(start, a)) for a, b in spans), 4)


def _rms_db(samples: array, rate: int, origin: float, start: float, end: float) -> float | None:
    lo = max(0, int((start - origin) * rate))
    hi = min(len(samples), int((end - origin) * rate))
    if hi <= lo:
        return None
    chunk = samples[lo:hi]
    power = sum(value * value for value in chunk) / len(chunk)
    return round(20 * math.log10(max(math.sqrt(power) / 32768, 1e-8)), 2)


def analyze(words: list[dict], first: int, last: int, fps: Fraction,
            speech: list[list[float]] | None, samples: array | None = None,
            rate: int = 16000, origin: float = 0.0) -> dict:
    """Pure source-indexed analysis; uncertain labels remain inspection prompts."""
    if not 0 <= first <= last < len(words):
        raise ValueError("candidate word range is outside source")
    rows = []
    for index in range(first, last + 1):
        word = words[index]
        start, end = float(word["start"]), float(word["end"])
        if not 0 <= start <= end:
            raise ValueError(f"invalid word timing at {index}")
        rows.append({"index": index, "word": word["word"], "start": start,
                     "end": end, "speaker": word.get("speaker", word.get("spk")),
                     "start_frame_floor": math.floor(start * fps),
                     "end_frame_ceil": math.ceil(end * fps)})
    durations = [row["end"] - row["start"] for row in rows if row["end"] > row["start"]]
    median = statistics.median(durations) if durations else 0.2
    events = []
    for row in rows:
        duration = row["end"] - row["start"]
        token = _clean(row["word"])
        if duration >= (0.6 if token in SHORT_FUNCTION else max(0.75, 1.6 * median)):
            events.append({"id": f"word_{row['index']}", "kind": "stretched_word",
                           "word_index": row["index"], "duration_s": round(duration, 4),
                           "rms_db": _rms_db(samples, rate, origin, row["start"], row["end"]) if samples is not None else None,
                           "speech_overlap_s": _overlap(row["start"], row["end"], speech) if speech is not None else None,
                           "interpretation": "inspect_for_hidden_stumble_or_pause"})
        if token in FILLER:
            events.append({"id": f"filler_{row['index']}", "kind": "filler_word",
                           "word_index": row["index"], "interpretation": "editorial_keep_or_remove"})
    for left, right in zip(rows, rows[1:]):
        start, end = left["end"], right["start"]
        if end - start < 0.35:
            continue
        events.append({"id": f"gap_{left['index']}_{right['index']}", "kind": "gap",
                       "after_word": left["index"], "before_word": right["index"],
                       "start": start, "end": end, "duration_s": round(end - start, 4),
                       "rms_db": _rms_db(samples, rate, origin, start, end) if samples is not None else None,
                       "speech_overlap_s": _overlap(start, end, speech) if speech is not None else None,
                       "interpretation": "inspect_speech_or_intentional_pause"})
    # ASR often butts consecutive word boxes through a real pause. A lexical-gap
    # scan cannot see it; compare measured nonspeech against the word boxes too.
    if speech is not None:
        for (_, speech_end), (next_start, _) in zip(speech, speech[1:]):
            start = max(float(speech_end), rows[0]["start"])
            end = min(float(next_start), rows[-1]["end"])
            if end - start < 0.35:
                continue
            covered = [row for row in rows if min(end, row["end"]) - max(start, row["start"]) > 0.01]
            label_overlap = sum(max(0.0, min(end, row["end"]) - max(start, row["start"]))
                                for row in covered)
            if label_overlap < min(0.15, (end - start) * 0.3):
                continue  # This is an ordinary transcript gap, already flagged above.
            events.append({"id": f"vad_conflict_{round(start * 1000)}_{round(end * 1000)}",
                           "kind": "vad_word_conflict", "start": round(start, 6),
                           "end": round(end, 6), "duration_s": round(end - start, 4),
                           "word_indices": [row["index"] for row in covered],
                           "word_label_overlap_s": round(label_overlap, 4),
                           "start_frame_floor": math.floor(start * fps),
                           "end_frame_ceil": math.ceil(end * fps),
                           "rms_db": _rms_db(samples, rate, origin, start, end) if samples is not None else None,
                           "interpretation": "ASR_labels_cover_measured_nonspeech_verify_audio_and_correct_timing"})
    return {"interaction_words": [first, last], "fps": str(fps), "words": rows,
            "speech_spans": speech, "events": events,
            "status": "MEASURED" if speech is not None and samples is not None else "PARTIAL"}


def extract(audio: Path, start: float, end: float, output: Path) -> None:
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-ss", f"{start:.6f}", "-t", f"{end-start:.6f}", "-i", str(audio),
                    "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(output)], check=True)


def duration(audio: Path) -> float:
    result = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries",
                                      "format=duration", "-of", "default=noprint_wrappers=1:nokey=1",
                                      str(audio)], text=True)
    return float(result.strip())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--words", required=True)
    parser.add_argument("--audio", required=True, help="Reference audio in the word clock")
    parser.add_argument("--first", type=int, required=True)
    parser.add_argument("--last", type=int, required=True)
    parser.add_argument("--fps", type=Fraction, required=True)
    parser.add_argument("--audio-offset", type=float, default=0.0,
                        help="Word-clock seconds corresponding to reference-audio time zero")
    parser.add_argument("--clock-evidence", help="Pinned mapping evidence required for a nonzero audio offset")
    parser.add_argument("--media-identity", type=Path,
                        help="Validated stable-copy identity from ingest; avoids rehashing large media")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    word_path, audio_path, output = Path(args.words), Path(args.audio), Path(args.out)
    if output.exists():
        parser.error("output exists; use a new versioned path")
    words = json.loads(word_path.read_text())["words"]
    if not 0 <= args.first <= args.last < len(words):
        parser.error("candidate word range is outside source")
    start = max(args.audio_offset, float(words[args.first]["start"]) - 0.5)
    end = float(words[args.last]["end"]) + 0.5
    audio_end = args.audio_offset + duration(audio_path)
    if float(words[args.last]["end"]) > audio_end + 0.002:
        parser.error("reference audio does not cover the final candidate word")
    end = min(end, audio_end)
    if end <= start or args.fps <= 0 or start < args.audio_offset:
        parser.error("invalid candidate time range or frame rate")
    if args.audio_offset and not args.clock_evidence:
        parser.error("nonzero audio offset requires --clock-evidence")
    with tempfile.TemporaryDirectory(prefix="candidate-performance-") as temp:
        wav = Path(temp) / "candidate.wav"
        extract(audio_path, start - args.audio_offset, end - args.audio_offset, wav)
        with wave.open(str(wav), "rb") as handle:
            rate = handle.getframerate()
            samples = array("h")
            samples.frombytes(handle.readframes(handle.getnframes()))
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
        from silero_vad import speech_spans
        local_speech = speech_spans(str(wav))
        speech = [[round(start + a, 6), round(start + b, 6)] for a, b in local_speech] if local_speech is not None else None
        result = analyze(words, args.first, args.last, args.fps, speech, samples, rate, start)
    result.update(schema=SCHEMA, source_words=pin(word_path),
                  reference_audio=pinned_media(audio_path, args.media_identity),
                  audio_clock_offset_s=args.audio_offset, word_clock_seconds=[start, end],
                  reference_audio_seconds=[start - args.audio_offset, end - args.audio_offset],
                  vad_engine="silero-vad" if speech is not None else "unavailable")
    if args.clock_evidence:
        result['clock_evidence'] = pin(Path(args.clock_evidence))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"out": str(output), "status": result["status"], "events": len(result["events"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
