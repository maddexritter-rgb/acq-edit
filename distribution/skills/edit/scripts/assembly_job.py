#!/usr/bin/env python3
"""Versioned assembly authorization and evidence checks; never an editorial judge."""
from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
from fractions import Fraction

SKILLS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SKILLS / 'assembly-design/scripts'))
_DIGEST_CACHE = {}
_PERSIST_MIN_BYTES = 1 << 30
_SAMPLE_BYTES = 1 << 20
_HASH_DB = Path(os.environ.get(
    'ACQ_ASSEMBLY_HASH_CACHE',
    str(Path.home() / 'Library/Caches/ACQAssembly/sha256.sqlite3')))


def require(ok, message):
    if not ok:
        raise ValueError(message)


def _sample_digest(path, size):
    """Cheap guard against a stale large-media cache entry with reused metadata."""
    h = hashlib.sha256()
    with path.open('rb') as f:
        h.update(f.read(min(_SAMPLE_BYTES, size)))
        if size > _SAMPLE_BYTES:
            f.seek(max(_SAMPLE_BYTES, size - _SAMPLE_BYTES))
            h.update(f.read(_SAMPLE_BYTES))
    return h.hexdigest()


def _persistent_digest(path, key, sample, sha=None):
    """Read/write a stat-and-sample-validated full SHA cache for large local media.

    Cache failure is nonfatal; callers still compute the complete SHA. A changed
    size, inode, device, mtime, ctime or sampled edge bytes forces a new full hash.
    """
    try:
        # Filesystems may return unsigned 64-bit inode/device identifiers. Prefixing
        # metadata keeps SQLite's INTEGER affinity from coercing or overflowing them.
        db_key = (key[0], *(f'n:{value}' for value in key[1:]))
        _HASH_DB.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(_HASH_DB, timeout=5)) as db:
            db.execute('CREATE TABLE IF NOT EXISTS digests ('
                       'path TEXT PRIMARY KEY, dev INTEGER, ino INTEGER, size INTEGER, '
                       'mtime_ns INTEGER, ctime_ns INTEGER, sample_sha256 TEXT, sha256 TEXT)')
            if sha is None:
                row = db.execute(
                    'SELECT sha256 FROM digests WHERE path=? AND dev=? AND ino=? '
                    'AND size=? AND mtime_ns=? AND ctime_ns=? AND sample_sha256=?',
                    (*db_key, sample)).fetchone()
                db.commit()
                return row[0] if row else None
            db.execute('INSERT OR REPLACE INTO digests VALUES (?,?,?,?,?,?,?,?)',
                       (*db_key, sample, sha))
            db.commit()
    except (OSError, sqlite3.Error):
        return None
    return sha


def digest(path):
    path = Path(path).resolve()
    stat = path.stat()
    key = (str(path), stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
    if key in _DIGEST_CACHE:
        return _DIGEST_CACHE[key]
    sample = _sample_digest(path, stat.st_size) if stat.st_size >= _PERSIST_MIN_BYTES else None
    if sample is not None:
        cached = _persistent_digest(path, key, sample)
        if cached is not None:
            after = path.stat()
            require((after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
                    == key[1:], 'evidence changed while checking cached hash: ' + str(path))
            _DIGEST_CACHE[key] = cached
            return cached
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    after = path.stat()
    require((after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
            == key[1:], 'evidence changed while hashing: ' + str(path))
    _DIGEST_CACHE[key] = h.hexdigest()
    if sample is not None:
        require(_sample_digest(path, stat.st_size) == sample,
                'evidence edge bytes changed while hashing: ' + str(path))
        _persistent_digest(path, key, sample, _DIGEST_CACHE[key])
    return _DIGEST_CACHE[key]


def pin(path):
    p = Path(path).resolve()
    return {'path': str(p), 'sha256': digest(p)}


def pinned(ref):
    require(isinstance(ref, dict), 'missing evidence pin')
    p = Path(ref['path'])
    require(p.is_absolute() and p.is_file(), 'missing absolute evidence: ' + str(p))
    require(digest(p) == ref['sha256'], 'stale evidence: ' + str(p))
    return p


def load(path):
    value = json.loads(Path(path).read_text())
    require(isinstance(value, dict), 'expected JSON object: ' + str(path))
    return value


def same_pin(a, b):
    return (isinstance(a, dict) and isinstance(b, dict) and
            a.get('sha256') == b.get('sha256') and
            Path(a.get('path', '')).resolve() == Path(b.get('path', '')).resolve())


def indices(ranges, count):
    require(isinstance(ranges, list) and ranges, 'missing word ranges')
    out = []
    for r in ranges:
        require(isinstance(r, list) and len(r) == 2 and
                all(type(i) is int for i in r) and 0 <= r[0] <= r[1] < count,
                'invalid or out-of-source word range')
        out.extend(range(r[0], r[1] + 1))
    return out


def skill_snapshot():
    # Pin the actual executable/instruction surface, not caches or media.
    files = set()
    for name in ('edit', 'assembly-design', 'cut', 'audit-script', 'long-form-ingest'):
        root = SKILLS / name
        for path in root.rglob('*'):
            if path.is_file() and path.suffix in {'.md', '.py', '.json'} and not any(
                    part in {'tests', '__pycache__', '.git', 'node_modules', '.venv'}
                    for part in path.relative_to(root).parts):
                files.add(path.resolve())
    for relative in ('live-clip/scripts/live_review_xml.py',
                     'live-clip/scripts/measured_multicam_xml.py', '_shared/speech_map_cut.py',
                     '_shared/silero_vad.py', '_shared/faded_trim_cut.py'):
        files.add((SKILLS / relative).resolve())
    return [pin(p) for p in sorted(files)]


def approval(ref, previous):
    a = load(pinned(ref))
    require(a.get('schema') == 'edit.human-approval/v1' and
            a.get('decision') == 'APPROVE_NEXT_BATCH', 'human batch approval missing')
    require(a.get('reviewed_job') == previous and bool(a.get('user_message')) and
            bool(a.get('message_id')), 'approval must identify the user message and reviewed job')
    # User-message identity is recorded provenance, not authentication.


def full_batch_authorization(ref, source_ids):
    """Validate an explicit, source-scoped request to process a complete batch.

    The authorization is pinned provenance, not authentication.  A message id is
    retained when the client exposes one, but must never be invented merely to
    satisfy the record.
    """
    a = load(pinned(ref))
    require(a.get('schema') == 'edit.full-batch-authorization/v1' and
            a.get('decision') == 'APPROVE_FULL_BATCH',
            'explicit full-batch authorization missing')
    authorized = a.get('authorized_source_ids')
    require(isinstance(authorized, list) and authorized and
            len(authorized) == len(set(authorized)) and set(authorized) == set(source_ids),
            'full-batch authorization source scope mismatch')
    require(isinstance(a.get('user_message'), str) and a['user_message'].strip(),
            'full-batch authorization must retain the verbatim user request')
    message_id = a.get('message_id')
    require(message_id is None or (isinstance(message_id, str) and message_id.strip()),
            'full-batch authorization message id must be real or omitted')
    return a


def validate_job(path, media_scope=None):
    job = load(path)
    require(job.get('schema') in {'edit.assembly-job/v1', 'edit.assembly-job/v2',
                                  'edit.assembly-job/v3', 'edit.assembly-job/v4'},
            'wrong assembly job schema')
    require(job.get('builder_id') and job.get('job_id'), 'missing job/builder identity')
    skills = job.get('skills', [])
    require(skills, 'skill pins missing')
    actual = {str(pinned(p).resolve()): p['sha256'] for p in skills}
    current = {p['path']: p['sha256'] for p in skill_snapshot()}
    require(actual == current, 'skill surface changed; explicitly adopt a new job revision')
    sources = job.get('sources', [])
    require(sources and len({s['id'] for s in sources}) == len(sources), 'missing/duplicate sources')
    source_ids = {s['id'] for s in sources}
    dialogue_ids = {s['id'] for s in sources if s.get('role', 'dialogue') == 'dialogue'}
    require(dialogue_ids, 'job needs a dialogue source')
    require(media_scope is None or media_scope in source_ids,
            'candidate media scope is not a registered source')
    for s in sources:
        # A full `check` verifies every stable copy. Per-candidate work rechecks the
        # selected media and all small job evidence without rereading every camera.
        if media_scope is None or s['id'] == media_scope:
            pinned(s['media'])
        if s.get('role') == 'picture_only':
            require(job['schema'] == 'edit.assembly-job/v4' and
                    s.get('primary_dialogue_source_id') in dialogue_ids and
                    s.get('relationship') and s.get('audio_not_transcribed_reason') and
                    'transcript' not in s and 'coverage' not in s,
                    'picture-only camera needs primary dialogue source and skip reason')
            continue
        require(s.get('role', 'dialogue') == 'dialogue', 'unknown source role')
        transcript = load(pinned(s['transcript']))
        count = len(transcript['words'])
        require(count > 0 and s.get('participants') and s.get('relationship'),
                'source needs words, participants and camera/session relationship')
        ledger = load(pinned(s['coverage']))
        require(ledger.get('transcript') == s['transcript'], 'coverage/transcript mismatch')
        covered = set(indices(ledger.get('read_ranges'), count))
        require(covered == set(range(count)), 'incomplete transcript coverage: ' + s['id'])
        rows = ledger.get('interactions', [])
        require(rows, 'interaction inventory missing')
        accounted = set()
        for row in rows:
            accounted.update(indices([row['words']], count))
            require(row.get('disposition') in {'candidate', 'excluded', 'deferred', 'non_content'}
                    and row.get('reason') and row.get('speakers') and row.get('kind'),
                    'interaction lacks classification, speakers or disposition reason')
        require(accounted == set(range(count)), 'interaction inventory has gaps')
        require(isinstance(s.get('coverage_gaps'), list), 'record media/transcript coverage gaps')
        for gap in s['coverage_gaps']:
            require(gap.get('disposition') and gap.get('evidence'), 'unreviewed media tail/gap')
            pinned(gap['evidence'])
    batch = job['batch']
    allowed_batch_kinds = ({'calibration', 'continuation', 'full'}
                           if job['schema'] == 'edit.assembly-job/v4'
                           else {'calibration', 'continuation'})
    require(batch.get('kind') in allowed_batch_kinds, 'invalid batch kind')
    candidates = job.get('candidates', {})
    calibration_limit = 3 if job['schema'] == 'edit.assembly-job/v3' else 6
    if job['schema'] == 'edit.assembly-job/v4' and batch['kind'] == 'full':
        require(candidates, 'full batch requires at least one authorized candidate')
        full_batch_authorization(batch.get('authorization'), source_ids)
    elif job['schema'] in {'edit.assembly-job/v3', 'edit.assembly-job/v4'} and batch['kind'] == 'calibration':
        require(len(candidates) == 3, 'v3 calibration requires exactly three candidates')
    else:
        require(candidates and len(candidates) <= (
                calibration_limit if batch['kind'] == 'calibration' else 5),
                'batch exceeds authorization limit')
    groups = {}
    for cid, c in candidates.items():
        require(c.get('source_id') in dialogue_ids and c.get('design_group'),
                'candidate dialogue source/group missing')
        groups[c['design_group']] = groups.get(c['design_group'], 0) + 1
        require(c.get('kind') in {'scripted_monologue', 'monologue', 'qa', 'l1_diagnosis',
                                 'conversation_story'}, 'missing moment classification')
        require(c.get('question_policy') in {'retain', 'self_contained', 'not_applicable'},
                'question policy missing')
        require(c.get('question_reason'), 'question policy needs source-specific reason')
        failures = 0
        for revision in c.get('failed_revisions', []):
            rejected = load(pinned(revision))
            require(rejected.get('verdict') in {'REVISE', 'UNKNOWN'}, 'invalid failed review history')
            failures += 1
        # v1-v3 retain the historical two-cycle hold.  V4 uses targeted repair and a
        # single post-cut final review; rejected drafts remain evidence but do not
        # mechanically condemn a candidate that can still be repaired or shown to the
        # editor as playable REVIEW material.
        if job['schema'] != 'edit.assembly-job/v4':
            require(failures <= 2, 'candidate exceeded two unsuccessful revision cycles: ' + cid)
    require(max(groups.values()) <= 5, 'design pass exceeds five candidates')
    if batch['kind'] == 'continuation':
        previous = batch['previous_job']
        pinned(previous)
        approval(batch['human_approval'], previous)
    return job


def authorize_plan(job_path, plan_path):
    from design_quality_gate import evaluate_clip
    plan = load(plan_path)
    cid = plan['clip_id']
    candidate = load(job_path).get('candidates', {}).get(cid)
    require(candidate is not None, 'candidate is not authorized: ' + cid)
    job = validate_job(job_path, media_scope=candidate['source_id'])
    require(cid in job['candidates'], 'candidate is not authorized: ' + cid)
    c = job['candidates'][cid]
    require(pinned(c['plan']).resolve() == Path(plan_path).resolve(), 'wrong plan revision')
    source = next(s for s in job['sources'] if s['id'] == c['source_id'])
    # Corrected candidate transcripts may differ from full discovery transcripts. Their
    # audio/raw provenance is checked by compile_assembly; source membership is explicit.
    require(same_pin(c['source_words'], {'path': plan['source_words'], 'sha256': plan['source_sha256']}),
            'candidate word-source mismatch')
    pinned(c['source_words'])
    require(c.get('source_mapping'), 'missing discovery-to-candidate clock/word mapping')
    mapping = load(pinned(c['source_mapping']))
    require(mapping.get('schema') == 'edit.source-mapping/v1' and
            mapping.get('source_id') == source['id'] and
            mapping.get('discovery_transcript') == source['transcript'] and
            mapping.get('candidate_words') == c['source_words'] and
            mapping.get('media') == source['media'], 'source mapping identity mismatch')
    verification = load(pinned(plan['verification']))
    require(same_pin(mapping.get('reference_audio'), {'path': verification['audio_path'],
            'sha256': verification['audio_sha256']}), 'reference audio is not mapped to media')
    require(mapping.get('clock_basis') in {'identical', 'measured'}, 'unknown source clock')
    if mapping['clock_basis'] == 'measured':
        pinned(mapping['sync_evidence'])
    elif mapping['reference_audio'] != mapping['media']:
        # Even an extracted audio file needs evidence of identical start/rate.
        pinned(mapping['sync_evidence'])
    if c['kind'] == 'l1_diagnosis':
        require('l1_diagnosis' in plan['profiles'], 'diagnosis silently downgraded')
    if job['schema'] == 'edit.assembly-job/v2':
        validate_candidate_performance(plan, c, mapping, verification)
    if job['schema'] in {'edit.assembly-job/v3', 'edit.assembly-job/v4'}:
        worksheet = Path(plan_path).parent / 'editorial_worksheet.json'
        require(c.get('editorial_worksheet') and
                pinned(c['editorial_worksheet']).resolve() == worksheet.resolve(),
                'v3 candidate must pin current editorial worksheet')
    if c['question_policy'] == 'retain':
        words = load(plan['source_words'])['words']
        selected = set(indices([s['words'] for s in plan['segments']], len(words)))
        require(set(indices(c.get('question_words'), len(words))) <= selected,
                'required question/condition removed')
    result = evaluate_clip(Path(plan_path).parent)
    require(result['status'] == 'PASS', 'design evidence invalid: ' + '; '.join(result['errors']))
    return job, c, plan, source


def validate_candidate_performance(plan, candidate, mapping, verification):
    """Bind post-design acoustic inspection to the exact source and selections.

    This validates evidence identity and decision coverage, not whether an editor
    made a good pacing choice or actually heard the audio.
    """
    evidence = load(pinned(plan.get('performance_evidence')))
    require(evidence.get('schema') == 'cut.candidate-performance/v2' and
            evidence.get('status') == 'MEASURED',
            'candidate performance map is old or incomplete; regenerate it with assembly-design')
    require(same_pin(evidence.get('source_words'), candidate['source_words']) and
            same_pin(evidence.get('reference_audio'), mapping['reference_audio']) and
            same_pin(evidence.get('reference_audio'), {
                'path': verification['audio_path'], 'sha256': verification['audio_sha256']}),
            'candidate performance source/audio mismatch')
    require(evidence.get('interaction_words') == plan['interaction_words'],
            'candidate performance map does not cover complete interaction')
    offset = evidence.get('audio_clock_offset_s', 0)
    require(type(offset) in {int, float} and offset >= 0,
            'invalid candidate performance audio offset')
    if offset:
        require(same_pin(evidence.get('clock_evidence'), mapping.get('sync_evidence')),
                'candidate performance clock evidence differs from source mapping')
    rows = load(pinned(candidate['source_words']))['words']
    first, last = plan['interaction_words']
    observed = evidence.get('words', [])
    require(len(observed) == last - first + 1 and
            all(row.get('index') == i and row.get('word') == rows[i]['word'] and
                row.get('start') == rows[i]['start'] and row.get('end') == rows[i]['end']
                for i, row in enumerate(observed, first)),
            'candidate performance words differ from current source')
    selected = set(indices([segment['words'] for segment in plan['segments']], len(rows)))
    same_segment = set()
    segment_for_index = {}
    for segment_number, segment in enumerate(plan['segments']):
        same_segment.update(range(segment['words'][0], segment['words'][1]))
        segment_for_index.update({i: segment_number for i in range(segment['words'][0], segment['words'][1] + 1)})
    relevant = {}
    for event in evidence.get('events', []):
        eid = event.get('id')
        require(isinstance(eid, str) and eid not in relevant,
                'duplicate or missing candidate performance event id')
        kind = event.get('kind')
        if kind == 'gap':
            left, right = event.get('after_word'), event.get('before_word')
            require(type(left) is int and type(right) is int and first <= left < right <= last,
                    'invalid performance gap word indices')
            if left in selected and right in selected:
                relevant[eid] = 'keep' if left in same_segment and right == left + 1 else 'remove'
        elif kind in {'stretched_word', 'filler_word'}:
            index = event.get('word_index')
            require(type(index) is int and first <= index <= last,
                    'invalid performance event word index')
            if index in selected:
                relevant[eid] = 'keep'
        elif kind == 'vad_word_conflict':
            word_indices = event.get('word_indices')
            require(isinstance(word_indices, list) and word_indices and
                    all(type(i) is int and first <= i <= last for i in word_indices),
                    'invalid VAD/word conflict indices')
            touched = [i for i in word_indices if i in selected]
            if touched:
                # If selected words straddle an editorial omission the nonspeech
                # is removed there; inside one kept segment it remains for review.
                relevant[eid] = ('keep' if len({segment_for_index[i] for i in touched}) == 1
                                 else 'remove')
        else:
            raise ValueError('unknown candidate performance event kind')
    decisions = plan.get('performance_decisions')
    require(isinstance(decisions, list), 'performance decisions missing')
    actual = {}
    for decision in decisions:
        eid = decision.get('event_id')
        require(eid in relevant and eid not in actual and
                decision.get('action') == relevant[eid] and
                isinstance(decision.get('why'), str) and len(decision['why'].strip()) >= 12,
                'unsupported or unexplained performance decision: ' + str(eid))
        actual[eid] = decision['action']
    require(set(actual) == set(relevant), 'selected performance events were not considered')
    return evidence


def verified_compile(job_path, clip_id):
    from assembly_plan import compile_assembly
    candidate = load(job_path).get('candidates', {}).get(clip_id)
    require(candidate is not None, 'candidate is not authorized: ' + clip_id)
    job = validate_job(job_path, media_scope=candidate['source_id'])
    c = job['candidates'][clip_id]
    require(load(pinned(c['plan'])).get('clip_id') == clip_id,
            'requested candidate does not match plan clip_id')
    _, _, plan, _ = authorize_plan(job_path, pinned(c['plan']))
    compiled = load(pinned(c['compiled']))
    require(compiled == compile_assembly(plan), 'compiled artifact does not belong to current plan')
    return job, c, plan, compiled


COLD = {'content_unit', 'hook', 'retain', 'reward', 'goodwill', 'value_compression', 'audience_growth'}
FIDELITY = {'context', 'question', 'qualifications', 'causality', 'omitted_value'}


def review_packet(job_path, clip_id, perspective):
    job, c, plan, compiled = verified_compile(job_path, clip_id)
    allowed = ({'final_editorial'} if job['schema'] == 'edit.assembly-job/v4'
               else {'cold_viewer', 'source_fidelity'})
    require(perspective in allowed, 'invalid review perspective')
    packet = {'schema': 'edit.editorial-packet/v1', 'clip_id': clip_id,
              'perspective': perspective, 'reviewed_plan': c['plan'],
              'reviewed_compiled': c['compiled'], 'source_sha256': plan['source_sha256'],
              'selected_dialogue': compiled['assembled_dialogue'],
              'selected_word_ranges': [s['words'] for s in plan['segments']],
              'rubric': str(SKILLS / 'audit-script/references/content_unit_review.md')}
    if perspective in {'source_fidelity', 'final_editorial'}:
        words = load(plan['source_words'])['words']
        a, b = plan['interaction_words']
        packet.update(source_dialogue=[{'source_word_index': i, **words[i]} for i in range(a, b+1)],
                      interaction_words=[a, b], moment_kind=c['kind'],
                      question_policy=c['question_policy'], question_words=c.get('question_words', []))
    if perspective == 'final_editorial':
        # Review the version that can actually be cut, not an earlier textual draft.
        resolved = load(pinned(c['resolved']))
        reconciled = load(pinned(c['reconciled']))
        packet.update(resolved=c['resolved'], reconciled=c['reconciled'],
                      source_spans=resolved['spans'], reconciled_words=reconciled)
    return packet


def validate_review(job_path, clip_id, perspective, review_ref):
    job, c, plan, compiled = verified_compile(job_path, clip_id)
    review = load(pinned(review_ref))
    packet = review_packet(job_path, clip_id, perspective)
    require(load(pinned(review['packet'])) == packet, 'review packet is stale or altered')
    require(review.get('schema') == 'edit.editorial-review/v1' and
            review.get('clip_id') == clip_id and review.get('perspective') == perspective,
            'review identity mismatch')
    require(review.get('agent_id') and review['agent_id'] != job['builder_id'],
            'reviewer must be independent of builder')
    invocation = load(pinned(review['invocation']))
    require(invocation.get('agent_id') == review['agent_id'] and invocation.get('tool_call_id')
            and invocation.get('packet') == review['packet'], 'review invocation provenance missing')
    require(invocation.get('fresh_context') is True, 'review did not run in fresh context')
    require(review.get('verdict') == 'PASS', 'independent review did not pass')
    checks = review.get('checks', {})
    expected = COLD | FIDELITY if perspective == 'final_editorial' else (
        COLD if perspective == 'cold_viewer' else FIDELITY)
    require(set(checks) == expected,
            'review criteria incomplete')
    words = load(plan['source_words'])['words']
    selected = set(compiled['intended_indices'])
    interaction = set(indices([plan['interaction_words']], len(words)))
    for label, check in checks.items():
        ids = indices(check.get('word_ranges'), len(words))
        permitted = selected if label in COLD else interaction
        require(set(ids) <= permitted, 'review evidence outside reviewed dialogue: ' + label)
        exact = ' '.join(words[i]['word'] for i in ids)
        require(check.get('quote') == exact, 'review quote is not exact source evidence: ' + label)
        require(check.get('verdict') == 'PASS' and check.get('reason'), 'criterion did not pass: ' + label)
    require(isinstance(review.get('fixes'), list), 'missing review fixes list')
    require(all(isinstance(f, dict) and type(f.get('required')) is bool for f in review['fixes']),
            'invalid fixes')
    require(not any(f['required'] for f in review['fixes']), 'required editorial fixes unresolved')
    return review


def native_packet(job_path, clip_id):
    from assembly_plan import reconcile
    job, c, plan, compiled = verified_compile(job_path, clip_id)
    if job['schema'] in {'edit.assembly-job/v3', 'edit.assembly-job/v4'}:
        source = next(s for s in job['sources'] if s['id'] == c['source_id'])
        mapping = load(pinned(c['source_mapping']))
        verification = load(pinned(plan['verification']))
        validate_candidate_performance(plan, c, mapping, verification)
    resolved = load(pinned(c['resolved']))
    reconciled = load(pinned(c['reconciled']))
    require(reconciled == reconcile(plan, resolved), 'stale retained-word reconciliation')
    if job['schema'] == 'edit.assembly-job/v4':
        validate_review(job_path, clip_id, 'final_editorial', c['reviews']['final_editorial'])
    else:
        reviewers = []
        executions = []
        for perspective in ('cold_viewer', 'source_fidelity'):
            r = validate_review(job_path, clip_id, perspective, c['reviews'][perspective])
            reviewers.append(r['agent_id'])
            executions.append(load(pinned(r['invocation']))['tool_call_id'])
        require(len(set(reviewers)) == 2, 'review perspectives need separate fresh executions')
        require(len(set(executions)) == 2, 'review perspectives reused one execution')
    return {'schema': 'edit.native-build-packet/v1', 'clip_id': clip_id,
            'job': pin(job_path), 'plan': c['plan'], 'compiled': c['compiled'],
            'resolved': c['resolved'], 'reconciled': c['reconciled'], 'reviews': c['reviews'],
            'source_id': c['source_id'], 'source_mapping': c['source_mapping'],
            'source_spans': resolved['spans'], 'fps': resolved['fps'],
            'statuses': {'structure': 'VALID', 'editorial': 'REVIEWED_PASS',
                         'words': 'RECONCILED', 'acoustic': 'BOUNDARIES_CHECKED',
                         'native': 'PENDING', 'human': 'PENDING'},
            'scope': 'Build input only; actual audio, native readback and human acceptance remain required.'}


PROVISIONAL_ISSUES = {'HUMAN_LISTEN', 'LEXICAL_RECONCILIATION',
                      'ACOUSTIC_EDGE', 'PICTURE_SYNC', 'FINAL_EDITORIAL'}


def authorize_provisional_plan(job_path, clip_id):
    from design_quality_gate import evaluate_clip
    candidate = load(job_path).get('candidates', {}).get(clip_id)
    require(candidate is not None, 'candidate is not authorized: ' + clip_id)
    job = validate_job(job_path, media_scope=candidate['source_id'])
    c = job['candidates'][clip_id]
    plan_path = pinned(c['plan'])
    plan = load(plan_path)
    require(plan.get('clip_id') == clip_id and
            same_pin(c['source_words'], {'path': plan['source_words'],
                                         'sha256': plan['source_sha256']}),
            'provisional plan source identity mismatch')
    require(c.get('editorial_worksheet') and
            pinned(c['editorial_worksheet']).parent == plan_path.parent,
            'provisional worksheet missing or outside plan revision')
    design = evaluate_clip(plan_path.parent)
    require(design['status'] == 'PASS',
            'provisional design evidence invalid: ' + '; '.join(design['errors']))
    source = next(s for s in job['sources'] if s['id'] == c['source_id'])
    mapping = load(pinned(c['source_mapping']))
    require(mapping.get('schema') == 'edit.source-mapping/v1' and
            mapping.get('source_id') == source['id'] and
            mapping.get('discovery_transcript') == source['transcript'] and
            mapping.get('candidate_words') == c['source_words'] and
            mapping.get('media') == source['media'] and
            mapping.get('clock_basis') == 'identical',
            'provisional source mapping mismatch')
    return job, c, plan, source, mapping


def provisional_native_packet(job_path, clip_id, cut_path):
    """Guard a playable review edit without laundering it into an approved cut."""
    job, c, plan, source, mapping = authorize_provisional_plan(job_path, clip_id)
    require(job['schema'] == 'edit.assembly-job/v4', 'provisional build requires v4 job')
    require(mapping['clock_basis'] == 'identical' and
            same_pin(mapping['media'], source['media']),
            'provisional identity-clock build needs the selected primary media')
    cut_ref = pin(cut_path)
    cut = load(cut_path)
    require(cut.get('schema') == 'edit.provisional-cut/v2' and
            cut.get('clip_id') == clip_id and
            same_pin(cut.get('media'), source['media']) and
            same_pin(cut.get('source_words'), c['source_words']),
            'provisional cut source identity mismatch')
    fps = cut.get('fps')
    try:
        rate = Fraction(fps)
    except (TypeError, ValueError, ZeroDivisionError):
        raise ValueError('invalid provisional frame rate') from None
    require(rate > 0 and fps == cut.get('fps'), 'invalid provisional frame rate')
    frames = cut.get('source_frames')
    require(isinstance(frames, list) and frames and all(
        isinstance(span, list) and len(span) == 2 and
        all(type(v) is int for v in span) and 0 <= span[0] < span[1]
        for span in frames), 'invalid provisional source frames')
    words = load(pinned(c['source_words']))['words']
    selected = indices(cut.get('word_ranges'), len(words))
    interaction = set(indices([plan['interaction_words']], len(words)))
    require(set(selected) <= interaction and len(selected) == len(set(selected)),
            'provisional words outside the complete interaction or repeated')
    if c['question_policy'] == 'retain':
        require(set(indices(c.get('question_words'), len(words))) <= set(selected),
                'provisional Q&A removed its required question')
    # A generous quarter-second tolerance admits imperfect ASR boxes, not unrelated speech.
    tolerance = float(rate) * .25
    require(all(any(a - tolerance <= float(words[i]['start']) * float(rate) <= b + tolerance
                    for a, b in frames) for i in selected),
            'provisional selected words are not covered by source frames')
    arc = cut.get('arc')
    require(isinstance(arc, dict) and set(arc) == {'hook', 'reasoning', 'payoff'},
            'provisional arc needs hook, reasoning and payoff source ranges')
    positions = []
    for beat in ('hook', 'reasoning', 'payoff'):
        beat_ids = indices(arc[beat], len(words))
        require(set(beat_ids) <= set(selected), 'provisional arc cites omitted words: ' + beat)
        positions.append(selected.index(beat_ids[0]))
    require(positions == sorted(positions), 'provisional arc is out of playback order')
    issues = cut.get('issues')
    require(isinstance(issues, list) and issues and all(
        isinstance(item, dict) and item.get('code') in PROVISIONAL_ISSUES and
        isinstance(item.get('why'), str) and item['why'].strip()
        for item in issues), 'provisional review needs explicit unresolved issues')
    edge_risks = []
    for n, (start, end) in enumerate(frames):
        for edge, frame in (('start', start), ('end', end)):
            seconds = frame / float(rate)
            for i in sorted(interaction):
                word = words[i]
                if float(word['start']) + .1 < seconds < float(word['end']) - .1:
                    edge_risks.append({'span': n, 'edge': edge, 'frame': frame,
                                       'word_index': i, 'word': word['word']})
    if edge_risks:
        require(any(item['code'] == 'ACOUSTIC_EDGE' for item in issues),
                'word-box edge risk needs explicit ACOUSTIC_EDGE review issue')
    note = cut.get('review_note')
    require(isinstance(note, str) and note.strip(), 'provisional marker note missing')
    return {'schema': 'edit.provisional-native-packet/v1', 'clip_id': clip_id,
            'job': pin(job_path), 'cut': cut_ref, 'plan': c['plan'],
            'media': source['media'], 'source_words': c['source_words'],
            'source_frames': frames, 'word_ranges': cut['word_ranges'],
            'spoken_text': ' '.join(words[i]['word'] for i in selected),
            'arc': arc, 'issues': issues, 'edge_risks': edge_risks,
            'review_note': note, 'fps': fps,
            'statuses': {'structure': 'DESIGN_SELF_CHECK', 'editorial': 'PENDING',
                         'words': 'PROVISIONAL', 'acoustic': 'HUMAN_LISTEN',
                         'native': 'PENDING', 'human': 'PENDING'},
            'scope': 'Review-only editable media; cannot enter clean approval.'}


def validate_provisional_packet(path):
    packet = load(path)
    require(packet.get('schema') == 'edit.provisional-native-packet/v1',
            'invalid provisional native packet')
    current = provisional_native_packet(pinned(packet['job']), packet['clip_id'],
                                        pinned(packet['cut']))
    require(packet == current, 'provisional native packet changed or stale')
    return packet


def validate_native_packet(path):
    packet = load(path)
    require(packet.get('schema') == 'edit.native-build-packet/v1', 'invalid native packet')
    job_path = pinned(packet['job'])
    require(packet == native_packet(job_path, packet['clip_id']), 'native packet changed or stale')
    return packet


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('command', choices=['snapshot-skills', 'check', 'review-packet',
                                      'prepare-native', 'prepare-provisional-native',
                                      'check-native'])
    ap.add_argument('--job', type=Path)
    ap.add_argument('--clip-id')
    ap.add_argument('--perspective', choices=['cold_viewer', 'source_fidelity', 'final_editorial'])
    ap.add_argument('--packet', type=Path)
    ap.add_argument('--cut', type=Path)
    ap.add_argument('--out', type=Path)
    args = ap.parse_args()
    try:
        if args.command == 'snapshot-skills':
            result = {'skills': skill_snapshot()}
        elif args.command == 'check-native':
            require(args.packet is not None, '--packet required')
            schema = load(args.packet).get('schema')
            result = (validate_provisional_packet(args.packet)
                      if schema == 'edit.provisional-native-packet/v1'
                      else validate_native_packet(args.packet))
        else:
            require(args.job is not None, '--job required')
            if args.command == 'check':
                validate_job(args.job)
                result = {'status': 'JOB_VALID', 'scope': 'Recorded coverage and authorization only.'}
            else:
                require(args.clip_id is not None, '--clip-id required')
                if args.command == 'review-packet':
                    result = review_packet(args.job, args.clip_id, args.perspective)
                elif args.command == 'prepare-provisional-native':
                    require(args.cut is not None, '--cut required')
                    result = provisional_native_packet(args.job, args.clip_id, args.cut)
                else:
                    result = native_packet(args.job, args.clip_id)
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            with args.out.open('x') as f:
                json.dump(result, f, indent=2); f.write('\n')
        else:
            print(json.dumps(result, indent=2))
        return 0
    except (ValueError, KeyError, TypeError, OSError) as e:
        print(json.dumps({'status': 'BLOCK', 'error': str(e)}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
