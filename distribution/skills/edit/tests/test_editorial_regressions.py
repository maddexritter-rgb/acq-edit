import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / (name + '.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


design = module('design_evidence')
select = module('clip_select')
assembled = module('assembled_gate')


class EditorialRegressions(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'words.json'
        self.words = [{'word': word, 'start': float(i), 'end': i + .8, 'spk': 'guest'}
                      for i, word in enumerate('Difficulty is not value. Clean pools better. Ask neighbors to switch.'.split())]
        self.path.write_text(json.dumps({'words': self.words}))
        self.spec = {'schema': 'edit.design-evidence/v1', 'clip_id': 'example',
                     'source_words': str(self.path), 'source_sha256': design.digest(self.path.read_bytes()),
                     'intent': 'Improve service and ask customers to switch',
                     'essential': [{'role': 'reward', 'words': [7, 10], 'why': 'Practical acquisition action'}],
                     'keep_spans': [[0, 10.9]], 'cleanup_review': 'Already clean continuous explanation'}

    def test_short_complete_idea_is_not_blocked_for_length(self):
        failures, warnings = assembled.check("short", "Clean pools better. Ask neighbors to switch.")
        self.assertEqual(failures, [])
        self.assertTrue(any("SHORT CONTENT" in w for w in warnings))

    def test_complete_zero_cut_idea_allowed(self):
        self.assertEqual(design.evaluate(self.spec)['status'], 'PASS')

    def test_thesis_without_selected_practical_payoff_blocks(self):
        self.spec['keep_spans'] = [[0, 3.9]]
        self.assertEqual(design.evaluate(self.spec)['status'], 'BLOCK')

    def test_unfinished_new_tail_can_be_removed(self):
        self.spec['essential'] = [{'role': 'reward', 'words': [4, 6], 'why': 'Completed service principle'}]
        self.spec['keep_spans'] = [[0, 6.9]]
        self.assertEqual(design.evaluate(self.spec)['status'], 'PASS')

    def test_source_change_invalidates_receipt(self):
        self.path.write_text(self.path.read_text() + ' ')
        with self.assertRaisesRegex(ValueError, 'changed'):
            design.evaluate(self.spec)

    def test_changed_spans_change_receipt_identity(self):
        first = design.evaluate(self.spec)
        self.spec['keep_spans'] = [[4, 10.9]]
        second = design.evaluate(self.spec)
        self.assertNotEqual(first['design_sha256'], second['design_sha256'])
        self.assertNotEqual(first['assembled_sha256'], second['assembled_sha256'])

    def test_overlap_and_invalid_indices_block(self):
        self.spec['keep_spans'] = [[0, 8], [7, 10.9]]
        with self.assertRaisesRegex(ValueError, 'overlap'):
            design.evaluate(self.spec)
        self.spec['keep_spans'] = [[0, 10.9]]
        self.spec['essential'][0]['words'] = [7, 999]
        with self.assertRaisesRegex(ValueError, 'range'):
            design.evaluate(self.spec)

    def test_word_and_segment_speaker_provenance(self):
        self.assertIn('speaker=guest', select.load_transcript(self.path))
        self.path.write_text(json.dumps({'segments': [{'start': 1, 'end': 3, 'text': 'Question?', 'speaker': 'host'}]}))
        self.assertIn('speaker=host', select.load_transcript(self.path))

    def test_rules_reach_proposal_model(self):
        rules = {'subset': 'podcast', 'structure_lift': {'interior_trims': {'lift': 1.1}}}
        prompt = select.proposal_prompt(rules)
        self.assertEqual(json.loads(prompt.split('ACTIVE EMPIRICAL PRIORS (not acceptance rules):\n')[1]), rules)

    def test_judge_failure_is_not_mine(self):
        with patch.object(select, 'call_claude', side_effect=RuntimeError('offline')):
            with self.assertRaises(RuntimeError):
                select.judge_rerank('source', [{'open_line': 'Claim', 'verdict': 'MINE'}])

    def test_judge_must_cover_every_candidate(self):
        cands = [{'open_line': 'Same opening', 'verdict': 'MINE'} for _ in range(12)]
        rows = [{'candidate_id': str(i), 'quality': 80} for i in range(12)]
        with patch.object(select, 'call_claude', return_value=json.dumps({'ranked': rows})):
            self.assertEqual(len(select.judge_rerank('source', cands)), 12)
        rows[-1]['candidate_id'] = '0'
        with patch.object(select, 'call_claude', return_value=json.dumps({'ranked': rows})):
            with self.assertRaises(ValueError):
                select.judge_rerank('source', cands)


if __name__ == '__main__':
    unittest.main()
