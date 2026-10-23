import copy,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch,Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
from framing_plan import validate_framing,filmcraft_motion,fusion_crop,require_static_fusion_crop
from common import sha
class FramingPlanTests(unittest.TestCase):
 def fixture(self,root):
  receipt=Path(root)/'framing.json';receipt.write_text('{}')
  shot={'mode':'fixed-crop','sourceWidth':640,'sourceHeight':360,'x':70,'y':10,'width':180,'height':320}
  return {'root':root},{'width':360,'height':640,'cuts':[{'id':'a','sourceId':'s'}],'sources':[{'id':'s','path':str(Path(root)/'source.mp4')}],'framing':{'schema':'acq-edit/framing-v1','receiptPath':str(receipt),'receiptSha256':sha(receipt),'shots':{'a':shot}}}
 def validate(self,project,spec,width=640,rotation=0):
  with patch('framing_plan.subprocess.check_output',return_value=json.dumps({'streams':[{'width':width,'height':360,'sample_aspect_ratio':'1:1','side_data_list':[{'rotation':rotation}]}]}).encode()):
   return validate_framing(project,spec)
 def test_exact_shared_geometry_maps_without_stretching_or_vertical_inversion(self):
  with tempfile.TemporaryDirectory() as root:
   project,spec=self.fixture(root);shot=self.validate(project,spec)['a']
   self.assertEqual(filmcraft_motion(spec,shot),{'anchor':[160,170],'position':[180,320],'scale':200})
   self.assertEqual(fusion_crop(spec,shot)['YOffset'],30)
 def test_refuses_stale_source_missing_shots_and_unqualified_motion(self):
  with tempfile.TemporaryDirectory() as root:
   project,spec=self.fixture(root)
   for change in [{'x':500},{'width':181},{'x':70.2},{'mode':'track'}]:
    changed=copy.deepcopy(spec);changed['framing']['shots']['a'].update(change)
    with self.assertRaises(RuntimeError):self.validate(project,changed)
   with self.assertRaisesRegex(RuntimeError,'geometry differs'):self.validate(project,spec,width=1280)
   with self.assertRaisesRegex(RuntimeError,'Rotated'):self.validate(project,spec,rotation=90)
   spec['framing']['shots']={}
   with self.assertRaisesRegex(RuntimeError,'Every source cut'):self.validate(project,spec)
 def test_receipt_is_pinned_and_cannot_escape_project(self):
  with tempfile.TemporaryDirectory() as root:
   project,spec=self.fixture(root);Path(spec['framing']['receiptPath']).write_text('changed')
   with self.assertRaisesRegex(RuntimeError,'receipt changed'):self.validate(project,spec)
   spec['framing']['receiptPath']='/outside.json'
   with self.assertRaisesRegex(RuntimeError,'outside'):self.validate(project,spec)
 def test_existing_animation_and_expressions_cannot_be_erased(self):
  field=Mock();field.GetAttrs.return_value={'INPS_ID':'XOffset'};field.GetConnectedOutput.return_value=None;field.GetExpression.return_value=None
  crop=Mock();crop.GetInputList.return_value={1:field}
  require_static_fusion_crop(crop,['XOffset'])
  field.GetConnectedOutput.return_value=object()
  with self.assertRaisesRegex(RuntimeError,'tracking revision'):require_static_fusion_crop(crop,['XOffset'])
  field.GetConnectedOutput.return_value=None;field.GetExpression.return_value='time * 2'
  with self.assertRaisesRegex(RuntimeError,'tracking revision'):require_static_fusion_crop(crop,['XOffset'])
  with self.assertRaisesRegex(RuntimeError,'input missing'):require_static_fusion_crop(crop,['YOffset'])
if __name__=='__main__':unittest.main()
