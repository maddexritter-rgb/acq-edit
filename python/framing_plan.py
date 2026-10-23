"""Native geometry translation for a framing decision owned by horizontal-to-vertical.

No subject detection, shot selection, smoothing or editorial camera changes live here.
"""
import json,subprocess
from common import inside,require,sha

def validate_framing(project,spec):
 framing=spec.get('framing',{})
 if not framing:return {}
 require(framing.get('schema')=='acq-edit/framing-v1','Use the shared framing schema; raw engine properties are not a portable camera plan')
 require(set(framing)<=set(['schema','receiptPath','receiptSha256','shots']),'Unknown framing operation')
 receipt=inside(project['root'],framing['receiptPath']);require(sha(receipt)==framing['receiptSha256'],'Framing decision receipt changed')
 shots=framing['shots'];require(isinstance(shots,dict) and set(shots)=={c['id'] for c in spec['cuts']},'Every source cut needs exactly one framing decision')
 sizes={}
 for cut in spec['cuts']:
  shot=shots[cut['id']]
  require(shot.get('mode')=='fixed-crop','This native route accepts fixed crops; tracking and panels require their explicit supported execution plan')
  require(set(shot)==set(['mode','sourceWidth','sourceHeight','x','y','width','height']),'Unknown or incomplete fixed-crop geometry')
  for key in ['sourceWidth','sourceHeight','x','y','width','height']:require(type(shot[key])==int,'Fixed crop geometry must use exact integer source pixels; never round a tracking plan')
  require(shot['width']>0 and shot['height']>0 and shot['x']>=0 and shot['y']>=0,'Invalid source crop')
  require(shot['x']+shot['width']<=shot['sourceWidth'] and shot['y']+shot['height']<=shot['sourceHeight'],'Crop exposes a source edge')
  require(shot['width']*spec['height']==shot['height']*spec['width'],'Crop aspect must match output without stretching')
  if cut['sourceId'] not in sizes:
   source=next(s for s in spec['sources'] if s['id']==cut['sourceId'])
   info=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_streams','-of','json',source['path']]))['streams']
   require(info,'Framing source has no picture');video=info[0]
   require(video.get('sample_aspect_ratio','1:1') in ['1:1','N/A'],'Anamorphic source needs an explicit geometry path')
   require(not any(float(d.get('rotation',0))%360 for d in video.get('side_data_list',[])),'Rotated source needs an explicit geometry path')
   sizes[cut['sourceId']]=(video['width'],video['height'])
  require(sizes[cut['sourceId']]==(shot['sourceWidth'],shot['sourceHeight']),'Source geometry differs from the reviewed crop')
 return shots

def filmcraft_motion(spec,shot):
 return {'anchor':[shot['x']+shot['width']/2,shot['y']+shot['height']/2],
         'position':[spec['width']/2,spec['height']/2],
         'scale':100*spec['width']/shot['width']}

def fusion_crop(spec,shot):
 # Shared coordinates start at the top left; Fusion crop offsets start at the bottom left.
 return {'KeepCentered':0,'KeepAspect':0,'XOffset':shot['x'],
         'YOffset':shot['sourceHeight']-shot['y']-shot['height'],
         'XSize':shot['width'],'YSize':shot['height']}

def require_static_fusion_crop(crop,fields):
 inputs={value.GetAttrs().get('INPS_ID'):value for value in crop.GetInputList().values()}
 for field in fields:
  require(field in inputs,'Native crop input missing: '+field)
  value=inputs[field]
  require(not value.GetConnectedOutput() and not value.GetExpression(),'Animated or driven framing requires a tracking revision; never replace it with a fixed crop')
