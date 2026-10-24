"""Reject live source-clock drift even when an old cached preview looks correct."""
import sys,unittest,tempfile
from pathlib import Path
from unittest.mock import MagicMock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
from resolve_sources import verify_timeline,pin_new_copy
from resolve import Adapter


class ResolveSourceTests(unittest.TestCase):
 def setUp(self):
  self.spec={'sources':[{'id':'source','path':'/fixture/source.mov'}],'cuts':[{'id':'first','sourceId':'source','recordFrame':0,'sourceInFrame':0,'frames':50}]}
  self.values={'MediaSource':'Timeline','GlobalIn':0,'GlobalOut':149,'ClipTimeStart':0,'ClipTimeEnd':149}
  self.tool=MagicMock();self.tool.GetAttrs.return_value={'TOOLS_RegID':'MediaIn','TOOLS_Name':'MediaIn1'};self.tool.GetInput.side_effect=lambda key:self.values.get(key)
  for key in ['GlobalIn','GlobalOut','ClipTimeStart','ClipTimeEnd']:
   port=getattr(self.tool,key);port.GetExpression.return_value=None;port.GetConnectedOutput.return_value=None
  self.attrs={'COMPN_GlobalStart':0,'COMPN_GlobalEnd':149,'COMPN_RenderStart':0,'COMPN_RenderEnd':49}
  self.comp=MagicMock();self.comp.GetAttrs.return_value=self.attrs;self.comp.GetToolList.return_value={1:self.tool}
  self.item=MagicMock();self.item.GetStart.return_value=0;self.item.GetLeftOffset.return_value=0;self.item.GetDuration.return_value=50;self.item.GetMediaPoolItem.return_value.GetClipProperty.return_value='/fixture/source.mov';self.item.GetFusionCompCount.return_value=1;self.item.GetFusionCompByIndex.return_value=self.comp
  self.timeline=MagicMock();self.timeline.GetItemListInTrack.return_value=[self.item]
 def test_zero_and_negative_clip_local_clocks_are_valid(self):
  verify_timeline(self.timeline,self.spec)
  self.spec['cuts'][0]['sourceInFrame']=50;self.item.GetLeftOffset.return_value=50
  self.attrs.update(COMPN_GlobalStart=-50,COMPN_GlobalEnd=99);self.values.update(GlobalIn=-50,ClipTimeStart=-50,GlobalOut=99,ClipTimeEnd=99)
  verify_timeline(self.timeline,self.spec)
 def test_observed_one_frame_delay_is_rejected_without_repair(self):
  self.values.update(GlobalIn=1,GlobalOut=150)
  with self.assertRaisesRegex(RuntimeError,'source clock differs: GlobalIn'):verify_timeline(self.timeline,self.spec)
  self.tool.SetInput.assert_not_called();self.assertEqual(self.values['GlobalIn'],1)
 def test_retime_or_driven_clock_is_not_treated_as_static_source(self):
  self.values['ClipTimeStart']=1
  with self.assertRaisesRegex(RuntimeError,'ClipTimeStart'):verify_timeline(self.timeline,self.spec)
  self.values['ClipTimeStart']=0;self.tool.GlobalIn.GetExpression.return_value='time'
  with self.assertRaisesRegex(RuntimeError,'clock is driven'):verify_timeline(self.timeline,self.spec)
 def test_picture_ranges_sources_and_render_coverage_are_bound(self):
  self.item.GetLeftOffset.return_value=1
  with self.assertRaisesRegex(RuntimeError,'picture timing'):verify_timeline(self.timeline,self.spec)
  self.item.GetLeftOffset.return_value=0;self.item.GetMediaPoolItem.return_value.GetClipProperty.return_value='/fixture/other.mov'
  with self.assertRaisesRegex(RuntimeError,'picture binding'):verify_timeline(self.timeline,self.spec)
  self.item.GetMediaPoolItem.return_value.GetClipProperty.return_value='/fixture/source.mov';self.attrs['COMPN_RenderEnd']=150
  with self.assertRaisesRegex(RuntimeError,'render range'):verify_timeline(self.timeline,self.spec)
 def test_explicit_panel_media_pool_clocks_are_owned_by_panel_verifier(self):
  self.values.update(MediaSource='MediaPool',GlobalIn=0,ClipTimeStart=50)
  verify_timeline(self.timeline,self.spec);self.tool.SetInput.assert_not_called()
 def test_graph_inspection_detects_and_does_not_hide_native_export_side_effects(self):
  with tempfile.TemporaryDirectory() as folder:
   adapter=Adapter({});adapter.project_root=Path(folder);(adapter.project_root/'10_WORK').mkdir()
   def export(path,index):Path(path).write_text('Composition { Tools = {} }');return True
   self.item.ExportFusionComp.side_effect=export;self.assertEqual(len(adapter.fusion_fingerprints(self.item)),1)
   def changed(path,index):self.values['GlobalIn']=1;return export(path,index)
   self.item.ExportFusionComp.side_effect=changed
   with self.assertRaisesRegex(RuntimeError,'inspection changed live source clocks'):adapter.fusion_fingerprints(self.item)
   self.tool.SetInput.assert_not_called();self.assertEqual(self.values['GlobalIn'],1)
 def copied(self):
  other=ResolveSourceTests();other.setUp();self.timeline.GetUniqueId.return_value='parent';other.timeline.GetUniqueId.return_value='new-copy';other.tool.SetInput.return_value=None
  return other
 def test_new_copy_pins_exact_values_without_writing_parent(self):
  other=self.copied();pin_new_copy(self.timeline,other.timeline,self.spec)
  self.tool.SetInput.assert_not_called();self.assertEqual(other.tool.SetInput.call_count,4)
  self.assertEqual(dict(call.args for call in other.tool.SetInput.call_args_list),{'GlobalIn':0,'GlobalOut':149,'ClipTimeStart':0,'ClipTimeEnd':149})
 def test_pin_refuses_same_timeline_shift_and_driver_before_writes(self):
  other=self.copied()
  with self.assertRaisesRegex(RuntimeError,'new timeline copy'):pin_new_copy(self.timeline,self.timeline,self.spec)
  other.values['GlobalIn']=1
  with self.assertRaisesRegex(RuntimeError,'source clock'):pin_new_copy(self.timeline,other.timeline,self.spec)
  other.values['GlobalIn']=0;other.tool.GlobalIn.GetConnectedOutput.return_value=object()
  with self.assertRaisesRegex(RuntimeError,'driven'):pin_new_copy(self.timeline,other.timeline,self.spec)
  self.tool.SetInput.assert_not_called();other.tool.SetInput.assert_not_called()
 def test_pin_checks_source_identity_and_write_readback(self):
  other=self.copied();other.values['MediaID']='unexpected'
  with self.assertRaisesRegex(RuntimeError,'duplication changed'):pin_new_copy(self.timeline,other.timeline,self.spec)
  other.tool.SetInput.assert_not_called();other.values.pop('MediaID')
  def changed(key,value):other.values[key]=value+1;return True
  other.tool.SetInput.side_effect=changed
  with self.assertRaisesRegex(RuntimeError,'changed during persistence'):pin_new_copy(self.timeline,other.timeline,self.spec)
 def test_pin_leaves_explicit_panel_clocks_alone(self):
  other=self.copied()
  for values in (self.values,other.values):values.update(MediaSource='MediaPool',GlobalIn=0,ClipTimeStart=50)
  pin_new_copy(self.timeline,other.timeline,self.spec)
  self.tool.SetInput.assert_not_called();other.tool.SetInput.assert_not_called()


if __name__=='__main__':unittest.main()
