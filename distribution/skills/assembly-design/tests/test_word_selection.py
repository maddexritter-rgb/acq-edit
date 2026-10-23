import hashlib
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / '_shared'))
from word_selection import select_indices, validate_indexed_spec


class WordSelectionTests(unittest.TestCase):
    def setUp(self):
        self.words = [(0, .1, 'Um'), (.15, .3, 'Test'), (.35, .5, 'demand.'), (.55, .7, 'Um')]
        self.d = {'words': [{'word': w, 'start': a, 'end': b} for a,b,w in self.words]}
        self.raw = json.dumps(self.d).encode()
        self.seg = {'in': .15, 'out': .5, 'source_words': [1,2]}
        self.spec = {'source_sha256': hashlib.sha256(self.raw).hexdigest(), 'segments': [self.seg]}

    def test_no_padded_neighbor_selection(self):
        validate_indexed_spec(self.spec, self.d, self.raw, True)
        self.assertEqual(select_indices(self.words, self.seg), [1,2])

    def test_legacy_unchanged(self):
        self.assertEqual(select_indices(self.words, {'in': .15, 'out': .5}), [0,1,2,3])

    def test_requires_preserve(self):
        with self.assertRaisesRegex(ValueError, 'preserve-internal'):
            validate_indexed_spec(self.spec, self.d, self.raw, False)

    def test_pins_source(self):
        with self.assertRaisesRegex(ValueError, 'changed'):
            validate_indexed_spec(self.spec, self.d, self.raw+b' ', True)

    def test_invalid_index(self):
        self.seg['source_words'] = [1,10]
        with self.assertRaises(ValueError): select_indices(self.words, self.seg)

    def test_flat_array_required(self):
        with self.assertRaisesRegex(ValueError, 'flat'):
            validate_indexed_spec(self.spec, {'segments':[self.d]}, self.raw, True)

    def test_mixed_selection_blocked(self):
        self.spec['segments'].append({'in': 0, 'out': .7})
        with self.assertRaisesRegex(ValueError, 'mix'):
            validate_indexed_spec(self.spec, self.d, self.raw, True)


if __name__ == '__main__': unittest.main()
