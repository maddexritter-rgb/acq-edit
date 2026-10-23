"""Regression cases from frame-quantization and false-success bridge failures."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from bridge_readback_guard import validate

FRAME = 1001 / 24000
TICKS = 10594584000


def clip(node, start, end, source_in, source_out):
    return {'nodeId': node, 'startSeconds': start * FRAME,
            'endSeconds': end * FRAME, 'inPointSeconds': source_in * FRAME,
            'outPointSeconds': source_out * FRAME, 'speed': 1}


def structure(*clips):
    return {'name': 'DISPOSABLE_TEST', 'frameRate': {'ticks': str(TICKS)},
            'videoTracks': [{'index': 0, 'clips': list(clips)}], 'audioTracks': []}


class BridgeReadbackGuardTests(unittest.TestCase):
    def test_butted_frame_exact_items_pass(self):
        result = validate(structure(clip('a', 0, 91, 100, 191),
                                    clip('b', 91, 277, 1429, 1615)))
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(result['reviewed_items'], 2)

    def test_half_frame_playhead_rounding_gap_fails(self):
        result = validate(structure(clip('a', 0, 91, 100, 191),
                                    clip('b', 92, 278, 1429, 1615)))
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(any('tiny gap 1 frame' in error for error in result['errors']))

    def test_false_success_move_stretch_and_overlap_fail(self):
        result = validate(structure(clip('a', 0, 91, 100, 191),
                                    clip('b', 91, 278, 1429, 1615),
                                    clip('c', 277, 310, 2000, 2033)))
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(any('timeline 187 frames != source 186' in error for error in result['errors']))
        self.assertTrue(any('overlap 1 frame' in error for error in result['errors']))

    def test_long_review_gap_requires_explicit_expected_length(self):
        result = validate(structure(clip('a', 0, 91, 100, 191),
                                    clip('b', 571, 757, 1429, 1615)))
        self.assertEqual(result['status'], 'FAIL')
        self.assertEqual(result['longer_gaps_to_reconcile'][0]['frames'], 480)
        approved = validate(structure(clip('a', 0, 91, 100, 191),
                                      clip('b', 571, 757, 1429, 1615)),
                            allowed_gap_frames={480})
        self.assertEqual(approved['status'], 'PASS')


if __name__ == '__main__':
    unittest.main()
