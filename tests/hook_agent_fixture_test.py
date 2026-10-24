import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from hook_agent_fixture import compare_plans,protected_native,protected_regions

class HookAgentFixtureTests(unittest.TestCase):
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
