#!/usr/bin/env python3
"""Apply explicit native dialogue operations; preserve partial receipts, never replay.

The author supplies the inspected component values. This does not select a mix,
infer native parameter units, or certify the sound of the result.
"""
import argparse
import json
from pathlib import Path
import sys
import uuid


def run(args):
    sys.path.insert(0, str(args.skills/'_shared'))
    from premiere_bridge import PremiereBridge, Profile, execute_operation
    spec=json.loads(args.spec.read_text())
    if spec.get('schema')!='acq-edit/premiere-dialogue-operations-v1' or not 1<=len(spec['operations'])<=100:
        raise ValueError('Explicit bounded dialogue operation list required')
    args.output.mkdir(exist_ok=False)
    client=PremiereBridge(Profile.load(args.profile))
    try:
        before=client.inspect('lab_snapshot',{})
        if before['projectPath']!=spec['projectPath'] or before['sequenceId']!=spec['sequenceId'] or before['revision']!=spec['expectedRevision']:
            raise ValueError('Dialogue baseline changed; inspect instead of replaying')
        (args.output/'before.json').write_text(json.dumps(before,indent=2))
        for index,request in enumerate(spec['operations']):
            # The host guard rechecks this complete revision immediately before
            # dispatch. Avoid a redundant full 187-Graphics snapshot here.
            current=before
            operation={'schema':'edit.native-operation/v1','stage':'music','operation_id':'dialogue-'+uuid.uuid4().hex,
                       'tool':'lab_apply_dialogue_effect','arguments':request,
                       'target':{'project_path':spec['projectPath'],'sequence_id':spec['sequenceId'],'expected_revision':current['revision']},
                       'intended_changes':['Explicit item-local dialogue effect'],
                       'protected_state':['Source cuts, all other effects, framing, captions and music']}
            (args.output/f'{index:02}-operation.json').write_text(json.dumps(operation,indent=2))
            result=execute_operation(client,operation,args.output/f'{index:02}-receipt.json',120)
            print(json.dumps({'operation':index,'result':result}),flush=True)
            before=client.inspect('lab_snapshot',{})
        (args.output/'after.json').write_text(json.dumps(before,indent=2))
        save={'schema':'edit.native-operation/v1','stage':'music','operation_id':'dialogue-save-'+uuid.uuid4().hex,
              'tool':'save_project','arguments':{},'target':{'project_path':spec['projectPath'],'sequence_id':spec['sequenceId'],'expected_revision':before['revision']},
              'intended_changes':['Save verified dialogue effect changes'],'protected_state':['All native timeline state']}
        execute_operation(client,save,args.output/'save.json',120)
        if client.inspect('lab_snapshot',{})!=before:raise ValueError('Timeline changed during save')
    finally:
        if not client.unsettled and not client.transport.pending:client.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('skills','profile','spec','output'):p.add_argument('--'+key,type=Path,required=True)
    run(p.parse_args())
