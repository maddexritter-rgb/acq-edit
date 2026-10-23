#!/usr/bin/env python3
"""Provider-neutral source-plan adapter. Structural checks are not editorial approval."""
import argparse
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import sys
import subprocess

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'edit' / 'scripts'))
from assembly_job import digest
from l1_cut_plan import compile_plan, interval, nonempty, require
from design_evidence import evaluate


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def fingerprint(value):
    return sha(json.dumps(value, sort_keys=True).encode())


def pinned(path, expected):
    p = Path(path)
    require(p.is_absolute() and p.is_file(), 'missing absolute evidence path')
    require(digest(p) == expected, 'evidence changed: ' + str(p))
    return p


def verification(plan, words):
    ref = plan['verification']
    v = json.loads(pinned(ref['path'], ref['sha256']).read_text())
    require(v.get('schema') == 'edit.transcript-verification/v1', 'invalid verification schema')
    require(v.get('source_words') == plan['source_words'] and
            v.get('source_sha256') == plan['source_sha256'], 'verification/source mismatch')
    raw = json.loads(pinned(v['raw_words'], v['raw_sha256']).read_text())['words']
    pinned(v['audio_path'], v['audio_sha256'])
    require(nonempty(v.get('reviewer')) and nonempty(v.get('method')), 'missing listening review')
    require(v.get('unresolved') == [], 'unresolved transcript issues')
    checked = set()
    for bounds in v['checked_words']:
        checked.update(interval(bounds, 0, len(words) - 1))
    require(set(interval(plan['interaction_words'], 0, len(words)-1)) <= checked,
            'candidate region not fully audio-checked')
    corrections = v['corrections']
    require(isinstance(corrections, list), 'corrections must be a list')
    require(raw == words or corrections, 'changed transcript needs evidenced corrections')
    # Every changed word must be inside a documented correction, including timing/speaker edits.
    raw_claimed, corrected_claimed = set(), set()
    for c in corrections:
        ri = set(interval(c['raw_words'], 0, len(raw)-1))
        ci = set(interval(c['corrected_words'], 0, len(words)-1))
        require(not ri & raw_claimed and not ci & corrected_claimed, 'overlapping corrections')
        raw_claimed.update(ri); corrected_claimed.update(ci)
        require(nonempty(c.get('heard')) and nonempty(c.get('why')), 'missing correction evidence')
        pinned(c['evidence']['path'], c['evidence']['sha256'])
    require([w for i, w in enumerate(raw) if i not in raw_claimed] ==
            [w for i, w in enumerate(words) if i not in corrected_claimed],
            'undocumented transcript changes')
    return v


def compile_assembly(plan):
    require(plan.get('schema') == 'edit.assembly-plan/v1', 'invalid assembly schema')
    require(plan.get('stage') != 'draft', 'unverified draft cannot compile')
    profiles = plan.get('profiles')
    require(isinstance(profiles, list) and profiles and
            all(p in {'monologue', 'qa', 'l1_diagnosis', 'conversation_story'} for p in profiles),
            'invalid moment profiles')
    review = plan.get('editorial_review', {})
    for key in ('promise', 'hook', 'payoff', 'context', 'qualifications',
                'omitted_branches', 'reorder_safety', 'ending_continuation', 'alternatives'):
        require(nonempty(review.get(key)), 'missing editorial review: ' + key)
    source = pinned(plan['source_words'], plan['source_sha256'])
    words = json.loads(source.read_text())['words']
    verified = verification(plan, words)
    # Reuse existing source accounting, reorder review and legacy evidence compiler.
    # Ordinary moments reuse membership accounting; diagnosis moments additionally
    # reuse the existing v6 semantic/branch/boundary checks, without duplicating them.
    legacy = dict(plan, schema='edit.l1-cut-plan/v1')
    diagnosis = plan.get('diagnosis')
    if 'l1_diagnosis' in profiles:
        fields = {'source_coverage', 'promise', 'promise_ranking', 'format_review',
                  'opening_review', 'ending_review', 'semantic_evidence', 'branch_review'}
        require(isinstance(diagnosis, dict) and set(diagnosis) == fields,
                'l1_diagnosis needs the complete diagnosis review contract')
        legacy.update(diagnosis)
        legacy['schema'] = 'edit.l1-cut-plan/v6'
    else:
        require(diagnosis is None, 'diagnosis review requires l1_diagnosis profile')
    legacy['target_seconds'] = plan.get('target_seconds', 10**9)
    result = compile_plan(legacy, source.parent)
    construction_review = result['receipt']['semantic_review']
    boundary_reviews = result['receipt']['boundary_reviews']
    result['receipt'] = {
        'schema': 'edit.assembly-receipt/v1', 'status': 'STRUCTURE_VALID',
        'plan_sha256': fingerprint(plan), 'source_sha256': plan['source_sha256'],
        'clip_id': plan['clip_id'],
        'profiles': profiles, 'construction_review': construction_review,
        'boundary_reviews': boundary_reviews,
        'scope': 'Source accounting only; acoustic, semantic, native and human review pending.'}
    result['intended_indices'] = result['design_receipt']['kept_word_indices']
    # Preserve speaker changes in readable dialogue, including within one selection.
    # Keep source indices alongside text so repeated phrases remain distinguishable.
    dialogue = []
    for n, segment in enumerate(plan['segments']):
        for i in interval(segment['words'], 0, len(words)-1):
            w = words[i]
            speaker = w.get('spk', w.get('speaker'))
            if (dialogue and dialogue[-1]['segment'] == n and
                    dialogue[-1]['speaker'] == speaker):
                dialogue[-1]['source_words'][1] = i
                dialogue[-1]['text'] += ' ' + w['word']
            else:
                dialogue.append({'segment': n, 'speaker': speaker,
                                 'source_words': [i, i], 'text': w['word']})
    result['assembled_dialogue'] = dialogue
    result['assembled_dialogue_text'] = '\n'.join(
        str(d['speaker'] if d['speaker'] is not None else 'UNKNOWN') + ': ' + d['text']
        for d in dialogue)
    result['cut_request'] = {'source_sha256': plan['source_sha256'], 'segments': [
        {'in': s['rough_source_seconds'][0], 'out': s['rough_source_seconds'][1],
         'n': n+1, 'cat': s['role'], 'source_words': s['words']}
        for n, s in enumerate(result['selection_guide'])]}
    if 'performance_evidence' in plan:
        result['cut_request']['performance_evidence'] = plan['performance_evidence']
        result['cut_request']['performance_decisions'] = plan['performance_decisions']
    performance = []
    for n, segment in enumerate(plan['segments']):
        if 'performance' not in segment:
            continue
        p = segment['performance']
        require(isinstance(p, dict) and nonempty(p.get('why')), 'performance needs reason')
        region = p.get('source_seconds')
        require(isinstance(region, list) and len(region) == 2 and
                all(type(v) in (int, float) and math.isfinite(v) for v in region) and
                0 <= region[0] < region[1], 'invalid performance interval')
        pinned(p['evidence']['path'], p['evidence']['sha256'])
        target = result['cut_request']['segments'][n]
        require(region[0] <= target['out'] and region[1] >= target['in'],
                'performance must attach to selected speech; separate shot requires design support')
        target['in'] = min(target['in'], region[0])
        target['out'] = max(target['out'], region[1])
        selected_range = set(range(segment['words'][0], segment['words'][1]+1))
        require(not any(i not in selected_range and w['end'] > target['in'] and
                        w['start'] < target['out'] for i, w in enumerate(words)),
                'performance interval adds unwanted words, including partial speech')
        target['performance'] = p
        performance.append({'segment': n, 'words': segment['words'], **p})
    if performance:
        # Keep legacy evidence valid even when the last ASR word precedes a real gesture tail.
        result['design']['source_media'] = {
            'path': verified['audio_path'], 'sha256': verified['audio_sha256']}
        result['design']['keep_spans'] = [[s['in'], s['out']]
                                          for s in result['cut_request']['segments']]
        result['design_receipt'] = evaluate(result['design'])
        require(result['design_receipt']['kept_word_indices'] == result['intended_indices'],
                'performance interval adds unwanted words; return to designer')
    result['performance'] = performance
    result['speech_map_performance'] = [
        s.get('performance', {}).get('source_seconds') for s in plan['segments']]
    return result


def reconcile(plan, resolved):
    compiled = compile_assembly(plan)
    require(resolved.get('schema') == 'edit.assembly-resolved/v1', 'invalid resolved schema')
    require(resolved.get('plan_sha256') == fingerprint(plan), 'stale resolved plan')
    require(resolved.get('source_sha256') == plan['source_sha256'], 'stale resolved source')
    rate = Fraction(str(resolved['fps']))
    require(rate > 0, 'invalid frame rate')
    ref = resolved['acoustic_evidence']
    acoustic = json.loads(pinned(ref['path'], ref['sha256']).read_text())
    words = json.loads(Path(plan['source_words']).read_text())['words']
    spans = resolved['spans']
    require(isinstance(spans, list) and spans, 'empty resolved spans')
    for s in spans:
        require(isinstance(s, list) and len(s) == 2 and
                all(type(v) in (int, float) and math.isfinite(v) for v in s) and
                0 <= s[0] < s[1], 'invalid resolved span')
        require(all(abs(v * float(rate) - round(v * float(rate))) < 1e-5 for v in s),
                'boundary not on source frame grid')
    chronological = sorted(spans)
    require(all(a[1] <= b[0] for a, b in zip(chronological, chronological[1:])),
            'resolved source overlap')
    selected, partial, final_words, span_words = [], [], [], []
    clock = 0.0
    for a, b in spans:
        count_before = len(selected)
        for i, w in enumerate(words):
            # Partial contact blocks even if the unwanted word midpoint is outside.
            overlaps = w['end'] > a + 1e-7 and w['start'] < b - 1e-7
            if w['start'] == w['end']:
                overlaps = a <= w['start'] < b
            if not overlaps:
                continue
            if w['start'] < a - 1e-7 or w['end'] > b + 1e-7:
                partial.append(i)
            selected.append(i)
            final_words.append({**w, 'source_word_index': i,
                                'source_start': w['start'], 'source_end': w['end'],
                                'start': clock + w['start'] - a,
                                'end': clock + w['end'] - a})
        require(len(selected) > count_before, 'word-empty resolved span')
        span_words.append(set(selected[count_before:]))
        clock += b-a
    expected = compiled['intended_indices']
    require(not partial, 'partial edge words require timing repair/redesign: ' + str(partial))
    require(selected == expected,
            'retained words changed; return to designer: ' + json.dumps({
                'added': sorted(set(selected)-set(expected)),
                'missing': sorted(set(expected)-set(selected)),
                'order_changed': set(selected) == set(expected)}))
    for p in compiled['performance']:
        first, last = p['words']
        matches = [s for s, ids in zip(spans, span_words) if {first, last} <= ids]
        require(len(matches) == 1, 'performance detached from selected speech')
        a, b = matches[0]; pa, pb = p['source_seconds']
        require(a <= pa + 1e-7 and b >= pb - 1e-7,
                'selected performance lost; return to designer')
    spec = dict(compiled['design'], keep_spans=spans)
    receipt = evaluate(spec)
    require(receipt['status'] == 'PASS' and receipt['kept_word_indices'] == expected,
            'resolved legacy evidence mismatch')
    require(isinstance(acoustic, list) and len(acoustic) == len(spans),
            'speech-map evidence must cover every resolved span')
    for entry, span in zip(acoustic, spans):
        require(isinstance(entry, dict) and all(
            isinstance(entry.get(edge), dict) and
            entry[edge].get('verdict') in {'OK', 'OK_MICRO_GAP'}
            for edge in ('start', 'end')),
            'unsafe or unverified acoustic boundary; return to designer')
        for edge in ('start', 'end'):
            detail = entry[edge]
            if detail['verdict'] == 'OK_MICRO_GAP':
                require(65 <= detail.get('gap_ms', -1) <= 140 and
                        detail.get('cut_db', 0) <= -36 and
                        isinstance(detail.get('preceding_word'), str) and
                        isinstance(detail.get('following_word'), str),
                        'micro-gap acoustic evidence is incomplete')
        result = entry.get('result')
        require(isinstance(result, list) and len(result) == 2 and
                all(type(v) in (int, float) and math.isfinite(v) for v in result),
                'invalid speech-map result')
        require(all(abs(v-t) <= .000501 for v, t in zip(result, span)),
                'acoustic evidence describes different boundaries')
    return {'schema': 'edit.assembly-reconciliation/v1', 'status': 'WORDS_RECONCILED',
            'plan_sha256': fingerprint(plan), 'source_sha256': plan['source_sha256'],
            'resolved_sha256': fingerprint(resolved), 'words': final_words,
            'spans': spans, 'design': spec, 'design_receipt': receipt, 'duration': clock,
            'performance': compiled['performance'],
            'scope': 'Word membership only; acoustic, semantic, native and human review pending.'}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('command', choices=['compile', 'reconcile'])
    ap.add_argument('--plan', type=Path, required=True)
    ap.add_argument('--job', type=Path, required=True,
                    help='Pinned edit.assembly-job/v1 authorization; no implicit legacy bypass')
    ap.add_argument('--resolved', type=Path)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    if args.out.exists():
        ap.error('output exists; use a new revision path')
    try:
        from assembly_job import authorize_plan
        authorize_plan(args.job, args.plan)
        plan = json.loads(args.plan.read_text())
        if args.command == 'reconcile':
            require(args.resolved is not None, '--resolved required')
            result = reconcile(plan, json.loads(args.resolved.read_text()))
        else:
            result = compile_assembly(plan)
    except (ValueError, KeyError, TypeError, OSError, ZeroDivisionError,
            subprocess.SubprocessError) as exc:
        print(json.dumps({'status': 'BLOCK', 'error': str(exc)})); return 2
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('x') as f:
        json.dump(result, f, indent=2); f.write('\n')
    print(json.dumps(result.get('receipt', {k: result[k] for k in ('status', 'scope')
                                           if k in result})))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
