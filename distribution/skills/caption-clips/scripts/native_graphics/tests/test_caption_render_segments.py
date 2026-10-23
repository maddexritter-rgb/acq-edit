import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from native_graphics.caption_render_segments import partition

class SegmentsTests(unittest.TestCase):
    def test_cut_does_not_create_gap_or_reveal_next_card(self):
        cards=[dict(id='a',text='current phrase',start_frame=0,end_frame=30),dict(id='b',text='next sentence',start_frame=30,end_frame=50)]
        rows=partition(cards,[12,24,40])
        self.assertEqual([(r['start_frame'],r['end_frame']) for r in rows],[(0,12),(12,24),(24,30),(30,40),(40,50)])
        self.assertTrue(all(r['text']=='current phrase' for r in rows if r['start_frame']<30))
        self.assertEqual([r['animation_elapsed_frames'] for r in rows],[0,12,24,0,10])
        self.assertEqual(sum(r['source_coverage_owner'] for r in rows),2)
        self.assertEqual(cards[0]['id'],'a')

    def test_genuine_blank_is_preserved(self):
        rows=partition([dict(id='a',start_frame=0,end_frame=10),dict(id='b',start_frame=30,end_frame=40)],[5,20,35])
        self.assertFalse(any(r['start_frame']<30 and r['end_frame']>10 for r in rows))

    def test_overlaps_fail(self):
        with self.assertRaises(ValueError):partition([dict(id='a',start_frame=0,end_frame=12),dict(id='b',start_frame=10,end_frame=20)],[])

    def test_edge_cuts_do_not_create_zero_length_segments(self):
        self.assertEqual(len(partition([dict(id='a',start_frame=0,end_frame=10)],[0,10])),1)

if __name__=='__main__':unittest.main()
