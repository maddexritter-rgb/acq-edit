"""Synthetic VAD/RMS tests, not an audition or a real acoustic certification."""
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch
import numpy as np

path = Path(__file__).resolve().parents[2] / '_shared' / 'speech_map_cut.py'
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / '_shared'))
spec = importlib.util.spec_from_file_location('performance_speech_map', path)
engine = importlib.util.module_from_spec(spec)
stub = types.ModuleType('silero_vad'); stub.speech_spans = None
with patch.dict(sys.modules, {'silero_vad': stub}):
    spec.loader.exec_module(engine)


class PerformanceBoundaryTests(unittest.TestCase):
    def test_exact_word_identity_survives_overlapping_labels(self):
        words = [{'word':'previous', 'start':.95, 'end':1.2},
                 {'word':'chosen', 'start':1., 'end':1.3},
                 {'word':'neighbor', 'start':1.29, 'end':1.32}]
        self.assertEqual(engine.boundary_word_indices(words, [1.,1.3]), (0,2))
        self.assertEqual(engine.boundary_word_indices(words, [1.,1.3],
                                                     {'source_words':[1,1]}), (1,1))

    def test_indexed_span_cannot_target_unrelated_region(self):
        with self.assertRaisesRegex(ValueError, 'does not contain'):
            engine.boundary_word_indices([{'word':'x','start':1.,'end':2.}], [5.,6.],
                                         {'source_words':[0,0]})

    def test_tail_is_preserved_beyond_word_edge_hug(self):
        env = np.full(1600, -65.)
        speech = [(2,3), (6,6.5)]
        ordinary, _ = engine.boundary(24, 'end', speech, env, 0, 8, 3)
        actual, report = engine.performance_boundary(24, 'end', speech, env, 0, 8, 5.5)
        self.assertLess(ordinary, 3.5)
        self.assertGreaterEqual(actual, 5.5)
        self.assertLess(actual, 6-engine.LEAD_MARGIN)
        self.assertEqual(report['verdict'], 'OK')

    def test_head_is_preserved(self):
        actual, report = engine.performance_boundary(24, 'start', [(2,3)],
                                                     np.full(1000,-65.), 0,5,1)
        self.assertLessEqual(actual,1)
        self.assertEqual(report['verdict'],'OK')

    def test_continuous_speech_refuses(self):
        actual, report = engine.performance_boundary(24, 'end', [(2,7)],
                                                     np.full(1600,-65.), 0,8,5.5)
        self.assertIsNone(actual)
        self.assertEqual(report['verdict'],'REFUSED')

    def test_unobserved_context_refuses(self):
        actual, report = engine.performance_boundary(24, 'end', [(2,3)],
                                                     np.full(800,-65.), 0,4,5.5)
        self.assertIsNone(actual)

    def test_excluded_opening_um_is_not_silently_included(self):
        # The former indexed --preserve-opener path accepted the early starts
        # of two real review clips despite excluding these transcript words.
        qa06 = [{'word': 'um,', 'start': 7393.460, 'end': 7393.556},
                {'word': 'when', 'start': 7393.653, 'end': 7393.750}]
        qa11 = [{'word': 'um', 'start': 8613.940, 'end': 8614.460},
                {'word': 'So', 'start': 8614.471, 'end': 8614.617}]
        self.assertEqual(engine.excluded_neighbor(qa06, 1, 1, 7393.261, 7393.9),
                         ('start', 0))
        self.assertEqual(engine.excluded_neighbor(qa11, 1, 1, 8613.939, 8614.9),
                         ('start', 0))
        self.assertIsNone(engine.excluded_neighbor(qa06, 1, 1, 7393.600, 7393.9))

    def test_excluded_next_word_blocks_overwide_tail(self):
        words = [{'word': 'payoff.', 'start': 2.0, 'end': 2.4},
                 {'word': 'Um', 'start': 2.6, 'end': 2.8}]
        self.assertEqual(engine.excluded_neighbor(words, 0, 0, 1.9, 2.7),
                         ('end', 1))
        self.assertIsNone(engine.excluded_neighbor(words, 0, 0, 1.9, 2.55))


if __name__ == '__main__': unittest.main()
