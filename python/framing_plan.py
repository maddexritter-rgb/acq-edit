"""Native geometry translation for a framing decision owned by horizontal-to-vertical.

No subject detection, shot selection, smoothing or editorial camera changes live here.
"""
import json,subprocess,math
from fractions import Fraction
from common import inside,require,sha
from pathlib import Path

def validate_framing(project,spec,source_probes=None):
 framing=spec.get('framing',{})
 if not framing:return {}
 require(framing.get('schema')=='acq-edit/framing-v1','Use the shared framing schema; raw engine properties are not a portable camera plan')
 require(set(framing)<=set(['schema','receiptPath','receiptSha256','shots']),'Unknown framing operation')
 receipt=inside(project['root'],framing['receiptPath']);require(sha(receipt)==framing['receiptSha256'],'Framing decision receipt changed')
 shots=framing['shots'];require(isinstance(shots,dict) and set(shots)=={c['id'] for c in spec['cuts']},'Every source cut needs exactly one framing decision')
 sizes=source_probes if source_probes is not None else {}
 for cut in spec['cuts']:
  shot=shots[cut['id']]
  if shot.get('mode')=='panel-layout':
   from panel_layout import validate
   validate(project,spec,cut,shot,sizes);continue
  require(shot.get('mode') in ['fixed-crop','tracked-crop'],'This route accepts fixed crops or explicit source-bound X tracking; panels need their own execution plan')
  tracked=shot['mode']=='tracked-crop'
  require(not tracked or spec.get('backend') in ['filmcraft','resolve'],'Native tracked crops are supported only by the selected FilmCraft or Resolve adapter')
  require(set(shot)==set(['mode','sourceWidth','sourceHeight','x','y','width','height']+(['xByFrame','sourceRange'] if tracked else [])),'Unknown or incomplete crop geometry')
  for key in ['sourceWidth','sourceHeight','y','width','height']+([] if tracked else ['x']):require(type(shot[key])==int,'Crop geometry must use exact integer source pixels')
  require(type(shot['x']) in (int,float) and math.isfinite(shot['x']),'Invalid crop X')
  if tracked:
   source=next(s for s in spec['sources'] if s['id']==cut['sourceId'])
   require(shot['sourceRange']=={'sourceId':source['id'],'sha256':source['sha256'],'inFrame':cut['sourceInFrame'],'frames':cut['frames']},'Tracking source range changed; recompute the owning framing handoff')
   xs=shot['xByFrame'];require(isinstance(xs,list) and len(xs)==cut['frames'] and xs,'Tracking needs one reviewed X per displayed frame')
   require(all(type(x) in (int,float) and math.isfinite(x) and 0<=x<=shot['sourceWidth']-shot['width'] for x in xs),'Tracking curve exposes a source edge or has invalid values')
   require(xs[0]==shot['x'],'Initial crop and first tracking key differ')
  require(shot['width']>0 and shot['height']>0 and shot['x']>=0 and shot['y']>=0,'Invalid source crop')
  require(shot['x']+shot['width']<=shot['sourceWidth'] and shot['y']+shot['height']<=shot['sourceHeight'],'Crop exposes a source edge')
  require(shot['width']*spec['height']==shot['height']*spec['width'],'Crop aspect must match output without stretching')
  if cut['sourceId'] not in sizes:
   source=next(s for s in spec['sources'] if s['id']==cut['sourceId'])
   info=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_streams','-of','json',source['path']]))['streams']
   require(info,'Framing source has no picture');video=info[0]
   require(video.get('sample_aspect_ratio','1:1') in ['1:1','N/A'],'Anamorphic source needs an explicit geometry path')
   require(not any(float(d.get('rotation',0))%360 for d in video.get('side_data_list',[])),'Rotated source needs an explicit geometry path')
   sizes[cut['sourceId']]=(video['width'],video['height'],video.get('r_frame_rate'),video.get('avg_frame_rate'))
  require(sizes[cut['sourceId']][:2]==(shot['sourceWidth'],shot['sourceHeight']),'Source geometry differs from the reviewed crop')
  if tracked:
   rates=sizes[cut['sourceId']][2:];expected=Fraction(spec['fps']['numerator'],spec['fps']['denominator'])
   require(all(rate and rate!='0/0' and Fraction(rate)==expected for rate in rates),'Tracked crops require matching constant source/timeline frame rates; reconform explicitly')
 return shots

def filmcraft_motion(spec,shot):
 return {'anchor':[shot['x']+shot['width']/2,shot['y']+shot['height']/2],
         'position':[spec['width']/2,spec['height']/2],
         'scale':100*spec['width']/shot['width']}

def fusion_crop(spec,shot):
 # Shared coordinates start at the top left; Fusion crop offsets start at the bottom left.
 return {'KeepCentered':0,'KeepAspect':0,'XOffset':math.floor(shot['x']) if shot['mode']=='tracked-crop' else shot['x'],
         'YOffset':shot['sourceHeight']-shot['y']-shot['height'],
         'XSize':shot['width'],'YSize':shot['height']}

def require_static_fusion_crop(crop,fields):
 inputs={value.GetAttrs().get('INPS_ID'):value for value in crop.GetInputList().values()}
 for field in fields:
  require(field in inputs,'Native crop input missing: '+field)
  value=inputs[field]
  require(not value.GetConnectedOutput() and not value.GetExpression(),'Animated or driven framing requires a tracking revision; never replace it with a fixed crop')


def filmcraft_tracking(c, item, cut, shot, frame_ticks):
 if shot['mode']!='tracked-crop':return
 for frame,x in enumerate(shot['xByFrame']):
  c.run('effects.setParam',{'clip':item['clip'],'effect':'motion','param':'anchor','value':[x+shot['width']/2,shot['y']+shot['height']/2],'time':(cut['recordFrame']+frame)*frame_ticks,'keyframe':True})
  c.run('effects.setInterpolation',{'clip':item['clip'],'effect':'motion','param':'anchor','mediaTime':(cut['sourceInFrame']+frame)*frame_ticks,'interpolation':'linear'})


def verify_filmcraft_framing(native,spec,frame_ticks):
 from common import read
 verify_filmcraft_framing_data(read(native),spec,frame_ticks)


def verify_filmcraft_framing_data(data,spec,frame_ticks,sequence_id=None):
 shots=spec.get('framing',{}).get('shots',{})
 if not shots:return
 seq=data['project']['items'][str(sequence_id if sequence_id is not None else data['view']['active_sequence'])]['kind']['Sequence'];items=seq['video_tracks'][0]['items']
 require(len(items)==len(spec['cuts']),'Native framing picture coverage differs')
 if any(s['mode']=='panel-layout' for s in shots.values()):
  require(seq['video_tracks'][0]['enabled'] and not any(t['solo'] for t in seq['video_tracks']),'Native panel master track visibility changed')
  nested_ids=[]
  for item,cut in zip(items,spec['cuts']):
   if shots[cut['id']]['mode']!='panel-layout':continue
   nested_ids.append(item['item'])
   nested=data['project']['items'][str(item['item'])]['kind'].get('Sequence')
   require(nested,'Panel nest replaced with flattened media')
   nested_ids.extend(i['item'] for t in nested['video_tracks'] for i in t['items'])
  require(len(nested_ids)==len(set(nested_ids)),'Panel occurrences share editable sequences; preserve independent framing')
 for item,cut in zip(items,spec['cuts']):
  if shots[cut['id']]['mode']=='panel-layout':
   from filmcraft_panels import verify
   verify(data,spec,cut,item,frame_ticks);continue
  require((item['start'],item['source_in'],item['duration'])==(cut['recordFrame']*frame_ticks,cut['sourceInFrame']*frame_ticks,cut['frames']*frame_ticks),'Native framing clocks differ')
  source=next(s for s in spec['sources'] if s['id']==cut['sourceId'])
  native_source=data['project']['items'][str(item['item'])]['kind']['Media']['media']['File']['path']
  require(Path(native_source).resolve()==Path(source['path']).resolve(),'Native framing source differs')
  shot=shots[cut['id']];m=next(e['params'] for e in item['effects'] if e['effect']=='motion')
  for key,value in filmcraft_motion(spec,shot).items():
   actual=m[key]['value'];expected={'Vec2':dict(zip(['x','y'],value))} if isinstance(value,list) else {'Float':value}
   # Static coordinates cross the same JSON/Rust boundary as tracking keys.
   # Preserve shape and types; allow only sub-nanopixel round-trip noise.
   def equal(a,b):
    if isinstance(b,dict):return isinstance(a,dict) and set(a)==set(b) and all(equal(a[k],b[k]) for k in b)
    return type(a) in (int,float) and math.isfinite(a) and math.isclose(a,b,rel_tol=0,abs_tol=1e-9)
   require(equal(actual,expected),'Native framing value differs: '+key)
   require(key=='anchor' or not m[key].get('keyframes'),'Unexpected animated framing: '+key)
  keys=m['anchor'].get('keyframes',[])
  if shot['mode']=='fixed-crop':require(not keys,'Fixed crop gained tracking');continue
  require(len(keys)==len(shot['xByFrame']),'Native tracking key count differs')
  for index,(key,x) in enumerate(zip(keys,shot['xByFrame'])):
   actual=key['value'].get('Vec2',{})
   # JSON/Rust/Python round trips can differ by one floating-point ULP after
   # adding the half-width. Keep clocks/interpolation exact; tolerate only a
   # billionth of a source pixel, not visible motion or relaxed framing bounds.
   coordinates=set(actual)=={'x','y'} and all(type(actual[k]) in (int,float) and math.isfinite(actual[k]) and math.isclose(actual[k],v,rel_tol=0,abs_tol=1e-9) for k,v in [('x',x+shot['width']/2),('y',shot['y']+shot['height']/2)])
   require(key['time']==(cut['sourceInFrame']+index)*frame_ticks and key['interp']=='Linear' and coordinates,'Native tracking clock/curve differs')
