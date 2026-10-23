import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from caption_profiles import build_profile_manifest,load_profile,PROFILE_IDS,validate_profile_manifest,split_caption_gap_shift
class ReviewedCleanup(unittest.TestCase):
 def setUp(self):
  self.profile=load_profile(sorted(PROFILE_IDS)[-1])
  self.words=[{'word':'Start','start':0.,'end':.3,'source_indices':[10]}, {'word':'yeah','start':.4,'end':.5,'source_indices':[11]}, {'word':'Continue','start':.8,'end':1.,'source_indices':[12]}]
  self.plan=[{'first':0,'last':0,'lines':['Start']},{'first':1,'last':1,'action':'omit','reason':'listener_backchannel'},{'first':2,'last':2,'lines':['Continue']}]
 def test_omission_evidence_and_pause(self):
  m=build_profile_manifest(self.words,self.profile,reviewed_plan=self.plan,hold_through=1.)
  validate_profile_manifest(m)
  self.assertEqual([c['text']for c in m['cards']],['Start','Continue'])
  self.assertEqual(m['caption_omissions'][0]['source_indices'],[11])
  self.assertLessEqual(m['cards'][0]['end'],.4)
  self.assertEqual(self.words[1]['word'],'yeah')
 def test_meaningful_answer_not_blacklisted(self):
  plan=[{'first':i,'last':i,'lines':[w['word']]}for i,w in enumerate(self.words)]
  m=build_profile_manifest(self.words,self.profile,reviewed_plan=plan)
  self.assertIn('yeah',[c['text'].lower()for c in m['cards']])
 def test_omission_reason_required(self):
  self.plan[1].pop('reason')
  with self.assertRaises(ValueError):build_profile_manifest(self.words,self.profile,reviewed_plan=self.plan)
 def test_actual_gap_centers_on_divider(self):self.assertEqual(split_caption_gap_shift(950,996,960),-13.)
 def test_invalid_gap_rejected(self):
  with self.assertRaises(ValueError):split_caption_gap_shift(960,950,960)
 def test_cut_lifetime_builder_and_validator(self):
  m=build_profile_manifest(self.words,self.profile,reviewed_plan=self.plan,picture_cut_frames=[8],hold_through=1.)
  validate_profile_manifest(m);self.assertEqual(m['cards'][0]['end_frame'],8)
  m['cards'][0]['end_frame']=10
  with self.assertRaises(ValueError):validate_profile_manifest(m)
if __name__=='__main__':unittest.main()
