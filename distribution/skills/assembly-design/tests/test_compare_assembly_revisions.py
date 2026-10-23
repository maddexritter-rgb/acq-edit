import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'compare_assembly_revisions.py'
spec = importlib.util.spec_from_file_location('compare_assembly_revisions', SCRIPT)
comparison = importlib.util.module_from_spec(spec)
spec.loader.exec_module(comparison)


class RevisionComparisonTest(unittest.TestCase):
    def test_interior_removal_is_flagged_even_when_hook_and_payoff_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = {'schema': 'edit.compiled-assembly/v1', 'design_path': 'a.json',
                    'design_sha256': 'one', 'clips': [{
                        'id': 'clip', 'source_words_sha256': 'words',
                        'spans': [{'word_range': [1, 5]}, {'word_range': [8, 12]},
                                  {'word_range': [20, 24]}],
                        'beats': {'hook': {'word_range': [1, 3]},
                                  'payoff': {'word_range': [21, 24]}}}]}
            after = json.loads(json.dumps(base))
            after['design_path'] = 'b.json'
            after['clips'][0]['spans'].pop(1)
            first, second = root / 'before.json', root / 'after.json'
            first.write_text(json.dumps(base))
            second.write_text(json.dumps(after))
            row = comparison.compare(first, second)['clips'][0]
            self.assertTrue(row['review_required'])
            self.assertTrue(row['checks']['selected_words_removed'])
            self.assertEqual(row['removed_word_ranges'], [[8, 12]])


if __name__ == '__main__':
    unittest.main()
