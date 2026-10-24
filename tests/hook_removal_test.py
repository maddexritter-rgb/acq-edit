"""Hook removal is exact-target editing, not a generic timeline rebuild."""
import copy,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'python'))
from hook_removal import compare_plans,filmcraft_target,verify_filmcraft


class HookRemovalTests(unittest.TestCase):
 def setUp(self):
  fixture=json.loads((ROOT/'tests/fixtures/filmcraft-hook-native.json').read_text());self.spec=fixture['spec'];self.prepared=fixture['prepared'];self.before=fixture['native']
  project=self.before['project'];project.update(name='parent',root={'name':'parent','children':[]},next_id=100)
  seq=project['items'][str(self.before['view']['active_sequence'])]['kind']['Sequence']
  seq['video_tracks'].insert(0,{'id':1,'items':[{'name':'manual effect, preserved'}]});seq['audio_tracks']=[{'id':2,'items':[{'gain':-6}]}]
  self.seq=seq;self.after=copy.deepcopy(self.before);after=self.after['project'];after['name']=after['root']['name']='fresh'
  after['items'][str(self.before['view']['active_sequence'])]['kind']['Sequence']['video_tracks'].pop()
 def test_removal_preserves_manual_layers_and_source_bin(self):
  self.assertEqual(filmcraft_target(self.before,self.spec,self.prepared,254016000000//25),17)
  verify_filmcraft(self.before,self.after,self.spec,self.prepared,'fresh',254016000000//25)
  self.after['project']['items']['unexpected']={'Media':'changed'}
  with self.assertRaisesRegex(RuntimeError,'protected native state'):verify_filmcraft(self.before,self.after,self.spec,self.prepared,'fresh',254016000000//25)
 def test_locked_or_changed_hook_is_not_removed(self):
  self.seq['video_tracks'][-1]['locked']=True
  with self.assertRaisesRegex(RuntimeError,'locked'):filmcraft_target(self.before,self.spec,self.prepared,254016000000//25)
  self.seq['video_tracks'][-1]['locked']=False;self.seq['video_tracks'][-1]['items'][0]['name']='manual title'
  with self.assertRaisesRegex(RuntimeError,'coverage'):filmcraft_target(self.before,self.spec,self.prepared,254016000000//25)
 def test_other_timing_and_audio_edits_cannot_hide_in_removal(self):
  self.after['project']['items'][str(self.after['view']['active_sequence'])]['kind']['Sequence']['audio_tracks'][0]['items'][0]['gain']=0
  with self.assertRaisesRegex(RuntimeError,'protected native state'):verify_filmcraft(self.before,self.after,self.spec,self.prepared,'fresh',254016000000//25)
 def test_plan_allows_only_explicit_hook_contract_removal(self):
  old={'cuts':[{'frames':50}],'captions':[{'text':'preserved'}],'hookContract':{'sha256':'pinned'}}
  new={k:copy.deepcopy(v) for k,v in old.items() if k!='hookContract'};compare_plans(old,new)
  for field,value in [('cuts',[{'frames':49}]),('captions',[{'text':'changed'}]),('backend','resolve')]:
   modified={**new,field:value}
   with self.assertRaisesRegex(RuntimeError,'cannot change'):compare_plans(old,modified)
  with self.assertRaisesRegex(RuntimeError,'existing contract'):compare_plans(new,new)
  with self.assertRaisesRegex(RuntimeError,'hook-free'):compare_plans(old,{**new,'hookContract':None})


if __name__=='__main__':unittest.main()
