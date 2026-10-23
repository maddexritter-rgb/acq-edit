"""Safety regressions for source-indexed selection; these do not score editorial quality."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from l1_cut_plan import compile_plan


class L1PlanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.words = [{'word': x, 'start': i, 'end': i + .7, 'speaker': 'owner'}
                      for i, x in enumerate('Costs matter. Repeated setup. What matters? Choose deliberately.'.split())]
        self.source = self.base / 'source.json'
        self.source.write_text(json.dumps({'words': self.words}))
        self.plan = {'schema': 'edit.l1-cut-plan/v1', 'clip_id': 'test',
                     'source_words': 'source.json', 'source_sha256': self.digest(),
                     'interaction_words': [0, 7], 'viewer': 'An owner',
                     'intent': 'Understand a tradeoff', 'cleanup_review': 'Removed repetition',
                     'target_seconds': 90,
                     'segments': [
                         {'words': [4, 5], 'role': 'context', 'why': 'The explicit question'},
                         {'words': [0, 1], 'role': 'reasoning', 'why': 'The reason',
                          'reorder': {'why': 'Question first', 'original_relationship': 'Reason then question',
                                      'edited_relationship': 'Question then the same reason'}},
                         {'words': [6, 7], 'role': 'reward', 'why': 'Decision rule'}],
                     'removals': [{'words': [2, 3], 'reason': 'redundant', 'why': 'Repeated setup'}],
                     'essential': [{'words': [6, 7], 'role': 'reward', 'why': 'Decision rule'}]}

    def digest(self):
        return hashlib.sha256(self.source.read_bytes()).hexdigest()

    def compile(self):
        return compile_plan(self.plan, self.base)

    def test_reordering_preserves_source_words_and_speakers(self):
        result = self.compile()
        self.assertEqual(result['assembled_text'], 'What matters? Costs matter. Choose deliberately.')
        self.assertEqual(result['receipt']['status'], 'STRUCTURE_VALID')
        self.assertEqual(result['receipt']['source_words_accounted'], 8)
        self.assertEqual(result['design_receipt']['speakers'], ['owner'] * 6)

    def test_changed_transcript_blocks_even_if_text_is_equivalent(self):
        self.source.write_text(self.source.read_text() + '\n')
        with self.assertRaisesRegex(ValueError, 'changed'): self.compile()

    def test_unexplained_move_blocks(self):
        self.plan['segments'][1].pop('reorder')
        with self.assertRaisesRegex(ValueError, 'relationship'): self.compile()

    def test_unaccounted_source_blocks(self):
        self.plan['removals'] = []
        with self.assertRaisesRegex(ValueError, 'unaccounted'): self.compile()

    def test_duplicate_keep_and_keep_remove_overlap_block(self):
        self.plan['segments'].append(self.plan['segments'][0])
        with self.assertRaisesRegex(ValueError, 'more than once'): self.compile()
        self.plan['segments'].pop()
        self.plan['removals'][0]['words'] = [1, 3]
        with self.assertRaisesRegex(ValueError, 'overlap'): self.compile()

    def test_removed_essential_words_block(self):
        self.plan['essential'].append({'words': [2, 3], 'role': 'reasoning', 'why': 'Necessary condition'})
        with self.assertRaisesRegex(ValueError, 'essential'): self.compile()

    def test_asr_overlap_cannot_silently_select_extra_words(self):
        self.words[2]['start'] = 1.2
        self.words[2]['end'] = 1.4
        self.source.write_text(json.dumps({'words': self.words}))
        self.plan['source_sha256'] = self.digest()
        with self.assertRaisesRegex(ValueError, 'different words'): self.compile()

    def test_invalid_word_timing_blocks(self):
        self.words[0]['start'] = -1
        self.source.write_text(json.dumps({'words': self.words}))
        self.plan['source_sha256'] = self.digest()
        with self.assertRaisesRegex(ValueError, 'times'): self.compile()

    def test_duration_does_not_auto_delete_content(self):
        self.plan['target_seconds'] = 1
        result = self.compile()
        self.assertEqual(result['receipt']['kept_words'], 6)
        self.assertTrue(result['receipt']['warnings'])

    def test_v1_is_legacy_but_still_compiles(self):
        result = self.compile()
        self.assertEqual(result['receipt']['plan_schema'], 'edit.l1-cut-plan/v1')
        self.assertTrue(any('Legacy v1' in x for x in result['receipt']['warnings']))

    def test_v2_requires_semantic_review(self):
        self.plan['schema'] = 'edit.l1-cut-plan/v2'
        with self.assertRaisesRegex(ValueError, 'source_coverage'):
            self.compile()
        self.plan['source_coverage'] = {
            'interaction_start_basis': 'Owner begins after handoff',
            'interaction_end_basis': 'Next owner begins after thanks',
            'handoff_checked': True}
        with self.assertRaisesRegex(ValueError, 'promise'):
            self.compile()
        self.plan['promise'] = {'kind': 'sub_answer', 'question': 'What matters?',
                                'payoff': 'Choose deliberately'}
        self.plan['opening_review'] = {'identity': 'An owner', 'tension': 'Costs matter',
                                       'uncertainty_or_condition': 'The choice remains conditional'}
        self.plan['ending_review'] = {'completion': 'Decision rule delivered',
                                      'raw_continuation': 'No reversal before handoff',
                                      'moved_reaction_or_thanks': 'None moved'}
        result = self.compile()
        self.assertEqual(result['receipt']['plan_schema'], 'edit.l1-cut-plan/v2')
        self.assertEqual(result['receipt']['semantic_review']['promise']['kind'], 'sub_answer')
        self.assertFalse(any('Legacy v1' in x for x in result['receipt']['warnings']))

    def test_v2_rejects_unchecked_handoff_and_blank_review(self):
        self.plan.update({
            'schema': 'edit.l1-cut-plan/v2',
            'source_coverage': {'interaction_start_basis': 'Owner begins',
                                'interaction_end_basis': 'Next owner begins',
                                'handoff_checked': False},
            'promise': {'kind': 'consultation', 'question': 'What matters?',
                        'payoff': 'Choose deliberately'},
            'opening_review': {'identity': 'An owner', 'tension': 'Costs matter',
                               'uncertainty_or_condition': 'Conditional choice'},
            'ending_review': {'completion': 'Decision rule', 'raw_continuation': 'No reversal',
                              'moved_reaction_or_thanks': 'None'}})
        with self.assertRaisesRegex(ValueError, 'source_coverage'):
            self.compile()
        self.plan['source_coverage']['handoff_checked'] = True
        self.plan['ending_review']['raw_continuation'] = '   '
        with self.assertRaisesRegex(ValueError, 'ending_review'):
            self.compile()

    def test_v3_requires_retained_semantic_evidence(self):
        self.plan.update({
            'schema': 'edit.l1-cut-plan/v3',
            'source_coverage': {'interaction_start_basis': 'Owner begins',
                                'interaction_end_basis': 'Next owner begins',
                                'handoff_checked': True},
            'promise': {'kind': 'sub_answer', 'question': 'What matters?',
                        'payoff': 'Choose deliberately'},
            'opening_review': {'identity': 'An owner', 'tension': 'What matters?',
                               'uncertainty_or_condition': 'Costs matter'},
            'ending_review': {'completion': 'Choose deliberately',
                              'raw_continuation': 'No reversal',
                              'moved_reaction_or_thanks': 'None moved'}})
        with self.assertRaisesRegex(ValueError, 'semantic_evidence'):
            self.compile()
        self.plan['semantic_evidence'] = {
            'promise_question': [[4, 5]], 'promise_payoff': [[6, 7]],
            'opening_identity': [[4, 4]], 'opening_tension': [[4, 5]],
            'opening_condition': [[0, 1]], 'ending_completion': [[6, 7]]}
        result = self.compile()
        self.assertEqual(result['receipt']['plan_schema'], 'edit.l1-cut-plan/v3')
        self.assertEqual(result['receipt']['semantic_review']['semantic_evidence']
                         ['promise_question']['text'], ['What matters?'])
        self.plan['semantic_evidence']['opening_identity'] = [[2, 3]]
        with self.assertRaisesRegex(ValueError, 'not retained: opening_identity'):
            self.compile()

    def test_v4_requires_grounded_branch_inventory(self):
        self.plan.update({
            'schema': 'edit.l1-cut-plan/v4',
            'source_coverage': {'interaction_start_basis': 'Owner begins',
                                'interaction_end_basis': 'Next owner begins',
                                'handoff_checked': True},
            'promise': {'kind': 'sub_answer', 'question': 'What matters?',
                        'payoff': 'Choose deliberately'},
            'opening_review': {'identity': 'An owner', 'tension': 'What matters?',
                               'uncertainty_or_condition': 'Costs matter'},
            'ending_review': {'completion': 'Choose deliberately',
                              'raw_continuation': 'No reversal',
                              'moved_reaction_or_thanks': 'None moved'},
            'semantic_evidence': {
                'promise_question': [[4, 5]], 'promise_payoff': [[6, 7]],
                'opening_identity': [[4, 4]], 'opening_tension': [[4, 5]],
                'opening_condition': [[0, 1]], 'ending_completion': [[6, 7]]}})
        with self.assertRaisesRegex(ValueError, 'branch_review'):
            self.compile()
        self.plan['branch_review'] = [
            {'label': 'Decision rule', 'source_ranges': [[4, 7]],
             'relationship': 'selected_promise', 'disposition': 'kept',
             'scope_action': 'not_needed', 'scope_effect': 'Completes the answer',
             'retained_evidence': [[4, 7]]},
            {'label': 'Repeated setup', 'source_ranges': [[2, 3]],
             'relationship': 'separate_promise', 'disposition': 'removed',
             'scope_action': 'claim_narrowed', 'scope_effect': 'Excluded from promise',
             'retained_evidence': []}]
        result = self.compile()
        self.assertEqual(result['receipt']['plan_schema'], 'edit.l1-cut-plan/v4')
        self.assertEqual(len(result['receipt']['semantic_review']['branch_review']), 2)

    def test_v4_blocks_false_branch_disposition_and_omitted_qualification(self):
        self.test_v4_requires_grounded_branch_inventory()
        self.plan['branch_review'][1]['disposition'] = 'kept'
        with self.assertRaisesRegex(ValueError, 'disposition disagrees'):
            self.compile()
        self.plan['branch_review'][1].update(
            {'disposition': 'removed', 'relationship': 'qualifies_selected',
             'scope_action': 'not_needed'})
        with self.assertRaisesRegex(ValueError, 'safe scope action'):
            self.compile()

    def test_v4_consultation_cannot_claim_narrowed_omission(self):
        self.test_v4_requires_grounded_branch_inventory()
        self.plan['promise']['kind'] = 'consultation'
        with self.assertRaisesRegex(ValueError, 'consultation cannot narrow'):
            self.compile()

    def test_v5_requires_review_for_mid_sentence_segment_start(self):
        self.test_v4_requires_grounded_branch_inventory()
        self.plan['schema'] = 'edit.l1-cut-plan/v5'
        self.words[3]['word'] = 'setup'
        self.source.write_text(json.dumps({'words': self.words}))
        self.plan['source_sha256'] = self.digest()
        with self.assertRaisesRegex(ValueError, 'segment start needs boundary review'):
            self.compile()
        self.plan['segments'][0]['start_boundary_review'] = {
            'original_phrase': 'Repeated setup What matters?',
            'edited_phrase': 'What matters?',
            'why_complete': 'The retained question has its own subject and predicate.'}
        result = self.compile()
        self.assertEqual(result['receipt']['plan_schema'], 'edit.l1-cut-plan/v5')
        self.assertEqual(result['receipt']['boundary_reviews'][0]['edge'], 'start')

    def test_v5_boundary_review_cannot_claim_unselected_cleanup(self):
        self.test_v4_requires_grounded_branch_inventory()
        self.plan['schema'] = 'edit.l1-cut-plan/v5'
        self.words[3]['word'] = 'setup'
        self.source.write_text(json.dumps({'words': self.words}))
        self.plan['source_sha256'] = self.digest()
        self.plan['segments'][0]['start_boundary_review'] = {
            'original_phrase': 'Repeated setup What matters?',
            'edited_phrase': 'Different words begin here.',
            'why_complete': 'Claims cleanup that the selected range does not perform.'}
        with self.assertRaisesRegex(ValueError, 'edited phrase disagrees'):
            self.compile()

    def test_v6_requires_ranked_promise_and_format_comparison(self):
        self.test_v4_requires_grounded_branch_inventory()
        self.plan['schema'] = 'edit.l1-cut-plan/v6'
        self.plan['promise']['scope_boundary'] = 'Answers the selected tradeoff only'
        with self.assertRaisesRegex(ValueError, 'promise_ranking'):
            self.compile()
        self.plan['promise_ranking'] = [
            {'rank': 1, 'promise': 'Owner-specific decision rule',
             'disposition': 'selected', 'why': 'Resolves the owner dilemma'},
            {'rank': 2, 'promise': 'Host-only anecdote',
             'disposition': 'not_selected', 'why': 'Loses the owner application'}]
        with self.assertRaisesRegex(ValueError, 'format_review'):
            self.compile()
        self.plan['format_review'] = {
            'owner_specific_value': 'Owner supplies the stakes and question',
            'host_only_alternative': 'A shorter host anecdote exists',
            'selection_basis': 'The owner-specific answer has the stronger useful payoff'}
        result = self.compile()
        self.assertEqual(result['receipt']['plan_schema'], 'edit.l1-cut-plan/v6')
        self.assertEqual(result['receipt']['semantic_review']['promise_ranking'][0]
                         ['disposition'], 'selected')
        self.assertFalse(result['receipt']['warnings'])

    def test_cli_failure_invalidates_old_success(self):
        p = self.base / 'plan.json'
        out = self.base / 'compiled'
        command = [sys.executable, str(ROOT / 'scripts' / 'l1_cut_plan.py'), '--plan', str(p), '--out', str(out)]
        p.write_text(json.dumps(self.plan))
        self.assertEqual(subprocess.run(command, capture_output=True).returncode, 0)
        self.assertTrue((out / 'rough_design_evidence.json').exists())
        self.assertFalse((out / 'design_evidence.json').exists())
        self.source.write_text('{}')
        self.assertEqual(subprocess.run(command, capture_output=True).returncode, 2)
        self.assertEqual(json.loads((out / 'l1_receipt.json').read_text())['status'], 'BLOCK')


if __name__ == '__main__': unittest.main()
