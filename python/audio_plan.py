"""Validate the music owner's explicit placement. Never select or invent music."""
import math
from common import inside,require,sha

def same_native_frame(actual,expected):
 """Ignore floating point representation noise, never a sample/frame edit."""
 return type(actual) in (float,int) and math.isclose(actual,expected,rel_tol=0,abs_tol=1e-9)

def validate_audio(project,spec,total_frames):
 audio=spec.get('audio',{});require(isinstance(audio,dict),'Audio plan must be an object')
 require(isinstance(audio.get('properties',{}),dict),'Native audio properties must be an object')
 require(not ('gainDb' in audio and 'AudioVolume' in audio.get('properties',{})),'Do not specify dialogue gain twice')
 require(set(audio)<=set(['gainDb','music','properties','dialogueEffects']),'Unsupported audio treatment; provide an explicit supported native plan')
 from dialogue_effects import validate as validate_dialogue
 validate_dialogue(project,spec)
 gain=audio.get('gainDb',0)
 require(isinstance(gain,(float,int)) and math.isfinite(gain) and -60<=gain<=12,'Dialogue gain must be finite dB in [-60,12]')
 beds=audio.get('music',[]);require(isinstance(beds,list),'Music must be an explicit list of placements')
 ids=set();prior_end=0
 for bed in beds:
  require(isinstance(bed.get('id'),str) and bed['id'] and bed['id'] not in ids,'Music placement needs a unique ID');ids.add(bed['id'])
  require(set(bed)<=set(['id','sourceId','startFrame','sourceInSample','samples','gainDb','fadeInSamples','fadeOutSamples','receiptPath','receiptSha256']),'Unsupported music property; do not silently drop an envelope or effect')
  require(any(s['id']==bed['sourceId'] for s in spec['sources']),'Music source is not project-owned')
  for key in ['startFrame','sourceInSample','samples','fadeInSamples','fadeOutSamples']:
   value=bed.get(key,0);require(type(value)==int and value>=0,'Music timing must be nonnegative integer frames/samples')
  require(bed['samples']>0,'Empty music placement')
  require(bed.get('fadeInSamples',0)+bed.get('fadeOutSamples',0)<=bed['samples'],'Music fades overlap')
  gain=bed['gainDb'];require(isinstance(gain,(float,int)) and math.isfinite(gain) and -60<=gain<=12,'Music gain must be finite dB in [-60,12]')
  start=bed['startFrame']*spec['fps']['denominator']/spec['fps']['numerator'];end=start+bed['samples']/spec['sampleRate']
  require(start>=prior_end and end<=total_frames*spec['fps']['denominator']/spec['fps']['numerator']+1e-9,'Music placements overlap or extend past the picture');prior_end=end
  receipt=inside(project['root'],bed['receiptPath']);require(sha(receipt)==bed['receiptSha256'],'Music selection/audition receipt changed')
 return beds

def resolve_music_frames(spec,bed):
 """Reject unqualified fractional placement instead of rounding the music owner's timing."""
 result={}
 for key in ['sourceInSample','samples','fadeInSamples','fadeOutSamples']:
  numerator=bed.get(key,0)*spec['fps']['numerator'];denominator=spec['sampleRate']*spec['fps']['denominator']
  require(numerator%denominator==0,'Resolve music timing must currently align to whole timeline frames; no silent rounding')
  result[key]=numerator//denominator
 return result

def linear_fade_points(bed,sample_rate):
 """Approximate a linear-amplitude fade in a native dB automation lane."""
 gain=bed['gainDb'];duration=bed['samples'];points={0:gain,duration:gain}
 for length,reverse in [(bed.get('fadeInSamples',0),False),(bed.get('fadeOutSamples',0),True)]:
  if not length:continue
  count=min(128,max(2,math.ceil(length/(sample_rate*.005))))
  for index in range(count+1):
   offset=round(length*index/count);amplitude=offset/length
   points[duration-offset if reverse else offset]=max(-96,gain+20*math.log10(amplitude)) if amplitude else -96
 return sorted(points.items())
