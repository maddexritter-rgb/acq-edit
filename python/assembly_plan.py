"""Bind canonical source-word and paired-seam decisions to native execution.

The existing skill compilers choose/resolve the ranges. This module only translates
and verifies their output; it never guesses speech boundaries or rewrites words.
"""
import argparse,json,os,subprocess,sys
from fractions import Fraction
from pathlib import Path
from common import SKILLS,inside,read,require,save,sha

def pinned(project,record,path_key,hash_key):
 path=inside(project['root'],record[path_key]);require(sha(path)==record[hash_key],'Pinned assembly input changed: '+path_key);return path

def bound_assembly(project,spec,verified_media=None):
 editorial=spec['editorial'];selection=pinned(project,editorial,'selectionPath','sha256');design=read(selection)
 require(design.get('schema')=='edit.assembly-selection/v2','Native spoken cuts require canonical v2 source-word design')
 compiled_path=pinned(project,editorial,'compiledPath','compiledSha256');saved=read(compiled_path)
 require(inside(project['root'],saved['design_path'])==selection,'Compiled design identity differs')
 for row in design['clips']:
  inside(project['root'],row['source_words']);inside(Path(project['root'])/'00_SOURCE',row['media'])
 sys.path.insert(0,str(SKILLS/'edit/scripts'));sys.path.insert(0,str(SKILLS/'assembly-design/scripts'))
 from compile_assembly import validate_compiled
 from pair_audio_seams import compile_pairs
 from validate_paired_word_coverage import validate
 compiled=validate_compiled(compiled_path);require(compiled['design_sha256']==editorial['sha256'],'Compiled selection hash differs')
 clips=[c for c in compiled['clips'] if c['id']==spec['clipId']];require(len(clips)==1,'Exact compiled clip missing');clip=clips[0]
 row=next(c for c in design['clips'] if c['id']==spec['clipId'])
 require(inside(project['root'],row['brain_preflight'])==inside(project['root'],spec['brain']['receiptPath']),'Brain receipt differs from the selected design')
 require(sha(spec['brain']['receiptPath'])==spec['brain']['sha256'],'Brain receipt changed')
 execution=editorial.get('execution');require(isinstance(execution,dict),'Pinned paired decisions and played-source routing required')
 decisions=pinned(project,execution,'decisionsPath','decisionsSha256');routing_path=pinned(project,execution,'routingPath','routingSha256');routing=read(routing_path)
 evidence=routing['evidence'];pinned(project,evidence,'path','sha256')
 d=read(decisions);paired=compile_pairs(d)
 require(all(j['status']!='PROPOSED' for j in paired['joins']),'Inspect both sides of each join before execution')
 require(d.get('outer_edge_evidence',{}).get('status') in ['LOCALLY_INSPECTED','LISTENED','EDITOR_APPROVED'],'Inspect both outer audio edges before execution')
 if d.get('selection'):require(inside(project['root'],d['selection'])==selection,'Paired decisions refer to another selection')
 require(paired['sample_rate']==spec['sampleRate'] and Fraction(paired['fps'])==Fraction(spec['fps']['numerator'],spec['fps']['denominator']),'Paired and native clocks differ')
 phones=pinned(project,execution,'phonemesPath','phonemesSha256') if execution.get('phonemesPath') else None
 coverage=validate(selection,paired,spec['clipId'],phones);require(not coverage['wholly_outside_word_count'],'Selected source word lies outside played audio')
 require(len(clip['spans'])==len(paired['source_frames']),'Paired cuts differ from selected spans')
 require(routing.get('source_clock_offset_samples')==0,'Nonzero source clock offsets require an explicit supported conform')
 def source_for(path):
  path=inside(Path(project['root'])/'00_SOURCE',path);items=[s for s in spec['sources'] if Path(s['path']).resolve()==path]
  require(len(items)==1,'Played source must identify exactly one project-owned source');s=items[0]
  if verified_media is None:actual=sha(path)
  else:
   matches=[m for m in verified_media if m['role']=='source' and m['id']==s['id'] and Path(m['path']).resolve()==path and m['expectedSha256']==s['sha256']]
   require(len(matches)==1,'Verified media set does not cover this source');actual=matches[0]['actualSha256']
  require(s['projectId']==project['id'] and actual==s['sha256'],'Played source changed or belongs to another project');return s
 picture=source_for(routing['picture']);audio=source_for(routing['media']);require(Path(clip['media']).resolve()==Path(audio['path']).resolve(),'Design and played audio identity differ')
 streams=lambda path:json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(path)]))['streams']
 au=[s for s in streams(audio['path']) if s['codec_type']=='audio'];vi=[s for s in streams(picture['path']) if s['codec_type']=='video']
 require(len(au)==1 and au[0]['codec_name'].startswith('pcm_') and int(au[0]['sample_rate'])==spec['sampleRate'],'Played dialogue must be matched-rate PCM with one explicit stream')
 require(au[0]['channels']==1 and routing.get('stream')==0 and routing.get('channel')==0,'Native shared dialogue route currently requires an explicitly prepared mono channel; never guess a stereo speaker channel')
 fps=Fraction(paired['fps']);require(len(vi)==1 and Fraction(vi[0]['r_frame_rate'])==fps and Fraction(vi[0]['avg_frame_rate'])==fps,'Picture must use the reviewed constant frame rate')
 cuts=[];cursor=0
 for index,(span,fr,sm,tm) in enumerate(zip(clip['spans'],paired['source_frames'],paired['source_samples'],paired['timeline_samples'])):
  first,last=span['word_range'];cuts.append({'id':f'span-{index+1}','sourceId':picture['id'],'audioSourceId':audio['id'],'sourceInFrame':fr[0],'frames':fr[1]-fr[0],'recordFrame':cursor,'audioInSample':sm[0],'audioSamples':sm[1]-sm[0],'audioRecordSample':tm[0],'wordIds':[str(i) for i in range(first,last+1)],'boundaryEvidence':str(decisions)});cursor+=fr[1]-fr[0]
 return {'cuts':cuts,'coverage':coverage,'durationFrames':cursor,'qualification':'source-word and paired-geometry binding; no listening or human approval'}

def verify_bound_plan(project,spec,verified_media=None):
 # Resolve's bundled interpreter has no scientific dependencies. The configured
 # shared interpreter owns canonical analysis; no other editor is imported.
 if verified_media is not None and spec['backend']!='resolve':
  expected=bound_assembly(project,spec,verified_media)['cuts']
  require(spec['cuts']==expected,'Native cuts differ from canonical source-word, picture or paired-audio ranges; recompile the plan')
  return
 interpreter=os.environ.get('ACQ_EDIT_SHARED_PYTHON',sys.executable)
 result=subprocess.run([interpreter,str(Path(__file__).resolve()),'verify'],input=json.dumps({'project':project,'spec':spec}),text=True,capture_output=True,timeout=300)
 require(result.returncode==0,'Canonical assembly binding failed: '+result.stderr.strip())
 expected=json.loads(result.stdout)['cuts'];require(spec['cuts']==expected,'Native cuts differ from canonical source-word, picture or paired-audio ranges; recompile the plan')

def compile_plan(project,packet):
 spec=read(inside(project['root'],packet['template']));require(spec['projectId']==project['id'] and spec['backend']==project['backend'],'Template identity/backend mismatch')
 require(not spec.get('cuts') and not spec.get('captions') and not spec.get('graphics') and not spec.get('framing') and not spec.get('audio',{}).get('music'),'Compile from an empty assembly template; recuts require fresh dependent finishing plans')
 binding=bound_assembly(project,spec);spec['cuts']=binding['cuts'];target=inside(project['root'],packet['output']);save(target,spec)
 from common import plan
 plan(project,{'plan':str(target)})
 return {'plan':str(target),'sha256':sha(target),'coverage':binding['coverage'],'durationFrames':binding['durationFrames'],'status':'compiled-awaiting-native-build-and-editorial-review'}

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('action',choices=['verify']);args=parser.parse_args()
 try:
  data=json.load(sys.stdin);print(json.dumps(bound_assembly(data['project'],data['spec'])))
 except Exception as error:
  print(str(error),file=sys.stderr);sys.exit(1)
