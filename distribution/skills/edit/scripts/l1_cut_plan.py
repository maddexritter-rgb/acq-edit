#!/usr/bin/env python3
"""Compile a source-indexed L1 editorial plan. No media edits or acoustic PASS."""
import argparse
import hashlib
import json
import math
import re
from pathlib import Path
from design_evidence import evaluate

ROLES = {'context', 'reasoning', 'example', 'reward'}
REMOVALS = {'off_arc', 'redundant', 'setup_detail', 'restart', 'filler',
            'conversational_tail', 'replaced_by_clearer_statement'}
PROMISE_KINDS = {'consultation', 'sub_answer', 'standalone_story', 'human_exchange'}
BRANCH_RELATIONSHIPS = {'selected_promise', 'separate_promise', 'qualifies_selected',
                        'reverses_selected'}
BRANCH_DISPOSITIONS = {'kept', 'partial', 'removed'}
SCOPE_ACTIONS = {'not_needed', 'claim_narrowed', 'qualification_retained_elsewhere',
                 'blocked'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def lexical_tokens(value):
    return re.findall(r"[A-Za-z0-9]+(?:'[A-Za-z0-9]+)?", str(value).lower())


def interval(value, lo, hi):
    require(isinstance(value, list) and len(value) == 2 and
            all(type(x) is int for x in value) and lo <= value[0] <= value[1] <= hi,
            'invalid word interval')
    return range(value[0], value[1]+1)


def compile_plan(plan, base):
    require(isinstance(plan, dict) and plan.get('schema') in
            ('edit.l1-cut-plan/v1', 'edit.l1-cut-plan/v2', 'edit.l1-cut-plan/v3',
             'edit.l1-cut-plan/v4', 'edit.l1-cut-plan/v5', 'edit.l1-cut-plan/v6'),
            'invalid plan schema')
    schema = plan['schema']
    for key in ('clip_id', 'intent', 'viewer', 'cleanup_review'):
        require(nonempty(plan.get(key)), 'missing '+key)
    require(nonempty(plan.get('source_words')), 'missing source_words')
    source = Path(plan['source_words']).expanduser()
    if not source.is_absolute():
        source = base/source
    source = source.resolve()
    raw = source.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    require(plan.get('source_sha256') == digest, 'source transcript changed')
    words = json.loads(raw)['words']
    require(isinstance(words, list) and bool(words), 'empty source transcript')
    for w in words:
        require(isinstance(w, dict) and nonempty(w.get('word')), 'invalid source word')
        require(all(type(w.get(k)) in (int, float) and math.isfinite(w[k]) for k in ('start','end'))
                and 0 <= w['start'] <= w['end'], 'invalid source word times')
    bounds = plan.get('interaction_words')
    interval(bounds, 0, len(words)-1)
    lo, hi = bounds
    semantic_review = None
    if schema in ('edit.l1-cut-plan/v2', 'edit.l1-cut-plan/v3', 'edit.l1-cut-plan/v4',
                  'edit.l1-cut-plan/v5', 'edit.l1-cut-plan/v6'):
        coverage = plan.get('source_coverage')
        require(isinstance(coverage, dict) and coverage.get('handoff_checked') is True and
                all(nonempty(coverage.get(k)) for k in ('interaction_start_basis',
                                                        'interaction_end_basis')),
                'v2 source_coverage must document full interaction bounds and checked handoff')
        promise = plan.get('promise')
        require(isinstance(promise, dict) and promise.get('kind') in PROMISE_KINDS and
                all(nonempty(promise.get(k)) for k in ('question', 'payoff')),
                'v2 promise needs kind, question and payoff')
        if schema == 'edit.l1-cut-plan/v6':
            require(nonempty(promise.get('scope_boundary')),
                    'v6 promise needs a scope boundary')
            ranking = plan.get('promise_ranking')
            require(isinstance(ranking, list) and bool(ranking),
                    'v6 needs promise_ranking')
            for rank, candidate in enumerate(ranking, 1):
                require(isinstance(candidate, dict) and candidate.get('rank') == rank and
                        candidate.get('disposition') in ('selected', 'not_selected') and
                        all(nonempty(candidate.get(k)) for k in ('promise', 'why')),
                        'v6 promise_ranking entries must be ordered and explained')
            require(sum(x['disposition'] == 'selected' for x in ranking) == 1,
                    'v6 promise_ranking needs exactly one selected promise')
            format_review = plan.get('format_review')
            require(isinstance(format_review, dict) and
                    all(nonempty(format_review.get(k)) for k in
                        ('owner_specific_value', 'host_only_alternative', 'selection_basis')),
                    'v6 format_review must compare owner value with a host-only alternative')
        opening = plan.get('opening_review')
        require(isinstance(opening, dict) and all(nonempty(opening.get(k)) for k in
                ('identity', 'tension', 'uncertainty_or_condition')),
                'v2 opening_review needs identity, tension and uncertainty_or_condition')
        ending = plan.get('ending_review')
        require(isinstance(ending, dict) and all(nonempty(ending.get(k)) for k in
                ('completion', 'raw_continuation', 'moved_reaction_or_thanks')),
                'v2 ending_review needs completion, raw_continuation and moved_reaction_or_thanks')
        semantic_review = {'source_coverage': coverage, 'promise': promise,
                           'opening_review': opening, 'ending_review': ending}
        if schema == 'edit.l1-cut-plan/v6':
            semantic_review['promise_ranking'] = ranking
            semantic_review['format_review'] = format_review
    segments = plan.get('segments')
    require(isinstance(segments, list) and bool(segments), 'empty segments')
    removals = plan.get('removals')
    require(isinstance(removals, list), 'removals must be a list')
    assignments = {}
    spans, selected, moves, guide, boundary_reviews = [], [], [], [], []
    previous = None
    for n, segment in enumerate(segments):
        require(isinstance(segment, dict) and segment.get('role') in ROLES and nonempty(segment.get('why')),
                'segment needs role and reason')
        ids = list(interval(segment.get('words'), lo, hi))
        for i in ids:
            require(i not in assignments, 'word selected more than once')
            assignments[i] = 'keep'
        if previous is not None and ids[0] < previous:
            move = segment.get('reorder')
            require(isinstance(move, dict) and all(nonempty(move.get(k)) for k in
                    ('why', 'original_relationship', 'edited_relationship')), 'backward move needs relationship review')
            moves.append({'segment': n, **move})
        if schema in ('edit.l1-cut-plan/v5', 'edit.l1-cut-plan/v6'):
            joins_from_gap = previous is None or ids[0] != previous + 1
            source_starts_mid_sentence = ids[0] > lo and not str(words[ids[0]-1]['word']).rstrip().endswith(('.', '!', '?'))
            review = segment.get('start_boundary_review')
            if joins_from_gap and source_starts_mid_sentence:
                require(isinstance(review, dict) and all(nonempty(review.get(k)) for k in
                        ('original_phrase', 'edited_phrase', 'why_complete')),
                        'v5 mid-sentence segment start needs boundary review')
            if review is not None:
                require(isinstance(review, dict) and all(nonempty(review.get(k)) for k in
                        ('original_phrase', 'edited_phrase', 'why_complete')),
                        'v5 start boundary review is incomplete')
                edited_tokens = lexical_tokens(review['edited_phrase'])
                selected_tokens = lexical_tokens(words[ids[0]]['word'])
                require(edited_tokens and selected_tokens and
                        edited_tokens[0] == selected_tokens[0],
                        'v5 start boundary edited phrase disagrees with selected words')
                boundary_reviews.append({'segment': n, 'edge': 'start', **review})
            source_ends_mid_sentence = ids[-1] < hi and not str(words[ids[-1]]['word']).rstrip().endswith(('.', '!', '?'))
            review = segment.get('end_boundary_review')
            if source_ends_mid_sentence:
                require(isinstance(review, dict) and all(nonempty(review.get(k)) for k in
                        ('original_phrase', 'edited_phrase', 'why_complete')),
                        'v5 mid-sentence segment end needs boundary review')
            if review is not None:
                require(isinstance(review, dict) and all(nonempty(review.get(k)) for k in
                        ('original_phrase', 'edited_phrase', 'why_complete')),
                        'v5 end boundary review is incomplete')
                edited_tokens = lexical_tokens(review['edited_phrase'])
                selected_tokens = lexical_tokens(words[ids[-1]]['word'])
                require(edited_tokens and selected_tokens and
                        edited_tokens[-1] == selected_tokens[-1],
                        'v5 end boundary edited phrase disagrees with selected words')
                boundary_reviews.append({'segment': n, 'edge': 'end', **review})
        previous = ids[-1]
        a = min(words[i]['start'] for i in ids)
        b = max(words[i]['end'] for i in ids)
        require(a < b, 'selected segment has no duration')
        spans.append([a,b]); selected.extend(ids)
        guide.append({'words':segment['words'], 'role':segment['role'], 'why':segment['why'],
                      'rough_source_seconds':[a,b], 'text':' '.join(words[i]['word'] for i in ids),
                      'speakers':[words[i].get('spk',words[i].get('speaker')) for i in ids]})
    for removal in removals:
        require(isinstance(removal, dict) and removal.get('reason') in REMOVALS and nonempty(removal.get('why')),
                'removal needs category and explanation')
        for i in interval(removal.get('words'), lo, hi):
            require(i not in assignments, 'keep/remove ranges overlap')
            assignments[i] = 'remove'
    require(len(assignments) == hi-lo+1, 'interaction has unaccounted words')
    if schema in ('edit.l1-cut-plan/v3', 'edit.l1-cut-plan/v4', 'edit.l1-cut-plan/v5',
                  'edit.l1-cut-plan/v6'):
        evidence = plan.get('semantic_evidence')
        required_evidence = ('promise_question', 'promise_payoff', 'opening_identity',
                             'opening_tension', 'opening_condition', 'ending_completion')
        require(isinstance(evidence, dict) and all(k in evidence for k in required_evidence),
                'v3 semantic_evidence needs retained support for promise, opening and ending')
        checked = {}
        for key in required_evidence:
            ranges = evidence[key]
            require(isinstance(ranges, list) and bool(ranges),
                    'v3 semantic evidence must contain at least one range: '+key)
            checked[key] = {'ranges': [], 'text': []}
            for value in ranges:
                ids = list(interval(value, lo, hi))
                require(all(assignments.get(i) == 'keep' for i in ids),
                        'v3 semantic evidence is not retained: '+key)
                checked[key]['ranges'].append(value)
                checked[key]['text'].append(' '.join(words[i]['word'] for i in ids))
        semantic_review['semantic_evidence'] = checked
    if schema in ('edit.l1-cut-plan/v4', 'edit.l1-cut-plan/v5', 'edit.l1-cut-plan/v6'):
        branches = plan.get('branch_review')
        require(isinstance(branches, list) and bool(branches),
                'v4 branch_review must inventory the substantive answer branches')
        checked_branches = []
        selected_branch_count = 0
        for branch in branches:
            require(isinstance(branch, dict) and nonempty(branch.get('label')) and
                    nonempty(branch.get('scope_effect')) and
                    branch.get('relationship') in BRANCH_RELATIONSHIPS and
                    branch.get('disposition') in BRANCH_DISPOSITIONS and
                    branch.get('scope_action') in SCOPE_ACTIONS,
                    'v4 branch needs label, relationship, disposition, scope action and effect')
            require(branch['scope_action'] != 'blocked',
                    'v4 branch review marks the selection blocked')
            source_ranges = branch.get('source_ranges')
            require(isinstance(source_ranges, list) and bool(source_ranges),
                    'v4 branch needs source_ranges')
            source_ids = []
            for value in source_ranges:
                source_ids.extend(interval(value, lo, hi))
            states = {assignments[i] for i in source_ids}
            expected_states = {'keep'} if branch['disposition'] == 'kept' else (
                {'remove'} if branch['disposition'] == 'removed' else {'keep', 'remove'})
            require(states == expected_states,
                    'v4 branch disposition disagrees with keep/remove accounting: '+branch['label'])
            retained = branch.get('retained_evidence', [])
            require(isinstance(retained, list), 'v4 retained_evidence must be a list')
            retained_text = []
            for value in retained:
                ids = list(interval(value, lo, hi))
                require(all(assignments.get(i) == 'keep' for i in ids),
                        'v4 branch retained evidence is not retained: '+branch['label'])
                retained_text.append(' '.join(words[i]['word'] for i in ids))
            if branch['relationship'] == 'selected_promise':
                selected_branch_count += 1
                require(retained, 'v4 selected branch needs retained evidence')
            if branch['relationship'] in ('qualifies_selected', 'reverses_selected') and \
                    branch['disposition'] != 'kept':
                require(branch['scope_action'] in
                        ('claim_narrowed', 'qualification_retained_elsewhere'),
                        'v4 omitted qualification/reversal needs an explicit safe scope action')
                if branch['scope_action'] == 'qualification_retained_elsewhere':
                    require(retained, 'v4 retained qualification needs retained evidence')
            checked_branches.append({**branch, 'retained_evidence_text': retained_text})
        require(selected_branch_count == 1,
                'v4 branch_review needs exactly one selected_promise branch')
        if promise['kind'] == 'consultation':
            require(not any(b['scope_action'] == 'claim_narrowed' for b in branches),
                    'v4 consultation cannot narrow its claim around an omitted branch')
            require(not any(b['relationship'] == 'separate_promise' and
                            b['disposition'] != 'kept' for b in branches),
                    'v4 consultation cannot omit a separate substantive promise')
        semantic_review['branch_review'] = checked_branches
    target = plan.get('target_seconds', 90)
    require(type(target) in (int,float) and math.isfinite(target) and target > 0, 'invalid target_seconds')
    design = {'schema':'edit.design-evidence/v1','clip_id':plan['clip_id'],
              'source_words':str(source),'source_sha256':digest,'intent':plan['intent'],
              'essential':plan.get('essential'),'keep_spans':spans,'cleanup_review':plan['cleanup_review']}
    receipt = evaluate(design)
    require(receipt['status']=='PASS', 'essential source words omitted')
    require(receipt['kept_word_indices']==selected,
            'ASR timing selects different words than the plan; resolve transcript timing before compiling')
    nominal = sum(b-a for a,b in spans)
    warnings = []
    if nominal > target:
        warnings.append('Longer than requested target; review content, do not auto-trim.')
    if schema == 'edit.l1-cut-plan/v1':
        warnings.append('Legacy v1 plan: opening, ending, promise and full-context reviews are not enforced.')
    elif schema == 'edit.l1-cut-plan/v2':
        warnings.append('Legacy v2 plan: semantic review prose is not tied to retained source evidence.')
    elif schema == 'edit.l1-cut-plan/v3':
        warnings.append('Legacy v3 plan: substantive answer branches are not structurally inventoried.')
    elif schema == 'edit.l1-cut-plan/v4':
        warnings.append('Legacy v4 plan: mid-sentence selection boundaries are not structurally reviewed.')
    elif schema == 'edit.l1-cut-plan/v5':
        warnings.append('Legacy v5 plan: promise ranking and L1 Q&A format preservation are not structurally reviewed.')
    result = {'schema':'edit.l1-cut-receipt/v1','status':'STRUCTURE_VALID',
              'clip_id':plan['clip_id'],'source_sha256':digest,
              'plan_schema':schema,
              'plan_sha256':hashlib.sha256(json.dumps(plan,sort_keys=True).encode()).hexdigest(),
              'source_words_accounted':hi-lo+1,'kept_words':len(selected),
              'rough_seconds':nominal,'target_seconds':target,'backward_moves':moves,
              'boundary_reviews':boundary_reviews,
              'warnings':warnings,
              'semantic_review':semantic_review,
              'scope':'Source membership and accounting only; editorial, speaker, acoustic and native checks pending.'}
    return {'receipt':result,'design':design,'selection_guide':guide,
            'assembled_text':' '.join(words[i]['word'] for i in selected), 'design_receipt':receipt}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    args.out.mkdir(parents=True,exist_ok=True)
    try:
        result=compile_plan(json.loads(args.plan.read_text()),args.plan.parent)
    except (ValueError,KeyError,TypeError,OSError) as exc:
        receipt={'schema':'edit.l1-cut-receipt/v1','status':'BLOCK','error':str(exc)}
        (args.out/'l1_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
        print(json.dumps(receipt));return 2
    # Invalidate an older successful receipt before touching its companion artifacts.
    (args.out/'l1_receipt.json').write_text(json.dumps({'schema':'edit.l1-cut-receipt/v1',
        'status':'BLOCK','error':'Compilation artifacts are being written'})+'\n')
    for key,name in [('design','rough_design_evidence.json'),
                     ('selection_guide','selection_guide.json'),('design_receipt','rough_design_receipt.json')]:
        (args.out/name).write_text(json.dumps(result[key],indent=2)+'\n')
    (args.out/'assembled_transcript.txt').write_text(result['assembled_text']+'\n')
    (args.out/'l1_receipt.json').write_text(json.dumps(result['receipt'],indent=2)+'\n')
    print(json.dumps(result['receipt']));return 0


if __name__=='__main__':raise SystemExit(main())
