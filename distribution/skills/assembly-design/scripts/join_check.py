#!/usr/bin/env python3
"""Measured join check: is every cut outside the words it keeps and the words it drops?

For each kept span in paired.json, aligns the edge words with MFA on the intact local
phrase (excluded neighbours included) and measures the cut against the played
waveform. Listener models miss clipped word endings (2026-10-15 controls), so
endings are judged here by measurement, never by a "sounds clean" verdict.

Blocking (exit 2 unless accepted with --accept JOIN_OR_EDGE:reason):
  CUT_INSIDE_WORD      out-point before a kept word's end, or in-point after its start
  LEAKS_EXCLUDED_WORD  out-point after the next removed word starts, or in-point before
                       the previous removed word ends
  LOCATORS_DISAGREE    AssemblyAI and MFA describe different sounds for the edge word (an edge
                       >0.25 s apart and neither interval inside the other: a stutter's other
                       occurrence, or a mislabelled word): resolve from the waveform or a third
                       transcript, then --accept. Either locator can be the wrong one. An ASR label
                       merely stretched over a pause (or squeezed) around MFA is the same word, so
                       MFA's tighter bounds are used and nothing blocks.
Warning (reported, not blocking):
  CUT_ON_SOUND         the 10 ms at the cut is well above room tone (breath, release, click)
If MFA is unavailable for an edge, AssemblyAI times are used and the edge is marked
`asr_only` (weaker evidence, never silently upgraded).
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from word_evidence import SR, HOP, envelope  # noqa: E402

SCHEMA = 'assembly.join-check/v1'
TOL = 0.005          # 5 ms: half a typical phone-alignment step
OCCURRENCE_S = 0.25  # MFA this far from the ASR locator has likely aligned a repeated word's other occurrence
SOUND_DB = 25        # above room tone at the cut
AUDIBLE_DB = 15      # a lost or leaked slice quieter than this (e.g. a stop closure) is not blocking
MFA_ROOT = Path.home() / '.local/share/script-cut'


ONES = ('zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen '
        'sixteen seventeen eighteen nineteen').split()
TENS = 'twenty thirty forty fifty sixty seventy eighty ninety'.split()


def spoken_number(n):
    """Digits as words so MFA can align money, percentages and counts (no 'and', no 'dollars')."""
    if n < 20:
        return ONES[n]
    if n < 100:
        return TENS[n // 10 - 2] + ('' if n % 10 == 0 else ' ' + ONES[n % 10])
    if n < 1000:
        return ONES[n // 100] + ' hundred' + ('' if n % 100 == 0 else ' ' + spoken_number(n % 100))
    for size, name in ((10 ** 9, 'billion'), (10 ** 6, 'million'), (1000, 'thousand')):
        if n >= size:
            return spoken_number(n // size) + ' ' + name + ('' if n % size == 0 else ' ' + spoken_number(n % size))


SCALES = {'k': 'thousand', 'm': 'million', 'b': 'billion'}


def norm(token):
    text = str(token).lower().replace('%', ' percent')
    text = re.sub(r'(\d)([kmb])\b', lambda m: m.group(1) + ' ' + SCALES[m.group(2)], text)   # $10K, $1.5M
    text = re.sub(r'(\d+)\.(\d+)', lambda m: m.group(1) + ' point ' + ' '.join(m.group(2)), text)
    text = re.sub(r'\d[\d,]*', lambda m: ' ' + spoken_number(int(m.group().replace(',', ''))) + ' ', text)
    return ' '.join(re.sub(r"[^\w\s'-]", '', text).replace('-', ' ').split())


def same_occurrence(asr, mfa):
    """True when MFA bounds describe the ASR-labelled sound: both edges within OCCURRENCE_S,
    or one interval nested in the other (a stretched, squeezed or zero-length ASR label)."""
    (a0, a1), (m0, m1) = asr, mfa
    near = abs(m0 - a0) <= OCCURRENCE_S and abs(m1 - a1) <= OCCURRENCE_S
    return near or a0 <= m0 <= m1 <= a1 or m0 <= a0 <= a1 <= m1


def mfa_align(words, indices, audio, cache_dir, aligner=None):
    """{word_index: (start, end)} from MFA on ±6-word intact windows; missing on failure."""
    if aligner:
        return aligner(indices)
    if not (MFA_ROOT / 'bin/micromamba').exists():
        return {}
    cache_dir = Path(cache_dir) / 'mfa'
    corpus, out = cache_dir / 'corpus', cache_dir / 'aligned'
    corpus.mkdir(parents=True, exist_ok=True)
    jobs = {}
    for i in sorted(set(indices)):
        a, b = max(0, i - 6), min(len(words) - 1, i + 6)
        toks = [(j, norm(words[j]['word'])) for j in range(a, b + 1)]
        start, end = max(0.0, words[a]['start'] - 0.3), words[b]['end'] + 0.3
        lab = ' '.join(t for _, t in toks if t)
        name = 'e' + hashlib.sha256(f'{audio}|{start:.3f}|{end:.3f}|{lab}'.encode()).hexdigest()[:16]
        jobs[i] = (name, start, toks)
        if not (out / f'{name}.json').exists() and not (corpus / f'{name}.wav').exists():
            (corpus / f'{name}.lab').write_text(lab)
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{start:.3f}', '-t', f'{end - start:.3f}',
                            '-i', str(audio), '-ac', '1', '-ar', '16000', str(corpus / f'{name}.wav')], check=True)
    pending = [n for n, _, _ in jobs.values() if not (out / f'{n}.json').exists()]
    if pending:
        subprocess.run([str(MFA_ROOT / 'bin/micromamba'), 'run', '-p', str(MFA_ROOT / 'mfa_env'), 'mfa', 'align',
                        str(corpus), 'english_us_arpa', 'english_us_arpa', str(out), '--temporary_directory',
                        str(cache_dir / 'tmp'), '--single_speaker', '--num_jobs', '4', '--output_format', 'json',
                        '--quiet', '--clean'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    found = {}
    for i, (name, start, toks) in jobs.items():
        path = out / f'{name}.json'
        if not path.exists():
            continue
        entries = [e for e in json.loads(path.read_text())['tiers']['words']['entries'] if e[2] not in ('', '<eps>')]
        parts = [(j, t.split()) for j, t in toks if t]
        if sum(len(p) for _, p in parts) != len(entries):
            continue  # alignment does not map 1:1 to the transcript; do not guess
        k = 0
        for j, p in parts:
            seg = entries[k:k + len(p)]
            k += len(p)
            if seg and j == i:  # trust a word only from the window centred on it
                found[j] = (start + seg[0][0], start + seg[-1][1])
    return found


def level(env, t0, t1):
    a, b = int(t0 * SR / HOP), max(int(t0 * SR / HOP) + 1, int(np.ceil(t1 * SR / HOP)))
    seg = env[max(0, a):min(len(env), b)]
    return float(seg.max()) if len(seg) else None


def check(paired_path, selection_path, clip_id, words_path, audio, cache_dir, accept=(), aligner=None):
    paired = json.loads(Path(paired_path).read_text())
    rate = int(paired['sample_rate'])
    clip = next(c for c in json.loads(Path(selection_path).read_text())['clips'] if c['id'] == clip_id)
    kept = clip['kept_word_ranges']
    samples = paired['source_samples']
    if len(kept) != len(samples):
        raise ValueError('selection kept ranges do not match paired spans')
    words = json.loads(Path(words_path).read_text())['words']
    kept_set = {i for a, b in kept for i in range(a, b + 1)}
    edges = []
    for n, ((a, b), (s0, s1)) in enumerate(zip(kept, samples)):
        edges.append({'edge': f'head{n + 1}', 'side': 'head', 'word': a, 'cut': s0 / rate, 'neighbour': a - 1})
        edges.append({'edge': f'tail{n + 1}', 'side': 'tail', 'word': b, 'cut': s1 / rate, 'neighbour': b + 1})
    need = [e['word'] for e in edges] + [e['neighbour'] for e in edges if 0 <= e['neighbour'] < len(words)]
    aligned = mfa_align(words, need, audio, cache_dir, aligner)
    # Stutters ("it's, uh, it's") can make MFA align the wrong occurrence; never judge a cut on that.
    suspect = {i: (a, b) for i, (a, b) in aligned.items()
               if not same_occurrence((words[i]['start'], words[i]['end']), (a, b))}
    for i in suspect:
        aligned.pop(i)
    env = envelope(audio, cache_dir)
    floor = float(np.percentile(env, 10))
    accepted = dict(item.split(':', 1) for item in accept)
    results, blocking = [], []
    for e in edges:
        i, cut, side = e['word'], e['cut'], e['side']
        bounds = aligned.get(i)
        src = 'mfa' if bounds else ('asr_only_mfa_disagreed' if i in suspect else 'asr_only')
        start, end = bounds or (words[i]['start'], words[i]['end'])
        issues, quiet = [], []
        if i in suspect:
            # 2026-10-15: on one clip MFA was right and ASR wrong (a dropped first word), on another
            # the reverse. Neither locator may silently win.
            issues.append(f'LOCATORS_DISAGREE: AssemblyAI and MFA place "{words[i]["word"]}" '
                          f'{1000 * abs(suspect[i][0] - words[i]["start"]):.0f} ms apart; resolve from the waveform')

        def judge(kind, t0, t1, text):
            # Block only when the lost/leaked slice carries sound; a silent closure is a note.
            loud = level(env, t0, t1)
            audible = loud is not None and loud > floor + AUDIBLE_DB
            (issues if audible else quiet).append(
                f'{kind}: {text} (' + (f'{loud - floor:.0f} dB above room tone' if audible else 'silent slice') + ')')
        if side == 'tail' and cut < end - TOL:
            judge('CUT_INSIDE_WORD', cut, end, f'cut {1000 * (end - cut):.0f} ms before "{words[i]["word"]}" ends')
        if side == 'head' and cut > start + TOL:
            judge('CUT_INSIDE_WORD', start, cut, f'cut {1000 * (cut - start):.0f} ms after "{words[i]["word"]}" starts')
        nb = e['neighbour']
        if 0 <= nb < len(words) and nb not in kept_set:
            nb_bounds = aligned.get(nb)
            if nb_bounds:  # only measured neighbours can prove a leak
                if side == 'tail' and cut > nb_bounds[0] + TOL:
                    judge('LEAKS_EXCLUDED_WORD', nb_bounds[0], cut, f'{1000 * (cut - nb_bounds[0]):.0f} ms of removed "{words[nb]["word"]}"')
                if side == 'head' and cut < nb_bounds[1] - TOL:
                    judge('LEAKS_EXCLUDED_WORD', cut, nb_bounds[1], f'{1000 * (nb_bounds[1] - cut):.0f} ms of removed "{words[nb]["word"]}"')
        db = level(env, cut - 0.010, cut) if side == 'tail' else level(env, cut, cut + 0.010)
        warnings = quiet + ([f'CUT_ON_SOUND: {db - floor:.0f} dB above room tone at the cut']
                            if db is not None and db > floor + SOUND_DB else [])
        decision = accepted.get(e['edge'])
        if issues and not decision:
            blocking.append(e['edge'])
        results.append({**e, 'word_text': words[i]['word'], 'evidence': src,
                        'word_bounds_s': [round(start, 3), round(end, 3)], 'cut_s': round(cut, 3),
                        'level_above_room_db': None if db is None else round(db - floor, 1),
                        'blocking': issues, 'warnings': warnings,
                        **({'accepted_by_editor': decision} if decision and issues else {})})
    return {'schema': SCHEMA, 'paired': str(Path(paired_path).resolve()), 'clip_id': clip_id,
            'room_floor_db': round(floor, 1), 'edges': results, 'blocking_edges': blocking,
            'status': 'JOINS_MEASURED_CLEAR' if not blocking else 'CUT_REPAIR_REQUIRED',
            'scope': 'Measured edge placement (MFA + waveform). Not listening approval.'}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--paired', required=True, type=Path)
    ap.add_argument('--selection', required=True, type=Path)
    ap.add_argument('--clip-id', required=True)
    ap.add_argument('--words', required=True, type=Path)
    ap.add_argument('--audio', required=True, type=Path, help='played dialogue on the paired sample clock')
    ap.add_argument('--cache-dir', required=True, type=Path)
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--accept', action='append', default=[], help='EDGE:reason, e.g. head11:breath kept for cadence')
    a = ap.parse_args()
    if a.out.exists():
        ap.error('output exists; use a new revision path')
    r = check(a.paired, a.selection, a.clip_id, a.words, a.audio, a.cache_dir, a.accept)
    with a.out.open('x') as f:
        json.dump(r, f, indent=1)
        f.write('\n')
    print(json.dumps({'status': r['status'], 'blocking': {e['edge']: e['blocking'] for e in r['edges'] if e['blocking']},
                      'warnings': {e['edge']: e['warnings'] for e in r['edges'] if e['warnings']},
                      'asr_only_edges': [e['edge'] for e in r['edges'] if e['evidence'].startswith('asr_only')],
                      'mfa_disagreed_inspect_by_waveform': [e['edge'] for e in r['edges'] if e['evidence'] == 'asr_only_mfa_disagreed']}, indent=1))
    return 2 if r['blocking_edges'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
