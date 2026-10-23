import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from caption_profiles import cap_hold_at_picture_cut
class HoldCuts(unittest.TestCase):
 def test_finished_tail(self):self.assertEqual(cap_hold_at_picture_cut(188,233,228,[230]),230)
 def test_live_speech_continues(self):self.assertEqual(cap_hold_at_picture_cut(397,421,420,[408]),421)
 def test_short_spoken_word_survives(self):self.assertEqual(cap_hold_at_picture_cut(229,233,232,[230]),233)
 def test_half_open_release_at_cut(self):self.assertEqual(cap_hold_at_picture_cut(10,25,20,[20]),20)
 def test_cut_before_card_ignored(self):self.assertEqual(cap_hold_at_picture_cut(30,40,36,[20,30]),40)
 def test_no_cuts_no_change(self):self.assertEqual(cap_hold_at_picture_cut(10,25,20,[]),25)
 def test_first_post_speech_cut(self):self.assertEqual(cap_hold_at_picture_cut(10,50,25,[40,20,30]),30)
if __name__=="__main__":unittest.main()
