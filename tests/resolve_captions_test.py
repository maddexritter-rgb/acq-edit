"""Portable caption-owner transport and Fusion clock contracts, not rendered approval."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'python'));sys.path.insert(0,str(ROOT/'distribution/skills/caption-clips/scripts'))
from common import sha,fingerprint
import caption_plan
from resolve_captions import card_nodes, verify_fonts


class ResolveCaptionTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
  self.patch=patch.object(caption_plan,'SKILLS',ROOT/'distribution/skills');self.patch.start();self.addCleanup(self.patch.stop)
  self.project={'id':'project','root':str(self.root),'backend':'resolve'}
  self.spec={'projectId':'project','clipId':'clip','backend':'resolve','width':640,'height':360,'fps':{'numerator':25,'denominator':1},'cuts':[{'recordFrame':0,'frames':25},{'recordFrame':25,'frames':50}]}
  self.profile={'allow_quote_italics':True,'guest_turn_italics':False,'caption_hold_through_seconds':.75,'caption_trailing_hold_seconds':.35,'resolve_caption_motion':'measured_fast_settle','resolve_caption_shadows':{'id':'fixture-shadow','wide':{'offset':[.003,-.003],'softness':[6,6],'opacity':1},'tight':{'offset':[.006,-.009],'softness':[2,2],'opacity':1}}}
  self.card={'id':'quote','start_frame':15,'speech_end':1.5,'text':'i can do this?','quote':True,'style':{'font':'Arial','fontStyle':'Bold','italicStyle':'Bold Italic','fusionSize':.08,'center':[.5,.425],'color':'#ffffff'}}
 def derive(self):
  profile=self.root/'profile.json';profile.write_text(json.dumps(self.profile))
  h={'schema':'acq-edit/caption-handoff-v1','owner':'caption-clips','projectId':'project','clipId':'clip','cutsFingerprint':fingerprint(self.spec['cuts']),'profile':{'path':str(profile),'sha256':sha(profile)},'cards':[self.card]}
  handoff=self.root/'handoff.json';handoff.write_text(json.dumps(h))
  return caption_plan.derive(self.project,self.spec,{'path':str(handoff),'sha256':sha(handoff)})
 def test_explicit_native_profile_reuses_owner_text_and_holds(self):
  result=self.derive();self.assertEqual(result['captions'][0]['text'],'“I can do this?”');self.assertTrue(result['cards'][0]['italic']);self.assertEqual(result['shadowProfile'],'fixture-shadow')
  rows=card_nodes(self.spec,result,self.spec['cuts'][0],0)
  self.assertEqual(len(rows),3);self.assertEqual(rows[0]['values']['SoftnessX1'],6);self.assertEqual(rows[-1]['values']['Style'],'Bold Italic');self.assertEqual(rows[-1]['values']['SoftnessX1'],0)
 def test_resolve_never_inherits_a_filmcraft_motion_or_shadow_preset(self):
  self.profile['filmcraft_caption_motion']=self.profile.pop('resolve_caption_motion')
  with self.assertRaisesRegex(RuntimeError,'Explicit supported Resolve'):self.derive()
  self.profile['resolve_caption_motion']='none';del self.profile['resolve_caption_shadows']
  with self.assertRaisesRegex(RuntimeError,'Explicit Resolve shadow'):self.derive()
 def test_exact_font_inventory_rejects_substitution(self):
  result=self.derive();host=MagicMock();host.Fusion.return_value.FontManager.GetFontList.return_value={'Arial':{'Bold':{},'Bold Italic':{}}}
  verify_fonts(host,result)
  host.Fusion.return_value.FontManager.GetFontList.return_value={'Arial':{'Bold':{}}}
  with self.assertRaisesRegex(RuntimeError,'Exact Resolve caption font face missing'):verify_fonts(host,result)
  host.Fusion.return_value.FontManager.GetFontList.return_value=None
  with self.assertRaisesRegex(RuntimeError,'font inventory unavailable'):verify_fonts(host,result)
 def test_continuation_keeps_elapsed_animation_and_source_comp_clock(self):
  result=self.derive();first=card_nodes(self.spec,result,self.spec['cuts'][0],0);second=card_nodes(self.spec,result,self.spec['cuts'][1],50)
  self.assertIn('time-0+-15',first[-1]['center']);self.assertIn('time-50+10',second[-1]['center'])
  self.assertEqual(second[-1]['start'],50);self.assertGreater(second[-1]['end'],50)
  env={'__builtins__':{},'Point':lambda x,y:(x,y),'iif':lambda c,a,b:a if c else b,'max':max}
  start=eval(first[-1]['center'],env,{'time':15})[1];continued=eval(second[-1]['center'],env,{'time':50})[1]
  self.assertGreater(start,.428);self.assertLess(continued,.426)
  self.assertAlmostEqual(eval(first[-1]['center'],env,{'time':25})[1],continued)
 def test_wrong_backend_coordinates_and_synthetic_face_are_refused(self):
  self.card['style']['position']=[320,220]
  with self.assertRaisesRegex(RuntimeError,'Unsupported caption style'):self.derive()
  del self.card['style']['position'];self.card['style']['syntheticQuoteItalic']=True
  with self.assertRaisesRegex(RuntimeError,'Unsupported caption style'):self.derive()
 def test_visibility_gates_each_shadow_at_record_clock_and_preserves_arrival(self):
  prepared=self.derive();self.spec['captionContract']={'fixture':True}
  prior=copy.deepcopy(self.spec)
  self.spec['captionVisibility']={'schema':'acq-edit/caption-visibility-v1','owner':'caption-clips','reason':'Synthetic window','evidence':'Fixture','hiddenRanges':[{'startFrame':16,'endFrame':17},{'startFrame':24,'endFrame':30}]}
  env={'__builtins__':{},'iif':lambda c,a,b:a if c else b,'max':max}
  for cut,start in zip(self.spec['cuts'],[0,50]):
   old=card_nodes(prior,prepared,cut,start);new=card_nodes(self.spec,prepared,cut,start)
   for a,b in zip(old,new):
    self.assertEqual({k:v for k,v in a.items() if k!='blend'},{k:v for k,v in b.items() if k!='blend'})
    for frame in range(cut['frames']):
     record=cut['recordFrame']+frame;time=start+frame
     original=eval(a['blend'],env,{'time':time});actual=eval(b['blend'],env,{'time':time})
     self.assertEqual(actual,0 if 16<=record<17 or 24<=record<30 else original)
 def test_visibility_protection_retains_other_blends_and_graph_fields(self):
  from resolve_caption_visibility import protected_graph
  raw='Composition { Tools = { ACQ_CaptionMerge_0_text = Merge { Inputs = { Blend = Input { Expression = "OLD", Value = 1 }, Background = Input { SourceOp = "MediaIn1", Source = "Output" } } }, Other = Merge { Inputs = { Blend = Input { Value = 1 } } } } }'
  original=protected_graph(raw,['ACQ_CaptionMerge_0_text'])
  self.assertEqual(original,protected_graph(raw.replace('"OLD"','"NEW"'),['ACQ_CaptionMerge_0_text']))
  self.assertNotEqual(original,protected_graph(raw.replace('Value = 1 } } }','Value = 0 } } }'),['ACQ_CaptionMerge_0_text']))
  self.assertNotEqual(original,protected_graph(raw.replace('"MediaIn1"','"Other"'),['ACQ_CaptionMerge_0_text']))
  with self.assertRaisesRegex(RuntimeError,'not a Merge'):protected_graph(raw,['Unknown'])
 def test_visibility_targets_refuse_locked_stale_and_noop_revisions(self):
  from resolve_caption_visibility import changes,apply
  prepared=self.derive();previous=copy.deepcopy(self.spec);self.spec['captionContract']={'fixture':True}
  self.spec['captionVisibility']={'schema':'acq-edit/caption-visibility-v1','owner':'caption-clips','reason':'Fixture','evidence':'Fixture','hiddenRanges':[{'startFrame':0,'endFrame':30}]}
  timeline=MagicMock();timeline.GetIsTrackLocked.return_value=True
  with self.assertRaisesRegex(RuntimeError,'locked'):changes(timeline,previous,self.spec,prepared)
  timeline.GetIsTrackLocked.return_value=False;items=[]
  for cut in self.spec['cuts']:
   item=MagicMock();comp=item.GetFusionCompByIndex.return_value;comp.GetAttrs.return_value={'COMPN_RenderStart':0};nodes={}
   for row in card_nodes(previous,prepared,cut,0):
    tool=MagicMock();tool.Blend.GetExpression.return_value=row['blend'];tool.Blend.SetExpression.side_effect=lambda expression,t=tool:setattr(t.Blend.GetExpression,'return_value',expression);nodes[row['mergeName']]=tool
   comp.FindTool.side_effect=nodes.get;items.append(item)
  timeline.GetItemListInTrack.return_value=items
  targets=changes(timeline,previous,self.spec,prepared);self.assertEqual(len(targets),6)
  apply(timeline,targets)
  with self.assertRaisesRegex(RuntimeError,'changed before revision'):changes(timeline,previous,self.spec,prepared)
  with self.assertRaisesRegex(RuntimeError,'do not affect'):changes(timeline,self.spec,self.spec,prepared)
 def test_visibility_adapters_refuse_another_backend_before_host_access(self):
  from resolve import Adapter as Resolve
  from filmcraft import Adapter as FilmCraft
  for adapter,backend in [(Resolve({}),'filmcraft'),(FilmCraft({}),'resolve')]:
   with self.assertRaisesRegex(RuntimeError,'selected .* backend'):
    adapter.revise_caption_visibility({'backend':backend},{})
 def test_common_json_read_is_utf8_even_in_resolve_like_ascii_locale(self):
  file=self.root/'unicode.json';file.write_text('{"caption":"“Hello”"}',encoding='utf-8')
  code='import sys;sys.path.insert(0,sys.argv[1]);from common import read;assert len(read(sys.argv[2])["caption"])==7'
  completed=subprocess.run([sys.executable,'-c',code,str(ROOT/'python'),str(file)],env={**os.environ,'LC_ALL':'C','LANG':'C','PYTHONUTF8':'0','PYTHONCOERCECLOCALE':'0'},capture_output=True)
  self.assertEqual(completed.returncode,0,completed.stderr)

if __name__=='__main__':unittest.main()
