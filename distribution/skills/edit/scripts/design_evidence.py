#!/usr/bin/env python3
"""Verify retention of source-grounded editorial anchors; not an acoustic/semantic audit."""
import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path


def digest(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def media_duration(ref):
    """Optional real media bound for explicitly selected nonverbal performance."""
    path = Path(ref['path'])
    require(path.is_absolute() and path.is_file(), 'missing absolute source media')
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    require(h.hexdigest() == ref.get('sha256'), 'source media changed')
    result = subprocess.run(['ffprobe', '-v', 'error', '-show_entries',
                             'format=duration', '-of', 'csv=p=0', str(path)],
                            check=True, capture_output=True, text=True, timeout=30)
    duration = float(result.stdout.strip())
    require(number(duration) and duration > 0, 'invalid media duration')
    return duration


def evaluate(spec):
    require(isinstance(spec, dict), 'design must be an object')
    require(spec.get('schema') == 'edit.design-evidence/v1', 'invalid schema')
    for key in ('clip_id', 'intent', 'cleanup_review'):
        require(isinstance(spec.get(key), str) and spec[key].strip(), f'missing {key}')
    path = Path(spec['source_words']).expanduser()
    require(path.is_absolute(), 'source_words must be absolute')
    raw = path.read_bytes()
    require(digest(raw) == spec.get('source_sha256'), 'source transcript changed')
    words = json.loads(raw)['words']
    require(isinstance(words, list) and words, 'empty words')
    for word in words:
        require(isinstance(word, dict), 'word must be an object')
        require(isinstance(word.get('word'), str) and word['word'].strip(), 'invalid word')
        require(number(word.get('start')) and number(word.get('end')) and
                0 <= word['start'] <= word['end'], 'invalid word timing')
    spans = spec.get('keep_spans')
    require(isinstance(spans, list) and spans, 'empty keep_spans')
    limit = max(w['end'] for w in words) + 1.0
    if 'source_media' in spec:
        limit = media_duration(spec['source_media'])
    for span in spans:
        require(isinstance(span, list) and len(span) == 2 and all(number(v) for v in span)
                and 0 <= span[0] < span[1] <= limit, 'invalid keep span')
    ordered = sorted(spans)
    require(all(a[1] <= b[0] for a, b in zip(ordered, ordered[1:])), 'source span overlap')
    # Midpoint membership tolerates ASR word-edge padding; acoustic checks remain separate.
    selected = [i for a, b in spans for i, w in enumerate(words)
                if a <= (w['start'] + w['end']) / 2 < b]
    require(selected, 'no retained words')
    included = set(selected)
    anchors = spec.get('essential')
    require(isinstance(anchors, list) and anchors, 'missing essential anchors')
    require(all(isinstance(x, dict) for x in anchors), 'anchors must be objects')
    require(any(x.get('role') == 'reward' for x in anchors), 'missing reward anchor')
    missing = []
    for anchor in anchors:
        require(anchor.get('role') in ('context', 'reasoning', 'example', 'reward'), 'invalid role')
        require(isinstance(anchor.get('why'), str) and anchor['why'].strip(), 'missing anchor reason')
        r = anchor.get('words')
        require(isinstance(r, list) and len(r) == 2 and all(type(i) is int for i in r)
                and 0 <= r[0] <= r[1] < len(words), 'invalid essential word range')
        absent = [i for i in range(r[0], r[1] + 1) if i not in included]
        if absent:
            missing.append({'role': anchor['role'], 'indices': absent,
                            'text': ' '.join(words[i]['word'] for i in absent)})
    text = ' '.join(words[i]['word'] for i in selected)
    return {'schema': 'edit.design-receipt/v1', 'clip_id': spec['clip_id'],
            'status': 'BLOCK' if missing else 'PASS', 'missing_essential': missing,
            'source_sha256': digest(raw),
            'design_sha256': digest(json.dumps(spec, sort_keys=True).encode()),
            'assembled_sha256': digest(text.encode()), 'assembled_text': text,
            'kept_word_indices': selected,
            'speakers': [words[i].get('spk', words[i].get('speaker')) for i in selected],
            'scope': 'Declared source-word retention only; requires editorial and acoustic review.'}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--input', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    out = Path(args.out)
    try:
        result = evaluate(json.loads(Path(args.input).read_text()))
    except (ValueError, KeyError, TypeError, OSError, subprocess.SubprocessError) as exc:
        result = {'schema': 'edit.design-receipt/v1', 'status': 'UNKNOWN', 'error': str(exc)}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + '\n')
    out.with_suffix('.assembled.txt').write_text(result.get('assembled_text', '') + '\n')
    print(json.dumps({k: v for k, v in result.items()
                      if k not in ('assembled_text', 'kept_word_indices', 'speakers')}))
    return 0 if result['status'] == 'PASS' else 2


if __name__ == '__main__':
    raise SystemExit(main())
