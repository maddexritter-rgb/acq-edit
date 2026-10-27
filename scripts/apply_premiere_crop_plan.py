#!/usr/bin/env python3
"""Transport reviewed shared crop curves through the framing owner's native API.
No detection, camera choices, source replacement or cross-editor render occurs.
"""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'.local/skills/horizontal-to-vertical/scripts'),str(ROOT/'python')]
from premiere_reframe_bridge import ReframeSession
from common import sha

def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('profile','plan','output'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();spec=json.loads(a.plan.read_text());out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
 if spec['backend']!='premiere':raise ValueError('Premiere plan required')
 session=ReframeSession(a.profile)
 try:
  before=session.inspect_active();root=Path(spec['sources'][0]['path']).parents[1]
  if not Path(before['project_path']).is_relative_to(root/'10_WORK'):raise ValueError('Native project differs')
  (out/'before.json').write_text(json.dumps(before,indent=2))
  session.duplicate(before,spec['title']+' Vertical',out)
  state=session.inspect_active();rows=[c for t in state['video_tracks'] for c in t['clips']]
  if len(rows)!=len(spec['cuts']):raise ValueError('Native picture coverage differs')
  sources={s['id']:s for s in spec['sources']};records=[]
  for cut,row in zip(spec['cuts'],rows):
   shot=spec['framing']['shots'][cut['id']];fps=spec['fps']['numerator']/spec['fps']['denominator']
   if shot['mode']!='tracked-crop' or len(shot['xByFrame'])!=cut['frames']:raise ValueError('Dense reviewed full-frame crop required')
   if row['media_path']!=sources[cut['sourceId']]['path'] or abs(row['source_in']-cut['sourceInFrame']/fps)>1e-6 or abs(row['end']-row['start']-cut['frames']/fps)>1e-6:raise ValueError('Native picture source or clocks differ')
   records.append({**{k:row[k] for k in ('track_index','item_index','name','media_path','start','end','source_in','source_out','speed')},'baseline_motion':row['motion'],'position':[.5,.5],'scale_percent':1920/shot['height']*100,'anchor_keys':[[f/fps,(x+shot['width']/2)/shot['sourceWidth'],(shot['y']+shot['height']/2)/shot['sourceHeight']] for f,x in enumerate(shot['xByFrame'])]})
  plan={'schema':'premiere-native-reframe/v1','project_path':state['project_path'],'sequence_name':state['sequence_name'],'sequence_id':state['sequence_id'],'sequence_dimensions':[1080,1920],'bridge_baseline':state['bridge_baseline'],'records':records,'sharedPlan':str(a.plan.resolve()),'sharedPlanSha256':sha(a.plan)}
  file=out/'motion-plan.json';file.write_text(json.dumps(plan,indent=2));result=session.apply(file,plan,timeout=180)
  (out/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps({'sequenceId':state['sequence_id'],'status':result['status']}))
 finally:
  if not session.client.unsettled and not session.client.transport.pending:session.close()
if __name__=='__main__':main()
