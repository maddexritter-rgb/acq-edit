"""Shared validation only. Editorial decisions remain in Assembly Design."""
import hashlib,json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SKILLS=ROOT/'.local/skills'
def require(ok,message):
 if not ok:raise RuntimeError(message)
def sha(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 return h.hexdigest()
def read(path):return json.loads(Path(path).read_text())
def save(path,value):
 p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(value,f,indent=2)
def inside(root,p):
 p=Path(p).resolve();require(p.is_relative_to(Path(root).resolve()),'Path outside selected project');return p
def plan(project,packet):
 p=read(packet['plan']);require(p['schema']=='acq-edit/plan-v1','Unsupported plan');require(p['projectId']==project['id'] and p['backend']==project['backend'],'Plan identity/backend mismatch')
 for evidence in [p['brain'],p['editorial']]:
  file=evidence.get('receiptPath') or evidence.get('selectionPath');inside(project['root'],file);require(sha(file)==evidence['sha256'],'Pinned evidence changed')
 require(p['editorial']['reviewed'],'Reviewed source-word selection required')
 selection=read(p['editorial']['selectionPath'])
 if selection.get('testFixture'):
  require(os.environ.get('ACQ_EDIT_TEST_FIXTURE')=='1','Synthetic plans require explicit ACQ_EDIT_TEST_FIXTURE=1 and cannot certify editorial acceptance')
 else:
  sys.path.insert(0,str(SKILLS/'edit/scripts'))
  from compile_assembly import validate_compiled
  compiled_path=p['editorial'].get('compiledPath');require(compiled_path,'Canonical compiled source-word assembly required; timestamp-only plans are refused');inside(project['root'],compiled_path)
  require(sha(compiled_path)==p['editorial'].get('compiledSha256'),'Compiled assembly changed')
  compiled=validate_compiled(Path(compiled_path));require(compiled['design_sha256']==p['editorial']['sha256'],'Plan selection differs from compiled design')
  clips=[c for c in compiled['clips'] if c['id']==p['clipId']];require(len(clips)==1,'Exact compiled clip missing');spans=clips[0]['spans'];require(len(spans)==len(p['cuts']),'Cut plan does not match compiled source-word spans')
  for cut,span in zip(p['cuts'],spans):
   first,last=span['word_range'];require(cut['wordIds']==[str(i) for i in range(first,last+1)],'Cut word IDs do not match canonical selection')

 for s in p['sources']:
  inside(Path(project['root'])/'00_SOURCE',s['path']);require(sha(s['path'])==s['sha256'],'Source changed')
 end=0
 for c in p['cuts']:
  require(c['wordIds'] and c['boundaryEvidence'],'Source-word and speech-boundary evidence required')
  require(c['recordFrame']==end and c['frames']>0,'Noncontiguous cut plan');end+=c['frames']
 require(end>0,'No cuts');return p
def fingerprint(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def result_receipt(project,packet,p,native,media,inspection):
 require(Path(native).is_file() and Path(media).is_file(),'Native project or export missing')
 receipt={'schema':'acq-edit/render-v1','projectId':project['id'],'backend':project['backend'],'clipId':p['clipId'],'parentId':packet.get('parentId'),'media':str(media),'nativeProject':str(native),'nativeFingerprint':sha(native),'planPath':packet['plan'],'expected':{'frames':sum(c['frames'] for c in p['cuts']),'width':p['width'],'height':p['height'],'fps':str(p['fps']['numerator'])+'/'+str(p['fps']['denominator'])},'nativeInspectionPath':str(inspection),'nativeRendered':True,'qualification':'mechanical-fixture' if read(p['editorial']['selectionPath']).get('testFixture') else 'editorial-workflow'}
 save(packet['receipt'],receipt);return receipt
