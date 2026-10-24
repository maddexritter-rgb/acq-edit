"""Guarded Agent Lab adapter. Uses canonical scope/lease and stage owners."""
import sys
from fractions import Fraction
from pathlib import Path
from common import *
from premiere_plan import verify_source_cuts
from premiere_installation import verify as verify_installation
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
           'projectLifecycle':'requires dedicated project open; automatic creation/reopening not yet implemented',
           'repair':None if connected and matches else 'Open the isolated ACQ Edit Agent panel in the supported Premiere version; do not select the production connector'}
  except Exception as error:
   return {'backend':'premiere','ready':False,'installation':self.installation,'connected':None,
           'hostQualified':False,'profileMode':self.profile.mode,'connectionError':str(error)[:1000],
           'repair':'Open the isolated ACQ Edit Agent panel in Premiere 26.3.0, then rerun doctor. No production connector fallback was attempted'}
  finally:client.close()
 def inspect(self,project,packet):
  client=PremiereBridge(self.profile)
  try:
   state=client.inspect('lab_snapshot',{});require(state['projectPath']==str(inside(project['root'],packet['nativeProject'])),'Wrong native Premiere project');return {'state':state,'fingerprint':fingerprint(state)}
  finally:client.close()
 def execute(self,project,packet):
  require(self.profile.mode=='scoped-edit','Production stages require scoped-edit profile');state=self.inspect(project,packet);require(state['fingerprint']==packet['expectedFingerprint'],'Native state changed; reconcile user edits')
  # Each operation was compiled by its owning canonical skill. The bridge checks exact
  # project, stage, input/output paths and the single-writer lease for every operation.
  native=inside(project['root'],packet['nativeProject']);operations=packet['operations'];require(operations,'No native operations supplied')
  directory=inside(project['root'],packet['receiptDirectory']);paths=[];ids=set()
  # Validate the whole packet before the first mutation. A valid Lab scope for
  # another project must never authorize work outside this toolkit project.
  for index,operation in enumerate(operations):
   require(operation['stage'] in ['assembly','reframe','captions','music','export'],'Unknown stage owner')
   require(operation['target']['project_path']==str(native),'Operation targets another native project')
   require(operation['operation_id'] not in ids,'Duplicate native operation ID');ids.add(operation['operation_id'])
   receipt=directory/f'{index:03}.json';require(not receipt.exists(),'Operation receipt exists; reconcile instead of replaying');paths.append(receipt)
  directory.mkdir(parents=True,exist_ok=True)
  receipts=[];saved_hash=None;client=PremiereBridge(self.profile)
  try:
   for operation,receipt in zip(operations,paths):
    receipts.append(execute_operation(client,operation,receipt,timeout=packet.get('timeoutSeconds',120)))
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
   links=client.inspect('inspect_assembly_links',{'project_path':str(native),'sequence_id':state['sequenceId'],'paged':True})
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
   final_links=client.inspect('inspect_assembly_links',{'project_path':str(native),'sequence_id':state['sequenceId'],'paged':True})
   final_links=final_links.get('data',final_links)
   require(final_links==links,'Native source or link state changed during export; reconcile before publication')
  finally:client.close()
  after=self.inspect(project,packet)
  require(after['fingerprint']==before['fingerprint'],'Native state changed during export; reconcile before publication')
  require(sha(native)==native_hash,'Saved native project changed during file verification')
  require(verify_source_cuts(p,after['state'],final_links)==source_verification,'Native source-cut verification changed during export')
  save(inspection,{'snapshot':after['state'],'exportBaseline':baseline,'exportResult':export,'nativeSha256':native_hash,'mediaVerification':verification,'nativeSourceLinks':final_links,'sourceCutVerification':source_verification})
  return result_receipt(project,packet,p,native,output,inspection,verification=verification,expected_native_hash=native_hash)
