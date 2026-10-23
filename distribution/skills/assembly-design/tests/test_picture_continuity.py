import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from compare_native_timing import audit_picture
class PictureContinuityTests(unittest.TestCase):
 def setUp(self):
  def item(i,start,end,src,links):return dict(id=i,start=str(start),end=str(end),inPoint=str(src),outPoint=str(src+end-start),links=links,media_path='source.mov',speed=1,nested=False,offline=False)
  self.s={'tracks':[[item('v1',0,100,1000,['a1']),item('v2',100,200,2000,['a2'])],[item('a1',0,110,1000,['v1']),item('a2',110,200,2010,['v2'])]]}
  self.g=[{'id':'clip','video_ids':['v1','v2']}]
 def codes(self):return {x['code']for x in audit_picture(self.s,20,self.g)['issues']}
 def test_legitimate_l_cut_keeps_source_sync(self):self.assertEqual(self.codes(),set())
 def test_subframe_hole_is_not_hidden_by_plan_equality(self):
  self.s['tracks'][0][0]['end']='99';self.s['tracks'][0][0]['outPoint']='1099'
  self.assertIn('PICTURE_GAP',self.codes());self.assertIn('PICTURE_OFF_SEQUENCE_GRID',self.codes())
 def test_shifted_picture_is_not_a_j_cut(self):
  c=self.s['tracks'][0][1];c['inPoint']='1980';c['outPoint']='2080';self.assertIn('AV_SOURCE_CLOCK_OFFSET',self.codes())
 def test_continuous_but_wrong_frame_clock(self):
  self.s['tracks'][0][0].update(end='101',outPoint='1101');self.s['tracks'][0][1].update(start='101',inPoint='2001')
  self.assertIn('PICTURE_OFF_SEQUENCE_GRID',self.codes());self.assertNotIn('PICTURE_GAP',self.codes())
 def test_protected_group_cannot_be_omitted(self):
  with self.assertRaises(ValueError):audit_picture(self.s,20,[{'id':'partial','video_ids':['v1']}])
 def test_audio_conflict_is_reported_not_repaired(self):
  self.s['tracks'][1][0]['outPoint']='1111';before=copy.deepcopy(self.s);r=audit_picture(self.s,20,self.g)
  self.assertEqual(r['audio_warnings'][0]['code'],'AUDIO_TAIL_CLOCK_CONFLICT');self.assertEqual(self.s,before)
 def test_overlap_and_duration_mismatch(self):
  self.s['tracks'][0][0]['end']='120';self.assertTrue({'PICTURE_OVERLAP','PICTURE_SOURCE_DURATION_MISMATCH'}<=self.codes())
if __name__=='__main__':unittest.main()
