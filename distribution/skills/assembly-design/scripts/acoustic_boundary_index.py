#!/usr/bin/env python3
"""Cached played-channel VAD index for pre-build edge proposals, never listening proof."""
import hashlib,json,math,subprocess,sys,time,wave,fcntl
from pathlib import Path
from fractions import Fraction

def digest(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()

def prepare(source,stream,channel,cache_dir,shared_dir=None):
 cache=Path(cache_dir);cache.mkdir(parents=True,exist_ok=True)
 with (cache/"index.lock").open("a") as lock:
  fcntl.flock(lock,fcntl.LOCK_EX)
  return _prepare(source,stream,channel,cache_dir,shared_dir)

def _prepare(source,stream,channel,cache_dir,shared_dir=None):
 source=Path(source).resolve();cache=Path(cache_dir);cache.mkdir(parents=True,exist_ok=True)
 if type(stream)!=int or stream<0 or type(channel)!=int or channel<0:raise ValueError('Explicit zero-based stream/channel required')
 stat=source.stat();identity={'path':str(source),'size':stat.st_size,'mtime_ns':stat.st_mtime_ns,'ctime_ns':stat.st_ctime_ns}
 shared=Path(shared_dir) if shared_dir else Path(__file__).resolve().parents[2]/'_shared'
 config={'revision':1,'source':identity,'stream':stream,'channel':channel,'vad_code':digest(shared/'silero_vad.py'),'threshold':0.5,'min_silence':0.05,'pad_ms':30}
 key=hashlib.sha256(json.dumps(config,sort_keys=True).encode()).hexdigest();folder=cache/key;receipt=folder/'index.json'
 if receipt.exists():
  data=json.loads(receipt.read_text())
  if data['config']!=config:raise ValueError('Acoustic cache identity conflict')
  return data,True
 folder.mkdir(exist_ok=True)
 probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','a','-show_entries','stream=channels,start_time','-of','json',str(source)]))['streams']
 if stream>=len(probe) or channel>=probe[stream]['channels']:raise ValueError('Unavailable played audio routing')
 if abs(float(probe[stream].get('start_time',0)))>1e-6:raise ValueError('Nonzero audio clock requires explicit conformed source')
 pcm=folder/'channel.wav'
 if not pcm.exists():
  subprocess.run(['ffmpeg','-v','error','-nostdin','-y','-i',str(source),'-map',f'0:a:{stream}','-vn','-af',f'pan=mono|c0=c{channel}','-ar','16000','-c:a','pcm_s16le',str(folder/'channel.pending.wav')],check=True)
  (folder/'channel.pending.wav').replace(pcm)
 with wave.open(str(pcm),'rb') as f:duration=f.getnframes()/f.getframerate()
 sys.path.insert(0,str(shared));from silero_vad import speech_spans
 t=time.monotonic();speech=speech_spans(pcm,min_silence=.05,speech_pad_ms=30,threshold=.5)
 if speech is None:raise RuntimeError('Local VAD unavailable; no timestamp-only fallback')
 data={'schema':'edit.acoustic-boundary-index/v1','config':config,'source_sha256':digest(source),'duration':duration,'speech':speech,'analysis_seconds':time.monotonic()-t,'status':'DETECTOR_EVIDENCE_NOT_LISTENED','routing_status':'CALLER_SPECIFIED_CHANNEL_NOT_NATIVE_ROUTING_CERTIFICATION'}
 tmp=folder/'index.pending.json';tmp.write_text(json.dumps(data,indent=2));tmp.replace(receipt)
 return data,False

def refine(words,index,side,fps,baseline,acoustic,max_search=.5):
 """Intersect a word-label gap with VAD non-speech. Never cross another label."""
 rate=Fraction(fps);duration=float(acoustic['duration']);word=words[index]
 label=float(word['start' if side=='start' else 'end'])
 if side=='start':lo=float(words[index-1]['end']) if index else 0.;hi=label
 else:lo=label;hi=float(words[index+1]['start']) if index+1<len(words) else duration
 lo=max(0.,lo,label-max_search);hi=min(duration,hi,label+max_search)
 result=dict(baseline);result['timestamp_frame']=baseline['frame'];result['acoustic_verified']=False
 if not any(max(float(word['start']),a)<min(float(word['end']),b) for a,b in acoustic['speech']):
  result.update(frame=None,seconds=None,risk=True,rule='ACOUSTIC_UNRESOLVED',risk_reason='Selected word locator has no detected speech support; inspect occurrence')
  return result
 if not all(math.isfinite(v) for v in [lo,hi,label]) or hi<=lo:
  result.update(frame=None,seconds=None,risk=True,rule='ACOUSTIC_UNRESOLVED',risk_reason='No separated label window; inspect phonemes/occurrence')
  return result
 # Padded speech blocks guard quiet onsets/releases. VAD is not word recognition.
 gaps=[];cursor=0.
 for a,b in acoustic['speech']:
  if a>cursor:gaps.append((cursor,a))
  cursor=max(cursor,b)
 if cursor<duration:gaps.append((cursor,duration))
 options=[]
 for a,b in gaps:
  lower=max(lo,a);upper=min(hi,b)
  # Strictly interior; never choose the exact detector boundary.
  f0=math.floor(Fraction(str(lower))*rate)+1;f1=math.ceil(Fraction(str(upper))*rate)-1
  if f0<=f1:
   preferred=baseline['frame'];frame=max(f0,min(f1,preferred));options.append((abs(frame-preferred),frame,[lower,upper]))
 if not options:
  result.update(frame=None,seconds=None,risk=True,rule='ACOUSTIC_UNRESOLVED',risk_reason='No source frame within both label gap and detected non-speech; local alignment required')
 else:
  _,frame,window=min(options);result.update(frame=frame,seconds=float(Fraction(frame,1)/rate),risk=False,rule='LOCAL_VAD_GAP_PROPOSAL',risk_reason=None,acoustic_window=window)
 return result
