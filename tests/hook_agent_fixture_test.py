import copy,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from hook_agent_fixture import compare_plans,protected_native,protected_regions,compare_visibility_plans,protected_visibility_native,protected_resolve_visibility

class HookAgentFixtureTests(unittest.TestCase):
 def resolve_fixture(self):
  state={'timeline':'first','name':'first','tracks':{'video':[[{'id':'clip','linkedIds':[],'fusion':['hash'],'start':0}]],'audio':[]},'trackState':{'video':[{'locked':False}],'audio':[]}}
  graph='Composition { Tools = { ACQ_CaptionMerge_0_text = Merge { Inputs = { Blend = Input { Expression = "old", Value = 1 }, Foreground = Input { SourceOp = "ACQ_Caption_0_text", Source = "Output" } } }, ACQ_Caption_0_text = TextPlus { Inputs = { StyledText = Input { Value = "Original" } } } } }'
  key=('video',0,0,0);return state,{key:graph},{key:['ACQ_CaptionMerge_0_text']},{'video:0:0':{'flags':['Blue']}}
 def test_resolve_visibility_checker_keeps_text_connections_and_metadata(self):
  state,graphs,targets,extra=self.resolve_fixture();baseline=protected_resolve_visibility(state,graphs,targets,extra);key=next(iter(graphs))
  changed={key:graphs[key].replace('"old"','"new"')};other=copy.deepcopy(state);other['timeline']='new';other['name']='new';other['tracks']['video'][0][0]['id']='new-clip'
  self.assertEqual(baseline,protected_resolve_visibility(other,changed,targets,extra))
  for before,after in [('"Original"','"Changed"'),('Source = "Output"','Source = "Other"')]:
   self.assertNotEqual(baseline,protected_resolve_visibility(state,{key:graphs[key].replace(before,after)},targets,extra))
  self.assertNotEqual(baseline,protected_resolve_visibility(state,graphs,targets,{'video:0:0':{'flags':[]}}))
 def test_resolve_visibility_checker_refuses_incomplete_graph_or_unknown_link(self):
  state,graphs,targets,extra=self.resolve_fixture()
  with self.assertRaisesRegex(RuntimeError,'Missing protected Fusion'):protected_resolve_visibility(state,{},targets,extra)
  state['tracks']['video'][0][0]['linkedIds']=['unknown']
  with self.assertRaisesRegex(RuntimeError,'outside protected tracks'):protected_resolve_visibility(state,graphs,targets,extra)
 def test_visibility_checker_only_allows_mask_and_new_hook_in_plan(self):
  first={'cuts':[{'frames':175}],'captions':[{'text':'original'}]}
  second={**copy.deepcopy(first),'captionVisibility':{'hiddenRanges':[{'startFrame':0,'endFrame':126}]},'hookContract':{'sha256':'new'}}
  compare_visibility_plans(first,second,first)
  for mutate in [lambda p:p['cuts'][0].update(frames=174),lambda p:p['captions'][0].update(text='changed'),lambda p:p['captionVisibility']['hiddenRanges'][0].update(endFrame=125)]:
   changed=copy.deepcopy(second);mutate(changed)
   with self.assertRaises(RuntimeError):compare_visibility_plans(first,changed,first)
 def test_visibility_checker_retains_native_caption_text_and_source_tracks(self):
  first=json.loads((Path(__file__).parent/'fixtures/filmcraft-caption-native.json').read_text());second=copy.deepcopy(first)
  seq=second['project']['items'][str(second['view']['active_sequence'])]['kind']['Sequence'];seq['video_tracks'].append({'items':[{'hook':True}]})
  for track in seq['video_tracks'][1:4]:
   for item in track['items']:
    next(e['params'] for e in item['effects'] if e['effect']=='opacity')['opacity']={'value':{'Float':0}}
  protected_visibility_native(first,second)
  seq['video_tracks'][1]['items'][0]['start']+=1
  with self.assertRaisesRegex(RuntimeError,'protected native tracks'):protected_visibility_native(first,second)
 def test_checker_requires_only_requested_changes_and_fresh_layout(self):
  seed={'cuts':[{'in':10,'frames':150}],'captions':[{'text':'NATIVE AGENT LOOP','startFrame':0,'endFrame':150}],'audio':{}}
  first=copy.deepcopy(seed);first['hookContract']={'sha256':'first','baseReceiptSha256':'base1'}
  second=copy.deepcopy(seed);second['captions'][0]['text']='UPDATED BODY CAPTION';second['hookContract']={'sha256':'second','baseReceiptSha256':'base2'}
  compare_plans(first,second,seed)
  for mutate in [lambda p:p['cuts'][0].update(frames=149),lambda p:p['captions'][0].update(startFrame=1),lambda p:p['hookContract'].update(baseReceiptSha256='base1')]:
   changed=copy.deepcopy(second);mutate(changed)
   with self.assertRaises(RuntimeError):compare_plans(first,changed,seed)
 def native(self,text):
  seq={'video_tracks':[{'items':[{'effects':[{'effect':'motion'}]}]},{'items':[{'effects':[{'effect':'graphic_text','params':{'text':{'value':{'Text':text}}}}]}]},{'items':[{'hook':True}]}],'audio_tracks':[{'gain':0}]}
  return {'view':{'active_sequence':1},'project':{'items':{'1':{'kind':{'Sequence':seq}},'2':{'kind':{'Media':{'path':'source'}}}}}}
 def test_remeasured_caption_preserves_original_region_explicitly(self):
  old={'protected_rects':[],'placement_intervals':[{'start_seconds':0,'end_seconds':5.04,'caption_bounds':[120,270,400,35],'protected_rects':[]}]}
  new=copy.deepcopy(old);new['placement_intervals'][0]['caption_bounds']=[167,267,303,18]
  with self.assertRaisesRegex(RuntimeError,'region was lost'):protected_regions(old,new)
  new['protected_rects']=[[120,270,400,35]];protected_regions(old,new)
  new['protected_rects'][0][2]=399
  with self.assertRaisesRegex(RuntimeError,'region was lost'):protected_regions(old,new)
 def test_native_checker_retains_all_nonhook_tracks_and_existing_bins(self):
  first=self.native('NATIVE AGENT LOOP');second=self.native('UPDATED BODY CAPTION');protected_native(first,second)
  changed=copy.deepcopy(second);changed['project']['items']['1']['kind']['Sequence']['audio_tracks'][0]['gain']=2
  with self.assertRaisesRegex(RuntimeError,'protected native tracks'):protected_native(first,changed)
  changed=copy.deepcopy(second);changed['project']['items']['2']['kind']['Media']['path']='replacement'
  with self.assertRaisesRegex(RuntimeError,'bin asset'):protected_native(first,changed)
  changed=copy.deepcopy(second);changed['project']['items']['1']['kind']['Sequence']['video_tracks'].insert(2,{'items':[{'oldHook':True,'effects':[]}]})
  with self.assertRaisesRegex(RuntimeError,'protected native tracks'):protected_native(first,changed)

if __name__=='__main__':unittest.main()
