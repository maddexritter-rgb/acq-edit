import unittest,sys,pathlib
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from acoustic_boundary_index import refine
from fractions import Fraction
class BoundaryTests(unittest.TestCase):
 def runedge(self,words,speech,side='start',idx=1,frame=30):return refine(words,idx,side,Fraction(30),{'frame':frame,'acoustic_verified':False},{'duration':5,'speech':speech})
 def test_cut_inside_speech_refused(self):
  w=[{'start':0,'end':.9},{'start':1.,'end':1.5}]
  self.assertIsNone(self.runedge(w,[[0,1.5]])['frame'])
 def test_gap_constrained(self):
  w=[{'start':0,'end':.7},{'start':1.,'end':1.5}]
  r=self.runedge(w,[[0,.75],[.95,1.5]])
  self.assertGreater(r['seconds'],.75);self.assertLess(r['seconds'],.95);self.assertFalse(r['acoustic_verified'])
 def test_quiet_word_not_erased(self):
  w=[{'start':0,'end':.9},{'start':1.,'end':1.5}]
  self.assertIsNone(self.runedge(w,[[0,.7]])['frame'])
 def test_overlap_refused(self):
  w=[{'start':0,'end':1.1},{'start':1.,'end':1.5}]
  self.assertIsNone(self.runedge(w,[[0,1.5]])['frame'])
 def test_no_excluded_word_restored(self):
  w=[{'start':0,'end':.94},{'start':1.,'end':1.5}]
  self.assertIsNone(self.runedge(w,[[0,.8],[.93,1.5]])['frame'])
 def test_tail_preserves_locator(self):
  w=[{'start':0,'end':.7},{'start':1.,'end':1.5},{'start':2.,'end':2.5}]
  r=self.runedge(w,[[0,.7],[1,1.65],[1.95,2.5]],'end',frame=46)
  self.assertGreater(r['seconds'],1.65);self.assertLess(r['seconds'],1.95)
 def test_no_grid_point(self):
  w=[{'start':0,'end':.99},{'start':1.01,'end':1.5}]
  self.assertIsNone(self.runedge(w,[[0,.9999],[1.,1.5]])['frame'])
if __name__=='__main__':unittest.main()
