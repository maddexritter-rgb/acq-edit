import copy
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('patchcheck', Path(__file__).resolve().parents[1] / 'scripts/validate_alignment_patch.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class AlignmentPatchTests(unittest.TestCase):
    def setUp(self):
        self.data = {'source_window': [1, 5], 'words': [
            {'word_index': 10, 'text': 'these', 'speaker': 'a', 'start': 2, 'end': 2.2},
            {'word_index': 11, 'text': 'employees', 'speaker': 'a', 'start': 2.3, 'end': 2.7},
            {'word_index': 12, 'text': 'work', 'speaker': 'a', 'start': 3, 'end': 3.3}],
            'patch': [{'word_index': 11, 'text': 'employees', 'start': 2.25, 'end': 2.8}]}

    def codes(self, data=None):
        return {i['code'] for i in module.validate(data or self.data)['issues']}

    def test_valid_repair_is_not_audio_pass(self):
        result = module.validate(self.data)
        self.assertEqual(result['issues'], [])
        self.assertEqual(result['acoustic_review'], 'NOT_PERFORMED')

    def test_wrong_occurrence_crosses_unchanged_neighbor(self):
        self.data['patch'][0].update(start=1.6, end=1.9)
        self.assertIn('NEIGHBOR_ORDER_CONFLICT', self.codes())

    def test_cross_speaker_conflict_is_not_silently_fixed(self):
        self.data['words'][0]['speaker'] = 'b'
        self.data['patch'][0].update(start=1.6, end=1.9)
        self.assertIn('CROSS_SPEAKER_ORDER_REQUIRES_INSPECTION', self.codes())

    def test_lexical_rewrite_rejected(self):
        self.data['patch'][0]['text'] = 'contractors'
        self.assertIn('CHANGED_WORD_IDENTITY', self.codes())

    def test_invalid_clocks(self):
        for value in [float('nan'), float('inf'), 0, 6]:
            data = copy.deepcopy(self.data)
            data['patch'][0]['start'] = value
            self.assertIn('INVALID_OR_OUT_OF_WINDOW_TIMES', self.codes(data))

    def test_duplicate_or_missing_ids(self):
        self.data['patch'].append(dict(self.data['patch'][0]))
        self.assertIn('UNKNOWN_OR_DUPLICATE_PATCH_ID', self.codes())
        self.data['patch'][1]['word_index'] = 99
        self.assertIn('UNKNOWN_OR_DUPLICATE_PATCH_ID', self.codes())

    def test_missing_context(self):
        self.data['words'] = self.data['words'][1:]
        self.assertIn('PATCH_LACKS_SURROUNDING_WORDS', self.codes())


if __name__ == '__main__':
    unittest.main()
