"""Offline stage handoffs and conservative review ranges for bounded Lab snapshots.

No host connection, journal, editing decisions or persistence/render approval.
Owning stage drivers must verify their own postconditions before writing a handoff.
"""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
import re
from premiere_bridge import BridgeError

STAGES = {'assembly', 'reframe', 'captions', 'music'}


def exact(value):
    if not isinstance(value, str) or not re.fullmatch(r'0|[1-9][0-9]{0,18}', value) or int(value) > 9223372036854775807:
        raise BridgeError('Handoff requires exact nonnegative int64 tick strings')
    return int(value)


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def target(snapshot):
    result = {'project_path': snapshot.get('projectPath'), 'sequence_id': snapshot.get('sequenceId')}
    if not isinstance(result['project_path'], str) or not Path(result['project_path']).is_absolute() or not isinstance(result['sequence_id'], str) or not result['sequence_id']:
        raise BridgeError('Handoff needs exact project and sequence identity')
    return result


def inventory(snapshot):
    tracks, items = {}, {}
    for track in snapshot['tracks']:
        kind, index = track['kind'], track['index']
        if type(kind) is not int or kind not in (0, 1) or type(index) is not int or index < 0 or (kind, index) in tracks:
            raise BridgeError('Ambiguous snapshot track identity')
        tracks[(kind, index)] = {k: v for k, v in track.items() if k != 'clips'}
        for item in track['clips']:
            native_id = item.get('id')
            key = (kind, native_id)
            if not isinstance(native_id, str) or not native_id or key in items:
                raise BridgeError('Ambiguous snapshot item identity')
            if exact(item['end']) <= exact(item['start']):
                raise BridgeError('Invalid snapshot item range')
            items[key] = {'track_index': index, 'item': item}
    return tracks, items


def merge_ranges(ranges):
    result = []
    for start, end in sorted(set(ranges)):
        if result and start <= result[-1][1]:
            result[-1][1] = max(end, result[-1][1])
        else:
            result.append([start, end])
    return [{'start_ticks': str(start), 'end_ticks': str(end)} for start, end in result]


def changed_review(before, after):
    if target(before) != target(after):
        raise BridgeError('Cannot compare different project/sequence targets')
    old_tracks, old = inventory(before); new_tracks, new = inventory(after)
    ranges = {0: [], 1: []}; full = {0: False, 1: False}; changes = []
    for key in sorted(old.keys() | new.keys()):
        previous, current = old.get(key), new.get(key)
        if fingerprint(previous) == fingerprint(current):
            continue
        kind, native_id = key
        for row in (previous, current):
            if row:
                ranges[kind].append((exact(row['item']['start']), exact(row['item']['end'])))
        changes.append({'kind': 'picture' if kind == 0 else 'audio', 'native_item_id': native_id,
                        'change': 'added' if previous is None else 'removed' if current is None else 'changed',
                        'before': copy.deepcopy(previous), 'after': copy.deepcopy(current)})
    for key in old_tracks.keys() | new_tracks.keys():
        if fingerprint(old_tracks.get(key)) != fingerprint(new_tracks.get(key)):
            full[key[0]] = True
    if fingerprint({k: v for k, v in before.items() if k != 'tracks'}) != fingerprint({k: v for k, v in after.items() if k != 'tracks'}):
        full = {0: True, 1: True}
    old_order = {(t['kind'], t['index']): [c['id'] for c in t['clips']] for t in before['tracks']}
    for track in after['tracks']:
        key = (track['kind'], track['index']); current = [c['id'] for c in track['clips']]
        prior = old_order.get(key, [])
        if set(prior) == set(current) and prior != current:
            full[key[0]] = True
    return {'items': changes, 'picture_ranges': merge_ranges(ranges[0]), 'audio_ranges': merge_ranges(ranges[1]),
            'full_picture_review_required': full[0], 'full_audio_review_required': full[1],
            'range_semantics': 'half-open exact timeline ticks; whole affected items, including old and new placement',
            'boundary_review_required': bool(changes), 'normal_final_review_required': True,
            'limits': ['Bounded snapshot only; unobserved properties and dependent effects are not certified.',
                       'Ranges are review requests, not reviewed frames or listening evidence.']}


def file_evidence(path):
    path = Path(path)
    if not path.is_absolute() or not path.is_file():
        raise BridgeError('Handoff evidence requires an existing absolute file')
    content = path.read_bytes()
    return {'path': str(path), 'sha256': hashlib.sha256(content).hexdigest()}, content


def write_handoff(path, *, stage, before, after, before_revision, after_revision, receipts, previous=None):
    if stage not in STAGES or any(not isinstance(r, str) or not re.fullmatch('[a-f0-9]{64}', r) for r in (before_revision, after_revision)):
        raise BridgeError('Invalid stage or native revision')
    identity = target(before)
    review = changed_review(before, after)
    evidence, operations = [], []
    for receipt in receipts:
        artifact, content = file_evidence(receipt); row = json.loads(content)
        op, result = row['operation'], row.get('result', {})
        op_target = {k: op['target'].get(k) for k in identity}
        native = result.get('operation') or {}
        if op.get('stage') != stage or op_target != identity or result.get('reconciled') is not True or native.get('status') != 'committed_unverified' or native.get('result', {}).get('success') is not True:
            raise BridgeError('Handoff cannot promote unresolved, failed or wrong-target operations')
        operation_id = op.get('operation_id')
        if not isinstance(operation_id, str) or not operation_id or operation_id in operations:
            raise BridgeError('Missing or duplicate operation identity')
        evidence.append(artifact); operations.append(operation_id)
    if not evidence:
        raise BridgeError('Handoff requires original operation receipts')
    parent = None
    if previous is not None:
        parent, content = file_evidence(previous); previous_row = json.loads(content)
        assert_fresh(previous_row, before, before_revision)
    handoff = {'schema': 'edit.sequence-stage-handoff/v1', 'stage': stage, 'target': identity,
               'before_revision': before_revision, 'after_revision': after_revision,
               'before_snapshot_sha256': fingerprint(before), 'after_snapshot_sha256': fingerprint(after),
               'before_snapshot': copy.deepcopy(before), 'after_snapshot': copy.deepcopy(after),
               'operation_ids': operations, 'operation_receipts': evidence, 'previous_handoff': parent,
               'changed_review': review,
               'evidence': {'execution': 'original_receipts_report_success', 'immediate_readback': 'owning_stage_checks_completed',
                            'persistence': 'reopen_not_run', 'rendered': 'not_run', 'listening': 'not_run', 'human_approval': 'not_recorded'},
               'limits': ['Local artifact hashes bind recorded data; they do not attest native execution or human review.',
                          'Not a complete Premiere state digest or a substitute for stage postconditions.']}
    # Never replace an earlier handoff, including after an uncertain attempt.
    with Path(path).open('x') as stream:
        json.dump(handoff, stream, indent=2, allow_nan=False)
    return handoff


def assert_fresh(handoff, snapshot, revision):
    if handoff.get('schema') not in ('edit.sequence-stage-handoff/v1', 'edit.sequence-creation-handoff/v1') or handoff.get('target') != target(snapshot):
        raise BridgeError('Handoff target changed')
    if handoff.get('after_snapshot_sha256') != fingerprint(handoff.get('after_snapshot')):
        raise BridgeError('Stored handoff snapshot changed')
    if revision != handoff.get('after_revision') or fingerprint(snapshot) != handoff.get('after_snapshot_sha256'):
        raise BridgeError('Fresh native state differs from the prior handoff; inspect and replan, never restore stale state')


def write_creation_handoff(path, *, stage, project_before, project_after, sequence_id, sequence_revision, receipt):
    """Record a newly created sequence without inventing a native empty baseline."""
    if stage not in {'assembly', 'reframe', 'captions'} or not isinstance(sequence_revision, str) or not re.fullmatch('[a-f0-9]{64}', sequence_revision):
        raise BridgeError('Invalid creation stage or native sequence revision')
    before={s['sequence_id']:s for s in project_before['sequences']}; after={s['sequence_id']:s for s in project_after['sequences']}
    if len(before)!=len(project_before['sequences']) or len(after)!=len(project_after['sequences']) or sequence_id in before or set(after)-set(before)!={sequence_id} or not set(before)<=set(after):
        raise BridgeError('Creation handoff requires exactly one new native sequence')
    if project_before['project_path']!=project_after['project_path'] or project_before['active_sequence_id']!=project_after['active_sequence_id'] or any(before[k]!=after[k] for k in before):
        raise BridgeError('Protected project state changed during creation')
    snapshot=after[sequence_id]['snapshot'];identity=target(snapshot)
    if identity!={'project_path':project_after['project_path'],'sequence_id':sequence_id}:
        raise BridgeError('Created snapshot identity mismatch')
    artifact,content=file_evidence(receipt);row=json.loads(content)
    op=row['operation'];result=row.get('result',{});native=result.get('operation') or {};data=native.get('result',{}).get('data',{})
    if (op.get('stage')!=stage or op['target'].get('project_path')!=identity['project_path']
            or op['target'].get('sequence_id')!=project_before['active_sequence_id']
            or op.get('arguments',{}).get('expected_project_revision')!=project_before['revision']
            or result.get('reconciled') is not True or native.get('status')!='committed_unverified' or native.get('result',{}).get('success') is not True
            or data.get('sequence_id')!=sequence_id or data.get('sequence_revision')!=sequence_revision or data.get('snapshot')!=snapshot):
        raise BridgeError('Creation receipt does not establish this new native sequence')
    _,items=inventory(snapshot);ranges={0:[],1:[]}
    for (kind,_),entry in items.items():ranges[kind].append((exact(entry['item']['start']),exact(entry['item']['end'])))
    handoff={'schema':'edit.sequence-creation-handoff/v1','stage':stage,'target':identity,
             'before_snapshot':None,'before_revision':None,'baseline_semantics':'sequence_absent_in_project_before',
             'project_before':copy.deepcopy(project_before),'project_after':copy.deepcopy(project_after),
             'project_before_sha256':fingerprint(project_before),'project_after_sha256':fingerprint(project_after),
             'after_snapshot':copy.deepcopy(snapshot),'after_snapshot_sha256':fingerprint(snapshot),'after_revision':sequence_revision,
             'operation_ids':[op['operation_id']],'operation_receipts':[artifact],'previous_handoff':None,
             'changed_review':{'picture_ranges':merge_ranges(ranges[0]),'audio_ranges':merge_ranges(ranges[1]),'full_picture_review_required':True,'full_audio_review_required':True,'boundary_review_required':True,'normal_final_review_required':True},
             'evidence':{'execution':'original_receipt_reports_success','immediate_readback':'owning_stage_checks_completed','persistence':'reopen_not_run','rendered':'not_run','listening':'not_run','human_approval':'not_recorded'},
             'limits':['Creation evidence is bounded native state, not complete project/source processing or render proof.','An absent sequence is not a fabricated empty native timeline.']}
    with Path(path).open('x') as stream:json.dump(handoff,stream,indent=2,allow_nan=False)
    return handoff
