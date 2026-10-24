import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
import common

class MediaIntegrityTests(unittest.TestCase):
 def setUp(self):
  temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.root=Path(temporary.name)
  for folder in ['00_SOURCE','10_WORK']:(self.root/folder).mkdir()
  self.source=self.root/'00_SOURCE/source.mp4';self.source.write_bytes(b'source fixture')
  self.graphic=self.root/'10_WORK/graphic.mov';self.graphic.write_bytes(b'graphic fixture')
  self.project={'id':'fixture','root':str(self.root),'backend':'filmcraft'}
  self.spec={'schema':'acq-edit/plan-v1','projectId':'fixture','backend':'filmcraft','clipId':'clip','sources':[{'id':'source-1','path':str(self.source),'sha256':common.sha(self.source)}],'graphics':[{'path':str(self.graphic),'sha256':common.sha(self.graphic)}],'cuts':[{'frames':25}],'width':640,'height':360,'fps':{'numerator':25,'denominator':1},'editorial':{'selectionPath':str(self.root/'10_WORK/selection.json')}}
  Path(self.spec['editorial']['selectionPath']).write_text('{"testFixture":true}')
  self.packet={'plan':str(self.root/'10_WORK/plan.json'),'receipt':str(self.root/'10_WORK/receipt.json')};Path(self.packet['plan']).write_text(json.dumps(self.spec))
  self.native=self.root/'10_WORK/native.fixture';self.native.write_bytes(b'original native checkpoint')
  self.media=self.root/'10_WORK/render.fixture';self.media.write_bytes(b'retained render output')
 def receipt(self):return common.result_receipt(self.project,self.packet,self.spec,self.native,self.media,self.root/'10_WORK/inspection.json')
 def test_reports_all_missing_and_changed_assets_with_exact_identity_and_expected_hash(self):
  self.source.rename(self.source.with_suffix('.held'));self.graphic.write_bytes(b'changed graphic')
  with self.assertRaises(RuntimeError) as error:common.verify_plan_media(self.project,self.spec)
  text=str(error.exception)
  for value in ['source-1',str(self.source),str(self.graphic),self.spec['sources'][0]['sha256'],'missing','changed']:self.assertIn(value,text)
  self.assertEqual(self.graphic.read_bytes(),b'changed graphic');self.assertFalse(Path(self.packet['receipt']).exists())
 def test_missing_media_is_reported_before_other_plan_evidence(self):
  self.source.rename(self.source.with_suffix('.held'))
  with self.assertRaisesRegex(RuntimeError,'Input media verification failed'):common.plan(self.project,self.packet)
 def test_symlink_outside_source_root_cannot_satisfy_matching_hash(self):
  held=self.root/'10_WORK/held.mp4';self.source.rename(held);self.source.symlink_to(held)
  with self.assertRaisesRegex(RuntimeError,'outside selected project'):common.verify_plan_media(self.project,self.spec)
 def test_change_during_output_decode_prevents_receipt_and_preserves_output(self):
  for target in [self.source,self.graphic]:
   before=target.read_bytes()
   def mutate(*args):target.write_bytes(b'changed during decode');return {'fullDecode':True}
   with self.subTest(target=target),patch('common.verify_native_render',side_effect=mutate),self.assertRaisesRegex(RuntimeError,'Media bytes changed'):self.receipt()
   self.assertFalse(Path(self.packet['receipt']).exists());self.assertEqual(self.media.read_bytes(),b'retained render output');self.assertEqual(self.native.read_bytes(),b'original native checkpoint');target.write_bytes(before)
 def test_plan_change_during_export_cannot_be_rebound_to_success_receipt(self):
  def mutate(*args):Path(self.packet['plan']).write_text(json.dumps({**self.spec,'clipId':'different'}));return {'fullDecode':True}
  with patch('common.verify_native_render',side_effect=mutate),self.assertRaisesRegex(RuntimeError,'Plan changed during native execution'):self.receipt()
  self.assertFalse(Path(self.packet['receipt']).exists())
 def test_unchanged_inputs_are_pinned_after_render_verification(self):
  with patch('common.verify_native_render',return_value={'fullDecode':True}):receipt=self.receipt()
  proof=receipt['inputMediaVerification'];self.assertEqual(proof['phase'],'after-render-verification');self.assertEqual(len(proof['files']),2)
  self.assertEqual([i['role'] for i in proof['files']],['source','graphic'])
  for item in proof['files']:self.assertEqual(item['expectedSha256'],item['actualSha256'])
 def test_resolve_resume_metadata_binds_the_exact_rendered_inspection(self):
  self.project['backend']='resolve';state={'project':'ACQ_fixture','timeline':'timeline-id','caption':'Original'}
  inspection=self.root/'10_WORK/inspection.json';inspection.write_text(json.dumps(state))
  target={'nativeProjectId':'native-id','database':{'DbType':'Disk','DbName':'Test'},'timelineId':'timeline-id','expectedFingerprint':common.fingerprint(state)}
  receipt=common.result_receipt(self.project,self.packet,self.spec,self.native,self.media,inspection,verification={'fixture':True},native_reopen=target)
  self.assertEqual(receipt['nativeReopen'],{**target,'inspectionSha256':common.sha(inspection)})
 def test_stale_resume_or_startup_override_cannot_enter_a_receipt(self):
  self.project['backend']='resolve';state={'project':'ACQ_fixture','timeline':'timeline-id'}
  inspection=self.root/'10_WORK/inspection.json';inspection.write_text(json.dumps(state))
  target={'nativeProjectId':'native-id','database':{'DbType':'Disk','DbName':'Test'},'timelineId':'timeline-id','expectedFingerprint':common.fingerprint(state)}
  for bad in [{**target,'expectedFingerprint':'0'*64},{**target,'timelineId':'other'},{**target,'emptyWorkspace':{'stale':True}}]:
   with self.assertRaisesRegex(RuntimeError,'Native reopen'):
    common.result_receipt(self.project,self.packet,self.spec,self.native,self.media,inspection,verification={'fixture':True},native_reopen=bad)
   self.assertFalse(Path(self.packet['receipt']).exists())

if __name__=='__main__':unittest.main()
