#!/usr/bin/env python3
"""Run the existing native stages once from a checked, authored finishing plan.

Every stage keeps its ordinary guards and immutable artifacts. Refuse an existing
output directory; ambiguous native outcomes require the normal reconciliation.
"""
import argparse,hashlib,json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def read(p):return json.loads(Path(p).read_text())
def write(p,v):Path(p).write_text(json.dumps(v,indent=2))
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('project','plan','output','clock','home','shadow-profile'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();project=read(a.project);spec=read(a.plan);out=a.output.resolve();root=Path(project['root']).resolve()
 if project['backend']!='filmcraft' or spec['projectId']!=project['id'] or spec['backend']!='filmcraft':raise ValueError('Exact FilmCraft project required')
 if not out.is_relative_to(root/'10_WORK'):raise ValueError('Execution output must be project-owned work')
 out.mkdir(parents=True,exist_ok=False);config=read(a.home/'config.json');env={**os.environ,'ACQ_EDIT_HOME':str(a.home.resolve())};clock=ROOT/'.local/skills/edit/scripts/run_clock.py'
 def run(stage,args,target):
  with target.open('x') as f:subprocess.run([sys.executable,str(clock),'--log',str(a.clock),'run','--stage',stage,'--',*map(str,args)],stdout=f,env=env,check=True)
  return read(target)
 def native(action,packet,stage):
  file=out/(stage+'-packet.json');write(file,packet)
  return run(stage,['node',ROOT/'dist/cli.js','native',project['id'],action,file],out/(stage+'-result.json'))
 built=native('build',{'plan':str(a.plan.resolve()),'output':str(out/'native')},'native_build')
 data=read(built['nativeProject']);master=data['project']['items'][str(data['view']['active_sequence'])]['kind']['Sequence'];items=master['video_tracks'][0]['items']
 if len(items)!=len(spec['cuts']):raise ValueError('Native picture count differs')
 ids=[i['item'] for i,c in zip(items,spec['cuts']) if spec.get('framing',{}).get('shots',{}).get(c['id'],{}).get('mode')=='panel-layout']
 target=built['nativeProject'];shadow=None
 if ids:
  write(out/'shadow-targets.json',ids)
  run('native_split_shadow',[sys.executable,ROOT/'.local/skills/horizontal-to-vertical/scripts/filmcraft_split_shadow.py','--project',target,'--binary',config['filmcraft'],'--out',out/'shadow','--profile',a.shadow_profile,'--targets',out/'shadow-targets.json'],out/'shadow-result.json')
  shadow=out/'shadow/receipt.json';target=str(out/'shadow/edit.fcproj')
 inspected=native('inspect',{'nativeProject':target,'session':str(out/'inspection-session')},'native_inspection')
 packet={'plan':str(a.plan.resolve()),'nativeProject':target,'expectedFingerprint':inspected['fingerprint'],'media':str(out/'export/clip.mp4'),'session':str(out/'export/session'),'inspection':str(out/'export/inspection.json'),'receipt':str(out/'export/receipt.json'),'parentId':None}
 if shadow:packet.update(shadowReceipt=str(shadow),shadowReceiptSha256=hashlib.sha256(shadow.read_bytes()).hexdigest())
 native('render',packet,'native_export_and_integrity')
 # Publication does not approve the clip. It preserves the native checkpoint and
 # exposes an unreviewed immutable version; visual/listening observations follow.
 published=run('review_publication',['node',ROOT/'dist/cli.js','publish',project['id'],packet['receipt']],out/'published.json')
 print(json.dumps({'version':published,'status':'published-unreviewed','execution':str(out)},indent=2))
if __name__=='__main__':main()
