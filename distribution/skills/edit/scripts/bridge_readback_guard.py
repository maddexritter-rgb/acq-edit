#!/usr/bin/env python3
"""Reject silent Premiere placement defects from sequence-structure readback JSON.

This verifies structural frame invariants, not source dialogue, audio quality, or
editorial intent. Deliberate longer review-sequence gaps remain visible in the
report; only tiny accidental gaps are blocking by default.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
import json
import math
from pathlib import Path
import re
import sys

TICKS_PER_SECOND = 254016000000
TIME_FIELDS = ('start', 'end', 'inPoint', 'outPoint')


def integer(value, label: str) -> int:
    """Tick strings avoid the precision ceiling of JavaScript JSON numbers."""
    if isinstance(value, bool) or not (
        isinstance(value, int) or isinstance(value, str) and re.fullmatch(r'-?\d+', value)
    ):
        raise ValueError(f'{label} must be an integer or integer string')
    return int(value)


def frame_duration(rate: dict, override=None) -> int:
    ticks = integer(override if override is not None else rate.get('ticks', 0), 'frame ticks')
    rational = None
    if 'numerator' in rate or 'denominator' in rate:
        numerator = integer(rate.get('numerator'), 'frame-rate numerator')
        denominator = integer(rate.get('denominator'), 'frame-rate denominator')
        if numerator <= 0 or denominator <= 0:
            raise ValueError('frame rate must be positive')
        rational = Fraction(TICKS_PER_SECOND * denominator, numerator)
        if rational.denominator != 1:
            raise ValueError('frame rate cannot be represented by whole Premiere ticks')
    if ticks == 0 and rational is not None:
        ticks = int(rational)
    if ticks <= 0:
        raise ValueError('missing frameRate.ticks or rational frame rate; pass --frame-ticks')
    if rational is not None and ticks != rational:
        raise ValueError('frameRate ticks and rational rate disagree')
    return ticks


def read_time(clip: dict, field: str) -> tuple[Fraction, str]:
    ticks_key, seconds_key = field + 'Ticks', field + 'Seconds'
    if ticks_key in clip:
        # Malformed exact values must never fall back to apparently valid seconds.
        if isinstance(clip[ticks_key], int) and abs(clip[ticks_key]) > 2**53 - 1:
            raise ValueError(f'{ticks_key} above JavaScript safe integer range needs a string')
        return Fraction(integer(clip[ticks_key], ticks_key)), 'exact_ticks'
    seconds = clip.get(seconds_key)
    if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or not math.isfinite(seconds):
        raise ValueError(f'missing or invalid {ticks_key}/{seconds_key}')
    return Fraction(str(seconds)) * TICKS_PER_SECOND, 'legacy_seconds'


def frame_number(seconds: float, frame_ticks: int) -> tuple[int, float]:
    exact = Fraction(str(seconds)) * TICKS_PER_SECOND / frame_ticks
    nearest = round(exact)
    return nearest, float(abs(exact - nearest))


def validate(structure: dict, small_gap_max_frames: int = 2,
             frame_ticks: int | None = None,
             allowed_gap_frames: set[int] | None = None,
             expected: dict | None = None) -> dict:
    rate = structure.get('frameRate', {})
    frame_ticks = frame_duration(rate, frame_ticks)
    comparison = compare_expected(structure, expected, frame_ticks) if expected is not None else None
    errors = []
    reviewed = 0
    precision = {'exact_ticks': 0, 'legacy_seconds': 0}
    intentional_gaps = []
    allowed_gap_frames = allowed_gap_frames or set()
    for kind in ('video', 'audio'):
        for track in structure.get(kind + 'Tracks', []):
            label = f"{kind}[{track.get('index', '?')}]"
            clips = []
            for clip in track.get('clips', []):
                try:
                    start, _ = read_time(clip, 'start')
                    clips.append((start, clip))
                except ValueError as exc:
                    errors.append(f'{label}/{clip.get("nodeId", "?")}: {exc}')
            clips = [clip for _, clip in sorted(clips, key=lambda row: row[0])]
            previous = None
            for clip in clips:
                reviewed += 1
                node = clip.get('nodeId', f"index-{clip.get('index', '?')}")
                frames = {}
                for field in TIME_FIELDS:
                    try:
                        ticks, mode = read_time(clip, field)
                    except ValueError as exc:
                        errors.append(f'{label}/{node}: {exc}')
                        continue
                    precision[mode] += 1
                    exact = ticks / frame_ticks
                    frame, residual = round(exact), abs(exact - round(exact))
                    frames[field + 'Seconds'] = frame
                    if residual > (0 if mode == 'exact_ticks' else Fraction(1, 10)):
                        errors.append(f'{label}/{node}: {field} is off grid ({residual} frame)')
                if len(frames) != 4:
                    continue
                timeline_frames = frames['endSeconds'] - frames['startSeconds']
                source_frames = frames['outPointSeconds'] - frames['inPointSeconds']
                if timeline_frames <= 0 or source_frames <= 0:
                    errors.append(f'{label}/{node}: nonpositive item duration')
                if clip.get('speed', 1) == 1 and timeline_frames != source_frames:
                    errors.append(f'{label}/{node}: timeline {timeline_frames} frames != source {source_frames} frames')
                if previous is not None:
                    gap = frames['startSeconds'] - previous[0]
                    if gap < 0:
                        errors.append(f'{label}/{previous[1]} -> {node}: overlap {abs(gap)} frame(s)')
                    elif gap > 0 and track.get('index') == 0 and comparison is not None and comparison['status'] == 'PASS':
                        intentional_gaps.append({'track': label, 'after': previous[1],
                                                 'before': node, 'frames': gap,
                                                 'authority': 'expected_assembly'})
                    elif 0 < gap <= small_gap_max_frames:
                        errors.append(f'{label}/{previous[1]} -> {node}: tiny gap {gap} frame(s)')
                    elif gap > small_gap_max_frames:
                        intentional_gaps.append({'track': label, 'after': previous[1],
                                                 'before': node, 'frames': gap})
                        if gap not in allowed_gap_frames:
                            errors.append(f'{label}/{previous[1]} -> {node}: unapproved gap {gap} frame(s)')
                previous = (frames['endSeconds'], node)
    if reviewed == 0:
        errors.append('no clip items were read back')
    if comparison is not None:
        errors.extend(comparison['errors'])
    return {'schema': 'edit.bridge-readback-guard/v2', 'status': 'PASS' if not errors else 'FAIL',
            'sequence': structure.get('name'), 'frame_ticks': frame_ticks,
            'reviewed_items': reviewed, 'errors': errors,
            'longer_gaps_to_reconcile': intentional_gaps, 'precision': precision,
            'expected_assembly': comparison,
            'evidence': {'structural': 'FAIL' if errors else 'PASS',
                         'native_linkage': 'not_run', 'persistence': 'not_run',
                         'rendered': 'not_run', 'listening': 'not_run'}}


def compare_expected(structure: dict, expected: dict, frame_ticks: int) -> dict:
    """Compare V1/A1 with review_xml.py's existing receipt, without new editorial gates.

    Matching media/ranges proves paired placement, not native link-group membership.
    Additional tracks are outside this comparison and remain subject to stage guards.
    """
    errors = []
    if expected.get('schema') != 'edit.review-xml-expected/v1':
        raise ValueError('expected edit.review-xml-expected/v1 receipt from review_xml.py')
    fps = Fraction(expected['fps'])
    if fps <= 0 or Fraction(TICKS_PER_SECOND, frame_ticks) != fps:
        errors.append('expected assembly frame rate differs from sequence')
    if structure.get('name') != expected.get('sequence_name'):
        errors.append('expected assembly sequence name differs; live identity guard is still required')
    items = expected.get('items')
    if not isinstance(items, list) or not items:
        raise ValueError('expected assembly has no items')
    wanted = []
    for item in items:
        bounds = []
        for key in ('timeline_frames', 'source_frames'):
            span = item.get(key)
            if not isinstance(span, list) or len(span) != 2:
                raise ValueError(f'expected item missing {key} pair')
            a, b = [integer(v, key) for v in span]
            if a < 0 or b <= a:
                raise ValueError(f'expected item invalid {key} range')
            bounds.extend((a * frame_ticks, b * frame_ticks))
        if not isinstance(item.get('media'), str) or not Path(item['media']).is_absolute():
            raise ValueError('expected item needs an absolute source media path')
        if bounds[1] - bounds[0] != bounds[3] - bounds[2]:
            raise ValueError('expected assembly changes playback duration')
        if wanted and bounds[0] < wanted[-1][1]:
            raise ValueError('expected assembly is out of order or overlaps')
        wanted.append(bounds)
    if integer(expected['timeline_frames'], 'timeline_frames') * frame_ticks != wanted[-1][1]:
        raise ValueError('expected assembly total differs from final item end')
    for kind in ('video', 'audio'):
        tracks = [t for t in structure.get(kind + 'Tracks', []) if t.get('index') == 0]
        if len(tracks) != 1:
            errors.append(f'{kind}[0]: expected exactly one primary track')
            continue
        actual = tracks[0].get('clips', [])
        if len(actual) != len(items):
            errors.append(f'{kind}[0]: {len(actual)} items != expected {len(items)}')
            continue
        try:
            actual = sorted(actual, key=lambda c: read_time(c, 'start')[0])
        except ValueError as exc:
            errors.append(f'{kind}[0]: {exc}')
            continue
        for index, (clip, item, bounds) in enumerate(zip(actual, items, wanted)):
            label = f'{kind}[0]/{index}'
            actual_path = clip.get('sourceMediaPath')
            same_path = isinstance(actual_path, str) and Path(actual_path).is_absolute() and Path(actual_path).resolve() == Path(item['media']).resolve()
            if not same_path:
                errors.append(f'{label}: source media differs or is missing')
            if clip.get('speed') != 1 or isinstance(clip.get('speed'), bool):
                errors.append(f'{label}: expected explicit normal playback speed')
            reversed_state = clip.get('reversed')
            if not (reversed_state is False or type(reversed_state) is int and reversed_state == 0):
                errors.append(f'{label}: forward playback not verified')
            if clip.get('sourceOffline') is not False:
                errors.append(f'{label}: online source not verified')
            for field, target in zip(TIME_FIELDS, bounds):
                try:
                    value, mode = read_time(clip, field)
                    if mode != 'exact_ticks':
                        errors.append(f'{label}: {field} needs exact ticks for assembly comparison')
                    elif value != target:
                        errors.append(f'{label}: {field} ticks {value} != expected {target}')
                except ValueError as exc:
                    errors.append(f'{label}: {exc}')
    return {'scope': 'primary_video_audio_placement', 'errors': errors,
            'status': 'PASS' if not errors else 'FAIL',
            'native_linkage': 'not_run'}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--structure', required=True, help='Unmodified get_sequence_structure JSON')
    parser.add_argument('--small-gap-max-frames', type=int, default=2)
    parser.add_argument('--frame-ticks', type=int,
                        help='Sequence frameRate.ticks from get_sequence_settings when absent in structure')
    parser.add_argument('--allow-gap-frames', type=int, action='append', default=[],
                        help='Explicitly approved inter-clip gap length in frames; repeat if needed')
    parser.add_argument('--expected', type=Path,
                        help='Optional review_xml.py .expected.json; requires exact tick readback')
    args = parser.parse_args()
    if args.small_gap_max_frames < 0:
        parser.error('small-gap-max-frames must be nonnegative')
    raw = sys.stdin.read() if args.structure == '-' else Path(args.structure).read_text()
    result = validate(json.loads(raw), args.small_gap_max_frames, args.frame_ticks,
                      set(args.allow_gap_frames),
                      json.loads(args.expected.read_text()) if args.expected else None)
    print(json.dumps(result, indent=2))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
