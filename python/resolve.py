"""Native Resolve Studio 21.1 adapter. Imports only the selected editor's API.

No foreign-editor conversion, FilmCraft runtime or flattened cross-editor output.
All timings read back before a render can be accepted. Unqualified host versions fail closed.
"""
import time,math,tempfile
from pathlib import Path
from common import *
from audio_plan import resolve_music_frames,same_native_frame
from resolve_framing import write_tracking,verify_timeline as verify_framing
from framing_plan import fusion_crop,require_static_fusion_crop
from resolve_precision import patch_checkpoint
from fusion_state import fusion_hash,SCHEMA as FUSION_STATE_SCHEMA
from resolve_sources import verify_timeline as verify_source_clocks,read_clocks,pin_new_copy
class Adapter:
 def __init__(self,config):self.config=config
 def connect(self):
  import DaVinciResolveScript
  r=DaVinciResolveScript.scriptapp('Resolve');require(r,'Resolve is disconnected. Start Studio and enable External scripting: Local.')
  require(r.IsStudio(),'DaVinci Resolve Studio required');require(r.GetVersionString().startswith('21.1.'),'This adapter is qualified against the 21.1 API; review installed scripting docs for other versions')
  return r
 def doctor(self):
  r=self.connect();p=r.GetProjectManager().GetCurrentProject();return {'backend':'resolve','connected':True,'version':r.GetVersionString(),'studio':r.IsStudio(),'currentProject':p.GetName() if p else None,'samplePrecision':{'available':r.GetVersion()[:4]==[21,1,1,10],'route':'new native DRT checkpoint with exact import/readback'},'nativeAcceptance':'mechanical fixtures verified; real editorial and pilot acceptance remain pending'}
 def selected(self,project):
  self.project_root=Path(project['root']);r=self.connect();p=r.GetProjectManager().GetCurrentProject();require(p and p.GetName()=='ACQ_'+project['id'],'Open this toolkit project in Resolve. Never switch or mutate an unrelated project implicitly.');return r,p
 def fusion_fingerprints(self,item):
  results=[]
  root=self.project_root/'10_WORK';root.mkdir(parents=True,exist_ok=True)
  with tempfile.TemporaryDirectory(prefix='fusion-inspect-',dir=root) as folder:
   for index in range(1,item.GetFusionCompCount()+1):
    comp=item.GetFusionCompByIndex(index);require(comp,'Fusion comp missing');before=read_clocks(comp);output=Path(folder)/f'{index}.comp';require(item.ExportFusionComp(str(output),index),'Cannot inspect native Fusion graph');require(read_clocks(comp)==before,'Fusion inspection changed live source clocks; preserve the timeline and reconcile');results.append(fusion_hash(output.read_text(encoding='utf-8')))
  return results
 def snapshot(self,p):
  t=p.GetCurrentTimeline();require(t,'No current timeline');tracks={};track_state={}
  def item_state(item):
   source=item.GetMediaPoolItem()
   return {'id':item.GetUniqueId(),'name':item.GetName(),'start':item.GetStart(True),'end':item.GetEnd(True),'left':item.GetLeftOffset(True),'duration':item.GetDuration(True),'properties':item.GetProperties(),'enabled':item.GetClipEnabled(),'source':source.GetUniqueId() if source else None,'sourcePath':source.GetClipProperty('File Path') if source else None,'fusion':self.fusion_fingerprints(item),'fades':item.GetFades(),'linkedIds':sorted(j.GetUniqueId() for j in (item.GetLinkedItems() or []))}
  for kind in ['video','audio']:
   tracks[kind]=[[item_state(i) for i in t.GetItemListInTrack(kind,n) or []] for n in range(1,t.GetTrackCount(kind)+1)]
   track_state[kind]=[{'enabled':t.GetIsTrackEnabled(kind,n),'locked':t.GetIsTrackLocked(kind,n)} for n in range(1,t.GetTrackCount(kind)+1)]
  return {'project':p.GetName(),'timeline':t.GetUniqueId(),'name':t.GetName(),'settings':t.GetSettings(),'fusionFingerprintSchema':FUSION_STATE_SCHEMA,'tracks':tracks,'trackState':track_state,'markers':t.GetMarkers()}
 def inspect(self,project,packet):
  r,p=self.selected(project)
  if p.GetCurrentTimeline():state=self.snapshot(p)
  else:
   from resolve_project import inspect_without_timeline
   state=inspect_without_timeline(p)
  return {'state':state,'fingerprint':fingerprint(state),'version':r.GetVersionString()}
 def build(self,project,packet):
  self.project_root=Path(project['root']);spec=plan(project,packet)
  require(not spec.get('hookContract'),'Add a prepared hook to its inspected finished native base; do not rebuild that base')
  caption_prepared=None
  if spec.get('captionContract'):
   from caption_plan import validate
   caption_prepared=validate(project,spec)
  for key in ['nativeProject','inspection']:require(not inside(project['root'],packet[key]).exists(),'Native build checkpoint/inspection exists; reconcile before retrying')
  r=self.connect();pm=r.GetProjectManager();current=pm.GetCurrentProject();name='ACQ_'+project['id']
  if caption_prepared:
   from resolve_captions import verify_fonts
   verify_fonts(r,caption_prepared)
  precise=any(value*spec['fps']['numerator']%(spec['sampleRate']*spec['fps']['denominator']) for cut in spec['cuts'] for value in [cut['audioInSample'],cut['audioSamples']])
  if precise:require(r.GetVersion()[:4]==[21,1,1,10],'Native sample geometry is qualified only for Resolve Studio 21.1.1 build 10; review the installed archive/API before changing this gate')
  if precise:require(all(c.get('audioSourceId') and 'audioRecordSample' in c for c in spec['cuts']),'Native precision needs compiled paired-source cuts')
  require(not current or current.GetName()==name,'Another Resolve project is open. Close it before creating this isolated project.');p=current or pm.CreateProject(name);require(p,'Could not create native Resolve project')
  timeline_name=spec['title']+'_'+packet['versionId'];names={p.GetTimelineByIndex(i).GetName() for i in range(1,p.GetTimelineCount()+1)}
  require(timeline_name not in names and timeline_name+'_precise' not in names,'Native timeline name exists; use a fresh version identity after inspecting the prior operation')
  for bed in spec.get('audio',{}).get('music',[]):resolve_music_frames(spec,bed)
  require(spec['width']>=256 and spec['height']>=256,'Resolve clamps timeline dimensions below 256 pixels; choose a supported output size')
  fps=spec['fps']['numerator']/spec['fps']['denominator'];require(p.SetSettings({'timelineFrameRate':str(fps),'timelineResolutionWidth':str(spec['width']),'timelineResolutionHeight':str(spec['height'])}),'Could not configure native project')
  pool=p.GetMediaPool();timeline=pool.CreateEmptyTimeline(timeline_name);require(timeline and p.SetCurrentTimeline(timeline),'Could not create selected timeline');require(timeline.SetStartTimecode('00:00:00:00'),'Could not set timeline clock')
  timeline.SetSettings({'useCustomSettings':'1'});timeline.SetSettings({'timelineResolutionWidth':str(spec['width']),'timelineResolutionHeight':str(spec['height'])});settings=timeline.GetSettings();require(int(settings['timelineResolutionWidth'])==spec['width'] and int(settings['timelineResolutionHeight'])==spec['height'] and abs(float(settings['timelineFrameRate'])-fps)<1e-6,'Native timeline geometry readback mismatch')
  sources={}
  for s in spec['sources']:
   items=pool.ImportMedia([s['path']]);require(items and len(items)==1,'Native source import failed');sources[s['id']]=items[0]
  pairs=[]
  for cut in spec['cuts']:
   media=sources[cut['sourceId']];video=pool.AppendToTimeline([{'mediaPoolItem':media,'startFrame':cut['sourceInFrame'],'endFrame':cut['sourceInFrame']+cut['frames'],'recordFrame':cut['recordFrame'],'mediaType':1,'trackIndex':1}]);require(video and len(video)==1,'Picture placement failed')
   astart=cut['audioInSample']*fps/spec['sampleRate'];aduration=cut['audioSamples']*fps/spec['sampleRate']
   arecord=cut['audioRecordSample']*fps/spec['sampleRate'] if 'audioRecordSample' in cut else cut['recordFrame']
   if precise:astart,aduration,arecord=cut['sourceInFrame'],cut['frames'],cut['recordFrame']
   audio=pool.AppendToTimeline([{'mediaPoolItem':sources[cut.get('audioSourceId',cut['sourceId'])],'startFrame':astart,'endFrame':astart+aduration,'recordFrame':arecord,'mediaType':2,'trackIndex':1}]);require(audio and len(audio)==1,'Audio placement failed')
   vi,ai=video[0],audio[0]
   for item,start,duration,record in [(vi,cut['sourceInFrame'],cut['frames'],cut['recordFrame']),(ai,astart,aduration,arecord)]:
    require(abs(item.GetStart(True)-record)<1e-6 and abs(item.GetDuration(True)-duration)<1e-6 and abs(item.GetLeftOffset(True)-start)<1e-6,'Native cut readback differs from precision plan; preserve evidence, do not round')
   require(timeline.SetClipsLinked([vi,ai],True),'Could not link picture/audio');pairs.append((cut,vi,ai))
  if precise:
   checkpoint=inside(project['root'],packet['nativeProject']);frame_checkpoint=checkpoint.with_suffix('.frame.drt');sample_checkpoint=checkpoint.with_suffix('.precision.drt')
   require(not frame_checkpoint.exists() and not sample_checkpoint.exists(),'Precision construction paths exist; reconcile before retrying')
   require(timeline.Export(str(frame_checkpoint),r.EXPORT_DRT),'Native frame checkpoint export failed')
   proof=patch_checkpoint(frame_checkpoint,sample_checkpoint,spec);save(checkpoint.with_suffix('.precision.json'),proof)
   imported=pool.ImportTimelineFromFile(str(sample_checkpoint));require(imported and p.SetCurrentTimeline(imported),'Native precision checkpoint import failed');timeline=imported;require(timeline.SetName(spec['title']+'_'+packet['versionId']+'_precise'),'Native precision timeline naming failed')
   videos=timeline.GetItemListInTrack('video',1);audios=timeline.GetItemListInTrack('audio',1);require(len(videos)==len(audios)==len(spec['cuts']),'Imported source coverage differs');pairs=[]
   for cut,vi,ai in zip(spec['cuts'],videos,audios):
    for item,source_id,start,length,record in [(vi,cut['sourceId'],cut['sourceInFrame'],cut['frames'],cut['recordFrame']),(ai,cut['audioSourceId'],cut['audioInSample']*fps/spec['sampleRate'],cut['audioSamples']*fps/spec['sampleRate'],cut['audioRecordSample']*fps/spec['sampleRate'])]:
     source=next(s for s in spec['sources'] if s['id']==source_id);require(Path(item.GetMediaPoolItem().GetClipProperty('File Path')).resolve()==Path(source['path']).resolve(),'Imported source identity differs')
     require(max(abs(item.GetStart(True)-record),abs(item.GetLeftOffset(True)-start),abs(item.GetDuration(True)-length))*spec['sampleRate']/fps<.001,'Imported timing differs from exact paired samples')
    require(abs((vi.GetStart(True)-vi.GetLeftOffset(True))-(ai.GetStart(True)-ai.GetLeftOffset(True)))*spec['sampleRate']/fps<.001,'Imported source clocks differ')
    require(timeline.SetClipsLinked([vi,ai],True),'Native precision AV linkage failed');require(ai.GetUniqueId() in [i.GetUniqueId() for i in vi.GetLinkedItems()],'Native link readback failed');pairs.append((cut,vi,ai))
   settings=timeline.GetSettings();require(int(settings['timelineResolutionWidth'])==spec['width'] and int(settings['timelineResolutionHeight'])==spec['height'] and abs(float(settings['timelineFrameRate'])-fps)<1e-6,'Imported native geometry differs')
  if precise:save(checkpoint.with_suffix('.precision-readback.json'),{'status':'native-import-ranges-sources-and-links-verified','timelineId':timeline.GetUniqueId(),'cuts':[{'cutId':cut['id'],'videoId':vi.GetUniqueId(),'audioId':ai.GetUniqueId(),'sourceInSample':cut['audioInSample'],'audioRecordSample':cut['audioRecordSample'],'audioSamples':cut['audioSamples']} for cut,vi,ai in pairs]})
  for cut,vi,ai in pairs:
   shot=spec.get('framing',{}).get('shots',{}).get(cut['id'])
   audio_props={'AudioVolumeEnabled':True,'AudioVolume':spec.get('audio',{}).get('gainDb',0),**spec.get('audio',{}).get('properties',{})}
   if audio_props:
    require(ai.SetProperties(audio_props),'Native audio treatment failed')
    actual=ai.GetProperties()
    for key,value in audio_props.items():require(actual.get(key)==value,'Native audio treatment readback mismatch: '+key)
   cards=[c for c in spec.get('captions',[]) if c['startFrame']<cut['recordFrame']+cut['frames'] and c['endFrame']>cut['recordFrame']]
   if cards or shot:self.compose(vi,cut,cards,spec,shot,caption_prepared,sources)
  for index,graphic in enumerate(spec.get('graphics',[])):
   require(sha(graphic['path'])==graphic['sha256'],'Graphic hash mismatch');media=pool.ImportMedia([graphic['path']]);require(media,'Graphic import failed')
   while timeline.GetTrackCount('video')<index+2:require(timeline.AddTrack('video'),'Cannot add graphics track')
   placed=pool.AppendToTimeline([{'mediaPoolItem':media[0],'startFrame':0,'endFrame':graphic['frames'],'recordFrame':graphic['startFrame'],'mediaType':1,'trackIndex':index+2}]);require(placed and len(placed)==1,'Graphics placement failed');item=placed[0]
   require(item.GetStart(True)==graphic['startFrame'] and item.GetDuration(True)==graphic['frames'] and item.GetLeftOffset(True)==0 and Path(item.GetMediaPoolItem().GetClipProperty('File Path')).resolve()==Path(graphic['path']).resolve(),'Native graphic source/timing readback mismatch')
  self.music(timeline,pool,sources,spec)
  verify_source_clocks(timeline,spec);verify_framing(timeline,spec)
  if caption_prepared:
   from resolve_captions import verify_timeline
   verify_timeline(timeline,spec,caption_prepared)
  require(pm.SaveProject(),'Native save failed');state=self.snapshot(p);save(inside(project['root'],packet['inspection']),state);native=inside(project['root'],packet['nativeProject']);require(not native.exists(),'Native checkpoint exists');require(pm.ExportProject(name,str(native),False),'Native DRP checkpoint failed')
  return {'nativeProject':str(native),'fingerprint':fingerprint(state),'timelineId':timeline.GetUniqueId(),'status':'native-built-awaiting-render'}
 def music(self,timeline,pool,sources,spec):
  for bed in spec.get('audio',{}).get('music',[]):
   timing=resolve_music_frames(spec,bed)
   while timeline.GetTrackCount('audio')<2:require(timeline.AddTrack('audio','stereo'),'Cannot add native music track')
   placed=pool.AppendToTimeline([{'mediaPoolItem':sources[bed['sourceId']],'mediaType':2,'trackIndex':2,'startFrame':timing['sourceInSample'],'endFrame':timing['sourceInSample']+timing['samples'],'recordFrame':bed['startFrame']}])
   require(placed and len(placed)==1,'Native music placement failed');item=placed[0]
   require(all(same_native_frame(a,b) for a,b in zip([item.GetStart(True),item.GetLeftOffset(True),item.GetDuration(True)],[bed['startFrame'],timing['sourceInSample'],timing['samples']])),'Native music timing readback mismatch')
   require(item.SetProperties({'AudioVolumeEnabled':True,'AudioVolume':bed['gainDb']}),'Native music gain failed')
   require(abs(item.GetProperties()['AudioVolume']-bed['gainDb'])<1e-6,'Native music gain readback mismatch')
   fades={'FadeIn':timing['fadeInSamples'],'FadeOut':timing['fadeOutSamples']}
   require(item.SetFades(fades),'Native music fades failed');actual=item.GetFades()
   require(all(actual.get(key)==value for key,value in fades.items()),'Native music fade readback mismatch')
 def compose(self,item,cut,cards,spec,shot=None,caption_prepared=None,sources=None):
  require(item.GetFusionCompCount()==0,'Existing Fusion comp must be merged rather than replaced');comp=item.AddFusionComp();require(comp,'Fusion unavailable');nodes=comp.GetToolList(False);source=next((n for n in nodes.values() if n.GetAttrs()['TOOLS_RegID']=='MediaIn'),None);output=next((n for n in nodes.values() if n.GetAttrs()['TOOLS_RegID']=='MediaOut'),None);require(source and output,'Fusion media endpoints missing')
  if shot and shot['mode']=='panel-layout':
   from resolve_panels import construct
   require(sources,'Panel Media Pool source bindings required')
   # The native pool inputs are the complete picture graph. Retaining the
   # disconnected default Timeline input adds unused, unstable loader state.
   original_name=source.GetAttrs()['TOOLS_Name'];source.Delete()
   require(not comp.FindTool(original_name),'Unused timeline input was not removed')
   source=construct(comp,spec,cut,shot,sources)
  elif shot:
   crop=comp.AddTool('Crop');resize=comp.AddTool('BetterResize');require(crop and resize,'Native Fusion framing nodes unavailable')
   crop.SetAttrs({'TOOLS_Name':'ACQ_FramingCrop'});resize.SetAttrs({'TOOLS_Name':'ACQ_FramingResize'})
   for key,value in fusion_crop(spec,shot).items():crop.SetInput(key,value);require(crop.GetInput(key)==value,'Native crop readback mismatch: '+key)
   for key,value in {'KeepAspect':0,'Width':spec['width'],'Height':spec['height']}.items():resize.SetInput(key,value);require(resize.GetInput(key)==value,'Native resize readback mismatch: '+key)
   crop.ConnectInput('Input',source);resize.ConnectInput('Input',crop);source=resize
   write_tracking(comp,crop,shot)
  if caption_prepared:
   from resolve_captions import construct
   construct(comp,source,output,cut,spec,caption_prepared)
   return
  for index,card in enumerate(cards):
   text=comp.AddTool('TextPlus');merge=comp.AddTool('Merge');require(text and merge,'Fusion text/merge unavailable');text.SetAttrs({'TOOLS_Name':f'ACQ_Caption_{index}'});style=card['style'];text.SetInput('UseFrameFormatSettings',0);text.SetInput('Width',spec['width']);text.SetInput('Height',spec['height']);text.SetInput('StyledText',card['text']);text.SetInput('Font',style.get('font','Arial'));text.SetInput('Size',style.get('fusionSize',style.get('size',64)/spec['width']));text.SetInput('Center',{1:.5,2:style.get('centerY',.22)})
   merge.ConnectInput('Background',source);merge.ConnectInput('Foreground',text)
   # Fusion source clock must be inspected for each media type; no timeline-clock assumptions.
   start=comp.GetAttrs()['COMPN_RenderStart']+max(0,card['startFrame']-cut['recordFrame']);end=comp.GetAttrs()['COMPN_RenderStart']+min(cut['frames'],card['endFrame']-cut['recordFrame'])
   merge.Blend.SetExpression(f'iif(time >= {start} and time < {end}, 1, 0)');source=merge
  output.ConnectInput('Input',source)
 def revise(self,project,packet):
  if packet.get('kind')=='text-hook-remove':return self.remove_hook(project,packet)
  if packet.get('kind')=='text-hook':return self.revise_hook(project,packet)
  if packet.get('kind')=='music-replacement':return self.revise_music(project,packet)
  if packet.get('kind')=='graphic-replacement':return self.revise_graphics(project,packet)
  if packet.get('kind')=='panel-framing':return self.revise_panels(project,packet)
  if packet.get('kind')=='tracking-framing':return self.revise_tracking(project,packet)
  if packet.get('kind')=='spoken-recut':
   from recut_execution import prepare,record
   prepared=prepare(project,packet);r,p=self.selected(project)
   require(not p.IsRenderingInProgress(),'Resolve is rendering; recut must wait')
   before=self.snapshot(p);require(fingerprint(before)==prepared['expected'],'Published parent native state changed; reconcile user edits before recutting')
   original=p.GetCurrentTimeline();built=self.build(project,packet['construction']);current=p.GetCurrentTimeline()
   require(current and current.GetUniqueId()==built['timelineId'],'Current timeline changed during recut; reconcile before switching')
   require(p.SetCurrentTimeline(original),'Cannot inspect preserved parent timeline')
   try:require(fingerprint(self.snapshot(p))==prepared['expected'],'Parent changed during recut; preserve new work for reconciliation')
   finally:
    require(p.GetCurrentTimeline().GetUniqueId()==original.GetUniqueId(),'Timeline changed during parent inspection; reconcile before switching')
    require(p.SetCurrentTimeline(current),'Cannot restore newly constructed timeline')
   require(fingerprint(self.snapshot(p))==built['fingerprint'],'New recut changed during parent verification')
   return record(project,packet,prepared,built)
  r,p=self.selected(project);before=self.snapshot(p);require(fingerprint(before)==packet['expectedFingerprint'],'Native state changed; inspect and merge user edits')
  require(packet['kind'] in ['caption-style','music-gain','fixed-framing'],'Spoken recuts require a new reviewed Assembly Design plan and new timeline; no partial dependent-layer edits')
  spec=plan(project,packet) if packet['kind']=='fixed-framing' or (packet['kind']=='caption-style' and packet.get('plan')) else None
  if spec:verify_source_clocks(p.GetCurrentTimeline(),spec)
  caption_prepared=None
  if spec and spec.get('captionContract'):
   from caption_plan import validate
   from resolve_captions import verify_fonts
   caption_prepared=validate(project,spec);verify_fonts(r,caption_prepared)
  if spec:require(int(before['settings']['timelineResolutionWidth'])==spec['width'] and int(before['settings']['timelineResolutionHeight'])==spec['height'],'Framing revision cannot resize the approved timeline')
  if packet['kind']=='fixed-framing':
   from resolve_panels import preflight_fixed_revision
   preflight_fixed_revision(p.GetCurrentTimeline(),spec,packet['edits'])
  original=p.GetCurrentTimeline();copy=original.DuplicateTimeline(packet['title']);require(copy and p.SetCurrentTimeline(copy),'Cannot preserve prior timeline before revision')
  pin_new_copy(original,copy,spec)
  for edit in packet['edits']:
   if packet['kind']=='caption-style':
    items=copy.GetItemListInTrack('video',edit['track']);require(0<=edit['itemIndex']<len(items),'Caption target absent');comp=items[edit['itemIndex']].GetFusionCompByIndex(edit['compIndex']);require(comp,'Caption Fusion comp absent');tool=comp.FindTool(edit['tool']);require(tool and edit['tool'].startswith('ACQ_Caption_'),'Only ACQ-owned caption nodes may be edited')
    for key,value in edit['inputs'].items():require(key in ['StyledText','Font','Size','Center','Style','Red1','Green1','Blue1'],'Unsupported caption property');tool.SetInput(key,value);actual=tool.GetInput(key);require(abs(actual-value)<1e-6 if isinstance(value,(int,float)) else actual==value,'Fusion input readback mismatch')
   elif packet['kind']=='fixed-framing':
    require(edit['track']==1,'Fixed framing targets the primary picture track');cut=next((c for c in spec['cuts'] if c['id']==edit['cutId']),None);require(cut,'Framing cut absent from plan')
    items=copy.GetItemListInTrack('video',1);require(0<=edit['itemIndex']<len(items),'Framing target absent');item=items[edit['itemIndex']]
    require(item.GetStart(True)==cut['recordFrame'] and item.GetLeftOffset(True)==cut['sourceInFrame'] and item.GetDuration(True)==cut['frames'],'Framing target range changed')
    source=next(s for s in spec['sources'] if s['id']==cut['sourceId']);require(Path(item.GetMediaPoolItem().GetClipProperty('File Path')).resolve()==Path(source['path']).resolve(),'Framing target source differs')
    comp=item.GetFusionCompByIndex(1);require(comp,'Native framing comp missing');crop=comp.FindTool('ACQ_FramingCrop');require(crop,'Owned native crop missing; do not replace an unrelated graph')
    require(spec['framing']['shots'][cut['id']]['mode']=='fixed-crop' and not comp.FindTool('ACQ_FramingTrack'),'Use a tracking revision for animated framing; fixed-framing never discards a curve')
    geometry=fusion_crop(spec,spec['framing']['shots'][cut['id']]);require_static_fusion_crop(crop,geometry)
    for key,value in geometry.items():crop.SetInput(key,value);require(crop.GetInput(key)==value,'Framing revision readback mismatch: '+key)
   else:
    require(edit['track']==2,'Music revisions target the inspected music track only');items=copy.GetItemListInTrack('audio',2);require(0<=edit['itemIndex']<len(items),'Music target absent');item=items[edit['itemIndex']]
    delta=edit['deltaDb'];require(isinstance(delta,(int,float)) and math.isfinite(delta) and -60<=delta<=12,'Invalid music gain delta')
    wanted=item.GetProperties()['AudioVolume']+delta;require(-60<=wanted<=12,'Music gain exceeds supported range');require(item.SetProperties({'AudioVolumeEnabled':True,'AudioVolume':wanted}),'Music gain revision failed');require(abs(item.GetProperties()['AudioVolume']-wanted)<1e-6,'Music gain revision readback mismatch')
  after=self.snapshot(p)
  before_cuts=[(i['start'],i['end'],i['left'],i['source']) for kind in ['video','audio'] for track in before['tracks'][kind] for i in track];after_cuts=[(i['start'],i['end'],i['left'],i['source']) for kind in ['video','audio'] for track in after['tracks'][kind] for i in track];require(before_cuts==after_cuts,'Finishing revision changed cuts')
  if spec:verify_source_clocks(copy,spec);verify_framing(copy,spec)
  if caption_prepared:
   from resolve_captions import verify_timeline
   verify_timeline(copy,spec,caption_prepared)
  pm=r.GetProjectManager();require(pm.SaveProject(),'Save failed');native=inside(project['root'],packet['nativeProject']);require(not native.exists(),'Checkpoint exists');require(pm.ExportProject(p.GetName(),str(native),False),'Checkpoint failed');save(inside(project['root'],packet['inspection']),after);return {'nativeProject':str(native),'fingerprint':fingerprint(after),'status':'revised-native-render-pending'}
 def revise_tracking(self,project,packet):
  from tracking_revision import prepare,protected_fusion
  from resolve_framing import revise_tracking
  previous,spec=prepare(project,packet);r,p=self.selected(project)
  require(not p.IsRenderingInProgress(),'Resolve render active; tracking revision must wait')
  before=self.snapshot(p);require(fingerprint(before)==packet['expectedFingerprint'],'Native state changed; reconcile user edits before revising tracking')
  verify_framing(p.GetCurrentTimeline(),previous)
  native=inside(project['root'],packet['nativeProject']);inspection=inside(project['root'],packet['inspection'])
  require(not native.exists() and not inspection.exists(),'Tracking revision outputs exist; reconcile before retrying')
  original=p.GetCurrentTimeline();duplicate=original.DuplicateTimeline(packet['title']);require(duplicate and p.SetCurrentTimeline(duplicate),'Cannot preserve parent timeline before tracking revision')
  pin_new_copy(original,duplicate,previous)
  verify_framing(duplicate,previous)
  indices=[i for i,cut in enumerate(spec['cuts']) if cut['id'] in packet['cutIds']]
  def protected_snapshot():
   state=self.snapshot(p);items=p.GetCurrentTimeline().GetItemListInTrack('video',1)
   with tempfile.TemporaryDirectory(prefix='tracking-protected-',dir=self.project_root/'10_WORK') as folder:
    for i in indices:
     file=Path(folder)/f'{i}.comp';require(items[i].ExportFusionComp(str(file),1),'Cannot inspect protected tracking graph')
     state['tracks']['video'][0][i]['fusion']=[protected_fusion(file.read_text(encoding='utf-8'))]
   return fingerprint(state)
  protected=protected_snapshot();items=duplicate.GetItemListInTrack('video',1)
  for i in indices:
   cut_id=spec['cuts'][i]['id'];revise_tracking(items[i].GetFusionCompByIndex(1),previous['framing']['shots'][cut_id],spec['framing']['shots'][cut_id])
  verify_framing(duplicate,spec);require(protected_snapshot()==protected,'Tracking revision changed protected native data')
  after=self.snapshot(p)
  require(p.SetCurrentTimeline(original),'Cannot verify parent after tracking revision')
  try:require(fingerprint(self.snapshot(p))==packet['expectedFingerprint'],'Parent timeline changed during tracking revision')
  finally:
   require(p.GetCurrentTimeline().GetUniqueId()==original.GetUniqueId(),'Timeline changed while checking parent; reconcile')
   require(p.SetCurrentTimeline(duplicate),'Cannot restore revised tracking timeline')
  require(fingerprint(self.snapshot(p))==fingerprint(after),'Revised tracking timeline changed during parent verification')
  pm=r.GetProjectManager();require(pm.SaveProject(),'Native save failed');require(pm.ExportProject(p.GetName(),str(native),False),'Native tracking checkpoint failed');save(inspection,after)
  return {'nativeProject':str(native),'timelineId':duplicate.GetUniqueId(),'fingerprint':fingerprint(after),'status':'revised-native-render-pending'}
 def revise_panels(self,project,packet):
  from panel_revision import prepare,resolve_changes,protected_fusion,duplicate_snapshot
  from resolve_panels import revise
  previous,spec,targets=prepare(project,packet);r,p=self.selected(project)
  require(not p.IsRenderingInProgress(),'Resolve render active; panel revision must wait')
  before=self.snapshot(p);require(fingerprint(before)==packet['expectedFingerprint'],'Native state changed; reconcile user edits before revising panels')
  verify_framing(p.GetCurrentTimeline(),previous)
  native=inside(project['root'],packet['nativeProject']);inspection=inside(project['root'],packet['inspection'])
  require(not native.exists() and not inspection.exists(),'Panel revision outputs exist; reconcile before retrying')
  def copy_state():
   state=self.snapshot(p);timeline=p.GetCurrentTimeline();graphs={}
   with tempfile.TemporaryDirectory(prefix='panel-copy-',dir=self.project_root/'10_WORK') as folder:
    for kind,tracks in state['tracks'].items():
     for track,items in enumerate(tracks):
      native_items=timeline.GetItemListInTrack(kind,track+1) or []
      for index,item in enumerate(items):
       for comp in range(len(item['fusion'])):
        file=Path(folder)/f'{kind}-{track}-{index}-{comp}.comp';require(native_items[index].ExportFusionComp(str(file),comp+1),'Cannot inspect duplicated Fusion graph');graphs[(kind,track,index,comp)]=file.read_text(encoding='utf-8')
   return duplicate_snapshot(state,graphs)
  original_copy_state=copy_state()
  original=p.GetCurrentTimeline();duplicate=original.DuplicateTimeline(packet['title']);require(duplicate and p.SetCurrentTimeline(duplicate),'Cannot preserve parent timeline before panel revision')
  pin_new_copy(original,duplicate,previous)
  require(duplicate.GetName()==packet['title'] and duplicate.GetUniqueId()!=original.GetUniqueId(),'Unexpected native duplicate identity')
  require(copy_state()==original_copy_state,'Native duplication changed protected state; reconcile before editing panels')
  verify_framing(duplicate,previous)
  changes={i:resolve_changes(spec,previous['framing']['shots'][cut['id']],spec['framing']['shots'][cut['id']],targets[cut['id']]) for i,cut in enumerate(spec['cuts']) if cut['id'] in targets}
  def protected_snapshot():
   state=self.snapshot(p);items=p.GetCurrentTimeline().GetItemListInTrack('video',1)
   with tempfile.TemporaryDirectory(prefix='panel-protected-',dir=self.project_root/'10_WORK') as folder:
    for i,(fields,curves) in changes.items():
     file=Path(folder)/f'{i}.comp';require(items[i].ExportFusionComp(str(file),1),'Cannot inspect protected panel graph')
     state['tracks']['video'][0][i]['fusion']=[protected_fusion(file.read_text(encoding='utf-8'),fields,curves)]
   return fingerprint(state)
  protected=protected_snapshot();items=duplicate.GetItemListInTrack('video',1)
  for i in changes:
   cut=spec['cuts'][i];revise(items[i].GetFusionCompByIndex(1),previous,spec,cut,targets[cut['id']])
  verify_framing(duplicate,spec);require(protected_snapshot()==protected,'Panel revision changed protected native data')
  after=self.snapshot(p);require(p.SetCurrentTimeline(original),'Cannot verify parent after panel revision')
  try:require(fingerprint(self.snapshot(p))==packet['expectedFingerprint'],'Parent changed during panel revision')
  finally:
   require(p.GetCurrentTimeline().GetUniqueId()==original.GetUniqueId(),'Timeline changed while checking parent; reconcile')
   require(p.SetCurrentTimeline(duplicate),'Cannot restore revised panel timeline')
  require(fingerprint(self.snapshot(p))==fingerprint(after),'Revised panel timeline changed during parent verification')
  pm=r.GetProjectManager();require(pm.SaveProject(),'Native save failed');require(pm.ExportProject(p.GetName(),str(native),False),'Native panel checkpoint failed');save(inspection,after)
  return {'nativeProject':str(native),'timelineId':duplicate.GetUniqueId(),'fingerprint':fingerprint(after),'status':'revised-native-render-pending'}
 def revise_graphics(self,project,packet):
  from graphics_revision import prepare
  from resolve_graphics import items,inspect,protected,replace,fresh_media
  previous,spec,indices=prepare(project,packet);r,p=self.selected(project)
  require(not p.IsRenderingInProgress(),'Resolve render active; graphic revision must wait')
  before=self.snapshot(p);require(fingerprint(before)==packet['expectedFingerprint'],'Native state changed; reconcile before replacing graphics')
  original=p.GetCurrentTimeline();items(original,previous,indices);original_detail=inspect(self,p)
  fresh_media(p.GetMediaPool(),spec,indices)
  native=inside(project['root'],packet['nativeProject']);inspection=inside(project['root'],packet['inspection'])
  require(not native.exists() and not inspection.exists(),'Graphic revision outputs exist; reconcile before retrying')
  require(packet['title'] not in [p.GetTimelineByIndex(i).GetName() for i in range(1,p.GetTimelineCount()+1)],'Revision timeline name exists')
  original_copy=inspect(self,p,duplicate=True);page=r.GetCurrentPage()
  require(r.OpenPage('edit') and r.GetCurrentPage()=='edit','Resolve take replacement requires the Edit page')
  try:
   duplicate=original.DuplicateTimeline(packet['title']);require(duplicate and p.SetCurrentTimeline(duplicate),'Cannot preserve parent before graphic replacement')
   pin_new_copy(original,duplicate,previous)
   require(duplicate.GetName()==packet['title'] and duplicate.GetUniqueId()!=original.GetUniqueId(),'Unexpected duplicate identity')
   require(inspect(self,p,duplicate=True)==original_copy,'Duplication changed protected state; reconcile before replacing graphics')
   clips=items(duplicate,previous,indices);baseline=protected(inspect(self,p),indices)
   for index in indices:
    asset=spec['graphics'][index];require(sha(asset['path'])==asset['sha256'],'Replacement graphic changed')
    media=p.GetMediaPool().ImportMedia([asset['path']]);require(media and len(media)==1,'Graphic import failed')
    replace(clips[index],media[0],asset)
   items(duplicate,spec,indices);require(protected(inspect(self,p),indices)==baseline,'Graphic replacement changed protected native state')
   after=self.snapshot(p);require(p.SetCurrentTimeline(original),'Cannot verify graphic parent')
   require(inspect(self,p)==original_detail,'Parent changed during graphic replacement')
   require(p.SetCurrentTimeline(duplicate),'Cannot restore revised graphic timeline')
   require(self.snapshot(p)==after,'Revision changed during parent verification')
   pm=r.GetProjectManager();require(pm.SaveProject(),'Native save failed');require(pm.ExportProject(p.GetName(),str(native),False),'Native graphic checkpoint failed');save(inspection,after)
   return {'nativeProject':str(native),'timelineId':duplicate.GetUniqueId(),'fingerprint':fingerprint(after),'status':'revised-native-render-pending'}
  finally:
   require(r.OpenPage(page),'Cannot restore Resolve page after graphic replacement')
 def revise_music(self,project,packet):
  from music_revision import prepare
  from resolve_music import items,inspect,fresh_media,source
  from resolve_music_archive import patch_checkpoint as replace_bindings
  previous,spec,indices=prepare(project,packet);indices=sorted(indices);r,p=self.selected(project)
  require(r.GetVersion()[:4]==[21,1,1,10],'Music archive replacement is qualified only for Resolve Studio 21.1.1 build 10')
  require(not p.IsRenderingInProgress(),'Resolve render active; music revision must wait')
  before=self.snapshot(p);require(fingerprint(before)==packet['expectedFingerprint'],'Native state changed; reconcile before replacing music')
  original=p.GetCurrentTimeline();clips=items(original,previous,indices);original_detail=inspect(self,p)
  fresh_media(p.GetMediaPool(),spec,indices)
  native=inside(project['root'],packet['nativeProject']);inspection=inside(project['root'],packet['inspection']);work=inside(project['root'],packet['archiveDirectory'])
  require(not native.exists() and not inspection.exists() and not work.exists(),'Music revision outputs exist; reconcile before retrying')
  names=[p.GetTimelineByIndex(i).GetName() for i in range(1,p.GetTimelineCount()+1)];donor_name=packet['title']+' sources'
  require(packet['title'] not in names and donor_name not in names,'Revision timeline name exists')
  baseline=inspect(self,p,duplicate=True,indices=indices);page=r.GetCurrentPage();work.mkdir(parents=True)
  try:
   require(original.Export(str(work/'parent.drt'),r.EXPORT_DRT),'Cannot export native parent timeline')
   pool=p.GetMediaPool();donor=pool.CreateEmptyTimeline(donor_name);require(donor and p.SetCurrentTimeline(donor),'Cannot create native source donor')
   require(donor.SetStartTimecode('00:00:00:00'),'Cannot set source donor clock')
   for index in indices:
    asset=source(spec,index);bed=spec['audio']['music'][index];timing=resolve_music_frames(spec,bed)
    require(sha(asset['path'])==asset['sha256'],'Replacement music changed');media=pool.ImportMedia([asset['path']]);require(media and len(media)==1,'Music import failed')
    require(not media[0].GetFlagList(),'Fresh replacement source has unexpected flags')
    for flag in clips[index].GetFlagList():require(media[0].AddFlag(flag),'Cannot preserve replacement source flag')
    placed=pool.AppendToTimeline([{'mediaPoolItem':media[0],'mediaType':2,'trackIndex':1,'startFrame':timing['sourceInSample'],'endFrame':timing['sourceInSample']+timing['samples'],'recordFrame':bed['startFrame']}])
    require(placed and len(placed)==1,'Cannot construct native source donor')
   require(donor.Export(str(work/'donor.drt'),r.EXPORT_DRT),'Cannot export native donor timeline')
   require(p.SetCurrentTimeline(original) and inspect(self,p)==original_detail,'Parent changed while preparing music source')
   proof=replace_bindings(work/'parent.drt',work/'donor.drt',work/'replacement.drt',previous,spec,indices);save(work/'archive-proof.json',proof)
   revised=pool.ImportTimelineFromFile(str(work/'replacement.drt'));require(revised and p.SetCurrentTimeline(revised),'Cannot import native music replacement')
   require(revised.GetUniqueId()!=original.GetUniqueId() and revised.SetName(packet['title']),'Unexpected replacement timeline identity')
   revised_items=items(revised,spec,indices)
   for index in indices:
    require(revised_items[index].SetName(original_detail['state']['tracks']['audio'][1][index]['name']),'Cannot restore selected music clip name after native import')
   require(inspect(self,p,duplicate=True,indices=indices)==baseline,'Music replacement changed protected native state, metadata or routing')
   after=self.snapshot(p);require(p.SetCurrentTimeline(original),'Cannot verify music parent')
   require(inspect(self,p)==original_detail,'Parent changed during music replacement')
   require(p.SetCurrentTimeline(revised) and self.snapshot(p)==after,'Revision changed during parent verification')
   pm=r.GetProjectManager();require(pm.SaveProject(),'Native save failed');require(pm.ExportProject(p.GetName(),str(native),False),'Native music checkpoint failed');save(inspection,after)
   save(work/'native-readback.json',{'archiveProofSha256':sha(work/'archive-proof.json'),'fingerprint':fingerprint(after),'parentPreserved':True,'protectedStatePreserved':True})
   return {'nativeProject':str(native),'timelineId':revised.GetUniqueId(),'fingerprint':fingerprint(after),'status':'revised-native-render-pending','musicBindingProof':str(work/'native-readback.json')}
  finally:
   require(r.OpenPage(page),'Cannot restore Resolve page after music replacement')
 def remove_hook(self,project,packet):
  from hook_removal import prepare
  from resolve_hooks import verify_timeline
  from resolve_graphics import inspect
  previous,spec,prepared=prepare(project,packet);r,p=self.selected(project)
  require(not p.IsRenderingInProgress(),'Resolve is rendering; wait before hook removal')
  before=self.snapshot(p);require(fingerprint(before)==packet['expectedFingerprint'],'Native state changed; reconcile before hook removal')
  original=p.GetCurrentTimeline();verify_source_clocks(original,previous);verify_timeline(original,previous,prepared)
  track=original.GetTrackCount('video');require(track>1 and not original.GetIsTrackLocked('video',track),'Owned hook track is locked or is the only picture track')
  original_detail=inspect(self,p);baseline=inspect(self,p,duplicate=True,omit_last_video_track=True)
  native=inside(project['root'],packet['nativeProject']);inspection=inside(project['root'],packet['inspection'])
  require(not native.exists() and not inspection.exists(),'Hook removal outputs exist; reconcile before retrying')
  require(packet['title'] not in {p.GetTimelineByIndex(i).GetName() for i in range(1,p.GetTimelineCount()+1)},'Hook removal timeline name exists')
  duplicate=original.DuplicateTimeline(packet['title']);require(duplicate and p.SetCurrentTimeline(duplicate),'Cannot duplicate hook parent')
  verify_timeline(duplicate,previous,prepared)
  require(duplicate.DeleteTrack('video',track),'Native hook track removal failed')
  pin_new_copy(original,duplicate,spec)
  verify_source_clocks(duplicate,spec)
  require(inspect(self,p,duplicate=True)==baseline,'Hook removal changed protected native state or metadata')
  after=self.snapshot(p);require(p.SetCurrentTimeline(original) and inspect(self,p)==original_detail,'Hook removal changed parent timeline')
  require(p.SetCurrentTimeline(duplicate) and self.snapshot(p)==after,'New timeline changed during parent verification')
  pm=r.GetProjectManager();require(pm.SaveProject(),'Cannot save hook-free revision');require(pm.ExportProject(p.GetName(),str(native),False),'Cannot checkpoint hook-free revision');save(inspection,after)
  return {'nativeProject':str(native),'timelineId':duplicate.GetUniqueId(),'fingerprint':fingerprint(after),'status':'revised-native-render-pending'}
 def revise_hook(self,project,packet):
  from hook_plan import validate
  from resolve_hooks import font_preflight,construct,verify_timeline
  from resolve_hook_archive import append_hook
  from resolve_graphics import inspect
  spec=plan(project,packet);prepared=validate(project,spec);require(prepared,'Prepare the hook contract first')
  r,p=self.selected(project);require(r.GetVersion()[:4]==[21,1,1,10],'Native hook archive route requires qualified Resolve Studio 21.1.1 build 10')
  require(not p.IsRenderingInProgress(),'Resolve is rendering; wait before hook construction')
  receipt=read(spec['hookContract']['baseReceipt']);require(sha(inside(project['root'],receipt['nativeProject']))==receipt['nativeFingerprint'],'Base native checkpoint changed')
  before=self.snapshot(p);require(fingerprint(before)==packet['expectedFingerprint']==fingerprint(read(inside(project['root'],receipt['nativeInspectionPath']))),'Current timeline differs from the finished cut studied for the hook')
  font_preflight(r,prepared);original=p.GetCurrentTimeline();original_detail=inspect(self,p);baseline=inspect(self,p,duplicate=True)
  native=inside(project['root'],packet['nativeProject']);inspection=inside(project['root'],packet['inspection']);work=inside(Path(project['root'])/'10_WORK',packet['archiveDirectory'])
  require(not native.exists() and not inspection.exists() and not work.exists(),'Hook outputs exist; reconcile before retrying')
  names={p.GetTimelineByIndex(i).GetName() for i in range(1,p.GetTimelineCount()+1)};donor_name=packet['title']+' hook source'
  require(packet['title'] not in names and donor_name not in names,'Hook timeline name exists');work.mkdir(parents=True);page=r.GetCurrentPage()
  try:
   require(original.Export(str(work/'parent.drt'),r.EXPORT_DRT),'Cannot export native parent timeline')
   pool=p.GetMediaPool();donor=pool.CreateEmptyTimeline(donor_name);require(donor and p.SetCurrentTimeline(donor),'Cannot create native hook donor')
   require(donor.SetStartTimecode('00:00:00:00') and r.OpenPage('edit'),'Cannot set hook donor clock/page')
   require(donor.SetSettings({'useCustomSettings':'1','timelineResolutionWidth':str(spec['width']),'timelineResolutionHeight':str(spec['height'])}),'Cannot set hook canvas')
   require(abs(float(donor.GetSettings()['timelineFrameRate'])-spec['fps']['numerator']/spec['fps']['denominator'])<1e-6,'Hook donor frame rate differs')
   require(donor.SetCurrentTimecode('00:00:00:00'),'Cannot select hook start');item=donor.InsertFusionCompositionIntoTimeline();require(item and item.SetName(prepared['name']),'Cannot create editable native hook generator')
   construct(item.GetFusionCompByIndex(1),spec,prepared)
   require(donor.Export(str(work/'donor.drt'),r.EXPORT_DRT),'Cannot export native hook donor')
   proof=append_hook(work/'parent.drt',work/'donor.drt',work/'hook.drt',prepared);save(work/'archive-proof.json',proof)
   require(p.SetCurrentTimeline(original) and inspect(self,p)==original_detail,'Parent changed while preparing hook')
   revised=pool.ImportTimelineFromFile(str(work/'hook.drt'));require(revised and p.SetCurrentTimeline(revised) and revised.SetName(packet['title']),'Cannot import native hook timeline')
   require(revised.GetUniqueId()!=original.GetUniqueId(),'Hook import replaced original timeline')
   # Native DRT import may restore source names instead of custom clip names.
   # Restore only those observed names on the new copy, then compare all state.
   for kind,tracks in before['tracks'].items():
    for track,clips in enumerate(tracks):
     actual=revised.GetItemListInTrack(kind,track+1) or [];require(len(actual)==len(clips),'Hook import changed source coverage')
     for old,new in zip(clips,actual):
      if new.GetName()!=old['name']:require(new.SetName(old['name']),'Cannot preserve custom clip name')
   verify_timeline(revised,spec,prepared)
   require(inspect(self,p,duplicate=True,omit_last_video_track=True)==baseline,'Hook import changed protected native state or metadata')
   after=self.snapshot(p);require(p.SetCurrentTimeline(original) and inspect(self,p)==original_detail,'Hook changed parent timeline')
   require(p.SetCurrentTimeline(revised) and self.snapshot(p)==after,'New hook timeline changed during parent verification')
   pm=r.GetProjectManager();require(pm.SaveProject(),'Cannot save native hook');require(pm.ExportProject(p.GetName(),str(native),False),'Cannot checkpoint native hook');save(inspection,after)
   return {'nativeProject':str(native),'timelineId':revised.GetUniqueId(),'fingerprint':fingerprint(after),'status':'revised-native-render-pending'}
  finally:require(r.OpenPage(page),'Cannot restore Resolve page after hook construction')
 def render(self,project,packet):
  spec=plan(project,packet);r,p=self.selected(project);verify_source_clocks(p.GetCurrentTimeline(),spec);state=self.snapshot(p);require(fingerprint(state)==packet['expectedFingerprint'],'Timeline changed before export');save(inside(project['root'],packet['inspection']),state)
  if spec.get('hookContract'):
   from hook_plan import validate
   from resolve_hooks import verify_timeline,font_preflight
   prepared=validate(project,spec);font_preflight(r,prepared);verify_timeline(p.GetCurrentTimeline(),spec,prepared)
  if spec.get('audio',{}).get('music'):
   from resolve_music import items as music_items
   music_items(p.GetCurrentTimeline(),spec)
  if spec.get('captionContract'):
   from caption_plan import validate
   from resolve_captions import verify_timeline,verify_fonts
   caption_prepared=validate(project,spec);verify_fonts(r,caption_prepared)
   verify_timeline(p.GetCurrentTimeline(),spec,caption_prepared)
  verify_framing(p.GetCurrentTimeline(),spec)
  from resolve_graphics import items as graphic_items
  graphic_items(p.GetCurrentTimeline(),spec)
  native=inside(project['root'],packet['nativeProject']);checkpoint_hash=sha(native)
  require(not p.IsRenderingInProgress(),'Another Resolve render is active');media=inside(project['root'],packet['media']);require(not media.exists(),'Never overwrite render');media.parent.mkdir(parents=True,exist_ok=True)
  require('H.264 Master' in p.GetRenderPresetList() and p.LoadRenderPreset('H.264 Master'),'Built-in H.264 Master preset unavailable; cannot reset native export state')
  require(p.SetCurrentRenderFormatAndCodec('mp4','H264'),'Native H264 export unavailable');require(p.SetCurrentRenderMode(1),'Cannot select single-clip render');require(p.SetRenderSettings({'SelectAllFrames':True,'TargetDir':str(media.parent),'CustomName':media.stem,'ExportVideo':True,'ExportAudio':True,'AudioCodec':'aac','AudioSampleRate':spec['sampleRate'],'FormatWidth':spec['width'],'FormatHeight':spec['height'],'FrameRate':spec['fps']['numerator']/spec['fps']['denominator']}),'Render settings refused')
  job=p.AddRenderJob();require(job,'Render job refused');save(str(media)+'.job.json',{'jobId':job});require(p.StartRendering([job],False),'Render did not start');deadline=time.monotonic()+4*3600
  while p.IsRenderingInProgress():require(time.monotonic()<deadline,'Render timeout; reconcile original job');time.sleep(1)
  status=p.GetRenderJobStatus(job);save(str(media)+'.status.json',status);require(status.get('JobStatus')=='Complete','Native render did not complete')
  require(sha(native)==checkpoint_hash,'Native checkpoint changed during render')
  verify_source_clocks(p.GetCurrentTimeline(),spec);require(fingerprint(self.snapshot(p))==packet['expectedFingerprint'],'Native timeline changed during render');return result_receipt(project,packet,spec,packet['nativeProject'],media,packet['inspection'])
