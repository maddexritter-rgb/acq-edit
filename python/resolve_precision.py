"""Exact audio geometry in a new Resolve-owned DRT checkpoint.

Qualified only against the native 21.1.1.0010 archive schema. All non-timing bytes
are preserved. This operates on an isolated freshly built assembly, never a live
user project or a project exported by another editor. Import/readback is mandatory.
"""
from fractions import Fraction
import html,math,re,struct,zipfile
from common import require,sha
SCHEMA_VERSION=b'DbAppVer="21.1.1.0010" DbPrjVer="17"'

def native_time(samples,fps,rate):
 require(type(samples)==int and samples>=0,'Exact nonnegative sample count required')
 value=Fraction(samples)*fps/rate;whole=value.numerator//value.denominator;fraction=value-whole
 return str(whole)+(('|'+struct.pack('<d',float(fraction)).hex()) if fraction else '')

def read_time(value):
 if not value:return 0.0
 match=re.fullmatch(r'(\d+)(?:\|([0-9a-fA-F]{16}))?',value);require(match,'Unknown native time field')
 fraction=struct.unpack('<d',bytes.fromhex(match[2]))[0] if match[2] else 0
 require(math.isfinite(fraction) and 0<=fraction<1,'Invalid native subframe value');return int(match[1])+fraction

def field(block,name):
 pattern=rb'<'+name.encode()+rb'(?:>([^<]*)</'+name.encode()+rb'>|/>)';matches=list(re.finditer(pattern,block));require(len(matches)==1,'Ambiguous native field: '+name)
 return pattern,matches[0].group(1) or b''

def patch_checkpoint(source,target,spec):
 require(not target.exists(),'Native precision checkpoint exists; reconcile before retrying')
 fps=Fraction(spec['fps']['numerator'],spec['fps']['denominator']);rate=spec['sampleRate'];cuts=spec['cuts'];sources={s['id']:s for s in spec['sources']}
 original_hash=sha(source);entries=[];containers=0;proof=[]
 with zipfile.ZipFile(source) as archive:
  for info in archive.infolist():
   data=archive.read(info.filename)
   if info.filename.startswith('SeqContainer/') and info.filename.endswith('.xml'):
    containers+=1;require(SCHEMA_VERSION in data,'Unqualified Resolve native archive version; no precision rewrite')
    clips=list(re.finditer(rb'<Sm2TiAudioClip\b[^>]*>.*?</Sm2TiAudioClip>',data,re.S));require(len(clips)==len(cuts),'Native dialogue count differs; precision import requires an un-finished single dialogue track')
    replacements=[]
    for match,cut in zip(clips,cuts):
     require(cut.get('audioSourceId') and 'audioRecordSample' in cut,'Compile a bound played-audio plan before native precision execution')
     block=match.group(0);_,path=field(block,'MediaFilePath');require(html.unescape(path.decode())==sources[cut['audioSourceId']]['path'],'Native dialogue source differs from the paired plan')
     for name,expected in [('Start',cut['recordFrame']),('In',cut['sourceInFrame']),('Duration',cut['frames'])]:
      _,value=field(block,name);require(abs(read_time(value.decode())-expected)<1e-9,'Native frame placeholder changed: '+name)
     for name,samples in [('Start',cut['audioRecordSample']),('In',cut['audioInSample']),('Duration',cut['audioSamples'])]:
      pattern,_=field(block,name);text=('<'+name+'>'+native_time(samples,fps,rate)+'</'+name+'>').encode();block,count=re.subn(pattern,lambda m:text,block);require(count==1,'Native timing replacement failed')
     replacements.append((match.start(),match.end(),block));proof.append({'cutId':cut['id'],'sourceId':cut['audioSourceId'],'sourceInSample':cut['audioInSample'],'audioSamples':cut['audioSamples'],'audioRecordSample':cut['audioRecordSample']})
    # Resolve writes some XML tag names with double colons. Preserve the archive
    # verbatim except these three verified leaf fields; do not reserialize XML.
    for start,end,block in reversed(replacements):data=data[:start]+block+data[end:]
   entries.append((info,data))
 require(containers==1,'Expected one native sequence container')
 with target.open('xb') as file,zipfile.ZipFile(file,'w',zipfile.ZIP_DEFLATED) as output:
  for info,data in entries:output.writestr(info,data)
 require(sha(source)==original_hash,'Frame checkpoint changed during precision construction')
 return {'sourceCheckpointSha256':original_hash,'precisionCheckpointSha256':sha(target),'archiveVersion':'21.1.1.0010/17','cuts':proof,'status':'awaiting-native-import-and-range-readback'}
