import unittest,tempfile,pathlib,sys,copy,json,concurrent.futures,time
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/"scripts"))
from spoken_preflight import compare, build_preview
from inspect_cut_boundaries import make_rows, alignment_context
class EvidenceTests(unittest.TestCase):
 def test_missing_tail_regression(self):
  x=compare([{'word':x} for x in 'but everyone learns eventually then you'.split()],'but everyone learned then you');self.assertEqual(x['status'],'REVIEW_REQUIRED');self.assertIn('eventually',str(x['issues']))
 def test_matching_text_not_approval(self):self.assertEqual(compare([{'word':'Eventually.'}],'eventually')['status'],'TEXT_MATCH_NOT_ACOUSTIC_APPROVAL')
 def test_repeated_omission(self):self.assertTrue(compare([{'word':'go'},{'word':'go'}],'go')['issues'])
 def test_blank_expected_rejected(self):
  with self.assertRaises(ValueError):compare([],'hello')
 def test_context_and_conflict_priority(self):
  words=[{'word':f'w{i}','start':i,'end':i+.5} for i in range(10)];clip={'kept_word_ranges':[[3,6]],'interaction_word_range':[0,9]};ph={'words':{'6':{'word_index':6,'word':'w6','aligned_start':6.,'aligned_end':7.5}}};rows,_,_=make_rows(clip,words,ph);tail=next(r for r in rows if r['kind']=='tail');self.assertIn('LOCATOR_DISAGREEMENT',tail['reasons']);self.assertGreaterEqual(tail['end'],8.5);self.assertFalse(tail['acoustic_approved'])
 def test_vad_conflict_word_ids(self):
  words=[{'word':f'w{i}','start':i,'end':i+.5} for i in range(10)];clip={'kept_word_ranges':[[3,6]],'interaction_word_range':[0,9]};rows,_,_=make_rows(clip,words,performance={'events':[{'kind':'vad_word_conflict','id':'vad_conflict_999_1000','word_indices':[4]}]});self.assertTrue(any(r['kind']=='vad_word_conflict' and r['word_index']==4 for r in rows))

class PreviewTests(unittest.TestCase):
 def test_exact_stereo_channel_and_intervals(self):
  import wave,struct
  with tempfile.TemporaryDirectory() as td:
   source=pathlib.Path(td)/'source.wav';out=pathlib.Path(td)/'preview.wav'
   with wave.open(str(source),'wb') as w:
    w.setnchannels(2);w.setsampwidth(2);w.setframerate(8);w.writeframes(struct.pack('<16h',*sum(([i,100+i] for i in range(8)),[])))
   paired={'sample_rate':8,'fps':8,'duration_frames':4,'source_samples':[[1,3],[5,7]],'timeline_samples':[[0,2],[2,4]]}
   build_preview(source,paired,out,1)
   with wave.open(str(out),'rb') as w:self.assertEqual(struct.unpack('<4h',w.readframes(4)),(101,102,105,106))
 def test_internal_gap_rejected(self):
  import wave
  with tempfile.TemporaryDirectory() as td:
   source=pathlib.Path(td)/'source.wav'
   with wave.open(str(source),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(8);w.writeframes(bytes(16))
   with self.assertRaises(ValueError):build_preview(source,{'sample_rate':8,'fps':8,'duration_frames':5,'source_samples':[[0,2],[4,6]],'timeline_samples':[[0,2],[3,5]]},pathlib.Path(td)/'preview.wav',0)

if __name__=='__main__':unittest.main()
