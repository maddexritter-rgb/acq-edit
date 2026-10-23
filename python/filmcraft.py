"""Headless FilmCraft adapter. No Premiere or Resolve imports or conversion."""
import json,sys,time,shutil,math
from pathlib import Path
from common import *
from audio_plan import linear_fade_points
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
   c.run('file.newSequence',{'name':p['title'],'width':p['width'],'height':p['height'],'fps':p['fps']['numerator']/p['fps']['denominator'],'sampleRate':sr,'video':3,'audio':2})
   for cut in p['cuts']:
    # No quantization: unequal speech/picture boundaries require canonical paired-audio assembly.
    require(cut['audioInSample']*TICKS//sr==cut['sourceInFrame']*ft and cut['audioSamples']*TICKS//sr==cut['frames']*ft,'Use canonical apply_filmcraft_assembly.py for sample-precision unequal A/V boundaries')
    c.run('timeline.place',{'item':sources[cut['sourceId']],'track':'V1','audioTrack':'A1','time':cut['recordFrame']*ft,'sourceIn':cut['sourceInFrame']*ft,'duration':cut['frames']*ft,'insert':False})
   self.audio(c,p,sources,ft)
   self.finish(c,p,ft)
   c.run('file.saveAs',{'path':str(native)})
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
 def finish(self,c,p,ft):
  require(not p.get('framing'),'Nontrivial framing must use canonical filmcraft_smooth_x.py with an inspected camera plan')
  for card in p.get('captions',[]):
   style=card['style'];graphic=c.run('graphics.newText',{'newClip':True,'text':card['text'],'position':style.get('position',[p['width']/2,p['height']*.78]),'font':style.get('font','Arial'),'fontStyle':style.get('fontStyle','Bold'),'size':style.get('size',64),'time':card['startFrame']*ft,'seconds':(card['endFrame']-card['startFrame'])*p['fps']['denominator']/p['fps']['numerator'],'track':1});c.run('graphics.set',{'clip':graphic['clip'],'layer':graphic['layer'],'props':{'align':'center'}})
  for asset in p.get('graphics',[]):
   require(sha(asset['path'])==asset['sha256'],'Graphic asset changed');item=c.tool('media_import',{'paths':[asset['path']]})['items'][0]
   c.run('timeline.place',{'item':item,'track':'V3','video':True,'audio':False,'time':asset['startFrame']*ft,'sourceIn':0,'duration':asset['frames']*ft,'insert':False})
 def revise(self,project,packet):
  # Work from an inspected copy so manual effects survive caption-only revisions.
  before=self.inspect(project,{'nativeProject':packet['nativeProject'],'session':packet['inspectSession']})
  require(before['fingerprint']==packet['expectedFingerprint'],'Native state changed; merge intervening edits before revising')
  require(packet.get('kind') in ['caption-style','music-gain'],'Use Assembly Design for recuts; this operation supports caption style or music gain only')
  target=inside(project['root'],packet['outputProject']);require(not target.exists(),'Revision destination exists');shutil.copy2(packet['nativeProject'],target)
  c=Filmcraft(self.config['filmcraft'],inside(project['root'],packet['session']),str(target))
  try:
   if packet['kind']=='caption-style':
    for edit in packet['edits']:c.run('graphics.set',{'clip':edit['clip'],'layer':edit.get('layer',0),'props':edit['props']})
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
   save(inside(project['root'],packet['inspection']),after)
  finally:c.close()
  return {'nativeProject':str(target),'fingerprint':fingerprint({'state':after,'fileHash':sha(target)}),'status':'revised-native-render-pending'}
 def render(self,project,packet):
  p=plan(project,packet);native=inside(project['root'],packet['nativeProject']);media=inside(project['root'],packet['media']);require(not media.exists(),'Never overwrite renders');media.parent.mkdir(parents=True,exist_ok=True)
  c=Filmcraft(self.config['filmcraft'],inside(project['root'],packet['session']),str(native))
  try:
   state=c.tool('sequence_inspect');require(fingerprint({'state':state,'fileHash':sha(native)})==packet['expectedFingerprint'],'Native state changed before export');save(inside(project['root'],packet['inspection']),state)
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
