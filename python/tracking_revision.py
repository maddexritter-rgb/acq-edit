"""Narrow X-curve revision contract; horizontal-to-vertical owns the new decision."""
import copy
from common import inside,require,sha,plan,fingerprint
from fusion_state import canonical_fusion,field,remove_field


def compare_plans(previous,current,cut_ids):
 require(isinstance(cut_ids,list) and cut_ids and len(cut_ids)==len(set(cut_ids)),'Select unique cut IDs for tracking revision')
 require({k:v for k,v in previous.items() if k!='framing'}=={k:v for k,v in current.items() if k!='framing'},'Tracking revision cannot change cuts, captions, audio, graphics, sources or other plan fields')
 old,new=previous.get('framing',{}),current.get('framing',{})
 require(old.get('schema')==new.get('schema')=='acq-edit/framing-v1','Both plans need a framing handoff')
 require(old['receiptSha256']!=new['receiptSha256'],'Tracking revision needs a fresh owning-skill decision receipt')
 require(set(old['shots'])==set(new['shots']) and set(cut_ids)<=set(old['shots']),'Tracking target coverage differs')
 for cut_id,shot in old['shots'].items():
  after=new['shots'][cut_id]
  if cut_id not in cut_ids:require(shot==after,'Unselected framing changed');continue
  require(shot['mode']==after['mode']=='tracked-crop','Tracking revision requires existing native tracked crops')
  unchanged=lambda s:{k:v for k,v in s.items() if k not in ['x','xByFrame']}
  require(unchanged(shot)==unchanged(after),'Tracking revision preserves source binding, Y, scale and crop size')
  require(shot['xByFrame']!=after['xByFrame'],'Selected tracking curve has no change')


def prepare(project,packet):
 old_path=inside(project['root'],packet['previousPlan'])
 require(sha(old_path)==packet['previousPlanSha256'],'Previous published plan changed')
 previous=plan(project,{'plan':str(old_path)});current=plan(project,packet)
 compare_plans(previous,current,packet['cutIds'])
 return previous,current


def protected_filmcraft(data,cut_ids,spec,destination_name=None):
 value=copy.deepcopy(data['project'])
 # FilmCraft derives these two document labels from the destination basename
 # when opening a copied project. Bind their expected value, never omit them.
 if destination_name is not None:value['name']=destination_name;value['root']['name']=destination_name
 sequence_id=str(data['view']['active_sequence']);seq=value['items'][sequence_id]['kind']['Sequence']
 require(len(seq['video_tracks'][0]['items'])==len(spec['cuts']),'Tracking picture coverage differs')
 for item,cut in zip(seq['video_tracks'][0]['items'],spec['cuts']):
  if cut['id'] not in cut_ids:continue
  motion=next(e['params'] for e in item['effects'] if e['effect']=='motion')
  # Only the reviewed anchor values/keys may differ. All source, audio, caption,
  # effect, track, project and sequence data remain in this comparison.
  motion['anchor'].pop('value');motion['anchor'].pop('keyframes')
 return fingerprint({'activeSequence':sequence_id,'project':value})


def protected_fusion(text):
 value=canonical_fusion(text);tools=field(value['composition'],'Tools')
 crop=field(tools,'ACQ_FramingCrop');spline=field(tools,'ACQ_FramingPathX')
 require(crop and crop.get('constructor')=='Crop' and spline and spline.get('constructor')=='BezierSpline','Owned tracking graph required for protected comparison')
 x=field(field(crop,'Inputs'),'XOffset')
 require(x and x.get('constructor')=='Input' and field(x,'Value') is not None and field(spline,'KeyFrames') is not None,'Owned tracking values missing')
 remove_field(x,'Value');remove_field(spline,'KeyFrames')
 return fingerprint(value)
