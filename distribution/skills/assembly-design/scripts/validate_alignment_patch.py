#!/usr/bin/env python3
"""Check a local timing correction without selecting cuts or certifying speech.

Input: {words: [{word_index, text, speaker, start, end}],
        patch: [{word_index, text, start, end}], source_window: [start, end]}.
Times are seconds on the same played-source clock. Include unchanged neighbors.
Rows must be in literal source order. Cross-speaker inversions require inspection.
"""
import argparse
import json
import math
from pathlib import Path


def validate(data):
    issues = []
    def issue(code, **details):
        issues.append({'code': code, **details})
    def number(x):
        return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)
    window = data.get('source_window', [])
    if len(window) != 2 or not all(number(x) for x in window) or window[0] >= window[1]:
        return {'status': 'REINSPECT_SOURCE_OCCURRENCE', 'issues': [{'code': 'INVALID_SOURCE_WINDOW'}], 'acoustic_review': 'NOT_PERFORMED'}
    words, patch = data.get('words', []), data.get('patch', [])
    if not words or not patch:
        issue('MISSING_WORDS_OR_PATCH')
    originals = {}
    for row in words:
        idx = row.get('word_index')
        if type(idx) is not int or idx in originals:
            issue('INVALID_OR_DUPLICATE_WORD_ID', word_index=idx)
        else:
            originals[idx] = row
    replacements = {}
    for row in patch:
        idx = row.get('word_index')
        if type(idx) is not int or idx not in originals or idx in replacements:
            issue('UNKNOWN_OR_DUPLICATE_PATCH_ID', word_index=idx)
            continue
        if row.get('text') != originals[idx].get('text'):
            issue('CHANGED_WORD_IDENTITY', word_index=idx)
        if 'speaker' in row and row['speaker'] != originals[idx].get('speaker'):
            issue('CHANGED_SPEAKER', word_index=idx)
        replacements[idx] = row
    merged = [{**row, **replacements.get(row.get('word_index'), {})} for row in words]
    valid = True
    for row in merged:
        a, b = row.get('start'), row.get('end')
        if not number(a) or not number(b) or not window[0] <= a < b <= window[1]:
            valid = False
            issue('INVALID_OR_OUT_OF_WINDOW_TIMES', word_index=row.get('word_index'))
    if valid:
        for left, right in zip(merged, merged[1:]):
            if left['word_index'] >= right['word_index']:
                issue('UNORDERED_SOURCE_IDS', word_index=right['word_index'])
            if right['start'] < left['start'] or right['end'] < left['end']:
                code = 'NEIGHBOR_ORDER_CONFLICT'
                if left.get('speaker') != right.get('speaker'):
                    code = 'CROSS_SPEAKER_ORDER_REQUIRES_INSPECTION'
                issue(code, previous_word_index=left['word_index'], word_index=right['word_index'])
    for idx in replacements:
        position = next((i for i, row in enumerate(words) if row.get('word_index') == idx), -1)
        if position in (0, len(words)-1):
            issue('PATCH_LACKS_SURROUNDING_WORDS', word_index=idx)
    return {'schema': 'edit.alignment-patch-check/v1',
            'status': 'REINSPECT_SOURCE_OCCURRENCE' if issues else 'GEOMETRY_CONSISTENT_NOT_ACOUSTIC_PROOF',
            'issues': issues, 'acoustic_review': 'NOT_PERFORMED'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    result = validate(json.loads(args.input.read_text()))
    with args.out.open('x') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
    print(result['status'])
    raise SystemExit(bool(result['issues']))


if __name__ == '__main__':
    main()
