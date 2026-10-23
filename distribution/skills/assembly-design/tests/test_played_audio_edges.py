"""Word preservation on the frame grid; these tests do not certify acoustics."""
import importlib.util
from fractions import Fraction
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('played_edges', Path(__file__).parents[1] / 'scripts/played_audio_edges.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class PlayedEdges(unittest.TestCase):
    def test_subframe_gap_gets_independent_audio_candidate(self):
        w = [{'start':1., 'end':1.401}, {'start':1.405, 'end':2.}]
        row=m.propose(w, [[0,0]], Fraction(30))[0]
        self.assertFalse(row['tail']['label_frame_feasible'])
        audio=row['tail']['audio']
        self.assertTrue(audio['label_sample_feasible'])
        self.assertTrue(1.401 <= audio['sample']/48000 <= 1.405)
        self.assertNotEqual(audio['sample']/48000, row['tail']['seconds'])
        self.assertFalse(audio['acoustic_verified'])

    def test_overlapping_words_do_not_get_fake_sample_precision(self):
        w=[{'start':0.,'end':1.1},{'start':1.,'end':2.}]
        row=m.propose(w,[[1,1]],Fraction(30))[0]
        self.assertIsNone(row['head']['audio']['sample'])
        self.assertEqual(row['head']['audio']['status'],'PROVISIONAL_SEAM')

    def test_short_gap_does_not_reintroduce_omitted_word(self):
        w = [{'word':'omit', 'start':0, 'end':.96}, {'word':'keep', 'start':1., 'end':1.4}]
        for fps in (Fraction(30), Fraction(24000,1001)):
            e = m.edge(w, 1, 'start', fps)
            if e['label_frame_feasible']:
                self.assertGreaterEqual(e['seconds'], .96)
                self.assertLessEqual(e['seconds'], 1.)
            else:
                self.assertTrue(e['risk'])
            self.assertFalse(e['acoustic_verified'])

    def test_handle_is_not_double_added(self):
        w = [{'start':1., 'end':1.4}]
        self.assertEqual(m.edge(w, 0, 'start', Fraction(30))['frame'], 28)

    def test_tail_contains_complete_label(self):
        w = [{'start':1., 'end':1.401}, {'start':1.405, 'end':2.}]
        e = m.edge(w, 0, 'end', Fraction(30))
        self.assertEqual(e['frame'], 43)
        self.assertFalse(e['label_frame_feasible'])
        self.assertTrue(e['risk'])

    def test_overlapped_labels_are_not_claimed_safe(self):
        w = [{'start':0., 'end':1.1}, {'start':1., 'end':2.}]
        e = m.edge(w, 1, 'start', Fraction(30))
        self.assertFalse(e['label_frame_feasible'])
        self.assertTrue(e['risk'])

    def test_late_hook_can_precede_earlier_reasoning(self):
        w = [{'start':1., 'end':2.}, {'start':3., 'end':4.}, {'start':5., 'end':6.}]
        rows = m.propose(w, [[2,2],[0,0]], Fraction(30))
        self.assertEqual([r['word_range'] for r in rows], [[2,2],[0,0]])
        self.assertTrue(all('source_overlap_with' not in r for r in rows))

    def test_adjacent_kept_ranges_can_remove_empty_pause(self):
        w = [{'start':1., 'end':2.}, {'start':3., 'end':4.}]
        rows = m.propose(w, [[0,0],[1,1]], Fraction(30))
        self.assertLess(rows[0]['source_frames'][1], rows[1]['source_frames'][0])

    def test_actual_intersection_requires_local_check(self):
        w = [{'start':1., 'end':2.1}, {'start':2., 'end':3.}]
        rows = m.propose(w, [[1,1],[0,0]], Fraction(30))
        self.assertTrue(all(r['status']=='LOCAL_CHECK' for r in rows))
        self.assertEqual(rows[0]['source_overlap_with'], [2])

    def test_repeated_selected_words_refused(self):
        with self.assertRaisesRegex(ValueError, 'repeated selected'):
            m.propose([{'start':1.,'end':2.}], [[0,0],[0,0]], Fraction(30))

    def test_positive_gaps_preserve_label_envelopes(self):
        for fps in (Fraction(24),Fraction(25),Fraction(30),Fraction(30000,1001),Fraction(60)):
            for millis in range(1, 401):
                w=[{'start':0.,'end':1.}, {'start':1.+millis/1000,'end':2.}]
                for index, side in ((0,'end'),(1,'start')):
                    e=m.edge(w,index,side,fps)
                    if e['label_frame_feasible']:
                        lo,hi=e['label_frame_envelope']
                        self.assertGreaterEqual(e['frame'],lo)
                        self.assertLessEqual(e['frame'],hi)


if __name__ == '__main__':
    unittest.main()
