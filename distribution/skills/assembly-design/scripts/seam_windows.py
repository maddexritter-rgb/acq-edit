#!/usr/bin/env python3
"""Paired-seam windows from MFA word bounds and 5 ms RMS valleys.

decide  Draft edit.paired-seam-decisions/v1 for pair_audio_seams.py from one clip's
        kept word ranges. Each window runs from the kept word's MFA edge toward the
        neighbouring word (at most 150 ms after a tail, 120 ms before a head, 2 ms
        clear of the neighbour); the preferred cut is the quietest 5 ms point in it.
        Fused joins (neighbour < 6 ms away) get a +/-4 ms window on the word edge.
        MFA is trusted only when it describes the ASR-labelled sound (edges within
        0.25 s, or nested in a stretched/squeezed label); otherwise the ASR time is
        used and join_check.py blocks the edge as LOCATORS_DISAGREE. Waveform-
        inspected windows override measured ones:
          --inspected '{"in": {"HEAD_WORD": [lo, pref, hi]}, "out": {"TAIL_WORD": [lo, pref, hi]}}'
        (seconds; a JSON string or file). --bounds-out writes the trusted MFA bounds
        in the --phonemes format pair_audio_seams.py and inspect_cut_boundaries.py read.
peek    Print ASR, MFA and a 10 ms envelope around chosen join_check.py edges, to
        decide fused joins and stutters from the waveform.

Same evidence as join_check.py (mfa_align, envelope): this proposes, join_check measures.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
import json
import math
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from join_check import mfa_align, same_occurrence  # noqa: E402
from word_evidence import SR, HOP, envelope  # noqa: E402

FUSED_S = 0.006       # neighbour closer than this: no gap to search
FUSED_PAD_S = 0.004   # window on a fused word edge
OUT_REACH_S = 0.15    # search after a kept tail
IN_REACH_S = 0.12     # search before a kept head
GUARD_S = 0.002       # stay clear of the neighbour word
MIN_SEARCH_S = 0.01   # narrower than this: no valley search
PREF_MARGIN_S = 0.003


def load_json_arg(value):
    """A JSON object given inline or as a file path."""
    if not value:
        return {}
    return json.loads(value if value.lstrip().startswith('{') else Path(value).read_text())


def load_inspected(value):
    """({head_word: (lo, pref, hi)}, {tail_word: (lo, pref, hi)}) in seconds."""
    data = load_json_arg(value)
    sides = []
    for side in ('in', 'out'):
        rows = {}
        for k, v in data.get(side, {}).items():
            if len(v) not in (3, 4):  # 4 = legacy [word_start, lo, pref, hi]
                raise ValueError(f'inspected {side}[{k}] needs [lo, pref, hi]')
            lo, pref, hi = map(float, v[-3:])
            if not lo <= pref <= hi:
                raise ValueError(f'inspected {side}[{k}] preference outside its window')
            rows[int(k)] = (lo, pref, hi)
        sides.append(rows)
    return tuple(sides)


def trusted_bounds(words, aligned):
    """MFA bounds that describe the ASR-labelled occurrence."""
    return {i: b for i, b in aligned.items() if same_occurrence((words[i]['start'], words[i]['end']), b)}


def plan(words, kept, bounds, env, sample_rate, fps, evidence, inspected_in=None, inspected_out=None):
    """(decisions, log rows). `bounds` must already be trusted (see trusted_bounds)."""
    inspected_in, inspected_out = inspected_in or {}, inspected_out or {}

    def bnd(i):
        return bounds.get(i) or (words[i]['start'], words[i]['end'])

    def valley(lo, hi):
        a = int(lo * SR / HOP)
        seg = env[a:max(a + 1, int(hi * SR / HOP))]
        if not len(seg):
            return (lo + hi) / 2
        return min(hi, max(lo, (a + int(np.argmin(seg)) + 0.5) * HOP / SR))

    def out_side(t):  # after kept tail word t
        if t in inspected_out:
            return inspected_out[t]
        e = bnd(t)[1]
        nxt = bnd(t + 1)[0] if t + 1 < len(words) else e + 0.5
        hi = min(nxt - GUARD_S, e + OUT_REACH_S) if nxt > e + FUSED_S else e + FUSED_PAD_S
        return e, (valley(e, hi) if hi - e > MIN_SEARCH_S else e + PREF_MARGIN_S), hi

    def in_side(h):  # before kept head word h
        if h in inspected_in:
            return inspected_in[h]
        s = bnd(h)[0]
        prv = bnd(h - 1)[1] if h > 0 else s - 0.5
        lo = max(0.0, max(prv + GUARD_S, s - IN_REACH_S) if prv < s - FUSED_S else s - FUSED_PAD_S)
        return lo, max(lo, valley(lo, s) if s - lo > MIN_SEARCH_S else s - PREF_MARGIN_S), s

    R = sample_rate
    joins, log = [], []
    for j in range(len(kept) - 1):
        t, h = kept[j][1], kept[j + 1][0]
        olo, op, ohi = out_side(t)
        ilo, ip, ihi = in_side(h)
        op, ip = min(ohi, max(op, olo + PREF_MARGIN_S)), max(ilo, min(ip, ihi - PREF_MARGIN_S))
        joins.append({'out_window': [round(olo * R), round(ohi * R)], 'in_window': [round(ilo * R), round(ihi * R)],
                      'preferred_out': round(op * R), 'preferred_in': round(ip * R),
                      'reason': f"out after '{words[t]['word']}' (locator end {olo:.3f}) / in before "
                                f"'{words[h]['word']}' (locator start {ihi:.3f}); quietest 5 ms points",
                      'evidence': [evidence], 'status': 'PROPOSED'})
        log.append((j + 1, words[t]['word'], ohi - olo, words[h]['word'], ihi - ilo))
    _, head, _ = in_side(kept[0][0])
    _, tail, _ = out_side(kept[-1][1])
    spf = Fraction(R) / Fraction(fps)
    first_sample, last_sample = round(head * R), round(tail * R)
    decisions = {'schema': 'edit.paired-seam-decisions/v1', 'sample_rate': R, 'fps': str(fps),
                 'span_count': len(kept),
                 'first_source_frame': math.floor(first_sample / spf), 'last_source_frame': math.ceil(last_sample / spf),
                 'first_source_sample': first_sample, 'last_source_sample': last_sample,
                 'outer_edge_evidence': {'status': 'PROPOSED', 'head': f'valley before word {kept[0][0]}',
                                         'tail': f'valley after word {kept[-1][1]}'},
                 'joins': joins}
    return decisions, log


def bounds_doc(words, bounds):
    return {'schema': 'assembly.mfa-word-bounds/v1', 'source': 'mfa',
            'scope': 'MFA bounds on intact +/-6-word windows that match the ASR occurrence; not listening proof.',
            'words': {str(i): {'word_index': i, 'word': words[i]['word'],
                               'aligned_start': round(s, 4), 'aligned_end': round(e, 4)}
                      for i, (s, e) in sorted(bounds.items())}}


def load_words(path):
    data = json.loads(Path(path).read_text())
    return data['words'] if isinstance(data, dict) else data


def write_new(path, doc):
    with Path(path).open('x') as f:
        json.dump(doc, f, indent=1)
        f.write('\n')


def decide(a):
    words = load_words(a.words)
    clips = [c for c in json.loads(a.selection.read_text())['clips'] if a.clip_id in (None, c['id'])]
    if len(clips) != 1:
        raise SystemExit('select exactly one clip with --clip-id')
    kept = clips[0]['kept_word_ranges']
    need = [i for s, e in kept for i in (s - 1, s, e, e + 1) if 0 <= i < len(words)]
    bounds = trusted_bounds(words, mfa_align(words, need, a.audio, a.cache_dir))
    inspected_in, inspected_out = load_inspected(a.inspected)
    decisions, log = plan(words, kept, bounds, envelope(a.audio, a.cache_dir), a.sample_rate, Fraction(a.fps),
                          str(a.cache_dir / 'mfa'), inspected_in, inspected_out)
    write_new(a.out, decisions)
    if a.bounds_out:
        write_new(a.bounds_out, bounds_doc(words, bounds))
    for n, tw, ow, hw, iw in log:
        print(f'join {n}: {tw} | out window {ow * 1000:.0f} ms ; {hw} | in window {iw * 1000:.0f} ms')
    asr_only = sorted(set(need) - set(bounds))
    if asr_only:
        print('ASR-only edges (no trusted MFA): ' + ', '.join(f"{i} '{words[i]['word']}'" for i in asr_only))


def peek(a):
    words = load_words(a.words)
    env = envelope(a.audio, a.cache_dir)
    edges = {e['edge']: e for e in json.loads(a.join_check.read_text())['edges']}
    for name in a.edges.split(','):
        e = edges[name]
        i = e['word']
        near = [j for j in (i - 1, i, i + 1) if 0 <= j < len(words)]
        aligned = mfa_align(words, near, a.audio, a.cache_dir)
        print(f"\n{name} '{e['word_text']}' cut {e['cut_s']} | ASR: " + ' '.join(
            f"{words[j]['word']}@{words[j]['start']:.2f}-{words[j]['end']:.2f}"
            for j in range(max(0, i - 2), min(len(words), i + 3))))
        print('  MFA:', {j: tuple(round(x, 3) for x in v) for j, v in aligned.items()})
        t0 = e['cut_s'] - 0.25
        steps = [t0 + k * 0.01 for k in range(50)]
        print('  env:', ' '.join(f'{t:.2f}:{env[int(t * SR / HOP)]:.0f}' for t in steps
                                 if 0 <= int(t * SR / HOP) < len(env)))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    d = sub.add_parser('decide', help='draft paired-seam decisions for one clip')
    d.add_argument('--words', required=True, type=Path, help='source word transcript (words[] with start/end)')
    d.add_argument('--audio', required=True, type=Path, help='played dialogue on the source clock')
    d.add_argument('--selection', required=True, type=Path, help='selection with kept_word_ranges')
    d.add_argument('--clip-id', help='required when the selection holds several clips')
    d.add_argument('--cache-dir', required=True, type=Path)
    d.add_argument('--fps', required=True, help='source picture rate, e.g. 30 or 24000/1001')
    d.add_argument('--sample-rate', type=int, default=48000)
    d.add_argument('--inspected', help='JSON (inline or file) of waveform-inspected windows')
    d.add_argument('--out', required=True, type=Path, help='new decisions JSON for pair_audio_seams.py')
    d.add_argument('--bounds-out', type=Path, help='new MFA bounds JSON for pair_audio_seams.py --phonemes')
    p = sub.add_parser('peek', help='print ASR/MFA/envelope around join_check edges')
    p.add_argument('--words', required=True, type=Path)
    p.add_argument('--audio', required=True, type=Path)
    p.add_argument('--join-check', required=True, type=Path, help='join_check.py output')
    p.add_argument('--edges', required=True, help='comma-separated edge names, e.g. head2,tail3')
    p.add_argument('--cache-dir', required=True, type=Path)
    a = ap.parse_args(argv)
    if a.cmd == 'decide':
        for path in (a.out, a.bounds_out):
            if path and path.exists():
                ap.error(f'{path} exists; use a new revision path')
        decide(a)
    else:
        peek(a)


if __name__ == '__main__':
    main()
