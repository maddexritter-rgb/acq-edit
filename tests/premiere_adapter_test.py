"""Adapter failure-boundary tests. Fake host responses never certify Premiere."""
import copy,importlib.util,json,sys,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'python'))
from common import fingerprint,sha
# Do not require an installed personal profile or materialized integration in CI.
bridge=types.ModuleType('premiere_bridge');bridge.Profile=object;bridge.PremiereBridge=object;bridge.execute_operation=None
with patch.dict(sys.modules,{'premiere_bridge':bridge}):
 spec=importlib.util.spec_from_file_location('premiere_adapter_under_test',ROOT/'python/premiere.py')
 premiere=importlib.util.module_from_spec(spec);spec.loader.exec_module(premiere)

class PremiereDoctorTests(unittest.TestCase):
 def test_doctor_uses_only_ping_and_does_not_dump_current_project(self):
  adapter=premiere.Adapter.__new__(premiere.Adapter)
  adapter.profile=types.SimpleNamespace(mode='scoped-edit',host_version='26.3.0')
  adapter.installation={'verified':True,'hostQualified':False}
  for connected,version,ready in [(True,'26.3.0 (build 12)',True),(False,'26.3.0',False),(True,'27.0.0',False),(True,'26.3.01',False)]:
   with self.subTest(connected=connected,version=version):
    calls=[]
    class Client:
     def __init__(self,profile):pass
     def inspect(self,name,args):
      calls.append(name)
      return {'data':{'connected':connected,'premiereVersion':version,'privateProject':{'tracks':'private source data'}}}
     def close(self):calls.append('close')
    with patch.object(premiere,'PremiereBridge',Client):result=adapter.doctor()
    self.assertEqual(calls,['ping','close']);self.assertEqual(result['ready'],ready)
    self.assertNotIn('private',json.dumps(result));self.assertFalse(result['hostQualified'])

 def test_constructor_verifies_installation_before_loading_or_starting_bridge(self):
  with patch.object(premiere,'verify_installation',side_effect=RuntimeError('external profile refused')),patch.object(premiere,'Profile') as profile,patch.object(premiere,'PremiereBridge') as client:
   with self.assertRaisesRegex(RuntimeError,'external profile'):premiere.Adapter({'premiereProfile':'/external/profile.json'})
   profile.assert_not_called();client.assert_not_called()

 def test_missing_panel_reports_unready_without_inspecting_or_switching_projects(self):
  adapter=premiere.Adapter.__new__(premiere.Adapter);adapter.profile=types.SimpleNamespace(mode='scoped-edit');adapter.installation={'verified':True}
  calls=[]
  class Client:
   def __init__(self,profile):pass
   def inspect(self,name,args):calls.append(name);raise RuntimeError('Panel probe timed out')
   def close(self):calls.append('close')
  with patch.object(premiere,'PremiereBridge',Client):result=adapter.doctor()
  self.assertEqual(calls,['ping','close']);self.assertFalse(result['ready']);self.assertIsNone(result['connected'])
  self.assertIn('Panel probe timed out',result['connectionError']);self.assertIn('isolated ACQ Edit Agent',result['repair'])

class PremiereAdapterTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name).resolve()
  self.native=self.root/'edit.prproj';self.native.write_bytes(b'fake saved host checkpoint')
  self.preset=self.root/'fixture.epr';self.preset.write_text('fake preset')
  self.project={'id':'fixture','root':str(self.root),'backend':'premiere'}
  self.state={'projectPath':str(self.native),'sequenceId':'sequence-1','revision':'a'*64,'tracks':[]}
  self.baseline={'project':str(self.native),'sequence':'sequence-1','state':{'tracks':[],'settings':{'videoFrameWidth':640,'videoFrameHeight':360,'videoFrameRate':{'ticks':'10160640000'},'audioSampleRate':{'ticks':'5292000'}}},'in_ticks':'0','out_ticks':'508032000000'}
  target={'project_path':str(self.native),'sequence_id':'sequence-1','expected_revision':'a'*64}
  def operation(tool,args,index):return {'schema':'edit.native-operation/v1','stage':'export','operation_id':f'op-{index}','tool':tool,'target':copy.deepcopy(target),'arguments':args,'intended_changes':['export only'],'protected_state':['all editorial state']}
  export={'baseline':copy.deepcopy(self.baseline),'start_ticks':'0','end_ticks':'508032000000','frame_ticks':10160640000,'sample_rate':48000,'preset_path':str(self.preset),'output_path':str(self.root/'render/clip.mp4')}
  self.packet={'nativeProject':str(self.native),'expectedFingerprint':fingerprint(self.state),'plan':str(self.root/'plan.json'),'output':export['output_path'],'inspection':str(self.root/'inspection.json'),'receipt':str(self.root/'receipt.json'),'receiptDirectory':str(self.root/'operations'),'operations':[operation('save_project',{},1),operation('lab_export_exact_range',export,2)]}
  selection=self.root/'selection.json';selection.write_text(json.dumps({'testFixture':True}))
  (self.root/'00_SOURCE').mkdir();source=self.root/'00_SOURCE/source.mov';source.write_bytes(b'fake fixture source')
  self.plan={'clipId':'clip-1','fps':{'numerator':25,'denominator':1},'width':640,'height':360,'sampleRate':48000,'sources':[{'id':'source','path':str(source),'sha256':sha(source)}],
   'cuts':[{'id':f'cut-{i}','sourceId':'source','frames':25,'recordFrame':i*25,'sourceInFrame':i*50,'audioInSample':i*96000,'audioSamples':48000} for i in range(2)],'editorial':{'selectionPath':str(selection)}}
  self.links={'project_path':str(self.native),'sequence_id':'sequence-1','frame_duration_ticks':'10160640000','verification':'stable_complete_paged_native_link_membership','items':[]}
  for kind,kind_id in [('video',0),('audio',1)]:
   track={'kind':kind_id,'index':0,'muted':False,'clips':[]};self.state['tracks'].append(track)
   for i,cut in enumerate(self.plan['cuts']):
    node=f'{kind}-{i}';start=cut['recordFrame']*10160640000;left=cut['sourceInFrame']*10160640000;duration=cut['frames']*10160640000
    item={'node_id':node,'source_id':'native-source','media_path':str(source),'offline':False,'start_ticks':str(start),'end_ticks':str(start+duration),'source_in_ticks':str(left),'source_out_ticks':str(left+duration),'speed':1,'speed_reversed':False,'disabled':False}
    self.links['items'].append({'kind':kind,'track_index':0,'item_index':i,'item':item,'linked_node_ids':[f'{"audio" if kind=="video" else "video"}-{i}'],'self_included':False})
    track['clips'].append({'id':node,'sourceId':'native-source','start':item['start_ticks'],'end':item['end_ticks'],'inPoint':item['source_in_ticks'],'outPoint':item['source_out_ticks'],'speed':1,'disabled':False})
  self.packet['expectedFingerprint']=fingerprint(self.state)
  Path(self.packet['plan']).write_text(json.dumps(self.plan))
  self.result={'path':export['output_path'],'start_ticks':export['start_ticks'],'end_ticks':export['end_ticks'],'expected_frames':50,'preserved_bounded_state':True,'restored_in':'0','restored_out':export['end_ticks']}
  self.mutations=[];self.remote_records={};self.batch_reads=[];self.link_calls=0;self.observed_baseline=copy.deepcopy(self.baseline);self.verification={'frames':50,'width':640,'height':360,'fullDecode':True}
  owner=self
  class Client:
   def __init__(self,profile):pass
   def inspect(self,name,args):
    if name=='lab_snapshot':return copy.deepcopy(owner.state)
    if name=='lab_inspect_export_state':return {'success':True,'data':copy.deepcopy(owner.observed_baseline)}
    if name=='inspect_assembly_links':
     owner.assertEqual(args,{'project_path':str(owner.native),'sequence_id':'sequence-1','paged':True});owner.link_calls+=1;return {'success':True,'data':copy.deepcopy(owner.links)}
    if name in ['lab_get_operation','lab_get_job']:
     key=(name,next(iter(args.values())));owner.batch_reads.append(key);return copy.deepcopy(owner.remote_records.get(key))
    raise AssertionError(name)
   def close(self):pass
  def execute(client,operation,receipt,timeout):
   self.mutations.append(operation['tool']);receipt.write_text(json.dumps({'fake':True,'operation':operation}))
   if operation['tool']=='lab_export_exact_range':Path(self.packet['output']).write_bytes(b'fake output; verifier mocked');return copy.deepcopy(self.result)
   return {'saved':True}
  self.addCleanup(patch.stopall)
  patch.object(premiere,'PremiereBridge',Client).start()
  self.executor=patch.object(premiere,'execute_operation',side_effect=execute).start()
  patch.object(premiere,'plan',return_value=self.plan).start()
  self.verifier=patch.object(premiere,'verify_native_render',return_value=self.verification).start()
  self.adapter=premiere.Adapter.__new__(premiere.Adapter);self.adapter.profile=types.SimpleNamespace(mode='scoped-edit');self.adapter.config={}

 def test_success_receipt_requires_save_exact_export_decode_and_final_state(self):
  result=self.adapter.render(self.project,self.packet)
  self.assertEqual(self.mutations,['save_project','lab_export_exact_range']);self.verifier.assert_called_once()
  self.assertTrue(result['nativeRendered']);self.assertEqual(result['backend'],'premiere')
  self.assertEqual(result['nativeFingerprint'],sha(self.native));self.assertEqual(result['qualification'],'mechanical-fixture')
  self.assertEqual(json.loads(Path(self.packet['inspection']).read_text())['snapshot'],self.state)
  evidence=json.loads(Path(self.packet['inspection']).read_text());self.assertEqual(evidence['nativeSourceLinks'],self.links)
  self.assertEqual(len(evidence['sourceCutVerification']['mapping']),2);self.assertEqual(self.link_calls,2)

 def test_later_malformed_stage_packet_cannot_partially_edit_native_project(self):
  original=sha(self.native)
  cases=[lambda o:o.update(schema='wrong'),lambda o:o.update(operation_id='../unsafe'),
   lambda o:o.update(tool=None),lambda o:o.update(stage='unknown'),lambda o:o.update(target=None),
   lambda o:o['target'].pop('sequence_id'),lambda o:o['target'].update(expected_revision='stale'),
   lambda o:o.update(arguments=[]),lambda o:o['arguments'].update(_lab={'operation_id':'other'}),
   lambda o:o.update(intended_changes=[]),lambda o:o.update(protected_state=None)]
  for change in cases:
   packet=copy.deepcopy(self.packet);change(packet['operations'][1])
   with self.subTest(packet=packet['operations'][1]),self.assertRaises(RuntimeError):self.adapter.execute(self.project,packet)
   self.assertEqual(self.mutations,[]);self.assertEqual(self.batch_reads,[])
   self.assertFalse(Path(packet['receiptDirectory']).exists());self.assertEqual(sha(self.native),original)

 def test_existing_later_remote_operation_refuses_whole_batch_without_local_receipts(self):
  original=sha(self.native)
  for endpoint in ['lab_get_operation','lab_get_job']:
   # Settled, unknown and even malformed existing records cannot be replayed.
   for record in [{'status':'committed_unverified'},{'state':'running'},{}]:
    self.remote_records={(endpoint,'op-2'):record};self.batch_reads.clear()
    with self.subTest(endpoint=endpoint,record=record),self.assertRaisesRegex(RuntimeError,'already exists'):
     self.adapter.execute(self.project,self.packet)
    self.assertEqual(self.mutations,[]);self.assertEqual(len(self.batch_reads),4)
    self.assertFalse(Path(self.packet['receiptDirectory']).exists());self.assertEqual(sha(self.native),original)

 def test_all_remote_ids_checked_before_dispatch_and_positive_timeout_required(self):
  original=self.executor.side_effect
  def checked(*args,**kwargs):
   self.assertEqual(self.batch_reads,[('lab_get_operation','op-1'),('lab_get_job','op-1'),('lab_get_operation','op-2'),('lab_get_job','op-2')])
   return original(*args,**kwargs)
  for timeout in [0,-1,True,float('nan'),float('inf'),'120']:
   packet=copy.deepcopy(self.packet);packet['timeoutSeconds']=timeout
   with self.subTest(timeout=timeout),self.assertRaisesRegex(RuntimeError,'timeout'):self.adapter.execute(self.project,packet)
   self.assertEqual(self.mutations,[]);self.assertEqual(self.batch_reads,[])
  self.executor.side_effect=checked;self.adapter.render(self.project,self.packet)
  self.assertEqual(self.mutations,['save_project','lab_export_exact_range'])

 def test_wrong_native_passage_source_link_or_playback_stops_before_export(self):
  original=copy.deepcopy(self.links)
  cases=[
   lambda l:l.update(project_path=str(self.root/'other.prproj')),
   lambda l:l.update(sequence_id='other-sequence'),
   lambda l:l.update(frame_duration_ticks='8467200000'),
   lambda l:l.update(verification='same_source_overlap_guess'),
   lambda l:l['items'][0]['item'].update(media_path=str(self.root/'wrong.mov')),
   lambda l:l['items'][0]['item'].update(offline=True),
   lambda l:l['items'][0]['item'].update(source_in_ticks='1'),
   lambda l:l['items'][0]['item'].update(start_ticks='0.0'),
   lambda l:l['items'][0]['item'].update(speed=2),
   lambda l:l['items'][0]['item'].update(speed_reversed=True),
   lambda l:l['items'][0]['item'].update(disabled=True),
   lambda l:l['items'][0].update(linked_node_ids=[]),
   lambda l:l['items'][2].update(linked_node_ids=['video-1']),
   lambda l:l['items'].append(copy.deepcopy(l['items'][0])),
   lambda l:l['items'].pop(),
  ]
  for i,change in enumerate(cases):
   with self.subTest(case=i):
    self.links=copy.deepcopy(original);change(self.links)
    with self.assertRaises(RuntimeError):self.adapter.render(self.project,self.packet)
    self.assertEqual(self.mutations,[]);self.assertFalse(Path(self.packet['receipt']).exists())

 def test_muted_dialogue_and_inconsistent_snapshots_are_not_valid_plan_execution(self):
  original=copy.deepcopy(self.state)
  for field in ['muted','sourceId','inPoint']:
   self.state=copy.deepcopy(original)
   if field=='muted':self.state['tracks'][1]['muted']=True
   else:self.state['tracks'][0]['clips'][0][field]='different' if field=='sourceId' else '5292000'
   self.packet['expectedFingerprint']=fingerprint(self.state)
   with self.subTest(field=field),self.assertRaises(RuntimeError):self.adapter.render(self.project,self.packet)
   self.assertEqual(self.mutations,[])

 def test_native_relink_during_export_is_not_hidden_by_unchanged_snapshot(self):
  def relink(*args):self.links['items'][0]['linked_node_ids']=[];return self.verification
  self.verifier.side_effect=relink
  with self.assertRaisesRegex(RuntimeError,'source or link state changed'):self.adapter.render(self.project,self.packet)
  self.assertEqual(self.mutations,['save_project','lab_export_exact_range']);self.assertFalse(Path(self.packet['receipt']).exists())
  self.assertTrue(Path(self.packet['output']).exists())

 def test_sample_precise_separate_audio_source_is_verified_without_frame_rounding(self):
  source=self.root/'00_SOURCE/dialogue.wav';source.write_bytes(b'fake separate dialogue')
  self.plan['sources'].append({'id':'dialogue','path':str(source),'sha256':sha(source)})
  cut=self.plan['cuts'][0];cut.update(audioSourceId='dialogue',audioInSample=11,audioRecordSample=11,audioSamples=47989)
  item=self.links['items'][2]['item'];item.update(source_id='native-dialogue',media_path=str(source),start_ticks=str(11*5292000),source_in_ticks=str(11*5292000))
  clip=self.state['tracks'][1]['clips'][0];clip.update(sourceId='native-dialogue',start=item['start_ticks'],inPoint=item['source_in_ticks'])
  self.packet['expectedFingerprint']=fingerprint(self.state);Path(self.packet['plan']).write_text(json.dumps(self.plan))
  self.adapter.render(self.project,self.packet)
  evidence=json.loads(Path(self.packet['inspection']).read_text());self.assertEqual(evidence['sourceCutVerification']['mapping'][0]['audioSourceId'],'dialogue')

 def test_missing_profile_never_falls_back_to_global_production_connector(self):
  for config in [{},{'premiereProfile':''},{'premiereProfile':'relative.json'},{'premiereProfile':str(self.root/'missing.json')}]:
   with self.subTest(config=config),self.assertRaisesRegex(RuntimeError,'production profiles are refused'):premiere.Adapter(config)

 def test_entire_operation_packet_is_preflighted_before_any_mutation(self):
  for change,reason in [
   (lambda ops:ops[1]['target'].update(project_path=str(self.root/'other.prproj')),'another native project'),
   (lambda ops:ops[1].update(operation_id=ops[0]['operation_id']),'Duplicate native operation'),
   (lambda ops:ops[1].update(stage='unknown'),'Unknown stage')]:
   with self.subTest(reason=reason):
    packet=copy.deepcopy(self.packet);change(packet['operations'])
    with self.assertRaisesRegex(RuntimeError,reason):self.adapter.execute(self.project,packet)
    self.assertEqual(self.mutations,[])
  directory=Path(self.packet['receiptDirectory']);directory.mkdir();(directory/'001.json').write_text('prior uncertain attempt')
  with self.assertRaisesRegex(RuntimeError,'receipt exists'):self.adapter.execute(self.project,self.packet)
  self.assertEqual(self.mutations,[])

 def test_invalid_export_contract_never_dispatches_save_or_export(self):
  cases=[
   (lambda p:p.update(output=str(self.root.parent/'outside.mp4')),'outside selected project'),
   (lambda p:p['operations'][1]['arguments'].update(start_ticks='10160640000'),'complete planned clip'),
   (lambda p:p['operations'][1]['arguments'].update(frame_ticks=8467200000),'frame grid'),
   (lambda p:p['operations'][1]['arguments'].update(sample_rate=44100),'sample grid'),
   (lambda p:p['operations'][1]['arguments']['baseline']['state']['settings'].update(videoFrameWidth=1920),'sequence geometry'),
   (lambda p:p['operations'][1]['arguments'].update(output_path=str(self.root/'other.mp4')),'output differs'),
   (lambda p:p['operations'][1].update(tool='export_sequence'),'typed exact-range'),
   (lambda p:p['operations'][0].update(arguments={'path':str(self.root/'new.prproj')}),'preserve the current project'),
   (lambda p:p.update(expectedFingerprint='old'),'Native state changed'),
  ]
  for change,reason in cases:
   with self.subTest(reason=reason):
    packet=copy.deepcopy(self.packet);change(packet)
    with self.assertRaisesRegex(RuntimeError,reason):self.adapter.render(self.project,packet)
    self.assertEqual(self.mutations,[])

 def test_stale_marks_and_preexisting_output_stop_before_mutation(self):
  self.observed_baseline['in_ticks']='5292000'
  with self.assertRaisesRegex(RuntimeError,'baseline changed'):self.adapter.render(self.project,self.packet)
  self.assertEqual(self.mutations,[])
  self.observed_baseline=copy.deepcopy(self.baseline);Path(self.packet['receipt']).write_text('existing result')
  with self.assertRaisesRegex(RuntimeError,'artifact exists'):self.adapter.render(self.project,self.packet)
  self.assertEqual(self.mutations,[])

 def test_host_success_without_mark_restoration_never_becomes_receipt(self):
  self.result['restored_out']='0'
  with self.assertRaisesRegex(RuntimeError,'restored marks'):self.adapter.render(self.project,self.packet)
  self.verifier.assert_not_called();self.assertFalse(Path(self.packet['receipt']).exists())

 def test_decode_failure_preserves_operation_evidence_without_success_receipt(self):
  self.verifier.side_effect=RuntimeError('audio-only render')
  with self.assertRaisesRegex(RuntimeError,'audio-only'):self.adapter.render(self.project,self.packet)
  self.assertEqual(len(list(Path(self.packet['receiptDirectory']).glob('*.json'))),2)
  self.assertFalse(Path(self.packet['receipt']).exists())

 def test_native_edits_during_verification_prevent_publication(self):
  def change_state(*args):self.state['revision']='b'*64;return self.verification
  self.verifier.side_effect=change_state
  with self.assertRaisesRegex(RuntimeError,'Native state changed during export'):self.adapter.render(self.project,self.packet)
  self.assertFalse(Path(self.packet['receipt']).exists())

 def test_saved_project_edits_during_verification_prevent_publication(self):
  def change_file(*args):self.native.write_bytes(b'intervening saved edit');return self.verification
  self.verifier.side_effect=change_file
  with self.assertRaisesRegex(RuntimeError,'Saved native project changed'):self.adapter.render(self.project,self.packet)
  self.assertFalse(Path(self.packet['receipt']).exists())

if __name__=='__main__':unittest.main()
