import copy
import unittest
from pathlib import Path
from style_library import allocate

class RotationTests(unittest.TestCase):
 def setUp(self):
  self.library={'schema':'hook-style-library/v1','library_id':'fixture','styles':[{'id':f's{i}','status':'approved','approval_evidence':'fixture approval','font_path':str(Path.home()/'Library/Fonts/Poppins-Bold.ttf'),'case':'preserve'} for i in range(20)]}
 def test_twenty_unique_then_cycle(self):
  p=allocate(self.library,[str(i) for i in range(21)])
  ids=[r['style_id'] for r in p['assignments']]
  self.assertEqual(len(set(ids[:20])),20);self.assertEqual(ids[20],ids[0])
  next_plan=allocate(self.library,['next'],p)
  self.assertEqual(next_plan['assignments'][0]['style_id'],'s1')
 def test_candidates_never_used(self):
  self.library['styles'][0]['status']='candidate'
  p=allocate(self.library,[str(i) for i in range(20)])
  self.assertNotIn('s0',[r['style_id'] for r in p['assignments']]);self.assertTrue(p['repeats_required'])
  for s in self.library['styles']:s['status']='candidate'
  with self.assertRaises(ValueError):allocate(self.library,['clip'])
 def test_snapshot_and_duplicate_clip(self):
  p=allocate(self.library,['clip']);self.library['styles'][0]['case']='upper'
  self.assertEqual(p['assignments'][0]['style']['case'],'preserve')
  with self.assertRaises(ValueError):allocate(self.library,['clip','clip'])
 def test_collection_and_copy_shape_select_compatible_style(self):
  self.library['styles']=[
   {**self.library['styles'][0],'id':'plain','collection':'reference','copy_shapes':['direct'],'semantic_beats':[1,2]},
   {**self.library['styles'][1],'id':'split','collection':'reference','copy_shapes':['question'],'semantic_beats':[2],
    'line_styles':[{'foreground':'#111111'},{'foreground':'#FFFFFF'}]},
   {**self.library['styles'][2],'id':'classic','collection':'classic'}]
  p=allocate(self.library,['a','b'],collection='reference',clip_shapes={
   'a':{'shape':'question','beats':2},'b':{'shape':'direct','beats':1}})
  self.assertEqual([r['style_id'] for r in p['assignments']],['split','plain'])
  with self.assertRaisesRegex(ValueError,'No compatible'):
   allocate(self.library,['c'],collection='reference',clip_shapes={'c':{'shape':'question','beats':1}})
if __name__=='__main__':unittest.main()
