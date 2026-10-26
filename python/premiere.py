"""Guarded Agent Lab adapter. Uses canonical scope/lease and stage owners."""
import sys,re,math
from fractions import Fraction
from pathlib import Path
from common import *
from premiere_plan import verify_source_cuts
from premiere_installation import verify as verify_installation
from premiere_session import inspect_result, open_project, reconcile_project
Profile=PremiereBridge=execute_operation=None
class Adapter:
 def __init__(self,config):
  global Profile,PremiereBridge,execute_operation
  self.installation=verify_installation(config,ROOT)
  # Do not import executable skill code before checking its materialization.
  sys.path.insert(0,str(SKILLS/'_shared'))
  from premiere_bridge import Profile,PremiereBridge,execute_operation
  profile=config.get('premiereProfile')
  require(isinstance(profile,str) and Path(profile).is_absolute() and Path(profile).is_file(),'Configure an explicit toolkit Premiere profile; global fallback is disabled')
  self.config=config;self.profile=Profile.load(profile)
 def doctor(self):
  client=PremiereBridge(self.profile)
  try:
   response=client.inspect('ping',{});ping=response.get('data',response)
   connected=ping.get('connected') is True;version=ping.get('premiereVersion')
   import re
   matches=isinstance(version,str) and re.match(r'^'+re.escape(self.profile.host_version)+r'(?:\D|$)',version) is not None
   return {'backend':'premiere','ready':connected and matches,'installation':self.installation,
           'connected':connected,'hostVersion':version,'expectedHostVersion':self.profile.host_version,
           'versionMatches':matches,'profileMode':self.profile.mode,'hostQualified':False,
           'projectLifecycle':'guarded create/reopen from an empty workspace; native host qualification pending',
           'repair':None if connected and matches else 'Open the isolated ACQ Edit Agent panel in the supported Premiere version; do not select the production connector'}
  except Exception as error:
   return {'backend':'premiere','ready':False,'installation':self.installation,'connected':None,
           'hostQualified':False,'profileMode':self.profile.mode,'connectionError':str(error)[:1000],
           'repair':'Open the isolated ACQ Edit Agent panel in Premiere 26.3.0, then rerun doctor. No production connector fallback was attempted'}
  finally:client.close()
 def inspect(self,project,packet):
  native=inside(project['root'],packet['nativeProject']);before_hash=sha(native)
  client=PremiereBridge(self.profile)
  try:
   state=client.inspect('lab_snapshot',{});result=inspect_result(project,native,state)
   require(result['nativeSha256']==before_hash,'Saved Premiere project changed during inspection')
   return result
  finally:client.close()
 def open(self,project,packet):return open_project(self,project,packet,PremiereBridge)
 def reconcile(self,project,packet):return reconcile_project(self,project,packet,PremiereBridge)
 def execute(self,project,packet):
  require(self.profile.mode=='scoped-edit','Production stages require scoped-edit profile');state=self.inspect(project,packet);require(state['fingerprint']==packet['expectedFingerprint'],'Native state changed; reconcile user edits')
  # Each operation was compiled by its owning canonical skill. The bridge checks exact
  # project, stage, input/output paths and the single-writer lease for every operation.
  native=inside(project['root'],packet['nativeProject']);operations=packet['operations'];require(isinstance(operations,list) and operations,'Native operations must be a nonempty list')
  timeout=packet.get('timeoutSeconds',120)
  require(type(timeout) in (int,float) and math.isfinite(timeout) and timeout>0,'Native operation timeout must be positive and finite')
  directory=inside(project['root'],packet['receiptDirectory']);paths=[];ids=set()
  # Validate the whole packet before the first mutation. A valid Lab scope for
  # another project must never authorize work outside this toolkit project.
  for index,operation in enumerate(operations):
   require(isinstance(operation,dict) and operation.get('schema')=='edit.native-operation/v1','Unknown native operation schema')
   require(operation.get('stage') in ['assembly','reframe','captions','music','export'],'Unknown stage owner')
   require(isinstance(operation.get('operation_id'),str) and re.fullmatch(r'[A-Za-z0-9_-]{1,80}',operation['operation_id']),'Invalid native operation ID')
   require(isinstance(operation.get('tool'),str) and re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',operation['tool']),'Invalid native operation tool')
   target=operation.get('target');require(isinstance(target,dict) and target.get('project_path')==str(native),'Operation targets another native project')
   require('sequence_id' in target and (target['sequence_id'] is None or isinstance(target['sequence_id'],str)),'Explicit native sequence identity required')
   require(isinstance(target.get('expected_revision'),str) and re.fullmatch(r'[a-f0-9]{64}',target['expected_revision']),'Exact native snapshot revision required')
   args=operation.get('arguments');require(isinstance(args,dict) and all(isinstance(k,str) and not k.startswith('_lab') for k in args),'Native arguments must not override Lab guards')
   for field in ['intended_changes','protected_state']:
    require(isinstance(operation.get(field),list) and operation[field],'Native operation must declare '+field)
   require(operation['operation_id'] not in ids,'Duplicate native operation ID');ids.add(operation['operation_id'])
   receipt=directory/f'{index:03}.json';require(not receipt.exists(),'Operation receipt exists; reconcile instead of replaying');paths.append(receipt)
  receipts=[];saved_hash=None;client=PremiereBridge(self.profile)
  try:
   # A missing local receipt is not evidence that a later native operation never
   # ran. Check every remote ID before dispatching the first item in the batch.
   # The canonical bridge still repeats its live checks at each submission.
   for operation in operations:
    op=operation['operation_id']
    prior=client.inspect('lab_get_operation',{'operation_id':op})
    job=client.inspect('lab_get_job',{'job_id':op})
    require(prior is None and job is None,'Native operation ID already exists; reconcile the original operation instead of starting this batch')
   directory.mkdir(parents=True,exist_ok=True)
   for operation,receipt in zip(operations,paths):
    receipts.append(execute_operation(client,operation,receipt,timeout=timeout))
    if operation['tool']=='save_project':saved_hash=sha(native)
  finally:client.close()
  return {'receipts':receipts,'savedNativeSha256':saved_hash,'status':'inspect-native-state-before-publishing'}
 build=execute
 revise=execute
 def render(self,project,packet):
  p=plan(project,packet);native=inside(project['root'],packet['nativeProject'])
  require(native.is_file(),'Saved native Premiere project required')
  output=inside(project['root'],packet['output']);inspection=inside(project['root'],packet['inspection']);receipt=inside(project['root'],packet['receipt'])
  require(len({output,inspection,receipt,native})==4,'Render artifacts must have distinct paths')
  require(not any(x.exists() for x in [output,inspection,receipt]),'Render artifact exists; reconcile instead of replaying')
  operations=packet['operations']
  require(len(operations)==2 and [x['tool'] for x in operations]==['save_project','lab_export_exact_range'],'Render requires one guarded save followed by one typed exact-range export')
  require(all(x['stage']=='export' for x in operations),'Render operations must belong to export')
  require(operations[0]['arguments']=={},'Save must preserve the current project path')
  args=operations[1]['arguments'];baseline=args['baseline']
  before=self.inspect(project,packet);state=before['state']
  require(before['fingerprint']==packet['expectedFingerprint'],'Native state changed before export')
  require(baseline['project']==str(native) and baseline['sequence']==state['sequenceId'],'Export baseline targets another project or sequence')
  require(all(x['target']=={'project_path':str(native),'sequence_id':state['sequenceId'],'expected_revision':state['revision']} for x in operations),'Export operation target differs from inspected state')
  ticks=Fraction(254016000000*p['fps']['denominator'],p['fps']['numerator']);frames=sum(c['frames'] for c in p['cuts'])
  require(ticks.denominator==1 and args['frame_ticks']==int(ticks),'Export frame grid differs from the plan')
  require(args['sample_rate']==p['sampleRate'],'Export sample grid differs from the plan')
  settings=baseline['state']['settings']
  require(settings['videoFrameWidth']==p['width'] and settings['videoFrameHeight']==p['height'] and int(settings['videoFrameRate']['ticks'])==int(ticks),'Native sequence geometry differs from the plan')
  require(Fraction(254016000000,int(settings['audioSampleRate']['ticks']))==p['sampleRate'],'Native sequence sample rate differs from the plan')
  require(args['start_ticks']=='0' and args['end_ticks']==str(frames*int(ticks)),'Export must cover the complete planned clip without trimming or padding')
  require(args['output_path']==str(output),'Native export output differs from receipt output')
  require(Path(args['preset_path']).is_absolute() and Path(args['preset_path']).is_file(),'Explicit installed export preset required')
  client=PremiereBridge(self.profile)
  try:
   observed=client.inspect('lab_inspect_export_state',{'project_path':str(native),'sequence_id':state['sequenceId']})
   observed=observed.get('data',observed)
   require(observed==baseline,'Export baseline changed; inspect current native state')
   links=client.inspect('inspect_assembly_links',{'project_path':str(native),'sequence_id':state['sequenceId'],'paged':True,'primary_av_only':True})
   links=links.get('data',links)
   source_verification=verify_source_cuts(p,state,links)
  finally:client.close()
  output.parent.mkdir(parents=True,exist_ok=True)
  execution=self.execute(project,packet);export=execution['receipts'][-1];native_hash=execution['savedNativeSha256']
  require(native_hash and sha(native)==native_hash,'Saved native project changed during export')
  require(export.get('path')==str(output) and export.get('start_ticks')==args['start_ticks'] and export.get('end_ticks')==args['end_ticks'] and export.get('expected_frames')==frames,'Native export result does not match requested range')
  require(export.get('preserved_bounded_state') is True and export.get('restored_in')==baseline['in_ticks'] and export.get('restored_out')==baseline['out_ticks'],'Native export did not confirm restored marks and preserved timeline')
  # Verify the actual file before issuing the shared success receipt. A settled
  # Lab operation is still only committed_unverified, never render acceptance.
  verification=verify_native_render(output,p)
  client=PremiereBridge(self.profile)
  try:
   final_links=client.inspect('inspect_assembly_links',{'project_path':str(native),'sequence_id':state['sequenceId'],'paged':True,'primary_av_only':True})
   final_links=final_links.get('data',final_links)
   require(final_links==links,'Native source or link state changed during export; reconcile before publication')
  finally:client.close()
  after=self.inspect(project,packet)
  require(after['fingerprint']==before['fingerprint'],'Native state changed during export; reconcile before publication')
  require(sha(native)==native_hash,'Saved native project changed during file verification')
  require(verify_source_cuts(p,after['state'],final_links)==source_verification,'Native source-cut verification changed during export')
  save(inspection,{'snapshot':after['state'],'nativeStateFingerprint':after['fingerprint'],'exportBaseline':baseline,'exportResult':export,'nativeSha256':native_hash,'mediaVerification':verification,'nativeSourceLinks':final_links,'sourceCutVerification':source_verification})
  return result_receipt(project,packet,p,native,output,inspection,verification=verification,expected_native_hash=native_hash,native_reopen=after['reopen'])
