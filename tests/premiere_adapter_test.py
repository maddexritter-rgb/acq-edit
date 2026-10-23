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
  self.plan={'clipId':'clip-1','fps':{'numerator':25,'denominator':1},'width':640,'height':360,'sampleRate':48000,'cuts':[{'frames':25},{'frames':25}],'editorial':{'selectionPath':str(selection)}}
  self.result={'path':export['output_path'],'start_ticks':export['start_ticks'],'end_ticks':export['end_ticks'],'expected_frames':50,'preserved_bounded_state':True,'restored_in':'0','restored_out':export['end_ticks']}
  self.mutations=[];self.observed_baseline=copy.deepcopy(self.baseline);self.verification={'frames':50,'width':640,'height':360,'fullDecode':True}
  owner=self
  class Client:
   def __init__(self,profile):pass
   def inspect(self,name,args):
    if name=='lab_snapshot':return copy.deepcopy(owner.state)
    if name=='lab_inspect_export_state':return {'success':True,'data':copy.deepcopy(owner.observed_baseline)}
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

 def test_missing_profile_never_falls_back_to_global_production_connector(self):
  for config in [{},{'premiereProfile':''},{'premiereProfile':'relative.json'},{'premiereProfile':str(self.root/'missing.json')}]:
   with self.subTest(config=config),self.assertRaisesRegex(RuntimeError,'global fallback is disabled'):premiere.Adapter(config)

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
