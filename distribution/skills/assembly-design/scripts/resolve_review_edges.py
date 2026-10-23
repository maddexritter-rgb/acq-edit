#!/usr/bin/env python3
"""Resolve selected words to source frames for a provisional editor-review timeline.

Use the calibrated speech map first. Preserve independently measured edges;
locally measure refused edges on the frame grid without changing selected words.
Provisional edges still require the editor's listening and adjustment.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile

import numpy as np

EDIT_SCRIPTS = Path(__file__).resolve().parents[2] / 'edit' / 'scripts'
STRICT_CUTTER = Path(__file__).resolve().parents[2] / '_shared' / 'speech_map_cut.py'
sys.path.insert(0, str(EDIT_SCRIPTS))
from compile_assembly import digest, validate_compiled  # noqa: E402


def source_fps(media: str) -> Fraction:
    raw = subprocess.check_output([
        'ffprobe', '-v', 'error', '-select_streams', 'v:0',
        '-show_entries', 'stream=avg_frame_rate,r_frame_rate', '-of', 'json', media
    ], text=True)
    rows = json.loads(raw).get('streams', [])
    if not rows:
        raise ValueError(f'{media}: no video stream')
    for key in ('avg_frame_rate', 'r_frame_rate'):
        rate = rows[0].get(key)
        if rate and rate != '0/0':
            return Fraction(rate)
    raise ValueError(f'{media}: no usable frame rate')


def strict_report(clip: dict, fps: Fraction) -> list[dict]:
    words_path = Path(clip['source_words'])
    spec = {'source_sha256': hashlib.sha256(words_path.read_bytes()).hexdigest(),
            'segments': [{'source_words': span['word_range']} for span in clip['spans']]}
    spans = [[span['asr_start'], span['asr_end']] for span in clip['spans']]
    with tempfile.TemporaryDirectory(prefix='assembly-review-edges-') as tmp:
        spec_path, report_path = Path(tmp) / 'selection.json', Path(tmp) / 'report.json'
        spec_path.write_text(json.dumps(spec))
        command = [sys.executable, str(STRICT_CUTTER), '--source', clip['media'],
                   '--words', str(words_path), '--spans', json.dumps(spans),
                   '--fps', str(fps), '--selection-spec', str(spec_path),
                   '--preserve-opener', '--end-margin-ms', '45',
                   '--lead-margin-ms', '60', '--report', str(report_path)]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode not in (0, 2) or not report_path.exists():
            raise RuntimeError(f"{clip['id']}: speech-map infrastructure failed: "
                               f"{result.stderr[-1000:] or result.stdout[-1000:]}")
        report = json.loads(report_path.read_text())
    if len(report) != len(spans):
        raise ValueError(f"{clip['id']}: speech-map report does not cover every span")
    return report


def local_audio(media: str, lo: float, hi: float) -> tuple[np.ndarray, float]:
    lo = max(0.0, lo)
    raw = subprocess.check_output([
        'ffmpeg', '-hide_banner', '-loglevel', 'error', '-ss', f'{lo:.6f}',
        '-t', f'{hi-lo:.6f}', '-i', media, '-vn', '-ac', '1', '-ar', '16000',
        '-f', 'f32le', '-acodec', 'pcm_f32le', '-',
    ])
    return np.frombuffer(raw, dtype=np.float32), lo


def energy_at(samples: np.ndarray, offset: float, at: float) -> float:
    center = round((at-offset) * 16000)
    window = samples[max(0, center-160):min(len(samples), center+160)]
    return float(20 * np.log10(np.sqrt(np.mean(window**2) + 1e-12))) if len(window) else 0.0


def provisional_edge(media: str, words: list[dict], word_index: int,
                     side: str, fps: Fraction) -> tuple[int, dict]:
    """Roomier V12 frame-grid RMS placement, bounded by neighboring labels."""
    rate = float(fps)
    word = words[word_index]
    previous = words[word_index-1] if word_index else None
    following = words[word_index+1] if word_index+1 < len(words) else None
    label = float(word['start'] if side == 'start' else word['end'])
    if side == 'start':
        lo, hi = label - .16, label + .015
        if previous:
            lo = max(lo, float(previous['end']) - .020)
        if previous and float(previous['end']) < label - .025:
            lo = max(lo, float(previous['end']) + .005)
        if previous and float(previous['end']) <= label - .05:
            hi = min(hi, label - .005)
    else:
        lo, hi = label - .015, label + .18
        if following:
            hi = min(hi, float(following['start']) + .020)
        if following and float(following['start']) > label + .025:
            hi = min(hi, float(following['start']) - .005)
            lo = max(lo, label + .005)
        elif following:
            hi = min(hi, float(following['start']) + .055)
    first = max(0, math.ceil(lo * rate))
    last = math.floor(hi * rate)
    if last < first:
        first = last = round(label * rate)
    samples, offset = local_audio(media, first/rate-.04, last/rate+.04)
    candidates = []
    for frame in range(first, last+1):
        at = frame/rate
        db = energy_at(samples, offset, at)
        candidates.append((db + 12.0 * abs(at-label), frame, db))
    _, frame, db = min(candidates)
    # A one-frame review handle protects consonants at a fused edge; it is
    # allowed only within the observed neighboring word-label tolerance.
    padded = frame-1 if side == 'start' else frame+1
    candidate_time = padded/rate
    overlap = (float(previous['end'])-candidate_time if side == 'start' and previous else
               candidate_time-float(following['start']) if side == 'end' and following else 0)
    if padded >= 0 and overlap <= .055:
        frame = padded
        db = energy_at(samples, offset, frame/rate)
    return frame, {'frame': frame, 'time': frame/rate, 'rms_db': round(db, 1),
                   'asr_label': label, 'search_frames': [first, last]}


def review_frames(clip: dict, report: list[dict], fps: Fraction,
                  words: list[dict]) -> tuple[list[list[int]], list[dict]]:
    """Keep one frame span per selected word span, labeling every uncertain edge."""
    if len(report) != len(clip['spans']):
        raise ValueError('report/span count mismatch')
    frames, issues = [], []
    rate = float(fps)
    for number, (span, verdict) in enumerate(zip(clip['spans'], report), 1):
        first, last = span['word_range']
        if verdict.get('source_words') != [first, last]:
            raise ValueError(f"{clip['id']} span {number}: speech-map word IDs changed")
        result = verdict.get('result')
        if result != 'REFUSED' and not (isinstance(result, list) and len(result) == 2):
            raise ValueError(f"{clip['id']} span {number}: unrecognized speech-map result")
        pair = []
        for side, index in (('start', first), ('end', last)):
            edge = verdict.get(side, {})
            at = edge.get('cut_time')
            if at is None and isinstance(result, list):
                at = result[0 if side == 'start' else 1]
            if at is not None and edge.get('verdict') not in ('FUSED', 'REFUSED'):
                frame = round(float(at) * rate)
            else:
                frame, evidence = provisional_edge(clip['media'], words, index, side, fps)
                issues.append({'span': number, 'edge': side,
                               'code': edge.get('verdict', 'PROVISIONAL_LOCAL_RMS'),
                               'word_range': [first, last],
                               'reason': edge.get('why', 'no calibrated quiet frame'),
                               'placement': evidence})
            pair.append(frame)
        start, end = pair
        if start < 0 or end <= start:
            raise ValueError(f"{clip['id']} span {number}: invalid frame interval")
        if frames and first > clip['spans'][number - 2]['word_range'][1] and start < frames[-1][1]:
            raise ValueError(f"{clip['id']} span {number}: source frame spans overlap; "
                             'manual local repair required, do not remove selected words')
        frames.append([start, end])
    return frames, issues


def resolve(compiled_path: Path, reports: dict[str, list[dict]] | None = None) -> dict:
    compiled = validate_compiled(compiled_path)
    rows = []
    for clip in compiled['clips']:
        fps = source_fps(clip['media'])
        word_path = Path(clip['source_words'])
        words = json.loads(word_path.read_text())['words']
        report = reports[clip['id']] if reports is not None else strict_report(clip, fps)
        frames, issues = review_frames(clip, report, fps, words)
        status = 'PROVISIONAL_SEAM' if issues else 'MEASURED_EDGES'
        note = ('Editor review: ' + status + '. ' +
                ('Uncertified edges need listening/frame adjustment: ' +
                 '; '.join(f"span {i['span']} {i['edge']} {i['code']}" for i in issues)
                 if issues else 'Acoustic listening and editorial approval remain pending.'))
        rows.append({'id': clip['id'], 'source_frames': frames, 'status': status,
                     'boundary_issues': issues, 'note': note})
    return {'schema': 'edit.resolved-assembly/v1',
            'compiled_path': str(compiled_path.resolve()),
            'compiled_sha256': digest(compiled_path), 'clips': rows}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiled', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error('output exists; use a new revision path')
    try:
        result = resolve(args.compiled)
        args.out.write_text(json.dumps(result, indent=2) + '\n')
    except (ValueError, KeyError, OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        parser.error(str(exc))
    print(json.dumps({'clips': len(result['clips']),
                      'provisional': sum(bool(row['boundary_issues']) for row in result['clips'])}))


if __name__ == '__main__':
    main()
