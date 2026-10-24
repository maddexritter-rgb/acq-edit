"""Execute reviewed source-local framing with native Fusion controls, never detect faces."""
from pathlib import Path
from common import require
from framing_plan import fusion_crop,require_static_fusion_crop


def track_positions(shot):
 import math
 return [.5+(math.floor(shot['x'])-x)/shot['sourceWidth'] for x in shot['xByFrame']]


def verify_linear_keys(keys,start,values):
 require(set(keys)=={start+i for i in range(len(values))},'Native X tracking frame coverage changed')
 for i,value in enumerate(values):
  key=keys[start+i];flags=key.get('Flags',{})
  require(abs(key[1]-value)<1e-9,'Native X tracking value changed')
  require(set(key)<=set([1,'Flags','LH','RH']) and set(flags)<=set(['Linear','LockedY']),'Unsupported native tracking key behavior')
  require('Linear' not in flags or flags['Linear'] is True,'Native X tracking interpolation changed')
  # Studio returns linear keys as relative one-third Bezier handles and may
  # omit the Linear flag. Verify the actual geometry, not the flag alone.
  for handle,neighbor in [('LH',i-1),('RH',i+1)]:
   if not 0<=neighbor<len(values):
    require(handle not in key,'Unexpected end tracking handle');continue
   if handle not in key:
    require(flags.get('Linear') is True,'Native tracking lost its linear handle');continue
   expected={1:(neighbor-i)/3,2:(values[neighbor]-value)/3}
   require(set(key[handle])=={1,2} and all(abs(key[handle][j]-expected[j])<1e-9 for j in [1,2]),'Native tracking easing changed')


def write_tracking(comp,crop,shot):
 if shot['mode']!='tracked-crop':return
 require(not comp.FindTool('ACQ_FramingTrack'),'Owned tracking node exists; reconcile before construction')
 source=crop.Input.GetConnectedOutput();require(source,'Tracking source missing')
 transform=comp.AddTool('Transform');path=comp.XYPath();spline=comp.BezierSpline()
 require(transform and path and spline,'Native framing controls unavailable')
 # Native modifier naming on reopen follows the parent input. Match it now
 # without a custom-name flag; do not normalize away real graph changes.
 transform.SetAttrs({'TOOLS_Name':'ACQ_FramingTrack'});path.SetAttrs({'TOOLS_Name':'ACQ_FramingPath'});spline.SetAttrs({'TOOLS_Name':'ACQ_FramingPathX','TOOLB_NameSet':False})
 transform.Center=path;path.X=spline;path.Y.ConnectTo(None);path.SetInput('Y',.5)
 for key,value in {'Size':1,'Angle':0,'Aspect':1}.items():transform.SetInput(key,value)
 start=comp.GetAttrs()['COMPN_RenderStart']
 spline.SetKeyFrames({start+i:{1:x,'Flags':{'Linear':True}} for i,x in enumerate(track_positions(shot))},True)
 transform.ConnectInput('Input',source.GetTool());crop.ConnectInput('Input',transform)
 verify_comp(comp,crop,shot)


def verify_comp(comp,crop,shot):
 fields=fusion_crop({},shot)
 require(crop.GetAttrs()['TOOLS_RegID']=='Crop','Owned framing crop type changed')
 require_static_fusion_crop(crop,fields)
 for key in fields:require(crop.GetInput(key)==fields[key],'Native framing property changed: '+key)
 if shot['mode']=='tracked-crop':
  transform=comp.FindTool('ACQ_FramingTrack');require(transform and transform.GetAttrs()['TOOLS_RegID']=='Transform','Native tracking transform missing')
  require(not transform.Center.GetExpression(),'Tracking expression replaced native keys')
  output=transform.Center.GetConnectedOutput();require(output,'Native tracking path disconnected')
  path=output.GetTool();require(path.GetAttrs()['TOOLS_RegID']=='XYPath' and path.GetAttrs()['TOOLS_Name']=='ACQ_FramingPath','Unexpected native tracking path')
  require_static_fusion_crop(path,['Y']);require(path.GetInput('Y')==.5,'Tracking Y changed')
  require(not path.X.GetExpression(),'Tracking expression replaced native keys')
  output=path.X.GetConnectedOutput();require(output,'Native X tracking disconnected')
  spline=output.GetTool();attrs=spline.GetAttrs()
  require(attrs['TOOLS_RegID']=='BezierSpline' and attrs['TOOLS_Name']=='ACQ_FramingPathX','Unexpected tracking driver; preserve manual edits')
  start=comp.GetAttrs()['COMPN_RenderStart'];xs=track_positions(shot);verify_linear_keys(spline.GetKeyFrames(),start,xs)
  for key,value in {'Size':1,'Angle':0,'Aspect':1}.items():
   require_static_fusion_crop(transform,[key]);require(transform.GetInput(key)==value,'Native tracking transform changed: '+key)
  for i in sorted(set([0,len(xs)//2,len(xs)-1])):
   point=transform.GetInput('Center',start+i)
   require(abs(point[1]-xs[i])<1e-9 and point[2]==.5,'Native X tracking evaluation differs')
  source=crop.Input.GetConnectedOutput();require(source and source.GetTool().GetAttrs()['TOOLS_Name']=='ACQ_FramingTrack','Crop lost tracking input')
  source=transform.Input.GetConnectedOutput();require(source and source.GetTool().GetAttrs()['TOOLS_RegID']=='MediaIn','Native tracking source changed')


def verify_timeline(timeline,spec):
 shots=spec.get('framing',{}).get('shots',{})
 if not shots:return
 items=timeline.GetItemListInTrack('video',1);require(len(items)==len(spec['cuts']),'Native framing picture coverage differs')
 require(timeline.GetIsTrackEnabled('video',1),'Framed picture track disabled')
 for item,cut in zip(items,spec['cuts']):
  require(item.GetClipEnabled() and (item.GetStart(True),item.GetLeftOffset(True),item.GetDuration(True))==(cut['recordFrame'],cut['sourceInFrame'],cut['frames']),'Native framing source clocks changed')
  source=next(s for s in spec['sources'] if s['id']==cut['sourceId'])
  require(Path(item.GetMediaPoolItem().GetClipProperty('File Path')).resolve()==Path(source['path']).resolve(),'Native framing source changed')
  require(item.GetFusionCompCount()==1,'Expected one owned framing composition')
  comp=item.GetFusionCompByIndex(1);crop=comp.FindTool('ACQ_FramingCrop');resize=comp.FindTool('ACQ_FramingResize')
  require(crop and resize,'Owned framing graph missing');verify_comp(comp,crop,shots[cut['id']])
  for key,value in {'KeepAspect':0,'Width':spec['width'],'Height':spec['height']}.items():
   require_static_fusion_crop(resize,[key]);require(resize.GetInput(key)==value,'Native output framing dimensions changed')
  link=resize.Input.GetConnectedOutput();require(link and link.GetTool().GetAttrs()['TOOLS_Name']=='ACQ_FramingCrop','Native resize source changed')
  if shots[cut['id']]['mode']=='fixed-crop':
   source=crop.Input.GetConnectedOutput();require(source and source.GetTool().GetAttrs()['TOOLS_RegID']=='MediaIn','Native crop source changed')


def revise_tracking(comp,previous,current):
 crop=comp.FindTool('ACQ_FramingCrop');require(crop,'Owned framing crop missing')
 verify_comp(comp,crop,previous)
 spline=comp.FindTool('ACQ_FramingPathX');start=comp.GetAttrs()['COMPN_RenderStart']
 crop.SetInput('XOffset',fusion_crop({},current)['XOffset'])
 spline.SetKeyFrames({start+i:{1:x,'Flags':{'Linear':True}} for i,x in enumerate(track_positions(current))},True)
 verify_comp(comp,crop,current)
