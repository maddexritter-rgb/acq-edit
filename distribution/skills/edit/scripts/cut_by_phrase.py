#!/usr/bin/env python3
"""Locate exact hook/payoff word candidates without editing or rendering.

Assembly Design owns the choice, source-word compilation and inspected speech edges.
Use the toolkit native route for construction. This helper never invokes old
project-local multicut/multifinish scripts or invents fixed audio padding.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path


def normalized(word):
    return ''.join(c for c in word.lower() if c.isalnum())


def locate(words, phrase, lo, hi, edge):
    tokens = [normalized(token) for token in phrase.split() if normalized(token)]
    if not tokens:
        raise ValueError('Phrase must contain spoken words')
    matches = []
    for start in range(len(words) - len(tokens) + 1):
        end = start + len(tokens) - 1
        clock = words[start]['start'] if edge == 'start' else words[end]['end']
        if lo <= clock <= hi and all(normalized(words[start+i]['word']) == token for i, token in enumerate(tokens)):
            matches.append({'wordStart': start, 'wordEnd': end, 'start': words[start]['start'], 'end': words[end]['end']})
    return matches


def candidates(words, near, hook, payoff):
    if not math.isfinite(near) or near < 0:
        raise ValueError('Near must be a finite nonnegative source time')
    previous = -1
    for word in words:
        start, end = word['start'], word['end']
        if (not isinstance(word['word'], str) or not all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) for x in (start, end))
                or start < 0 or end < start or start < previous):
            raise ValueError('Expected ordered source words with finite second-based start/end clocks')
        previous = start
    hooks = locate(words, hook, max(0, near-9), near+14, 'start')
    pairs = []
    for opening in hooks:
        for closing in locate(words, payoff, opening['start'], opening['start']+150, 'end'):
            if closing['wordStart'] >= opening['wordEnd'] and closing['end'] > opening['start']:
                pairs.append({'hook': opening, 'payoff': closing})
    return pairs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--transcript', type=Path, required=True, help='JSON with words containing word/start/end in source seconds')
    parser.add_argument('--near', type=float, required=True)
    parser.add_argument('--hook', required=True)
    parser.add_argument('--payoff', required=True)
    args = parser.parse_args()
    raw = args.transcript.read_bytes()
    pairs = candidates(json.loads(raw)['words'], args.near, args.hook, args.payoff)
    print(json.dumps({'schema': 'acq-edit/phrase-locations-v1', 'locatorOnly': True,
                      'transcript': str(args.transcript.resolve()), 'transcriptSha256': hashlib.sha256(raw).hexdigest(),
                      'candidates': pairs, 'requiresSourceWordDesign': True}, indent=2))
    return 0 if pairs else 1


if __name__ == '__main__':
    raise SystemExit(main())
