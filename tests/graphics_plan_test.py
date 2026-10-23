import copy,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
from graphics_plan import validate_graphics
from common import sha

class GraphicsPlanTests(unittest.TestCase):
 def setUp(self):
  self.folder=tempfile.TemporaryDirectory();self.addCleanup(self.folder.cleanup);root=Path(self.folder.name);(root/'10_WORK').mkdir();self.media=root/'10_WORK/overlay.mov';self.media.write_bytes(b'fixture')
  self.project={'root':str(root)};self.asset={'path':str(self.media),'sha256':sha(self.media),'startFrame':5,'frames':25};self.spec={'width':640,'height':360,'fps':{'numerator':25,'denominator':1},'graphics':[self.asset]}
  self.stream={'codec_type':'video','codec_name':'prores','profile':'4444','pix_fmt':'yuva444p12le','width':640,'height':360,'avg_frame_rate':'25/1','r_frame_rate':'25/1','nb_read_frames':'25'}
 def validate(self,spec=None,streams=None):
  with patch('graphics_plan.subprocess.check_output',return_value=json.dumps({'streams':streams or [self.stream]}).encode()),patch('graphics_plan.subprocess.run') as decode:
   result=validate_graphics(self.project,spec or self.spec,50)
   self.assertEqual(decode.call_count,len((spec or self.spec)['graphics']))
   return result
 def test_overlaps_are_preserved_in_explicit_back_to_front_order(self):
  self.spec['graphics'].append({**self.asset,'startFrame':10})
  self.assertEqual(self.validate(),self.spec['graphics'])
 def test_timing_and_unhandled_effects_fail_before_probe(self):
  for change in [{'startFrame':-1},{'startFrame':True},{'frames':0},{'frames':1.5},{'startFrame':30},{'opacity':.5}]:
   spec=copy.deepcopy(self.spec);spec['graphics'][0].update(change)
   with patch('graphics_plan.subprocess.check_output') as probe,self.assertRaises(RuntimeError):validate_graphics(self.project,spec,50)
   probe.assert_not_called()
 def test_changed_or_external_assets_are_refused_before_probe(self):
  self.media.write_bytes(b'changed')
  with self.assertRaisesRegex(RuntimeError,'changed'):validate_graphics(self.project,self.spec,50)
  self.asset['path']=str(Path(self.folder.name)/'outside.mov')
  with self.assertRaisesRegex(RuntimeError,'outside'):validate_graphics(self.project,self.spec,50)
 def test_media_cannot_be_implicitly_cropped_retimed_looped_or_opaque(self):
  for change in [{'width':1280},{'height':720},{'avg_frame_rate':'30/1'},{'r_frame_rate':'30/1'},{'nb_read_frames':'24'},{'pix_fmt':'yuv444p12le'},{'profile':'HQ'},{'codec_name':'h264'},{'sample_aspect_ratio':'2:1'},{'side_data_list':[{'rotation':90}]},{'tags':{'rotate':'90'}}]:
   with self.assertRaises(RuntimeError):self.validate(streams=[{**self.stream,**change}])
  with self.assertRaisesRegex(RuntimeError,'no audio'):self.validate(streams=[self.stream,{'codec_type':'audio'}])
  with self.assertRaisesRegex(RuntimeError,'one video'):self.validate(streams=[self.stream,self.stream])
 def test_change_during_decode_is_detected(self):
  with patch('graphics_plan.subprocess.check_output',return_value=json.dumps({'streams':[self.stream]}).encode()),patch('graphics_plan.subprocess.run',side_effect=lambda *a,**k:self.media.write_bytes(b'changed')),self.assertRaisesRegex(RuntimeError,'during validation'):
   validate_graphics(self.project,self.spec,50)

if __name__=='__main__':unittest.main()
