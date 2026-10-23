#!/usr/bin/env python3
"""Re-listen to a clip's riskiest joins as they will actually play, in one Gemini call.

Picks at most --max-joins (default 5) joins from paired.json whose edge words are
fused/tight in the word-evidence table or carry Gemini delivery tags, renders each
join exactly as cut (2 s before + 2 s after the splice), and asks Gemini what it
hears. Returns observations for the editor-model to act on (move a boundary, revise
a word); never a pass/fail. If Gemini is unavailable the result says so and the clip
continues on its local evidence. Cached: an unchanged join is never paid for twice.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / '_shared'))
import gemini_audio  # noqa: E402

SCHEMA = 'assembly.gemini-seams/v1'
CONTEXT_S = 2.0
GAP_S = 1.0
HEARD = ('clean', 'clipped_word', 'leaked_sound', 'unnatural_pause', 'breath_or_click', 'other')
PROMPT = """This audio contains {n} edited dialogue joins, each {ctx:.0f} s before and {ctx:.0f} s after a splice,
separated by {gap:.0f} s of silence. Listen to sound only, not content.
{listing}
For each join report what you hear at the splice: clean, clipped_word (start or end of a word cut
off), leaked_sound (a fragment of an unwanted word or syllable), unnatural_pause, breath_or_click,
or other. Do not reconstruct sounds because you understand the sentence. Return JSON exactly:
{{"joins":[{{"join":int,"heard":"<one of the above>","confidence":"high|medium|low","note":"short"}}]}}
"""


def decode(audio, rate):
    raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(audio), '-vn', '-ac', '1', '-ar', str(rate),
                                   '-f', 'f32le', '-'])
    return np.frombuffer(raw, '<f4')


def to_mp3(x, rate):
    return subprocess.run(['ffmpeg', '-v', 'error', '-f', 'f32le', '-ar', str(rate), '-ac', '1', '-i', '-',
                           '-ar', '16000', '-c:a', 'libmp3lame', '-b:a', '48k', '-f', 'mp3', '-'],
                          input=x.astype('<f4').tobytes(), stdout=subprocess.PIPE, check=True).stdout


def risk(by_index, out_word, in_word):
    """Join risk from the selected words on each side (ASR labels are too stretched to find them by time)."""
    left, right = by_index[out_word], by_index[in_word]
    before_right = by_index.get(in_word - 1)
    edges = [left.get('after') or {}, (before_right or {}).get('after') or {}]
    states = [e.get('state') for e in edges]
    score = 3 * states.count('fused') + states.count('tight') + (1 if left['gemini'] or right['gemini'] else 0)
    loudest = max((e['valley_db'] for e in edges if e.get('valley_db') is not None), default=-120.0)
    return score, left, right, states, loudest


def run(paired_path, selection_path, clip_id, audio, evidence_path, cache_dir, out, max_joins=5, max_usd=2.0,
        models=gemini_audio.FALLBACK_MODELS,
        caller=gemini_audio.call_chain, decoder=decode, encoder=to_mp3):
    paired = json.loads(Path(paired_path).read_text())
    rate = int(paired['sample_rate'])
    rows = json.loads(Path(evidence_path).read_text())['words']
    by_index = {r['i']: r for r in rows}
    samples = paired['source_samples']
    clip = next(c for c in json.loads(Path(selection_path).read_text())['clips'] if c['id'] == clip_id)
    kept = clip['kept_word_ranges']
    if len(kept) != len(samples):
        raise ValueError('selection kept ranges do not match paired spans; use the exact pause-split selection')
    candidates = []
    for j in range(len(samples) - 1):
        out_t, in_t = samples[j][1] / rate, samples[j + 1][0] / rate
        score, left, right, states, loudest = risk(by_index, kept[j][1], kept[j + 1][0])
        candidates.append({'join': j + 1, 'score': score, 'out_s': round(out_t, 3), 'in_s': round(in_t, 3),
                           'out_word': [left['i'], left['word']], 'in_word': [right['i'], right['word']],
                           'waveform': states, 'loudest_edge_db': loudest})
    chosen = sorted([c for c in candidates if c['score'] > 0], key=lambda c: (-c['score'], -c['loudest_edge_db'], c['join']))[:max_joins]
    chosen.sort(key=lambda c: c['join'])
    result = {'schema': SCHEMA, 'paired': str(Path(paired_path).resolve()), 'model': None, 'not_flagged': [],
              'joins_total': len(candidates), 'checked': chosen, 'heard': [], 'status': 'NO_RISKY_JOINS',
              'scope': 'Listener observations at the splice. Not an approval; the editor-model decides.'}
    if chosen:
        x = decoder(audio, rate)
        ctx, gap = int(CONTEXT_S * rate), np.zeros(int(GAP_S * rate), np.float32)
        parts, listing, cursor = [], [], 0.0
        for n, c in enumerate(chosen, 1):
            o, i = samples[c['join'] - 1][1], samples[c['join']][0]
            piece = np.concatenate([x[max(0, o - ctx):o], x[i:i + ctx]])
            listing.append(f"Join {n}: {cursor:.1f}-{cursor + len(piece) / rate:.1f} s, splice at "
                           f"{cursor + min(ctx, o) / rate:.1f} s ('{c['out_word'][1]}' | '{c['in_word'][1]}')")
            parts += [piece, gap]
            cursor += (len(piece) + len(gap)) / rate
        prompt = PROMPT.format(n=len(chosen), ctx=CONTEXT_S, gap=GAP_S, listing='\n'.join(listing))
        r = caller(encoder(np.concatenate(parts[:-1]), rate), prompt, cache_dir=cache_dir,
                   budget=gemini_audio.Budget(max_usd, 3), models=models)
        result.update(status=r['status'], model=r.get('model'), detail=r.get('detail'), usage=r.get('usage'),
                      usd=round(r.get('usd', 0.0), 4))
        for h in (r.get('result') or {}).get('joins', []) if r['status'] in ('OK', 'CACHED') else []:
            try:
                n = int(h['join'])
            except (KeyError, TypeError, ValueError):
                continue
            if 1 <= n <= len(chosen) and h.get('heard') in HEARD:
                if h['heard'] == 'clean':
                    # Qualification controls: listeners miss clipped word endings, so "clean"
                    # is not evidence. Endings are judged by join_check.py measurements.
                    result['not_flagged'].append(chosen[n - 1]['join'])
                    continue
                result['heard'].append({**chosen[n - 1], 'heard': h['heard'],
                                        'confidence': h.get('confidence'), 'note': str(h.get('note', ''))[:200]})
    with Path(out).open('x') as f:
        json.dump(result, f, indent=1)
        f.write('\n')
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--paired', required=True, type=Path)
    ap.add_argument('--selection', required=True, type=Path, help='the exact pause-split v2 selection paired.json was solved for')
    ap.add_argument('--clip-id', required=True)
    ap.add_argument('--audio', required=True, type=Path, help='played dialogue on the paired sample clock')
    ap.add_argument('--evidence', required=True, type=Path, help='word_evidence.py table')
    ap.add_argument('--cache-dir', required=True, type=Path)
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--max-joins', type=int, default=5)
    ap.add_argument('--model', help='one model only; default is the fallback chain')
    a = ap.parse_args()
    if a.out.exists():
        ap.error('output exists; use a new revision path')
    r = run(a.paired, a.selection, a.clip_id, a.audio, a.evidence, a.cache_dir, a.out, a.max_joins,
            models=(a.model,) if a.model else gemini_audio.FALLBACK_MODELS)
    print(json.dumps({'status': r['status'], 'checked': [c['join'] for c in r['checked']],
                      'model': r.get('model'), 'flagged': [(h['join'], h['heard'], h['confidence']) for h in r['heard']],
                      'not_flagged_is_not_proof': r['not_flagged'],
                      'usd': r.get('usd'), 'detail': r.get('detail')}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
