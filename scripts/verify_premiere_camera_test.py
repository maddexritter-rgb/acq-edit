#!/usr/bin/env python3
"""Readback checks for an explicit camera-switch test, separate from approval."""
import argparse,copy,json,math
from pathlib import Path

def require(ok,message):
    if not ok:raise ValueError(message)

def verify(design,before,after,results,links):
    require(before['projectPath']==after['projectPath'] and before['sequenceId']==after['sequenceId'],'Camera test target changed')
    require(len(results)==len(design['shots']),'Not all planned shots completed')
    indices={s['request']['track_index'] for s in design['shots']}
    def protected(s):
        s=copy.deepcopy(s)
        for t in s['tracks']:
            if t['kind']==0 and t['index'] in indices:t['clips']=[]
        for k in ['revision','revisionScope','uxp']:s.pop(k,None)
        return s
    require(protected(before)==protected(after),'Dialogue, captions or another protected track changed')
    require(links['project_path']==after['projectPath'] and links['sequence_id']==after['sequenceId'],'Source readback target differs')
    rows=[c for t in after['tracks'] if t['kind']==0 and t['index'] in indices for c in t['clips']]
    count=0
    for shot,result in zip(design['shots'],results):
        r=shot['request'];matches=[c for c in rows if c['id']==result['item']['id']];require(len(matches)==1,'Missing camera shot');c=matches[0]
        require((c['start'],c['end'],c['inPoint'],c['outPoint'])==(r['start_ticks'],r['end_ticks'],r['source_in_ticks'],r['source_out_ticks']) and c['speed']==1 and c['disabled'] is False,'Camera shot clocks/playback changed')
        source=[x['item'] for x in links['items'] if x['kind']=='video' and x['item']['node_id']==c['id']]
        require(len(source)==1 and source[0]['media_path']==r['media_path'] and source[0]['offline'] is False and source[0]['is_sequence'] is False and source[0]['speed_reversed'] in [False,0],'Camera shot is offline, reversed, flattened or relinked')
        motion=[fx for fx in c['components'] if fx['matchName']=='AE.ADBE Motion'];require(len(motion)==1,'Camera Motion missing')
        props={p['name']:p for p in motion[0]['properties']};keys=props['Anchor Point'].get('keys',[])
        require(len(keys)==len(r['anchor_keys']),'Sparse camera tracking')
        for i,(a,b) in enumerate(zip(keys,r['anchor_keys'])):
            require(int(a['ticks'])==int(r['source_in_ticks'])+i*int(r['frame_ticks']) and len(a['value'])==2 and all(math.isfinite(x) and abs(x-y)<1e-7 for x,y in zip(a['value'],b)),'Camera key differs from frozen source curve')
        require(abs(props['Scale']['value']-r['scale'])<.0001 and props['Position']['value']==[.5,.5] and not props['Position'].get('keys') and not props['Scale'].get('keys'),'Camera scale/position changed')
        count+=len(keys)
    for index in indices:
        clips=sorted((c for t in after['tracks'] if t['kind']==0 and t['index']==index for c in t['clips']),key=lambda c:int(c['start']))
        expected_end=max(int(c['end']) for t in before['tracks'] if t['kind']==0 and t['index']==index for c in t['clips'])
        require(clips and int(clips[0]['start'])==0 and int(clips[-1]['end'])==expected_end and all(a['end']==b['start'] for a,b in zip(clips,clips[1:])),'Visible camera track has a gap/overlap')
    return {'shots':len(results),'denseKeys':count,'protectedTracks':'unchanged','sourceLinked':True,'visibleCoverage':'continuous','visualApproval':False}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ['design','run','readback','links','output']:p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args();load=lambda p:json.loads(p.read_text())
    result=verify(load(a.design),load(a.run/'before.json'),load(a.readback),[load(p) for p in sorted(a.run.glob('*-result.json'))],load(a.links))
    with a.output.open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps(result))
