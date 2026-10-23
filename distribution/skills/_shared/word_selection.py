"""Validate exact source-word selections shared by assembly frame tools."""
import hashlib
import json
from pathlib import Path


def validate_indexed_spec(spec, transcript, raw, preserve_internal):
    indexed = any('source_words' in s for s in spec['segments'])
    if not indexed:
        return
    if not preserve_internal:
        raise ValueError('Indexed selections require --preserve-internal')
    if not isinstance(transcript, dict) or not isinstance(transcript.get('words'), list):
        raise ValueError('Indexed selections require the pinned flat words array')
    if hashlib.sha256(raw).hexdigest() != spec.get('source_sha256'):
        raise ValueError('Indexed selection transcript changed')
    if not all('source_words' in s for s in spec['segments']):
        raise ValueError('Do not mix indexed and time-window selections')
    if any(w.get('start') is None for w in transcript['words']):
        raise ValueError('Indexed transcript contains missing timing')
    if 'performance_evidence' in spec:
        evidence_pin = spec['performance_evidence']
        path = Path(evidence_pin['path'])
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != evidence_pin['sha256']:
            raise ValueError('Candidate performance evidence changed')
        evidence = json.loads(path.read_text())
        if evidence.get('schema') != 'cut.candidate-performance/v2' or evidence.get('status') != 'MEASURED':
            raise ValueError('Candidate performance evidence is old or incomplete; regenerate it')
        if evidence.get('source_words', {}).get('sha256') != spec['source_sha256']:
            raise ValueError('Candidate performance transcript differs from cut transcript')
        if not isinstance(spec.get('performance_decisions'), list):
            raise ValueError('Candidate performance decisions missing from cut request')


def select_indices(words, segment):
    if 'source_words' in segment:
        bounds = segment['source_words']
        if not (isinstance(bounds, list) and len(bounds) == 2 and
                all(type(i) is int for i in bounds) and
                0 <= bounds[0] <= bounds[1] < len(words)):
            raise ValueError('Invalid exact source-word range')
        return list(range(bounds[0], bounds[1] + 1))
    return [i for i, w in enumerate(words)
            if w[0] >= float(segment['in']) - .20 and w[0] < float(segment['out']) + .25]
