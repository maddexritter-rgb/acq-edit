#!/usr/bin/env python3
"""Reconcile a settled split's early panel-clock failure; preserve partial panels.

Only the early panel-construction regression case is accepted. This is not a general
unlock command and cannot settle timeouts, missing responses or placed overlays.
"""
import argparse, copy, hashlib, json, os, sys
from datetime import datetime, timezone
from pathlib import Path

def validate(plan, record, job, baseline, state, protected=()):
    op=plan['operation_id']; target=plan['target']; args=plan['arguments']
    guard=dict(operation_id=op,project_path=target['project_path'],sequence_id=target['sequence_id'],expected_revision=target['expected_revision'])
    fp=hashlib.sha256(json.dumps(dict(name=plan['tool'],args=args,guard=guard),ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
    if plan['tool']!='lab_place_camera_split' or record.get('tool')!=plan['tool'] or record.get('status')!='unknown' or record.get('fingerprint')!=fp:raise ValueError('Original unknown split request required')
    if job.get('state')!='settled' or job.get('fingerprint')!=fp or job.get('result')!=record or record.get('result',{}).get('success') is not False or record.get('result',{}).get('error') not in ('Error: PANEL_SOURCE_CLOCK_READBACK','Error: PANEL_NEST_PLACEMENT_FAILED','Error: PROTECTED_MASTER_CHANGED'):raise ValueError('Terminal panel-clock response required')
    if state.get('project_path')!=target['project_path']:raise ValueError('Project changed')
    master=[s for s in state['sequences'] if s['sequence_id']==target['sequence_id']]
    if len(master)!=1:raise ValueError('Master missing')
    current=copy.deepcopy(master[0]['snapshot']); n=sum(t['kind']==0 for t in baseline['tracks'])
    na=sum(t['kind']==1 for t in baseline['tracks'])
    known={s['snapshot'].get('sequenceId'):s for s in state['sequences'] if s['name'] in [args['name']+'_PANEL_0',args['name']+'_PANEL_1']}
    added=[]
    for t in current['tracks']:
        keep=[]
        for c in t['clips']:
            if c['name'] in [args['name']+'_PANEL_0',args['name']+'_PANEL_1']:
                if c['start']!=args['start_ticks'] or c['end']!=args['end_ticks'] or c['inPoint']!='0' or int(c['outPoint'])!=int(args['end_ticks'])-int(args['start_ticks']):raise ValueError('Placed nest clocks changed')
                if t['kind']==0 and t['index'] not in args['tracks']:raise ValueError('Unexpected overlay track')
                added.append({'id':c['id'],'kind':t['kind'],'track':t['index'],'name':c['name']})
            else:keep.append(c)
        t['clips']=keep
    if added and (len(known)!=2 or len(added)>6):raise ValueError('Unexpected partial placements')
    extra=[t for t in current['tracks'] if (t['kind']==0 and t['index']>=n) or (t['kind']==1 and t['index']>=na)]
    if len(extra)>6 or any(t['clips'] or t.get('transitions') for t in extra):raise ValueError('Overlay content requires manual reconciliation')
    current['tracks']=[t for t in current['tracks'] if t not in extra]
    if current!=baseline:raise ValueError('Protected master changed')
    protected_ids=[]
    for prior in protected:
        match=[s for s in state['sequences'] if s['sequence_id']==prior['sequenceId']]
        if len(match)!=1 or match[0]['snapshot']!=prior:raise ValueError('Protected sequence changed')
        protected_ids.append(prior['sequenceId'])
    panels=[s for s in state['sequences'] if s['sequence_id']!=target['sequence_id'] and s['sequence_id'] not in protected_ids]
    if not 1<=len(panels)<=2:raise ValueError('Single-master regression fixture required')
    for s in panels:
        names=[args['name']+'_PANEL_'+str(i) for i in range(2)]
        if s['name'] not in names:raise ValueError('Unexpected sequence')
        p=args['panels'][names.index(s['name'])]; snap=s['snapshot']; clips=[c for t in snap['tracks'] for c in t['clips']]
        if len(clips)!=1 or any(t['kind']==1 and t['clips'] for t in snap['tracks']):raise ValueError('Unexpected panel content')
        c=clips[0]
        if c['name']!=args['name']+'_SOURCE_'+str(names.index(s['name'])) or c['start']!='0' or c['speed']!=1 or c['disabled']:raise ValueError('Panel changed')
        if abs(int(c['inPoint'])-int(p['source_in_ticks']))>int(args['frame_ticks']) or abs(int(c['outPoint'])-int(p['source_out_ticks']))>int(args['frame_ticks']):raise ValueError('Panel clock differs beyond rounding')
    return dict(protected_master_unchanged=True,retained_placements=added,empty_added_tracks=len(extra),retained_panel_ids=[s['sequence_id'] for s in panels],host_mutations=0)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--toolkit',type=Path,required=True);p.add_argument('--plan',type=Path,required=True);p.add_argument('--evidence',type=Path,required=True);p.add_argument('--protected-baseline',type=Path,action='append',default=[]);a=p.parse_args()
    sys.path.insert(0,str(a.toolkit/'.local/skills/_shared'))
    from premiere_bridge import Profile,PremiereBridge
    profile=Profile.load(a.toolkit/'.local/premiere-profile.json');root=Path(profile.cwd)/'lab/runtime'; plan=json.loads(a.plan.read_text());op=plan['operation_id']
    if not op or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in op):raise ValueError('Invalid operation')
    fd=os.open(root/'reconcile.lock',os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    try:
        lock=root/'writer.lock';lock_stat=lock.stat();rp=root/'operations'/f'{op}.json';jp=root/'jobs'/f'{op}.json';record=json.loads(rp.read_text());job=json.loads(jp.read_text());baseline=json.loads((root/'operations'/f'{op}.baseline.json').read_text())
        lease=json.loads((root/'lease.json').read_text())
        if lease['projectPath']!=plan['target']['project_path'] or datetime.fromisoformat(lease['expiresAt']).timestamp()<=datetime.now().timestamp():raise ValueError('Live exact-project lease required')
        for file in (root/'operations').glob('*.json'):
            if file.name.endswith('.baseline.json'):continue
            other=json.loads(file.read_text())
            if other['operationId']!=op and other['startedAt']>=record['startedAt']:raise ValueError('More recent operation exists')
        if any(json.loads(f.read_text()).get('state') in ('queued','running') for f in (root/'jobs').glob('*.json')):raise ValueError('Active native job')
        client=PremiereBridge(profile)
        try:state=client.inspect('inspect_project_sequences',{'project_path':plan['target']['project_path']})['data']
        finally:client.close()
        protected=[json.loads(f.read_text()) for f in a.protected_baseline]
        proof=validate(plan,record,job,baseline,state,protected)
        evidence={'schema':'acq.camera-split-recovery/v1','at':datetime.now(timezone.utc).isoformat(),'original_operation':record,'original_job':job,'native_state':state,'protected_baselines':protected,'proof':proof,'outcome':'failed_partial_preserved','replay':False}
        with a.evidence.open('x') as f:json.dump(evidence,f,indent=2)
        if json.loads(rp.read_text())!=record or json.loads(jp.read_text())!=job or lock.stat().st_ino!=lock_stat.st_ino:raise ValueError('State changed during reconciliation')
        record=copy.deepcopy(record);record['status']='failed';record['evidence']['execution']='failed_partial_preserved';record['evidence']['readback']='master_unchanged_partial_panels_retained';record['reconciliation']={'evidencePath':str(a.evidence),'sha256':hashlib.sha256(a.evidence.read_bytes()).hexdigest(),**proof}
        job=copy.deepcopy(job);job['outcome']='failed';job['result']=record
        for file,data in [(rp,record),(jp,job)]:
            temp=file.with_suffix('.reconciled');temp.write_text(json.dumps(data,indent=2)+'\n');temp.replace(file)
        lock.unlink();print(json.dumps(record['reconciliation'],indent=2))
    finally:os.close(fd);(root/'reconcile.lock').unlink()
if __name__=='__main__':main()
