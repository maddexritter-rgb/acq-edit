import unittest,copy
from unittest.mock import patch
import premiere_native_reframe as n
class ReviewedShotsTests(unittest.TestCase):
 def test_yunet_confidence_is_not_landmark_coordinate(self):
  # bbox, five landmark xy pairs, confidence
  face=[500,100,100,100,530,130,570,130,550,150,530,180,570,180,.2]
  self.assertIsNone(n.select_face([face],None,(0,0,1,1),1280,720))
  face[-1]=.95
  self.assertIsNotNone(n.select_face([face],None,(0,0,1,1),1280,720))
 def test_podcast_size_floor_rejects_small_set_object(self):
  face=[100,100,20,24]+[0]*10+[.99]
  self.assertIsNone(n.select_face([face],None,(0,0,1,1),1280,720,n.PRESETS["podcast"]["min_face_height720"]))

 def test_stale_or_incomplete_map_refused(self):
  c={'node_id':'v','media_path':'/source','start_ticks':'0','end_ticks':'10','source_in_ticks':'20','source_out_ticks':'30'}
  s={'project_path':'/p','sequence_id':'seq','bridge_baseline':{'revision':'r'},'video_tracks':[{'clips':[c]}]}
  m={'schema':'premiere-reviewed-shots/v1','project_path':'/p','sequence_id':'seq','revision':'r','items':[{**c,'camera_id':'camera','layout':'portrait'}]}
  with patch.object(n,'source_items',return_value=[c]):
   self.assertEqual(n.bind_reviewed_shots(s,m)['video_tracks'][0]['clips'][0]['camera_id'],'camera')
   for field,value in [('revision','stale'),('items',[])]:
    wrong={**m,field:value}
    with self.assertRaises(ValueError):n.bind_reviewed_shots(s,wrong)
   wrong=copy.deepcopy(m);wrong['items'][0]['source_in_ticks']='21'
   with self.assertRaises(ValueError):n.bind_reviewed_shots(s,wrong)
 def test_camera_change_does_not_force_anchor_continuity(self):
  a={'media_path':'/same','camera_id':'left','track_index':0,'end':1,'start':0,'scale_percent':100}
  b={**a,'camera_id':'right','start':1,'end':2}
  self.assertFalse(n.same_camera_seam(a,b))
if __name__=='__main__':unittest.main()
