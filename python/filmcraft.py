"""Headless FilmCraft adapter. No Premiere or Resolve imports or conversion."""
import json,sys,time,shutil,math
from pathlib import Path
from common import *
from audio_plan import linear_fade_points
from framing_plan import filmcraft_motion,filmcraft_tracking,verify_filmcraft_framing
sys.path.insert(0,str(SKILLS/'edit/scripts'))
from filmcraft_client import Filmcraft
TICKS=254016000000
class Adapter:
 def __init__(self,config):self.config=config
 def doctor(self):
  binary=Path(self.config.get('filmcraft',''))
  return {'backend':'filmcraft','binaryPresent':binary.is_file(),'binarySha256':sha(binary) if binary.is_file() else None,'nativeAcceptance':'not implied by discovery','pin':'71438c627b5cbcfb550526c3971f4d0037733c5c'}
 def inspect(self,project,packet):
  native=inside(project['root'],packet['nativeProject']);c=Filmcraft(self.config['filmcraft'],inside(project['root'],packet['session']),str(native))
  try:state=c.tool('sequence_inspect');return {'nativeProject':str(native),'fileHash':sha(native),'state':state,'fingerprint':fingerprint({'state':state,'fileHash':sha(native)})}
  finally:c.close()
 def build(self,project,packet):
  p=plan(project,packet);out=inside(project['root'],packet['output']);out.mkdir(exist_ok=False,parents=True)
  require(TICKS*p['fps']['denominator']%p['fps']['numerator']==0,'Unsupported frame tick grid');ft=TICKS*p['fps']['denominator']//p['fps']['numerator'];sr=p['sampleRate'];require(TICKS%sr==0,'Unsupported audio sample grid')
  require(not p.get('audio',{}).get('properties'),'Resolve-specific audio properties cannot be applied by FilmCraft')
  native=out/'edit.fcproj';c=Filmcraft(self.config['filmcraft'],out/'session')
  try:
   sources={}
   for s in p['sources']:sources[s['id']]=c.tool('media_import',{'paths':[s['path']]})['items'][0]
   c.run('file.newSequence',{'name':p['title'],'width':p['width'],'height':p['height'],'fps':p['fps']['numerator']/p['fps']['denominator'],'sampleRate':sr,'video':max(3,(4 if p.get('captionContract') else 2)+len(p.get('graphics',[]))),'audio':2})
   for cut in p['cuts']:
    if cut.get('audioSourceId'):
     before=c.tool('sequence_inspect');ids={i['clip'] for kind in ['video','audio'] for track in before[kind] for i in track['items']}
     c.run('timeline.place',{'item':sources[cut['sourceId']],'track':'V1','video':True,'audio':False,'time':cut['recordFrame']*ft,'sourceIn':cut['sourceInFrame']*ft,'duration':cut['frames']*ft,'insert':False})
     st=TICKS//sr;c.run('timeline.place',{'item':sources[cut['audioSourceId']],'track':'A1','video':False,'audio':True,'time':cut['recordFrame']*ft,'sourceIn':cut['sourceInFrame']*ft,'duration':cut['frames']*ft,'insert':False})
     state=c.tool('sequence_inspect');vv=[i for i in state['video'][0]['items'] if i['clip'] not in ids];aa=[i for i in state['audio'][0]['items'] if i['clip'] not in ids]
     require(len(vv)==len(aa)==1,'Paired placement created unexpected source streams');v,a=vv[0],aa[0]
     require((v['start'],v['sourceIn'],v['duration'])==(cut['recordFrame']*ft,cut['sourceInFrame']*ft,cut['frames']*ft),'Picture placement differs from paired plan')
     require((a['start'],a['sourceIn'],a['duration'])==(cut['recordFrame']*ft,cut['sourceInFrame']*ft,cut['frames']*ft),'Native placeholder differs from picture range')
     require(v['start']-v['sourceIn']==a['start']-a['sourceIn'],'Paired source clocks differ');c.run('clip.link',{'clips':[v['clip'],a['clip']]})
     linked=c.tool('sequence_inspect');v=next(i for i in linked['video'][0]['items'] if i['clip']==v['clip']);a=next(i for i in linked['audio'][0]['items'] if i['clip']==a['clip']);require(v['link'] is not None and v['link']==a['link'],'Native AV linkage failed')
    else:
     require(cut['audioInSample']*TICKS//sr==cut['sourceInFrame']*ft and cut['audioSamples']*TICKS//sr==cut['frames']*ft,'Compile the canonical paired-source plan for unequal A/V boundaries')
     c.run('timeline.place',{'item':sources[cut['sourceId']],'track':'V1','audioTrack':'A1','time':cut['recordFrame']*ft,'sourceIn':cut['sourceInFrame']*ft,'duration':cut['frames']*ft,'insert':False})
   if any(cut.get('audioSourceId') for cut in p['cuts']):
    require(all(cut.get('audioSourceId') for cut in p['cuts']),'Do not mix paired and unbound dialogue cuts')
    # The canonical assembly skill uses saved native data for sample geometry:
    # timeline.place snaps record/duration to frames even for audio-only media.
    frame_project=out/'frame-assembly.fcproj';c.run('file.saveAs',{'path':str(frame_project)});c.close()
    data=read(frame_project);sequence=data['project']['items'][str(data['view']['active_sequence'])]['kind']['Sequence'];items=sequence['audio_tracks'][0]['items'];require(len(items)==len(p['cuts']),'Unexpected dialogue stream count')
    st=TICKS//sr
    for item,cut in zip(items,p['cuts']):item.update(start=cut['audioRecordSample']*st,source_in=cut['audioInSample']*st,duration=cut['audioSamples']*st)
    save(native,data);c=Filmcraft(self.config['filmcraft'],out/'paired-reopen',str(native));state=c.tool('sequence_inspect')
    for cut,v,a in zip(p['cuts'],state['video'][0]['items'],state['audio'][0]['items']):
     require((a['start'],a['sourceIn'],a['duration'])==(cut['audioRecordSample']*st,cut['audioInSample']*st,cut['audioSamples']*st),'Reopened audio differs from exact paired samples')
     require(v['link'] is not None and v['link']==a['link'] and v['start']-v['sourceIn']==a['start']-a['sourceIn'],'Reopened native linkage/source clocks differ')
   panel_layouts={}
   if any(s.get('mode')=='panel-layout' for s in p.get('framing',{}).get('shots',{}).values()):
    from filmcraft_panels import construct
    panel_layouts=construct(c,p,sources,ft)
   self.audio(c,p,sources,ft)
   self.finish(c,p,ft,project)
   c.run('file.saveAs',{'path':str(native)})
   if panel_layouts:
    from filmcraft_panels import bind
    c.close();data=read(native);bind(data,p,panel_layouts,ft)
    panel_native=out/'panel-assembly.fcproj';save(panel_native,data)
    c=Filmcraft(self.config['filmcraft'],out/'panel-reopen',str(panel_native))
    c.run('file.saveAs',{'path':str(native)})
   verify_filmcraft_framing(native,p,ft)
   if p.get('captionContract'):
    from caption_plan import validate,verify_native
    save(out/'caption-verification.json',verify_native(native,p,validate(project,p),ft))
   state=c.tool('sequence_inspect');save(out/'inspection.json',state)
  finally:c.close()
  reopened=self.inspect(project,{'nativeProject':str(native),'session':str(out/'reopen')});save(out/'reopened.json',reopened)
  return {'nativeProject':str(native),'inspection':str(out/'reopened.json'),'fingerprint':reopened['fingerprint'],'status':'built-native-render-pending'}
 def audio(self,c,p,sources,ft):
  sample_tick=TICKS//p['sampleRate']
  dialogue=c.tool('sequence_inspect')['audio'][0]['items']
  for clip in dialogue:
   c.run('effects.setParam',{'clip':clip['clip'],'effect':'volume','param':'level','value':p.get('audio',{}).get('gainDb',0)})
  for bed in p.get('audio',{}).get('music',[]):
   before={i['clip'] for track in c.tool('sequence_inspect')['audio'] for i in track['items']}
   c.run('timeline.place',{'item':sources[bed['sourceId']],'track':'A2','video':False,'audio':True,'time':bed['startFrame']*ft,'sourceIn':bed['sourceInSample']*sample_tick,'duration':bed['samples']*sample_tick,'insert':False})
   clips=[i for i in c.tool('sequence_inspect')['audio'][1]['items'] if i['clip'] not in before]
   require(len(clips)==1,'Music placement created unexpected audio streams; provide a prepared stereo/mono source')
   clip=clips[0];require(clip['start']==bed['startFrame']*ft and clip['sourceIn']==bed['sourceInSample']*sample_tick and clip['duration']==bed['samples']*sample_tick,'Music timing readback mismatch')
   c.run('effects.setParam',{'clip':clip['clip'],'effect':'volume','param':'level','value':bed['gainDb']})
   fade_in=bed.get('fadeInSamples',0);fade_out=bed.get('fadeOutSamples',0)
   if fade_in or fade_out:
    for offset,db in linear_fade_points(bed,p['sampleRate']):
     c.run('effects.setParam',{'clip':clip['clip'],'effect':'volume','param':'level','value':db,'time':clip['start']+offset*sample_tick,'keyframe':True})
     c.run('effects.setInterpolation',{'clip':clip['clip'],'effect':'volume','param':'level','mediaTime':clip['sourceIn']+offset*sample_tick,'interpolation':'linear'})
 def finish(self,c,p,ft,project=None):
  shots=p.get('framing',{}).get('shots',{})
  if shots:
   items=c.tool('sequence_inspect')['video'][0]['items'];require(len(items)==len(p['cuts']),'Picture coverage differs from framing plan')
   for cut,item in zip(p['cuts'],items):
    require(item['start']==cut['recordFrame']*ft and item['sourceIn']==cut['sourceInFrame']*ft and item['duration']==cut['frames']*ft,'Stale native picture range')
    if shots[cut['id']]['mode']=='panel-layout':continue
    for param,value in filmcraft_motion(p,shots[cut['id']]).items():c.run('effects.setParam',{'clip':item['clip'],'effect':'motion','param':param,'value':value})
    filmcraft_tracking(c,item,cut,shots[cut['id']],ft)
  if p.get('captionContract'):
   from caption_plan import validate,build_native
   build_native(c,p,validate(project,p),ft)
  for card in ([] if p.get('captionContract') else p.get('captions',[])):
   style=card['style'];graphic=c.run('graphics.newText',{'newClip':True,'text':card['text'],'position':style.get('position',[p['width']/2,p['height']*.78]),'font':style.get('font','Arial'),'fontStyle':style.get('fontStyle','Bold'),'size':style.get('size',64),'time':card['startFrame']*ft,'seconds':(card['endFrame']-card['startFrame'])*p['fps']['denominator']/p['fps']['numerator'],'track':1});c.run('graphics.set',{'clip':graphic['clip'],'layer':graphic['layer'],'props':{'align':'center'}})
  for index,asset in enumerate(p.get('graphics',[])):
   require(sha(asset['path'])==asset['sha256'],'Graphic asset changed');item=c.tool('media_import',{'paths':[asset['path']]})['items'][0]
   track=index+(4 if p.get('captionContract') else 2)
   c.run('timeline.place',{'item':item,'track':f'V{track+1}','video':True,'audio':False,'time':asset['startFrame']*ft,'sourceIn':0,'duration':asset['frames']*ft,'insert':False})
   placed=c.tool('sequence_inspect')['video'][track]['items'];require(len(placed)==1,'Unexpected native graphic coverage');graphic=placed[0]
   require(graphic['item']==item and graphic['start']==asset['startFrame']*ft and graphic['duration']==asset['frames']*ft and graphic['sourceIn']==0,'Native graphic source/timing readback mismatch')
 def revise(self,project,packet):
  if packet.get('kind')=='tracking-framing':return self.revise_tracking(project,packet)
  if packet.get('kind')=='spoken-recut':
   from recut_execution import prepare,record
   prepared=prepare(project,packet);parent=prepared['version'];native=inside(project['root'],parent['nativeProject'])
   before=self.inspect(project,{'nativeProject':str(native),'session':packet['inspectSession']})
   require(before['fingerprint']==prepared['expected'],'Published parent native state changed; reconcile user edits before recutting')
   built=self.build(project,packet['construction'])
   after=self.inspect(project,{'nativeProject':str(native),'session':packet['verifySession']})
   require(after['fingerprint']==prepared['expected'],'Parent changed during recut; preserve new work for reconciliation')
   return record(project,packet,prepared,built)
  # Work from an inspected copy so manual effects survive caption-only revisions.
  before=self.inspect(project,{'nativeProject':packet['nativeProject'],'session':packet['inspectSession']})
  require(before['fingerprint']==packet['expectedFingerprint'],'Native state changed; merge intervening edits before revising')
  require(packet.get('kind') in ['caption-style','music-gain','fixed-framing'],'Use Assembly Design for recuts; this operation supports caption style, music gain or fixed framing only')
  spec=plan(project,packet) if packet['kind']=='fixed-framing' or (packet['kind']=='caption-style' and packet.get('plan')) else None
  if packet['kind']=='fixed-framing':
   targets={e['cutId'] for e in packet['edits']};shots=spec['framing']['shots']
   require(targets and targets<=set(shots) and all(shots[i]['mode']=='fixed-crop' for i in targets),'Fixed framing cannot target tracked crops or native panels; use a dedicated revision route')
  if spec:require(before['state']['settings']['width']==spec['width'] and before['state']['settings']['height']==spec['height'],'Finishing revision cannot resize the approved timeline')
  target=inside(project['root'],packet['outputProject']);require(not target.exists(),'Revision destination exists');shutil.copy2(packet['nativeProject'],target)
  c=Filmcraft(self.config['filmcraft'],inside(project['root'],packet['session']),str(target))
  try:
   if packet['kind']=='caption-style':
    for edit in packet['edits']:c.run('graphics.set',{'clip':edit['clip'],'layer':edit.get('layer',0),'props':edit['props']})
   elif packet['kind']=='fixed-framing':
    native_data=read(target)
    for edit in packet['edits']:
     cut=next((cut for cut in spec['cuts'] if cut['id']==edit['cutId']),None);require(cut,'Framing cut absent from plan')
     items=[i for i in c.tool('sequence_inspect')['video'][0]['items'] if i['clip']==edit['clip']];require(len(items)==1,'Exact framing target missing');item=items[0]
     ft=TICKS*spec['fps']['denominator']//spec['fps']['numerator']
     require(item['start']==cut['recordFrame']*ft and item['sourceIn']==cut['sourceInFrame']*ft and item['duration']==cut['frames']*ft,'Framing target range changed')
     source=next(s for s in spec['sources'] if s['id']==cut['sourceId']);actual=native_data['project']['items'][str(item['item'])]['kind']['Media']['media']['File']['path'];require(Path(actual).resolve()==Path(source['path']).resolve(),'Framing target source differs')
     require(spec['framing']['shots'][cut['id']]['mode']=='fixed-crop','Use a tracking revision for animated framing; fixed-framing never discards a curve')
     motion=next(e['params'] for e in item['effects'] if e['effect']=='motion');require(not any(motion[k]['keyframes'] for k in ['anchor','position','scale']),'Animated framing requires a tracking revision; never replace it with a fixed crop')
     for param,value in filmcraft_motion(spec,spec['framing']['shots'][cut['id']]).items():c.run('effects.setParam',{'clip':item['clip'],'effect':'motion','param':param,'value':value})
   else:
    for edit in packet['edits']:
     state=c.tool('sequence_inspect');clips=[i for i in state['audio'][1]['items'] if i['clip']==edit['clip']];require(len(clips)==1,'Exact music-track clip missing')
     delta=edit['deltaDb'];require(isinstance(delta,(int,float)) and math.isfinite(delta) and -60<=delta<=12,'Invalid music gain delta')
     wanted=clips[0]['gainDb']+delta;require(-60<=wanted<=12,'Music clip gain exceeds supported range')
     c.run('clip.audioGain',{'clips':[edit['clip']],'mode':'adjust','db':delta})
     actual=next(i for i in c.tool('sequence_inspect')['audio'][1]['items'] if i['clip']==edit['clip']);require(abs(actual['gainDb']-wanted)<1e-6,'Music revision gain readback mismatch')
   c.run('file.save');after=c.tool('sequence_inspect')
   cuts=lambda state:[(i['clip'],i['start'],i['duration'],i['sourceIn'],i['item']) for kind in ['video','audio'] for track in state[kind] for i in track['items']]
   require(cuts(before['state'])==cuts(after),'Finishing revision changed cuts')
   if spec:verify_filmcraft_framing(target,spec,TICKS*spec['fps']['denominator']//spec['fps']['numerator'])
   if spec and spec.get('captionContract'):
    from caption_plan import validate,verify_native
    verify_native(target,spec,validate(project,spec),TICKS*spec['fps']['denominator']//spec['fps']['numerator'])
   save(inside(project['root'],packet['inspection']),after)
  finally:c.close()
  return {'nativeProject':str(target),'fingerprint':fingerprint({'state':after,'fileHash':sha(target)}),'status':'revised-native-render-pending'}
 def revise_tracking(self,project,packet):
  from tracking_revision import prepare,protected_filmcraft
  previous,spec=prepare(project,packet);native=inside(project['root'],packet['nativeProject']);parent_hash=sha(native)
  before=self.inspect(project,{'nativeProject':str(native),'session':packet['inspectSession']})
  require(before['fingerprint']==packet['expectedFingerprint'],'Native state changed; reconcile user edits before revising tracking')
  ft=TICKS*spec['fps']['denominator']//spec['fps']['numerator'];verify_filmcraft_framing(native,previous,ft)
  baseline=protected_filmcraft(read(native),packet['cutIds'],previous,Path(packet['outputProject']).stem)
  target=inside(project['root'],packet['outputProject']);inspection=inside(project['root'],packet['inspection'])
  require(not target.exists() and not inspection.exists(),'Tracking revision outputs exist; reconcile before retrying')
  shutil.copy2(native,target);c=Filmcraft(self.config['filmcraft'],inside(project['root'],packet['session']),str(target))
  try:
   items=c.tool('sequence_inspect')['video'][0]['items']
   for cut,item in zip(spec['cuts'],items):
    if cut['id'] not in packet['cutIds']:continue
    shot=spec['framing']['shots'][cut['id']]
    c.run('effects.toggleAnimation',{'clip':item['clip'],'effect':'motion','param':'anchor'})
    c.run('effects.setParam',{'clip':item['clip'],'effect':'motion','param':'anchor','value':filmcraft_motion(spec,shot)['anchor']})
    filmcraft_tracking(c,item,cut,shot,ft)
   c.run('file.save');verify_filmcraft_framing(target,spec,ft)
   require(protected_filmcraft(read(target),packet['cutIds'],spec)==baseline,'Tracking revision changed protected native data')
   require(sha(native)==parent_hash,'Parent project changed during tracking revision')
   after=c.tool('sequence_inspect');save(inspection,after)
  finally:c.close()
  return {'nativeProject':str(target),'fingerprint':fingerprint({'state':after,'fileHash':sha(target)}),'status':'revised-native-render-pending'}
 def render(self,project,packet):
  p=plan(project,packet);native=inside(project['root'],packet['nativeProject']);media=inside(project['root'],packet['media']);require(not media.exists(),'Never overwrite renders');media.parent.mkdir(parents=True,exist_ok=True)
  c=Filmcraft(self.config['filmcraft'],inside(project['root'],packet['session']),str(native))
  try:
   state=c.tool('sequence_inspect');require(fingerprint({'state':state,'fileHash':sha(native)})==packet['expectedFingerprint'],'Native state changed before export');save(inside(project['root'],packet['inspection']),state)
   verify_filmcraft_framing(native,p,TICKS*p['fps']['denominator']//p['fps']['numerator'])
   if p.get('captionContract'):
    from caption_plan import validate,verify_native
    verify_native(native,p,validate(project,p),TICKS*p['fps']['denominator']//p['fps']['numerator'])
   job=c.run('file.exportMedia',{'path':str(media),'format':'h264','audio':True,'range':'entire','wait':False})
   save(str(media)+'.job.json',job);deadline=time.monotonic()+4*3600
   while True:
    jobs=c.run('jobs.list');active=[j for j in jobs if not j.get('finished')]
    if not active:
     require(not any(j.get('error') or j.get('cancelled') for j in jobs),'Native export failed');break
    require(time.monotonic()<deadline,'Native export timed out; reconcile original job');time.sleep(1)
   require(fingerprint({'state':c.tool('sequence_inspect'),'fileHash':sha(native)})==packet['expectedFingerprint'],'Native project changed during export')
  finally:c.close()
  return result_receipt(project,packet,p,native,media,packet['inspection'])
