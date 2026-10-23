import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
from fusion_state import fusion_hash,FusionFormatError

TEXT='''TextPlus { Inputs = { StyledText = Input { Value = "A caption", },
 Size = Input { Value = 0.05, }, Blend = Input { Expression = "time > 5", },
 } }'''
SOURCE='''Loader { Clips = { Clip { Filename = "/fixture/source.mov", TrimOut = 99, } },
 CustomData = { MediaProps = { MEDIA_AUDIO_TRACKS_DESC = {
 { MEDIA_AUDIO_TRACK_ID = "Timeline Audio", MEDIA_AUDIO_TRACK_NAME = "Timeline Audio [old]", MEDIA_AUDIO_SAMPLE_RATE = 48000, },
 { MEDIA_AUDIO_TRACK_ID = "source-id", MEDIA_AUDIO_TRACK_NAME = "source.mov", },
 } } } }'''
MERGE='''Merge { Inputs = { Background = Input { SourceOp = "Source", Source = "Output" },
 Foreground = Input { SourceOp = "Caption", Source = "Output" } } }'''
def graph(order=False,counter=9):
 tools=[f'Caption = {TEXT}',f'Source = {SOURCE}',f'Merge = {MERGE}']
 if order:tools.reverse()
 return f'Composition {{ CurrentID = {counter}, RenderRange = {{ 0, 24 }}, Tools = {{'+','.join(tools)+'} }'

class FusionStateTests(unittest.TestCase):
 def test_reordered_tables_counter_and_cached_timeline_label_are_stable(self):
  before=graph();after=graph(True,13).replace('Timeline Audio [old]','Timeline Audio [current]')
  self.assertEqual(fusion_hash(before),fusion_hash(after))
 def test_real_graph_changes_remain_visible(self):
  for old,new in [('A caption','Changed caption'),('0.05','0.06'),('time > 5','time > 6'),
   ('SourceOp = "Caption"','SourceOp = "Source"'),('/fixture/source.mov','/fixture/other.mov'),
   ('TrimOut = 99','TrimOut = 98'),('48000','44100'),('"source-id"','"other-id"'),
   ('"source.mov"','"renamed-source.mov"'),('RenderRange = { 0, 24 }','RenderRange = { 0, 25 }')]:
   with self.subTest(change=(old,new)):self.assertNotEqual(fusion_hash(graph()),fusion_hash(graph().replace(old,new)))
 def test_keyframe_shapes_and_ordered_tables_are_preserved(self):
  source='Composition { Tools = { Curve = BezierSpline { KeyFrames = { [0] = { 1, RH = { 2, 3 } }, [25] = { 4 } }, Order = ordered() { A = 1, B = 2 } } } }'
  self.assertNotEqual(fusion_hash(source),fusion_hash(source.replace('RH = { 2, 3 }','RH = { 2, 4 }')))
  self.assertNotEqual(fusion_hash(source),fusion_hash(source.replace('A = 1, B = 2','B = 2, A = 1')))
  self.assertNotEqual(fusion_hash(source),fusion_hash(source.replace('[25]','[26]')))
 def test_literal_text_and_tool_local_ids_are_never_stripped(self):
  source=graph().replace('A caption','CurrentID = 9, Timeline Audio [old]').replace('Size = Input','CurrentID = 1, Size = Input')
  self.assertNotEqual(fusion_hash(source),fusion_hash(source.replace('CurrentID = 1, Size','CurrentID = 2, Size')))
  self.assertNotEqual(fusion_hash(source),fusion_hash(source.replace('CurrentID = 9, Timeline Audio','CurrentID = 8, Timeline Audio')))
 def test_equal_numeric_values_and_quoted_field_names_normalize(self):
  self.assertEqual(fusion_hash(graph()),fusion_hash(graph().replace('Size =','["Size"] =').replace('0.05','5e-2')))
 def test_duplicate_and_unsupported_content_fail_closed(self):
  for text in ['Composition { Tools = {}, Tools = {} }','Composition { Tools = {}, ["Tools"] = {} }',
   'Composition { Tools = { 1, [1] = 2 } }','Composition { Tools = {}, Script = os.execute("command") }',
   'Composition { Tools = {} } trailing','Composition { Tools = {','Composition { Tools = {}, Long = [[script]] }',
   'Composition { CurrentID = "wrong type", Tools = {} }']:
   with self.subTest(text=text),self.assertRaises(FusionFormatError):fusion_hash(text)
 def test_unknown_tool_fields_are_retained(self):
  a='Composition { Tools = { Custom = Plugin { UnrecognizedFutureInput = { A = 1 } } } }'
  self.assertNotEqual(fusion_hash(a),fusion_hash(a.replace('A = 1','A = 2')))
 def test_exact_empty_preferences_and_successful_media_query_cache_normalize(self):
  before=graph().replace('MediaProps = {','MediaProps = { __Queried = true,').replace('RenderRange =','Prefs = { Comp = { SpellCheck = {}, Views = { View1 = {} }, Width = 640 } }, RenderRange =')
  after=before.replace('__Queried = true,','').replace('SpellCheck = {}, Views = { View1 = {} },','')
  self.assertEqual(fusion_hash(before),fusion_hash(after))
  for old,new in [('SpellCheck = {}','SpellCheck = { Enabled = true }'),('View1 = {}','View1 = { Zoom = 2 }'),('View1 = {}','View1 = {}, View2 = {}'),('Width = 640','Width = 641'),('__Queried = true','__Queried = false'),('__Queried = true','__Queried = "future"')]:
   with self.subTest(change=(old,new)):self.assertNotEqual(fusion_hash(before),fusion_hash(before.replace(old,new)))
 def test_lookalike_cache_and_preference_fields_are_not_stripped(self):
  for location in ['Tools = { Text = TextPlus { CustomData = { MediaProps = { __Queried = true } } } }',
   'Tools = { Source = Loader { __Queried = true } }',
   'Tools = { Source = Loader { CustomData = { MediaProps = FutureMetadata { __Queried = true } } } }',
   'Tools = { Source = Loader { CustomData = FutureMetadata { MediaProps = { __Queried = true } } } }',
   'Tools = {}, Prefs = FuturePrefs { Comp = { SpellCheck = {}, Views = { View1 = {} } } }',
   'Tools = {}, Prefs = { SpellCheck = {}, Views = { View1 = {} } }',
   'Tools = { Text = TextPlus { SpellCheck = {}, Views = { View1 = {} } } }']:
   source='Composition { '+location+' }'
   changed=source.replace('__Queried = true','').replace('SpellCheck = {}, Views = { View1 = {} }','')
   self.assertNotEqual(fusion_hash(source),fusion_hash(changed))

if __name__=='__main__':unittest.main()
