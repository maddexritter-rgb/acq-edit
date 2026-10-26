#!/usr/bin/env python3
"""Read-only recovery of the historical null-selection finalization failure.

Does not import, retry a mutation, erase an attempt or weaken native-state checks.
Only the precise saved/verified assembly state can produce a recovered handoff.
"""
import argparse
import json
from pathlib import Path
import sys


def recover(client, directory, write_handoff):
    out = Path(directory).resolve()
    read = lambda name: json.loads((out / name).read_text())
    restore = read('restore-operation.json')
    operation = restore['operation']
    if operation['tool'] != 'set_active_sequence' or operation['arguments'] != {'sequence_id': None}:
        raise ValueError('Only the historical empty-selection failure is supported')
    before, after = read('before.json'), read('after.json')
    prior = read('project-before.json')
    sid = after['sequenceId']
    if prior['active_sequence_id'] is not None or operation['target']['sequence_id'] != sid:
        raise ValueError('This was not an initially empty selection')
    if operation['target']['expected_revision'] != after['revision']:
        raise ValueError('Failed restoration is not bound to the saved snapshot')
    for name in ('edges-operation.json', 'save-operation.json'):
        result = read(name)['result']
        if not result.get('reconciled') or result['operation']['status'] != 'committed_unverified' or result['operation']['result'].get('success') is not True:
            raise ValueError('Edges and save must have settled success receipts')
    op_id = operation['operation_id']
    job = client.inspect('lab_get_job', {'job_id': op_id})
    receipt = client.inspect('lab_get_operation', {'operation_id': op_id})
    if job is not None or receipt is not None:
        raise ValueError('A recorded restore attempt needs its ordinary reconciliation route')
    current = client.inspect('lab_snapshot', {})
    if current != after:
        raise ValueError('Native state changed after the saved audio edit')
    links = client.inspect('inspect_assembly_links', {'project_path': after['projectPath'], 'sequence_id': sid})['data']
    if links != read('links-after.json'):
        raise ValueError('Native links changed')
    final = client.inspect('inspect_project_sequences', {'project_path': after['projectPath']})['data']
    old = {r['sequence_id']: r for r in prior['sequences']}
    new = {r['sequence_id']: r for r in final['sequences']}
    raw = lambda v: {k: x for k, x in v.items() if k not in ('revision', 'revisionScope', 'uxp')}
    if (final['project_path'] != prior['project_path'] or set(old) != set(new)
            or any(old[k] != new[k] for k in old if k != sid)
            or final['active_sequence_id'] != sid or new[sid]['snapshot'] != raw(after)
            or client.inspect('lab_snapshot', {}) != after):
        raise ValueError('Protected project state changed')
    recovery = out / 'empty-selection-recovery'
    recovery.mkdir(exist_ok=False)
    handoff = recovery / 'stage-handoff.json'
    write_handoff(handoff, stage='assembly', before=raw(before), after=raw(after),
                  before_revision=before['revision'], after_revision=after['revision'],
                  receipts=[out/'edges-operation.json', out/'save-operation.json'],
                  previous=out.parent/'stage-handoff.json')
    evidence = {'schema': 'acq-edit/empty-selection-recovery-v1', 'operationId': op_id,
                'job': job, 'operation': receipt, 'snapshot': current, 'project': final,
                'stageHandoff': str(handoff), 'nativeMutations': 0,
                'resolution': 'Saved exact state and native links verified; keep new assembly selected; never replay null restoration',
                'persistence': 'reopen_not_run', 'rendered': False, 'userApproved': False}
    (recovery/'receipt.json').write_text(json.dumps(evidence, indent=2))
    return evidence


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skills', type=Path, required=True)
    parser.add_argument('--profile', required=True)
    parser.add_argument('--directory', required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.skills.resolve()/'_shared'))
    from premiere_bridge import PremiereBridge, Profile
    from premiere_stage_handoff import write_handoff
    client = PremiereBridge(Profile.load(args.profile))
    try:
        result = recover(client, args.directory, write_handoff)
        print(json.dumps({k: result[k] for k in ('operationId', 'stageHandoff', 'resolution', 'nativeMutations')}, indent=2))
    finally:
        client.close()
