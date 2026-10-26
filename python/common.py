"""Shared validation only. Editorial decisions remain in Assembly Design."""
import hashlib,json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SKILLS=ROOT/'.local/skills'
def require(ok,message):
 if not ok:raise RuntimeError(message)
def timed_call(stage, function, *args, **kwargs):
 start=time.monotonic();status='failed'
 try:
  result=function(*args,**kwargs);status='complete';return result
 finally:
  folder=os.environ.get('ACQ_EDIT_NATIVE_OPERATION_DIR')
  if folder:
   with (Path(folder)/'performance.jsonl').open('a') as f:
    f.write(json.dumps({'stage':stage,'seconds':time.monotonic()-start,'status':status})+'\n')
def sha(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 return h.hexdigest()
def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def save(path,value):
 p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x',encoding='utf-8') as f:json.dump(value,f,indent=2)
def inside(root,p):
 p=Path(p).resolve();require(p.is_relative_to(Path(root).resolve()),'Path outside selected project');return p
def verify_plan_media(project,spec):
 """Hash the exact source/overlay bytes without touching an editor or repairing files."""
 results=[];failures=[]
 for role,folder,items in [('source','00_SOURCE',spec.get('sources',[])),('graphic','10_WORK',spec.get('graphics',[]))]:
  for index,item in enumerate(items):
   entry={'role':role,'id':item.get('id',str(index)),'path':item.get('path'),'expectedSha256':item.get('sha256')}
   try:
    target=inside(Path(project['root'])/folder,item['path'])
    require(target.is_file(),'Media is missing or is not a regular file')
    entry['actualSha256']=sha(target)
    require(entry['actualSha256']==item['sha256'],'Media bytes changed')
    results.append(entry)
   except (OSError,RuntimeError,KeyError,TypeError) as error:
    failures.append({**entry,'error':str(error)})
 if failures:
  raise RuntimeError('Input media verification failed. Preserve the existing files and versions; restore the exact expected bytes or import a new source and redesign. '+json.dumps(failures,ensure_ascii=False))
 return results
def plan(project,packet):
 p=read(inside(project['root'],packet['plan']));require(not p.get('hookContract'),'Opening text hooks have been removed; preserve legacy projects and use their pinned toolkit version');require(p['schema']=='acq-edit/plan-v1','Unsupported plan');require(p['projectId']==project['id'] and p['backend']==project['backend'],'Plan identity/backend mismatch')
 verified_media=timed_call('source-verification-before',verify_plan_media,project,p)
 for evidence in [p['brain'],p['editorial']]:
  file=evidence.get('receiptPath') or evidence.get('selectionPath');inside(project['root'],file);require(sha(file)==evidence['sha256'],'Pinned evidence changed')
 require(p['editorial']['reviewed'],'Reviewed source-word selection required')
 selection=read(p['editorial']['selectionPath'])
 if selection.get('testFixture'):
  require(os.environ.get('ACQ_EDIT_TEST_FIXTURE')=='1','Synthetic plans require explicit ACQ_EDIT_TEST_FIXTURE=1 and cannot certify editorial acceptance')
 else:
  require(p['backend'] not in ['filmcraft','resolve'] or not p.get('captions') or p.get('captionContract'),'Production FilmCraft/Resolve body captions require the pinned caption-clips handoff; basic fixture text is not a production fallback')
  from brain_receipts import verify_saved
  guidance=verify_saved(p['brain']['receiptPath'])
  if p['brain'].get('versionsPath'):
   versions=inside(project['root'],p['brain']['versionsPath']);require(sha(versions)==p['brain'].get('versionsSha256'),'Brain version index changed');index=read(versions)
   require(index.get('projectId')==project['id'] and index.get('sha256')==p['brain']['sha256'] and index.get('versions')==guidance['versions'],'Brain version index does not describe this project/context')
  from assembly_plan import verify_bound_plan
  verify_bound_plan(project,p,verified_media=verified_media)

 end=0
 for c in p['cuts']:
  require(c['wordIds'] and c['boundaryEvidence'],'Source-word and speech-boundary evidence required')
  require(c['recordFrame']==end and c['frames']>0,'Noncontiguous cut plan');end+=c['frames']
 require(end>0,'No cuts')
 for card in p.get('captions',[]):
  require(type(card.get('startFrame'))==int and type(card.get('endFrame'))==int and 0<=card['startFrame']<card['endFrame']<=end,'Caption timing lies outside the current cut plan')
  require(isinstance(card.get('text'),str) and card['text'].strip() and isinstance(card.get('style'),dict),'Caption text and native style required')
 if 'referenceStyle' in p:
  from reference_style import validate as validate_reference
  validate_reference(project,p)
 if 'captionVisibility' in p:
  from caption_visibility import ranges
  ranges(p)
 if p.get('captionContract'):
  from caption_plan import validate
  validate(project,p)
 from audio_plan import validate_audio
 validate_audio(project,p,end)
 from framing_plan import validate_framing
 validate_framing(project,p)
 from graphics_plan import validate_graphics
 validate_graphics(project,p,end)
 return p
def fingerprint(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def verify_native_render(media,spec):
 from fractions import Fraction
 info=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(media)]));streams=info.get('streams',[]);video=[s for s in streams if s['codec_type']=='video'];audio=[s for s in streams if s['codec_type']=='audio']
 require(len(video)==1 and audio,'Native output must contain exactly one picture stream and an audio stream; host completion is insufficient')
 v=video[0];require(v['width']==spec['width'] and v['height']==spec['height'],'Native render geometry differs')
 require(Fraction(v['avg_frame_rate'])==Fraction(spec['fps']['numerator'],spec['fps']['denominator']),'Native render frame rate differs')
 decoded=subprocess.run(['ffmpeg','-v','error','-xerror','-i',str(media),'-map','0:v:0','-map','0:a','-fps_mode','passthrough','-progress','pipe:1','-nostats','-f','null','-'],check=True,capture_output=True)
 progress=decoded.stdout.decode();counts=[int(line.split('=',1)[1]) for line in progress.splitlines() if line.startswith('frame=')]
 require('progress=end' in progress and counts and counts[-1]==sum(c['frames'] for c in spec['cuts']),'Native render frame count differs or decode did not finish')
 return {'frames':counts[-1],'width':v['width'],'height':v['height'],'fullDecode':True}

def result_receipt(project,packet,p,native,media,inspection,*,verification=None,expected_native_hash=None,native_reopen=None,finishing_evidence=None):
 require(Path(native).is_file() and Path(media).is_file(),'Native project or export missing')
 # Adapters may supply the result of this same verifier when they need a final
 # native-state readback after decoding. This is internal, never a packet field.
 if verification is None:verification=timed_call('render-full-decode',verify_native_render,media,p)
 if expected_native_hash is not None:require(sha(native)==expected_native_hash,'Saved native project changed during render verification')
 receipt={'schema':'acq-edit/render-v1','projectId':project['id'],'backend':project['backend'],'clipId':p['clipId'],'parentId':packet.get('parentId'),'media':str(media),'nativeProject':str(native),'nativeFingerprint':sha(native),'planPath':packet['plan'],'expected':{'frames':sum(c['frames'] for c in p['cuts']),'width':p['width'],'height':p['height'],'fps':str(p['fps']['numerator'])+'/'+str(p['fps']['denominator'])},'nativeInspectionPath':str(inspection),**({'jobId':os.environ['ACQ_EDIT_JOB_ID']} if os.environ.get('ACQ_EDIT_JOB_ID') else {}),'nativeRendered':True,'mediaVerification':verification,'qualification':'mechanical-fixture' if read(p['editorial']['selectionPath']).get('testFixture') else 'editorial-workflow'}
 if finishing_evidence is not None:receipt['finishingEvidence']=finishing_evidence
 if native_reopen is not None:
  state=read(inspection)
  if project['backend']=='premiere':
   require(set(native_reopen)=={'schema','nativeProject','nativeSha256','expectedFingerprint','sequenceId'} and native_reopen.get('schema')=='acq-edit/premiere-reopen-v1','Native reopen packet contains unexpected fields')
   require(native_reopen['nativeProject']==str(native)==state['snapshot']['projectPath'] and native_reopen['nativeSha256']==sha(native)==state['nativeSha256'] and native_reopen['sequenceId']==state['snapshot']['sequenceId'] and fingerprint(state['snapshot'])==native_reopen['expectedFingerprint']==state['nativeStateFingerprint'],'Native reopen identity/fingerprint differs from rendered inspection')
  else:
   require(project['backend']=='resolve' and state['project']=='ACQ_'+project['id'] and state['timeline']==native_reopen['timelineId'] and fingerprint(state)==native_reopen['expectedFingerprint'],'Native reopen identity/fingerprint differs from rendered inspection')
   require(set(native_reopen)=={'nativeProjectId','database','timelineId','expectedFingerprint'},'Native reopen packet contains unexpected fields')
  receipt['nativeReopen']={**native_reopen,'inspectionSha256':sha(inspection)}
 if receipt['qualification']=='editorial-workflow':
  from brain_receipts import verify_saved
  receipt['brainEvidence']=verify_saved(p['brain']['receiptPath'])
 if p.get('captionContract'):
  from caption_plan import validate
  captions=validate(project,p)
  receipt['captionEvidence']={'owner':'caption-clips','handoffSha256':p['captionContract']['sha256'],'helperHashes':captions['helperHashes'],'shadowProfile':captions['shadowProfile'],'cards':len(captions['cards'])}
  if p.get('captionVisibility'):receipt['captionEvidence']['visibility']=p['captionVisibility']
 if 'referenceStyle' in p:
  from reference_style import validate as validate_reference
  receipt['referenceEvidence']={'contract':p['referenceStyle'],'snapshot':validate_reference(project,p)}
 if packet.get('recutVerification'):
  proof_path=inside(project['root'],packet['recutVerification']);proof=read(proof_path)
  require(proof.get('schema')=='acq-edit/recut-execution-v1' and proof['backend']==project['backend'] and proof['parentVersionId']==packet.get('parentId') and proof['parentPreserved'] is True,'Recut verification identity differs')
  require(proof['planSha256']==sha(packet['plan']) and proof['newNativeSha256']==sha(native) and proof['construction']['fingerprint']==packet['expectedFingerprint'],'Recut plan/native evidence changed before rendering')
  receipt.update(recutVerificationPath=str(proof_path),recutVerificationSha256=sha(proof_path))
 require(read(inside(project['root'],packet['plan']))==p,'Plan changed during native execution; preserve output and reconcile before publication')
 receipt['inputMediaVerification']={'phase':'after-render-verification','files':timed_call('source-verification-after',verify_plan_media,project,p)}
 save(inside(project['root'],packet['receipt']),receipt);return receipt
