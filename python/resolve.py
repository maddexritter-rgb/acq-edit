"""Native Resolve Studio 21.1 adapter. Imports only the selected editor's API.

No XML, Premiere project, FilmCraft runtime or flattened cross-editor output.
All timings read back before a render can be accepted. Unqualified host versions fail closed.
"""
import time,math,tempfile
from pathlib import Path
from common import *
from audio_plan import resolve_music_frames
class Adapter:
 def __init__(self,config):self.config=config
 def connect(self):
  import DaVinciResolveScript
  r=DaVinciResolveScript.scriptapp('Resolve');require(r,'Resolve is disconnected. Start Studio and enable External scripting: Local.')
  require(r.IsStudio(),'DaVinci Resolve Studio required');require(r.GetVersionString().startswith('21.1.'),'This adapter is qualified against the 21.1 API; review installed scripting docs for other versions')
  return r
 def doctor(self):
  r=self.connect();p=r.GetProjectManager().GetCurrentProject();return {'backend':'resolve','connected':True,'version':r.GetVersionString(),'studio':r.IsStudio(),'currentProject':p.GetName() if p else None,'nativeAcceptance':'pending dedicated fixture renders'}
 def selected(self,project):
  self.project_root=Path(project['root']);r=self.connect();p=r.GetProjectManager().GetCurrentProject();require(p and p.GetName()=='ACQ_'+project['id'],'Open this toolkit project in Resolve. Never switch or mutate an unrelated project implicitly.');return r,p
 def fusion_fingerprints(self,item):
  results=[]
  root=self.project_root/'10_WORK';root.mkdir(parents=True,exist_ok=True)
  with tempfile.TemporaryDirectory(prefix='fusion-inspect-',dir=root) as folder:
   for index in range(1,item.GetFusionCompCount()+1):
    comp=item.GetFusionCompByIndex(index);require(comp,'Fusion comp missing');comp.GetAttrs();output=Path(folder)/f'{index}.comp';require(item.ExportFusionComp(str(output),index),'Cannot inspect native Fusion graph');results.append(sha(output))
  return results
 def snapshot(self,p):
  t=p.GetCurrentTimeline();require(t,'No current timeline');tracks={}
  for kind in ['video','audio']:
   tracks[kind]=[[{'id':i.GetUniqueId(),'name':i.GetName(),'start':i.GetStart(True),'end':i.GetEnd(True),'left':i.GetLeftOffset(True),'duration':i.GetDuration(True),'properties':i.GetProperties(),'source':i.GetMediaPoolItem().GetUniqueId() if i.GetMediaPoolItem() else None,'fusion':self.fusion_fingerprints(i),'fades':i.GetFades()} for i in t.GetItemListInTrack(kind,n) or []] for n in range(1,t.GetTrackCount(kind)+1)]
  return {'project':p.GetName(),'timeline':t.GetUniqueId(),'name':t.GetName(),'settings':t.GetSettings(),'tracks':tracks}
 def inspect(self,project,packet):
  r,p=self.selected(project);state=self.snapshot(p);return {'state':state,'fingerprint':fingerprint(state),'version':r.GetVersionString()}
 def build(self,project,packet):
  self.project_root=Path(project['root']);spec=plan(project,packet);r=self.connect();pm=r.GetProjectManager();current=pm.GetCurrentProject();name='ACQ_'+project['id']
  require(not current or current.GetName()==name,'Another Resolve project is open. Close it before creating this isolated project.');p=current or pm.CreateProject(name);require(p,'Could not create native Resolve project')
  for bed in spec.get('audio',{}).get('music',[]):resolve_music_frames(spec,bed)
  fps=spec['fps']['numerator']/spec['fps']['denominator'];require(p.SetSettings({'timelineFrameRate':str(fps),'timelineResolutionWidth':str(spec['width']),'timelineResolutionHeight':str(spec['height'])}),'Could not configure native project')
  pool=p.GetMediaPool();timeline=pool.CreateEmptyTimeline(spec['title']+'_'+packet['versionId']);require(timeline and p.SetCurrentTimeline(timeline),'Could not create selected timeline');require(timeline.SetStartTimecode('00:00:00:00'),'Could not set timeline clock')
  timeline.SetSettings({'useCustomSettings':'1'});timeline.SetSettings({'timelineResolutionWidth':str(spec['width']),'timelineResolutionHeight':str(spec['height'])});settings=timeline.GetSettings();require(int(settings['timelineResolutionWidth'])==spec['width'] and int(settings['timelineResolutionHeight'])==spec['height'] and abs(float(settings['timelineFrameRate'])-fps)<1e-6,'Native timeline geometry readback mismatch')
  sources={}
  for s in spec['sources']:
   items=pool.ImportMedia([s['path']]);require(items and len(items)==1,'Native source import failed');sources[s['id']]=items[0]
  pairs=[]
  for cut in spec['cuts']:
   media=sources[cut['sourceId']];video=pool.AppendToTimeline([{'mediaPoolItem':media,'startFrame':cut['sourceInFrame'],'endFrame':cut['sourceInFrame']+cut['frames'],'recordFrame':cut['recordFrame'],'mediaType':1,'trackIndex':1}]);require(video and len(video)==1,'Picture placement failed')
   astart=cut['audioInSample']*fps/spec['sampleRate'];aduration=cut['audioSamples']*fps/spec['sampleRate']
   audio=pool.AppendToTimeline([{'mediaPoolItem':media,'startFrame':astart,'endFrame':astart+aduration,'recordFrame':cut['recordFrame'],'mediaType':2,'trackIndex':1}]);require(audio and len(audio)==1,'Audio placement failed')
   vi,ai=video[0],audio[0]
   for item,start,duration in [(vi,cut['sourceInFrame'],cut['frames']),(ai,astart,aduration)]:
    require(abs(item.GetStart(True)-cut['recordFrame'])<1e-6 and abs(item.GetDuration(True)-duration)<1e-6 and abs(item.GetLeftOffset(True)-start)<1e-6,'Native cut readback differs from precision plan; preserve evidence, do not round')
   require(timeline.SetClipsLinked([vi,ai],True),'Could not link picture/audio');pairs.append((cut,vi,ai))
   props=spec.get('framing',{}).get(cut['id'],{})
   if props:require(vi.SetProperties(props),'Native framing failed')
   audio_props={'AudioVolumeEnabled':True,'AudioVolume':spec.get('audio',{}).get('gainDb',0),**spec.get('audio',{}).get('properties',{})}
   if audio_props:
    require(ai.SetProperties(audio_props),'Native audio treatment failed')
    actual=ai.GetProperties()
    for key,value in audio_props.items():require(actual.get(key)==value,'Native audio treatment readback mismatch: '+key)
   cards=[c for c in spec.get('captions',[]) if c['startFrame']<cut['recordFrame']+cut['frames'] and c['endFrame']>cut['recordFrame']]
   if cards:self.captions(vi,cut,cards,spec)
  for graphic in spec.get('graphics',[]):
   require(sha(graphic['path'])==graphic['sha256'],'Graphic hash mismatch');media=pool.ImportMedia([graphic['path']]);require(media,'Graphic import failed')
   while timeline.GetTrackCount('video')<2:require(timeline.AddTrack('video'),'Cannot add graphics track')
   require(pool.AppendToTimeline([{'mediaPoolItem':media[0],'startFrame':0,'endFrame':graphic['frames'],'recordFrame':graphic['startFrame'],'mediaType':1,'trackIndex':2}]),'Graphics placement failed')
  self.music(timeline,pool,sources,spec)
  require(pm.SaveProject(),'Native save failed');state=self.snapshot(p);save(inside(project['root'],packet['inspection']),state);native=inside(project['root'],packet['nativeProject']);require(not native.exists(),'Native checkpoint exists');require(pm.ExportProject(name,str(native),False),'Native DRP checkpoint failed')
  return {'nativeProject':str(native),'fingerprint':fingerprint(state),'timelineId':timeline.GetUniqueId(),'status':'native-built-awaiting-render'}
 def music(self,timeline,pool,sources,spec):
  for bed in spec.get('audio',{}).get('music',[]):
   timing=resolve_music_frames(spec,bed)
   while timeline.GetTrackCount('audio')<2:require(timeline.AddTrack('audio','stereo'),'Cannot add native music track')
   placed=pool.AppendToTimeline([{'mediaPoolItem':sources[bed['sourceId']],'mediaType':2,'trackIndex':2,'startFrame':timing['sourceInSample'],'endFrame':timing['sourceInSample']+timing['samples'],'recordFrame':bed['startFrame']}])
   require(placed and len(placed)==1,'Native music placement failed');item=placed[0]
   require(item.GetStart(True)==bed['startFrame'] and item.GetLeftOffset(True)==timing['sourceInSample'] and item.GetDuration(True)==timing['samples'],'Native music timing readback mismatch')
   require(item.SetProperties({'AudioVolumeEnabled':True,'AudioVolume':bed['gainDb']}),'Native music gain failed')
   require(abs(item.GetProperties()['AudioVolume']-bed['gainDb'])<1e-6,'Native music gain readback mismatch')
   fades={'FadeIn':timing['fadeInSamples'],'FadeOut':timing['fadeOutSamples']}
   require(item.SetFades(fades),'Native music fades failed');actual=item.GetFades()
   require(all(actual.get(key)==value for key,value in fades.items()),'Native music fade readback mismatch')
 def captions(self,item,cut,cards,spec):
  require(item.GetFusionCompCount()==0,'Existing Fusion comp must be merged rather than replaced');comp=item.AddFusionComp();require(comp,'Fusion unavailable');nodes=comp.GetToolList(False);source=next((n for n in nodes.values() if n.GetAttrs()['TOOLS_RegID']=='MediaIn'),None);output=next((n for n in nodes.values() if n.GetAttrs()['TOOLS_RegID']=='MediaOut'),None);require(source and output,'Fusion media endpoints missing')
  for index,card in enumerate(cards):
   text=comp.AddTool('TextPlus');merge=comp.AddTool('Merge');require(text and merge,'Fusion text/merge unavailable');text.SetAttrs({'TOOLS_Name':f'ACQ_Caption_{index}'});style=card['style'];text.SetInput('StyledText',card['text']);text.SetInput('Font',style.get('font','Arial'));text.SetInput('Size',style.get('size',64)/spec['height']);text.SetInput('Center',{1:.5,2:style.get('centerY',.22)})
   merge.ConnectInput('Background',source);merge.ConnectInput('Foreground',text)
   # Fusion source clock must be inspected for each media type; no timeline-clock assumptions.
   start=comp.GetAttrs()['COMPN_RenderStart']+max(0,card['startFrame']-cut['recordFrame']);end=comp.GetAttrs()['COMPN_RenderStart']+min(cut['frames'],card['endFrame']-cut['recordFrame'])
   merge.Blend.SetExpression(f'iif(time >= {start} and time < {end}, 1, 0)');source=merge
  output.ConnectInput('Input',source)
 def revise(self,project,packet):
  r,p=self.selected(project);before=self.snapshot(p);require(fingerprint(before)==packet['expectedFingerprint'],'Native state changed; inspect and merge user edits')
  require(packet['kind'] in ['caption-style','music-gain'],'Spoken recuts require a new reviewed Assembly Design plan and new timeline; no partial dependent-layer edits')
  original=p.GetCurrentTimeline();copy=original.DuplicateTimeline(packet['title']);require(copy and p.SetCurrentTimeline(copy),'Cannot preserve prior timeline before revision')
  for edit in packet['edits']:
   if packet['kind']=='caption-style':
    items=copy.GetItemListInTrack('video',edit['track']);require(0<=edit['itemIndex']<len(items),'Caption target absent');comp=items[edit['itemIndex']].GetFusionCompByIndex(edit['compIndex']);require(comp,'Caption Fusion comp absent');tool=comp.FindTool(edit['tool']);require(tool and edit['tool'].startswith('ACQ_Caption_'),'Only ACQ-owned caption nodes may be edited')
    for key,value in edit['inputs'].items():require(key in ['StyledText','Font','Size','Center','Style','Red1','Green1','Blue1'],'Unsupported caption property');tool.SetInput(key,value);actual=tool.GetInput(key);require(abs(actual-value)<1e-6 if isinstance(value,(int,float)) else actual==value,'Fusion input readback mismatch')
   else:
    require(edit['track']==2,'Music revisions target the inspected music track only');items=copy.GetItemListInTrack('audio',2);require(0<=edit['itemIndex']<len(items),'Music target absent');item=items[edit['itemIndex']]
    delta=edit['deltaDb'];require(isinstance(delta,(int,float)) and math.isfinite(delta) and -60<=delta<=12,'Invalid music gain delta')
    wanted=item.GetProperties()['AudioVolume']+delta;require(-60<=wanted<=12,'Music gain exceeds supported range');require(item.SetProperties({'AudioVolumeEnabled':True,'AudioVolume':wanted}),'Music gain revision failed');require(abs(item.GetProperties()['AudioVolume']-wanted)<1e-6,'Music gain revision readback mismatch')
  after=self.snapshot(p)
  before_cuts=[(i['start'],i['end'],i['left'],i['source']) for kind in ['video','audio'] for track in before['tracks'][kind] for i in track];after_cuts=[(i['start'],i['end'],i['left'],i['source']) for kind in ['video','audio'] for track in after['tracks'][kind] for i in track];require(before_cuts==after_cuts,'Finishing revision changed cuts')
  pm=r.GetProjectManager();require(pm.SaveProject(),'Save failed');native=inside(project['root'],packet['nativeProject']);require(not native.exists(),'Checkpoint exists');require(pm.ExportProject(p.GetName(),str(native),False),'Checkpoint failed');save(inside(project['root'],packet['inspection']),after);return {'nativeProject':str(native),'fingerprint':fingerprint(after),'status':'revised-native-render-pending'}
 def render(self,project,packet):
  spec=plan(project,packet);r,p=self.selected(project);state=self.snapshot(p);require(fingerprint(state)==packet['expectedFingerprint'],'Timeline changed before export');save(inside(project['root'],packet['inspection']),state)
  native=inside(project['root'],packet['nativeProject']);checkpoint_hash=sha(native)
  require(not p.IsRenderingInProgress(),'Another Resolve render is active');media=inside(project['root'],packet['media']);require(not media.exists(),'Never overwrite render');media.parent.mkdir(parents=True,exist_ok=True)
  require(p.SetCurrentRenderFormatAndCodec('mp4','H264'),'Native H264 export unavailable');require(p.SetCurrentRenderMode(1),'Cannot select single-clip render');require(p.SetRenderSettings({'SelectAllFrames':True,'TargetDir':str(media.parent),'CustomName':media.stem,'ExportVideo':True,'ExportAudio':True,'FormatWidth':spec['width'],'FormatHeight':spec['height'],'FrameRate':spec['fps']['numerator']/spec['fps']['denominator']}),'Render settings refused')
  job=p.AddRenderJob();require(job,'Render job refused');save(str(media)+'.job.json',{'jobId':job});require(p.StartRendering([job],False),'Render did not start');deadline=time.monotonic()+4*3600
  while p.IsRenderingInProgress():require(time.monotonic()<deadline,'Render timeout; reconcile original job');time.sleep(1)
  status=p.GetRenderJobStatus(job);save(str(media)+'.status.json',status);require(status.get('JobStatus')=='Complete','Native render did not complete')
  require(sha(native)==checkpoint_hash,'Native checkpoint changed during render')
  require(fingerprint(self.snapshot(p))==packet['expectedFingerprint'],'Native timeline changed during render');return result_receipt(project,packet,spec,packet['nativeProject'],media,packet['inspection'])
