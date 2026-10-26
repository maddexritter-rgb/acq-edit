#!/usr/bin/env python3
"""Reconcile one completed import whose implicit Graphics chain differed.

Read-only: never replay import or rewrite the original uncertain journal. Only
the observed 26.3 default component expansion is accepted. The caption owner
still verifies every card, all clocks, media links and protected sequences.
"""
import argparse
import copy
import json
import os
from pathlib import Path
import sys
from datetime import datetime, timezone


def expanded_structure(request):
    result = copy.deepcopy(request)
    for track in result['tracks']:
        for item in track['items']:
            if item['source_kind'] == 'graphic':
                if item['component_match_names'] != ['AE.ADBE Motion', 'AE.ADBE Opacity', 'AE.ADBE Geometry2', 'AE.ADBE Text']:
                    raise ValueError('Unsupported declared Graphics chain')
                item['component_match_names'] = ['AE.ADBE Opacity', 'AE.ADBE Motion', 'AE.ADBE Graphic Group', 'AE.ADBE Geometry2', 'AE.ADBE Text']
    return result


def recover(client, directory, owner, native):
    directory = Path(directory)
    read = lambda name: json.loads((directory/name).read_text())
    original = read('transfer-operation.json')['operation']
    if original['tool'] != 'lab_import_prepared_caption_sequence':
        raise ValueError('Expected original caption import')
    opid = original['operation_id']
    job = client.inspect('lab_get_job', {'job_id': opid})
    operation = client.inspect('lab_get_operation', {'operation_id': opid})
    if (job.get('state') != 'settled' or job.get('operationId') != opid
            or operation.get('operationId') != opid or operation.get('status') != 'unknown'
            or operation.get('result') != {'success': False, 'error': 'Error: IMPORTED_COMPONENT_CHAIN_MISMATCH'}):
        raise ValueError('Only a terminal component-chain mismatch can be reconciled')
    prepared = read('prepared.json')
    artifacts = prepared['artifacts']
    checked = owner.prepare(*(a['path'] for a in artifacts), native)
    if checked != prepared:
        raise ValueError('Prepared artifact verification changed')
    before = read('before.json')
    project = before['project_path']
    after = client.inspect('inspect_project_sequences', {'project_path': project})['data']
    if after['active_sequence_id'] != before['active_sequence_id']:
        raise ValueError('Active sequence changed')
    mapping = owner.map_import(prepared, before, after)
    full = client.inspect('get_full_sequence_info', {'sequence_id': prepared['sequence_id']})['data']
    request = expanded_structure(read('structure.json')['structure']['expectation'])
    structure = owner.verify_structure(request, after, full)
    if client.inspect('inspect_project_sequences', {'project_path': project})['data'] != after:
        raise ValueError('Project changed during reconciliation')
    out = directory/'component-chain-recovery'
    out.mkdir(exist_ok=False)
    proof = {'schema': 'acq-edit/premiere-caption-import-recovery-v1',
             'operationId': opid, 'originalOperation': operation, 'originalJob': job,
             'resolution': 'Import complete; exact component expansion independently verified; never replay',
             'nativeMutations': 0, 'project': after, 'cardMap': mapping,
             'structure': structure, 'expectation': request,
             'persistence': 'not_saved', 'rendered': False, 'userApproved': False}
    (out/'receipt.json').write_text(json.dumps(proof, indent=2))
    return out/'receipt.json'


def release_verified_lock(client, proof_path, runtime):
    """Retire only this terminal import's lock after a second live inspection.

    Both original journals and lock bytes are retained in the recovery folder.
    This is not a generic force-unlock: newer native operations, any running job,
    changed project, changed original receipt or absent lock refuse recovery.
    """
    proof_path, runtime = Path(proof_path), Path(runtime)
    proof = json.loads(proof_path.read_text()); opid = proof['operationId']
    if proof['schema'] != 'acq-edit/premiere-caption-import-recovery-v1':
        raise ValueError('Verified caption recovery required')
    mutex = runtime/'reconcile.lock'; fd = os.open(mutex, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
    try:
        record_path = runtime/'operations'/f'{opid}.json'
        raw = record_path.read_bytes(); record = json.loads(raw)
        resuming = (record.get('status') == 'reconciled_import_verified'
                    and record.get('reconciliation', {}).get('proof') == str(proof_path.resolve()))
        if resuming:
            restored = dict(record); restored.pop('reconciliation'); restored['status'] = 'unknown'
            if restored != proof['originalOperation']:
                raise ValueError('Interrupted recovery journal differs')
        elif record != proof['originalOperation']:
            raise ValueError('Original operation changed')
        for path in (runtime/'operations').glob('*.json'):
            if path.name.endswith('.baseline.json'): continue
            other = json.loads(path.read_text())
            if other['operationId'] != opid and other['startedAt'] >= record['startedAt']:
                raise ValueError('Newer native operation exists')
        jobs = [json.loads(p.read_text()) for p in (runtime/'jobs').glob('*.json')]
        if any(j.get('state') in ('queued', 'running') for j in jobs):
            raise ValueError('A native job is still active')
        original_job = next(j for j in jobs if j['jobId'] == opid)
        if original_job['state'] != 'settled' or original_job['result'] != proof['originalOperation']:
            raise ValueError('Original job is not terminal and bound to its operation')
        live = client.inspect('inspect_project_sequences', {'project_path': proof['project']['project_path']})['data']
        if live != proof['project'] or record_path.read_bytes() != raw:
            raise ValueError('Project or operation changed since verification')
        lock = runtime/'writer.lock'
        if not lock.is_file() or lock.stat().st_size:
            raise ValueError('Expected the original empty runtime writer lock')
        out = proof_path.parent
        original_file = out/'original-journal.json'
        if resuming:
            if json.loads(original_file.read_text()) != proof['originalOperation']:
                raise ValueError('Original recovery evidence differs')
        else:
            with original_file.open('xb') as f: f.write(raw)
        record['status'] = 'reconciled_import_verified'
        record['reconciliation'] = {'at': datetime.now(timezone.utc).isoformat(),
            'proof': str(proof_path.resolve()), 'host_edit': 'none',
            'original_result_retained': True, 'resolution': proof['resolution']}
        stage = record_path.with_suffix('.recovered')
        with stage.open('x') as f: json.dump(record, f, indent=2); f.flush(); os.fsync(f.fileno())
        os.replace(stage, record_path)
        # Keep evidence instead of deleting the old lock.
        retired = runtime/f'{opid}.retired-writer.lock'
        if retired.exists(): raise ValueError('Retired lock already exists')
        os.rename(lock, retired)
        return {'status': 'RECONCILED_IMPORT_VERIFIED', 'nativeMutations': 0}
    finally:
        os.close(fd); mutex.unlink()


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ('skills', 'profile', 'directory'): ap.add_argument('--'+name, required=True)
    ap.add_argument('--release-runtime', type=Path)
    args = ap.parse_args(); skills = Path(args.skills).resolve()
    sys.path[:0] = [str(skills/'caption-clips/scripts'), str(skills/'_shared')]
    import apply_native_captions as owner
    import premiere_native_cards as native
    from premiere_bridge import PremiereBridge, Profile
    client = PremiereBridge(Profile.load(args.profile))
    try:
        if args.release_runtime:
            print(release_verified_lock(client, Path(args.directory)/'component-chain-recovery/receipt.json', args.release_runtime))
        else: print(recover(client, args.directory, owner, native))
    finally: client.close()
