#!/usr/bin/env python3
"""Execute a frozen camera-only plan on an explicitly chosen test sequence.

Never resumes by replaying a mutation: retain each operation and receipt, and
reconcile uncertain outcomes before preparing a new plan.
"""
import argparse,json,sys,uuid
from pathlib import Path

def run(a):
    sys.path.insert(0,str(a.toolkit/'.local/skills/_shared'))
    from premiere_bridge import Profile,PremiereBridge,execute_operation
    design=json.loads(a.plan.read_text())
    if design.get('owner')!='assembly-design' or not 1<=len(design.get('shots',[]))<=30:
        raise ValueError('Explicit bounded Assembly Design camera plan required')
    a.output.mkdir(exist_ok=False)
    c=PremiereBridge(Profile.load(a.toolkit/'.local/premiere-profile.json'))
    try:
        snap=c.inspect('lab_snapshot',{})
        if (snap['projectPath'],snap['sequenceId'],snap['revision'])!=(str(a.project),a.sequence,a.revision):
            raise ValueError('Camera baseline changed; reconcile before applying')
        (a.output/'before.json').write_text(json.dumps(snap,indent=2))
        for i,shot in enumerate(design['shots']):
            op={'schema':'edit.native-operation/v1','stage':'reframe','operation_id':'camera-shot-'+uuid.uuid4().hex,
                'tool':'lab_place_tracked_camera_shot','arguments':shot['request'],
                'target':{'project_path':str(a.project),'sequence_id':a.sequence,'expected_revision':snap['revision']},
                'intended_changes':[shot['reason']],'protected_state':['Dialogue, captions, other tracks and original sequences']}
            (a.output/f'{i:02}-operation.json').write_text(json.dumps(op,indent=2))
            result=execute_operation(c,op,a.output/f'{i:02}-receipt.json',180)
            (a.output/f'{i:02}-result.json').write_text(json.dumps(result,indent=2))
            print(json.dumps({'shot':i+1,'keys':result.get('keys'),'verified':result.get('protected_state_verified')}),flush=True)
            snap=c.inspect('lab_snapshot',{})
        (a.output/'after.json').write_text(json.dumps(snap,indent=2))
        save={'schema':'edit.native-operation/v1','stage':'reframe','operation_id':'camera-save-'+uuid.uuid4().hex,'tool':'save_project','arguments':{},'target':{'project_path':str(a.project),'sequence_id':a.sequence,'expected_revision':snap['revision']},'intended_changes':['Save camera test'],'protected_state':['All timeline state']}
        execute_operation(c,save,a.output/'save.json',180)
    finally:
        if not c.unsettled and not c.transport.pending:c.close()

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ['toolkit','plan','project','output']:p.add_argument('--'+k,type=Path,required=True)
    for k in ['sequence','revision']:p.add_argument('--'+k,required=True)
    run(p.parse_args())
