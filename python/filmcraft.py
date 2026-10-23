"""Headless FilmCraft adapter. No Premiere or Resolve imports or conversion."""
import json,sys,time,shutil
from pathlib import Path
from common import *
sys.path.insert(0,str(SKILLS/'edit/scripts'))
from filmcraft_client import Filmcraft
TICKS=254016000000
class Adapter:
 def __init__(self,config):self.config=config
 def doctor(self):
  binary=Path(self.config.get('filmcraft',''))
  return {'backend':'filmcraft','binaryPresent':binary.is_file(),'binarySha256':sha(binary) if binary.is_file() else None,'nativeAcceptance':'not implied by discovery','pin':'71438c627b5cbcfb550526c3971f4d0037733c5c'}
 def inspect(self,project,packet):
  native=inside(project['root'],packet['nativeProject']);c=Filmcraft(self.config['filmcraft'],packet['session'],str(native))
  try:state=c.tool('sequence_inspect');return {'nativeProject':str(native),'fileHash':sha(native),'state':state,'fingerprint':fingerprint(state)}
  finally:c.close()
 def build(self,project,packet):
  p=plan(project,packet);out=inside(project['root'],packet['output']);out.mkdir(exist_ok=False,parents=True)
  require(TICKS*p['fps']['denominator']%p['fps']['numerator']==0,'Unsupported frame tick grid');ft=TICKS*p['fps']['denominator']//p['fps']['numerator'];sr=p['sampleRate'];require(TICKS%sr==0,'Unsupported audio sample grid')
  require(not p.get('audio',{}).get('music'),'Music placement requires an explicit native finishing packet')
  native=out/'edit.fcproj';c=Filmcraft(self.config['filmcraft'],out/'session')
  try:
   sources={}
   for s in p['sources']:sources[s['id']]=c.tool('media_import',{'paths':[s['path']]})['items'][0]
   c.run('file.newSequence',{'name':p['title'],'width':p['width'],'height':p['height'],'fps':p['fps']['numerator']/p['fps']['denominator'],'sampleRate':sr,'video':3,'audio':2})
   for cut in p['cuts']:
    # No quantization: unequal speech/picture boundaries require canonical paired-audio assembly.
    require(cut['audioInSample']*TICKS//sr==cut['sourceInFrame']*ft and cut['audioSamples']*TICKS//sr==cut['frames']*ft,'Use canonical apply_filmcraft_assembly.py for sample-precision unequal A/V boundaries')
    c.run('timeline.place',{'item':sources[cut['sourceId']],'track':'V1','audioTrack':'A1','time':cut['recordFrame']*ft,'sourceIn':cut['sourceInFrame']*ft,'duration':cut['frames']*ft,'insert':False})
   self.finish(c,p,ft)
   c.run('file.saveAs',{'path':str(native)})
   state=c.tool('sequence_inspect');save(out/'inspection.json',state)
  finally:c.close()
  reopened=self.inspect(project,{'nativeProject':str(native),'session':str(out/'reopen')});save(out/'reopened.json',reopened)
  return {'nativeProject':str(native),'inspection':str(out/'reopened.json'),'fingerprint':reopened['fingerprint'],'status':'built-native-render-pending'}
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
  require(packet.get('kind')=='caption-style','Use Assembly Design for recuts; this operation supports caption properties only')
  target=inside(project['root'],packet['outputProject']);require(not target.exists(),'Revision destination exists');shutil.copy2(packet['nativeProject'],target)
  c=Filmcraft(self.config['filmcraft'],packet['session'],str(target))
  try:
   for edit in packet['edits']:c.run('graphics.set',{'clip':edit['clip'],'layer':edit.get('layer',0),'props':edit['props']})
   c.run('file.save');after=c.tool('sequence_inspect');save(packet['inspection'],after)
  finally:c.close()
  return {'nativeProject':str(target),'fingerprint':fingerprint(after),'status':'revised-native-render-pending'}
 def render(self,project,packet):
  p=plan(project,packet);native=inside(project['root'],packet['nativeProject']);media=inside(project['root'],packet['media']);require(not media.exists(),'Never overwrite renders');media.parent.mkdir(parents=True,exist_ok=True)
  c=Filmcraft(self.config['filmcraft'],packet['session'],str(native))
  try:
   state=c.tool('sequence_inspect');require(fingerprint(state)==packet['expectedFingerprint'],'Native state changed before export');save(packet['inspection'],state)
   job=c.run('file.exportMedia',{'path':str(media),'format':'h264','audio':True,'range':'entire','wait':False})
   save(str(media)+'.job.json',job);deadline=time.monotonic()+4*3600
   while True:
    jobs=c.run('jobs.list');active=[j for j in jobs if not j.get('finished')]
    if not active:
     require(not any(j.get('error') or j.get('cancelled') for j in jobs),'Native export failed');break
    require(time.monotonic()<deadline,'Native export timed out; reconcile original job');time.sleep(1)
  finally:c.close()
  return result_receipt(project,packet,p,native,media,packet['inspection'])
