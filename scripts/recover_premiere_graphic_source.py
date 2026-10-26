#!/usr/bin/env python3
"""Reconcile only a still-image mark refusal with an unchanged native timeline.

Retain the imported, unused image and every original journal. No editor mutation,
save, placement or replay occurs. A changed timeline or newer operation refuses.
"""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import sys


def recover(args):
    sys.path.insert(0,str(args.skills/'_shared'))
    from premiere_bridge import PremiereBridge,Profile
    original=json.loads(args.receipt.read_text())
    plan=original['operation'];opid=plan['operation_id'];target=plan['target']
    if plan['tool']!='lab_place_graphic_asset':raise ValueError('Only graphic placement recovery supported')
    before=json.loads(args.before.read_text())
    if (before['projectPath']!=target['project_path'] or before['sequenceId']!=target['sequence_id'] or before['revision']!=target['expected_revision']):raise ValueError('Original baseline mismatch')
    profile=Profile.load(args.profile);runtime=Path(profile.cwd)/'lab/runtime'
    mutex=runtime/'reconcile.lock';fd=os.open(mutex,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    client=PremiereBridge(profile)
    try:
        path=runtime/'operations'/f'{opid}.json';raw=path.read_bytes();record=json.loads(raw)
        if record!=original['result']['operation'] or record['status']!='unknown' or record['result']!={'success':False,'error':'Error: GRAPHIC_SOURCE_MARK_READBACK'}:raise ValueError('Only the original terminal source-mark refusal is supported')
        jobs=[json.loads(p.read_text()) for p in (runtime/'jobs').glob('*.json')]
        if any(j['state'] in ('queued','running') for j in jobs):raise ValueError('Native work remains active')
        job=next(j for j in jobs if j['jobId']==opid)
        if job['state']!='settled' or job['result']!=record:raise ValueError('Original job not terminal')
        for p in (runtime/'operations').glob('*.json'):
            if p.name.endswith('.baseline.json'):continue
            other=json.loads(p.read_text())
            if other['operationId']!=opid and other['startedAt']>=record['startedAt']:raise ValueError('A newer native operation exists')
        live=client.inspect('lab_snapshot',{})
        if live!=before:raise ValueError('Native timeline changed')
        source=client.inspect('get_project_item_info',{'item_id':args.source_id})['data']
        if source['nodeId']!=args.source_id or source['mediaPath']!=plan['arguments']['media_path'] or source['offline'] or source['inPoint']!=0:raise ValueError('Imported source differs')
        full=client.inspect('inspect_project_sequences',{'project_path':target['project_path']})['data']
        for seq in full['sequences']:
            for track in seq['snapshot']['tracks']:
                for clip in track['clips']:
                    if clip.get('sourceId')==args.source_id or clip.get('mediaPath')==source['mediaPath']:raise ValueError('Imported source has a native consumer')
        if client.inspect('lab_snapshot',{})!=before or path.read_bytes()!=raw:raise ValueError('State changed during reconciliation')
        lock=runtime/'writer.lock'
        if not lock.is_file() or lock.stat().st_size:raise ValueError('Original empty writer lock required')
        args.output.mkdir()
        (args.output/'original-operation.json').write_bytes(raw)
        proof={'schema':'acq-edit/premiere-graphic-source-recovery-v1','operationId':opid,'before':before,'source':source,'project':full,'originalJob':job,'resolution':'PNG imported; source mark quantization refused before timeline placement. Retain unused source. No replay.','nativeMutations':0,'userApproved':False}
        proof_path=args.output/'receipt.json';proof_path.write_text(json.dumps(proof,indent=2))
        record['status']='reconciled_source_only';record['reconciliation']={'at':datetime.now(timezone.utc).isoformat(),'proof':str(proof_path.resolve()),'host_edit':'none','original_result_retained':True,'resolution':proof['resolution']}
        pending=path.with_suffix('.recovered')
        with pending.open('x') as f:json.dump(record,f,indent=2);f.flush();os.fsync(f.fileno())
        os.replace(pending,path);lock.rename(runtime/f'{opid}.retired-writer.lock')
        return {'status':'RECONCILED_SOURCE_ONLY','timelineUnchanged':True,'nativeMutations':0,'proof':str(proof_path)}
    finally:
        if not client.unsettled and not client.transport.pending:client.close()
        os.close(fd);mutex.unlink()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('skills','profile','receipt','before','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--source-id',required=True)
    print(json.dumps(recover(p.parse_args()),indent=2))
