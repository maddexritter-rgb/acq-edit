#!/usr/bin/env python3
"""Materialize framing-owner geometry and evidence without inventing camera intent.

The caller supplies calibrated complete-head offsets and crop height/headroom for
each view. Tracking follows measured faces only when dense evidence exists. This
creates a proposal/contact sheets; --accept requires actual prior frame inspection.
"""
import argparse,copy,hashlib,json,math,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'python'),str(ROOT/'.local/skills/horizontal-to-vertical/scripts')]
from common import fingerprint,sha,read
from composition_review import validate

def write(p,x):p.write_text(json.dumps(x,indent=2))
def prepare(plan,obs,decisions,out):
 from PIL import Image,ImageDraw
 import numpy as np
 from filmcraft_smooth_x import dense_subject_x,smooth_x
 out.mkdir(parents=True,exist_ok=False);spec=copy.deepcopy(plan);cuts={c['id']:c for c in spec['cuts']};views={};entries=[];layouts={};shots={};pictures=[]
 for view in obs['items']:
  key=view['cutId']+':'+view['role'];d=decisions['views'][key];cut=cuts[view['cutId']];mode=d['layout'];panel=mode=='split';rect={'x':0,'y':0 if d.get('position','top')=='top' else spec['height']//2,'width':spec['width'],'height':spec['height']//2 if panel else spec['height']}
  samples=view['samples'];faces=[s['face']for s in samples]
  overrides=d.get('headOverrides',{})
  if any(f is None and str(s['frame']) not in overrides for s,f in zip(samples,faces)):raise ValueError('Missing subject evidence: '+key)
  off=d['headOffsets'];heads=[overrides.get(str(s['frame'])) or [f[0]+off[0],f[1]+off[1],f[0]+off[2],f[1]+off[3]] for s,f in zip(samples,faces)]
  h=d['cropHeight'];cw=h*rect['width']//rect['height'];
  if cw*rect['height']!=h*rect['width']:raise ValueError('Crop height must preserve exact integer aspect')
  x=round(d.get('cropX',float(np.median([(a+c)/2-cw/2 for a,b,c,z in heads]))));y=round(d.get('cropY',float(np.median([b-h*d['headroom'] for a,b,c,z in heads]))));sw,sh=view['sourceWidth'],view['sourceHeight'];x=max(0,min(sw-cw,x));y=max(0,min(sh-h,y))
  crop={'mode':'fixed-crop','sourceWidth':sw,'sourceHeight':sh,'x':x,'y':y,'width':cw,'height':h}
  if d.get('tracking',True):
   dense,origins=dense_subject_x(view,cut['frames'],fallbacks=d.get('trackingFallbacks',[]))
   curve=smooth_x(dense+(off[0]+off[2])/2-cw/2,d.get('smoothFrames',10));xs=np.clip(curve,0,sw-cw).tolist();crop.update(mode='tracked-crop',x=xs[0],xByFrame=xs,sourceRange=view['sourceRange'])
   write(out/(view['cutId']+'-'+view['role']+'-tracking.json'),{'sourceRange':view['sourceRange'],'detectorModelSha256':obs['detectorModelSha256'],'rawFaces':view['denseFaces'],'frameOrigins':origins,'fallbacks':d.get('trackingFallbacks',[]),'smoothing':{'savgolWindowMax':7,'savgolOrder':2,'gaussianSigmaFrames':d.get('smoothFrames',10)},'xByFrame':xs,'y':y})
  elif not d.get('fixedCropReason'):
   raise ValueError('Fixed crop requires an explicit reviewed exception: '+key)
  views[key]=(view,crop,rect)
  entry={'cutId':cut['id'],**({'panelId':view['role']}if panel else {}),'sourceRange':view['sourceRange'],'headBoundsMethod':'visually-calibrated-envelope','visualInspection':'source-frames-reviewed','samples':[{'frame':s['frame'],'head':head,'evidence':s['evidence']}for s,head in zip(samples,heads)]};entries.append(entry)
  if panel:
   shots.setdefault(cut['id'],{'mode':'panel-layout','panels':[]})['panels'].append({'id':view['role'],'sourceRange':view['sourceRange'],'rect':rect,'crop':crop})
  else:shots[cut['id']]=crop
 for key,shot in shots.items():
  if shot['mode']=='panel-layout':
   shot['panels'].sort(key=lambda p:p['rect']['y']);layouts[key]=[{k:v for k,v in p.items() if k!='crop'}for p in shot['panels']]
 camera=out/'camera-decisions.json';write(camera,{'schema':'acq-edit/camera-layout-v1','owner':'assembly-design','cutsSha256':fingerprint(spec['cuts']),'width':spec['width'],'height':spec['height'],'fps':spec['fps'],'layouts':layouts})
 for shot in shots.values():
  if shot['mode']=='panel-layout':shot.update(cameraReceiptPath=str(camera),cameraReceiptSha256=sha(camera))
 profile=read(decisions['profile']);profile_path=out/'profile.json';write(profile_path,profile)
 spec['framing']={'schema':'acq-edit/framing-v1','shots':shots};review={'schema':'acq-edit/composition-review-v1','owner':'horizontal-to-vertical','shotsSha256':fingerprint(shots),'profile':{'path':str(profile_path),'sha256':sha(profile_path)},'entries':entries}
 # Structural measurement validation is not visual approval. Proposal stays
 # unreviewed until the separate accept action below.
 metrics=validate(spec,review,profile);write(out/'metrics.json',metrics)
 for e in review['entries']:e['visualInspection']='prepared-not-reviewed'
 write(out/'review-proposed.json',review);write(out/'plan-proposed.json',spec)
 for cut in spec['cuts']:
  selected=[(v,c,r)for v,c,r in views.values()if v['cutId']==cut['id']]
  for index in range(len(selected[0][0]['samples'])):
   canvas=Image.new('RGB',(180,320));frame=selected[0][0]['samples'][index]['frame']
   for v,c,r in selected:
    s=v['samples'][index];im=Image.open(s['evidence']['path']);sx,sy=im.width/v['sourceWidth'],im.height/v['sourceHeight'];cx=c['xByFrame'][frame]if c['mode']=='tracked-crop'else c['x'];box=(cx*sx,c['y']*sy,(cx+c['width'])*sx,(c['y']+c['height'])*sy);im=im.crop(box).resize((180,160 if len(selected)>1 else 320));canvas.paste(im,(0,round(r['y']/spec['height']*320)))
   pictures.append((canvas,f'{cut["id"]} +{frame}'))
 for page in range(math.ceil(len(pictures)/24)):
  sheet=Image.new('RGB',(1080,1360),'#171717');draw=ImageDraw.Draw(sheet)
  for i,(im,label)in enumerate(pictures[page*24:(page+1)*24]):x=i%6*180;y=i//6*340;sheet.paste(im,(x,y+20));draw.text((x+2,y+3),label,fill='white')
  sheet.save(out/f'review-{page+1}.jpg',quality=90)
 return {'measurements':len(metrics['samples']),'pages':math.ceil(len(pictures)/24),'status':'proposal-requires-source-frame-inspection'}

def accept(folder):
 review=read(folder/'review-proposed.json');spec=read(folder/'plan-proposed.json')
 for e in review['entries']:e['visualInspection']='source-frames-reviewed'
 validate(spec,review,read(review['profile']['path']));target=folder/'review.json'
 if target.exists():raise ValueError('Review already accepted; preserve it')
 write(target,review);receipt=folder/'receipt.json';write(receipt,{'schema':'acq-edit/framing-composition-v1','owner':'horizontal-to-vertical','review':str(target),'reviewSha256':sha(target),'shotsSha256':fingerprint(spec['framing']['shots'])});spec['framing'].update(receiptPath=str(receipt),receiptSha256=sha(receipt));write(folder/'plan.json',spec)
 return {'plan':str(folder/'plan.json'),'status':'source-framing-reviewed-native-render-pending'}

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--accept',type=Path)
 for n in ('plan','observations','decisions','output'):p.add_argument('--'+n,type=Path)
 a=p.parse_args()
 if a.accept:print(json.dumps(accept(a.accept.resolve())));return
 if not all([a.plan,a.observations,a.decisions,a.output]):p.error('Supply plan, observations, decisions and output')
 print(json.dumps(prepare(read(a.plan),read(a.observations),read(a.decisions),a.output.resolve())))
if __name__=='__main__':main()
