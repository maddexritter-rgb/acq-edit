#!/usr/bin/env python3
"""Propose frame edges from AssemblyAI words on the audio actually played.

This is a proposal, not acoustic certification. Ambiguous joins require local
source-audio inspection and, when useful, independent short-window alignment.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path


def edge(words: list[dict], index: int, side: str, fps: Fraction,
         head_handle_frames: int = 2) -> dict:
    if fps <= 0 or not 0 <= head_handle_frames <= 3:
        raise ValueError('positive fps and a 0–3 frame head handle are required')
    word = words[index]
    rate = float(fps)
    if side == 'start':
        neighbor = words[index - 1] if index else None
        label = float(word['start'])
        gap = label - float(neighbor['end']) if neighbor else None
        # The frame handle is a minimum preferred margin, NOT another pad
        # applied after a gap-safe position has already been chosen.
        handle = max(.07, head_handle_frames / rate)
        if gap is None:
            seconds, rule = label - handle, 'NO_PREVIOUS_LABEL'
        elif gap >= .14:
            seconds, rule = label - min(handle, gap / 2), 'HANDLE_WITHIN_LABEL_GAP'
        elif gap > 0:
            seconds, rule = label - gap / 2, 'MIDPOINT_SHORT_LABEL_GAP'
        else:
            seconds, rule = label - .04, 'OVERLAPPED_LABEL'
        lower = max(0, math.ceil(Fraction(str(neighbor['end'])) * fps)) if neighbor else 0
        upper = math.floor(Fraction(str(word['start'])) * fps)
        feasible = lower <= upper
        frame = max(lower, min(upper, round(seconds * rate))) if feasible else max(0, upper)
        risk = bool(neighbor and frame / rate <= float(neighbor['end']) + 1 / rate)
        risk_reason = 'neighbor may bleed into selected opener' if risk else None
    elif side == 'end':
        neighbor = words[index + 1] if index + 1 < len(words) else None
        label = float(word['end'])
        gap = float(neighbor['start']) - label if neighbor else None
        if gap is None:
            seconds, rule = label + .12, 'NO_NEXT_LABEL'
        elif gap >= .20:
            seconds, rule = label + .10, '100MS_WITHIN_LABEL_GAP'
        elif gap > 0:
            seconds, rule = label + gap / 2, 'MIDPOINT_SHORT_LABEL_GAP'
        else:
            seconds, rule = label + .04, 'OVERLAPPED_LABEL'
        lower = math.ceil(Fraction(str(word['end'])) * fps)
        upper = math.floor(Fraction(str(neighbor['start'])) * fps) if neighbor else None
        feasible = upper is None or lower <= upper
        frame = max(lower, round(seconds * rate))
        if feasible and upper is not None:
            frame = min(upper, frame)
        risk = frame / rate < label + 1 / rate or bool(
            neighbor and frame / rate >= float(neighbor['start']) - 1 / rate)
        risk_reason = 'selected tail or excluded next word may be affected' if risk else None
    else:
        raise ValueError(side)
    if not feasible:
        risk, risk_reason = True, 'no label-separated source frame; inspect or redesign locally'
    return {'word_index': index, 'word': word.get('word', word.get('text')),
            'side': side, 'frame': frame, 'seconds': frame / rate,
            'unquantized_proposal_seconds': seconds,
            'label_seconds': label, 'neighbor_gap_ms': None if gap is None else round(gap * 1000),
            'rule': rule, 'risk': risk, 'risk_reason': risk_reason,
            'label_frame_envelope': [lower, upper], 'label_frame_feasible': feasible,
            'acoustic_verified': False}


def sample_proposal(words, index, side, frame_proposal, sample_rate):
    """Independent sample candidate, bounded by advisory word labels, not a PASS."""
    if sample_rate not in (44100, 48000, 96000):
        raise ValueError('supported audio sample rate required')
    w = words[index]
    if side == 'start':
        low = math.ceil(Fraction(str(words[index-1]['end'])) * sample_rate) if index else 0
        high = math.floor(Fraction(str(w['start'])) * sample_rate)
    else:
        low = math.ceil(Fraction(str(w['end'])) * sample_rate)
        high = math.floor(Fraction(str(words[index+1]['start'])) * sample_rate) if index+1 < len(words) else None
    feasible = high is None or low <= high
    candidate = round(Fraction(str(frame_proposal['unquantized_proposal_seconds'])) * sample_rate)
    sample = max(low, candidate) if high is None else max(low, min(high, candidate))
    return {'sample_rate':sample_rate, 'sample':sample if feasible else None,
            'label_sample_envelope':[low,high], 'label_sample_feasible':feasible,
            'status':'PROPOSED' if feasible else 'PROVISIONAL_SEAM', 'acoustic_verified':False}


def propose(words: list[dict], ranges: list[list[int]], fps: Fraction,
            head_handle_frames: int = 2, audio_sample_rate: int = 48000) -> list[dict]:
    result = []
    selected = set()
    for n, (first, last) in enumerate(ranges, 1):
        if first < 0 or last < first or last >= len(words):
            raise ValueError(f'span {n}: invalid word indices')
        ids = set(range(first, last + 1))
        if selected & ids:
            raise ValueError(f'span {n}: repeated selected words; explicit replay needs a separate design')
        selected.update(ids)
        head = edge(words, first, 'start', fps, head_handle_frames)
        tail = edge(words, last, 'end', fps, head_handle_frames)
        head['audio'] = sample_proposal(words, first, 'start', head, audio_sample_rate)
        tail['audio'] = sample_proposal(words, last, 'end', tail, audio_sample_rate)
        if head['frame'] >= tail['frame']:
            raise ValueError(f'span {n}: nonpositive frame range')
        result.append({'span': n, 'word_range': [first, last],
                       'source_frames': [head['frame'], tail['frame']],
                       'head': head, 'tail': tail,
                       'status': 'LOCAL_CHECK' if head['risk'] or tail['risk'] else 'PROPOSED'})
    # Playback order is editorial: a later hook may precede earlier reasoning.
    # Check physical intersections independent of that order, not monotonicity.
    for i, left in enumerate(result):
        for right in result[i + 1:]:
            a, b = left['source_frames'], right['source_frames']
            if max(a[0], b[0]) < min(a[1], b[1]):
                for row, other in ((left, right), (right, left)):
                    row['status'] = 'LOCAL_CHECK'
                    row.setdefault('source_overlap_with', []).append(other['span'])
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--words', required=True, type=Path)
    parser.add_argument('--ranges', required=True, type=Path,
                        help='JSON list of inclusive [first_word_index,last_word_index]')
    parser.add_argument('--fps', required=True)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--acoustic-source', type=Path, help='Enable cached local pre-build speech checks; requires explicit routing')
    parser.add_argument('--stream', type=int)
    parser.add_argument('--channel', type=int)
    parser.add_argument('--cache-dir', type=Path)
    parser.add_argument('--head-handle-frames', type=int, default=2)
    parser.add_argument('--audio-sample-rate', type=int, choices=(44100,48000,96000), default=48000)
    args = parser.parse_args()
    if args.out.exists():
        parser.error('output exists; use a new revision path')
    if not 0 <= args.head_handle_frames <= 3:
        parser.error('head handle must be 0–3 frames')
    words = json.loads(args.words.read_text())['words']
    ranges = json.loads(args.ranges.read_text())
    result = {'schema': 'edit.played-audio-edge-proposals/v1',
              'algorithm_revision': 3,
              'fps': str(Fraction(args.fps)),
              'words_path': str(args.words.resolve()),
              'words_sha256': hashlib.sha256(args.words.read_bytes()).hexdigest(),
              'head_handle_frames': args.head_handle_frames,
              'audio_sample_rate': args.audio_sample_rate,
              'spans': propose(words, ranges, Fraction(args.fps), args.head_handle_frames, args.audio_sample_rate)}
    if args.acoustic_source:
        if args.stream is None or args.channel is None or args.cache_dir is None:
            parser.error('acoustic source requires --stream, --channel and --cache-dir')
        from acoustic_boundary_index import prepare, refine
        acoustic, hit = prepare(args.acoustic_source, args.stream, args.channel, args.cache_dir)
        result['acoustic_index'] = {'source_sha256': acoustic['source_sha256'], 'config': acoustic['config'], 'cache_hit': hit}
        result['algorithm_revision'] = 4
        for span in result['spans']:
            for key, side, idx in [('head', 'start', span['word_range'][0]), ('tail', 'end', span['word_range'][1])]:
                proposal = refine(words, idx, side, Fraction(args.fps), span[key], acoustic)
                proposal['audio'] = {'sample_rate': args.audio_sample_rate, 'sample': None,
                                    'status': 'UNRESOLVED_INDEPENDENT_AUDIO_EDGE', 'acoustic_verified': False}
                span[key] = proposal
            span['timestamp_source_frames'] = span.pop('source_frames')
            pair = [span['head']['frame'], span['tail']['frame']]
            span['source_frames'] = pair if None not in pair and pair[0] < pair[1] else None
            span['status'] = 'PROPOSED_NOT_LISTENED' if span['source_frames'] else 'PROVISIONAL_SEAM'
        result['execution_status'] = 'PROPOSALS_ONLY_NOT_AN_AUDIO_PLAN'
    elif any(x is not None for x in (args.stream, args.channel, args.cache_dir)):
        parser.error('routing/cache arguments require --acoustic-source')
    args.out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'spans': len(result['spans']),
                      'local_checks': sum(s['status'] in ('LOCAL_CHECK', 'PROVISIONAL_SEAM') for s in result['spans'])}))


if __name__ == '__main__':
    main()
