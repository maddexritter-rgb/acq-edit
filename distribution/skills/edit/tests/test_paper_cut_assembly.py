from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'compile_assembly.py'
spec = importlib.util.spec_from_file_location('compile_assembly_paper_cut', SCRIPT)
compiler = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compiler)


def write_receipt(path, fetched_at=None):
    ctx = {'schema': 'editorial-brain.context/v1',
           'query': {'format': 'q_and_a', 'includeRequiredReading': True},
           'playbooks': [{'playbook_id': 'assembly-universal', 'body': 'x'}]}
    encoded = json.dumps(ctx, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    ctx['client_receipt'] = {'fetched_at': (fetched_at or datetime.now(timezone.utc)).isoformat(),
                             'response_sha256': hashlib.sha256(encoded.encode('utf-8')).hexdigest()}
    path.write_text(json.dumps(ctx))
    return str(path)


class PaperCutAssemblyTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.media = root / 'source.mp4'
        self.media.touch()
        self.words = root / 'words.json'
        tokens = ['So', 'question?', 'Um,', 'The', 'answer', 'works.', 'So', 'right?', 'Yes.']
        self.words.write_text(json.dumps({'words': [
            {'word': token, 'start': i * 0.5, 'end': i * 0.5 + 0.3,
             'speaker': 'guest' if i in (0, 1, 6, 7) else 'answerer'}
            for i, token in enumerate(tokens)]}))
        self.row = {
            'id': 'clip', 'source_words': str(self.words), 'media': str(self.media),
            'interaction_word_range': [0, 8],
            'hook_word_range': [1, 1], 'reasoning_word_range': [3, 4],
            'payoff_word_range': [8, 8],
            'paper_cut': [
                {'word_range': [0, 0], 'action': 'CUT', 'reason': 'Disposable lead-in'},
                {'word_range': [1, 1], 'action': 'KEEP'},
                {'word_range': [2, 2], 'action': 'CUT', 'reason': 'Answer filler'},
                {'word_range': [3, 5], 'action': 'KEEP'},
                {'word_range': [6, 7], 'action': 'CUT', 'reason': 'Guest echo'},
                {'word_range': [8, 8], 'action': 'KEEP'},
            ],
            'speaker_roles': {'guest': 'questioner', 'answerer': 'answerer'},
            'payoff_speaker': 'answerer',
            'editorial_intent': 'Question, answer, then confirmation',
            'brain_preflight': write_receipt(root / 'clip.preflight.v1.json'),
        }

    def compile(self):
        path = Path(self.temp.name) / 'design.json'
        path.write_text(json.dumps({'schema': 'edit.assembly-selection/v2',
                                    'clips': [self.row]}))
        return compiler.compile_design(path)['clips'][0]

    def test_complete_paper_cut_builds_literal_words_and_speaker_receipt(self):
        clip = self.compile()
        self.assertEqual(clip['playback_text'], 'question? The answer works. Yes.')
        self.assertEqual(clip['paper_cut']['first_role'], 'questioner')
        self.assertEqual(clip['paper_cut']['last_role'], 'answerer')
        self.assertEqual(clip['paper_cut']['retained_filler_indices'], [])
        self.assertIsNone(clip['omitted_source_continuation'])

    def test_compiler_exposes_omitted_interaction_tail(self):
        self.row['paper_cut'][4]['word_range'] = [6, 8]
        self.row['paper_cut'].pop()
        self.row['payoff_word_range'] = [5, 5]
        clip = self.compile()
        self.assertEqual(clip['omitted_source_continuation']['word_range'], [6, 8])
        self.assertEqual(clip['omitted_source_continuation']['text'], 'So right? Yes.')

    def test_rejects_unaccounted_source_words(self):
        self.row['paper_cut'].pop(2)
        with self.assertRaisesRegex(ValueError, 'cover the interaction exactly'):
            self.compile()

    def test_rejects_opening_on_um(self):
        self.row['paper_cut'][0]['word_range'] = [0, 1]
        self.row['paper_cut'][1]['word_range'] = [2, 2]
        self.row['paper_cut'][2]['word_range'] = [3, 3]
        self.row['paper_cut'][2]['action'] = 'KEEP'
        self.row['paper_cut'][2].pop('reason')
        self.row['paper_cut'][3]['word_range'] = [4, 5]
        self.row['hook_word_range'] = [2, 2]
        with self.assertRaisesRegex(ValueError, 'opening starts on filler'):
            self.compile()

    def test_rejects_retained_unjustified_filler(self):
        self.row['paper_cut'][1]['word_range'] = [1, 2]
        self.row['paper_cut'].pop(2)
        with self.assertRaisesRegex(ValueError, 'every retained um'):
            self.compile()

    def test_opening_so_requires_deliberate_reason(self):
        self.row['paper_cut'][0]['action'] = 'KEEP'
        self.row['paper_cut'][0].pop('reason')
        self.row['hook_word_range'] = [0, 1]
        with self.assertRaisesRegex(ValueError, 'opening connective so'):
            self.compile()
        self.row['opening_connective_reason'] = 'The connective introduces a necessary contrast.'
        self.assertEqual(self.compile()['paper_cut']['first_word_index'], 0)

    def test_rejects_wrong_payoff_speaker(self):
        self.row['payoff_speaker'] = 'guest'
        with self.assertRaisesRegex(ValueError, 'payoff_speaker does not match'):
            self.compile()

    def test_questioner_ending_requires_explicit_payoff_reason(self):
        self.row['paper_cut'][4]['action'] = 'KEEP'
        self.row['paper_cut'][4].pop('reason')
        self.row['paper_cut'][5]['action'] = 'CUT'
        self.row['paper_cut'][5]['reason'] = 'Different ending'
        self.row['payoff_word_range'] = [6, 7]
        self.row['payoff_speaker'] = 'guest'
        with self.assertRaisesRegex(ValueError, 'questioner ending needs'):
            self.compile()

    def test_rejects_one_reason_stamped_over_several_ranges(self):
        for index in (1, 3, 5):
            self.row['paper_cut'][index]['reason'] = 'Retained source-native reasoning or payoff.'
        with self.assertRaisesRegex(ValueError, 'templated paper cut.*share one reason'):
            self.compile()

    def test_short_filler_cuts_may_share_a_reason(self):
        self.row['paper_cut'][0]['reason'] = 'Filler'
        self.row['paper_cut'][2]['reason'] = 'Filler'
        self.assertEqual(self.compile()['playback_text'], 'question? The answer works. Yes.')

    def test_rejects_editorial_intent_pasted_as_reason(self):
        self.row['paper_cut'][4]['reason'] = self.row['editorial_intent']
        with self.assertRaisesRegex(ValueError, 'editorial_intent copied verbatim'):
            self.compile()

    def test_rejects_rationale_copied_between_clips(self):
        twin = json.loads(json.dumps(self.row))
        twin['id'] = 'clip-2'
        twin['brain_preflight'] = write_receipt(Path(self.temp.name) / 'clip-2.preflight.v1.json')
        note = 'Live reading: universal v3 and Q&A v3 changed the opening to keep the condition.'
        self.row['live_reading'] = twin['live_reading'] = note
        path = Path(self.temp.name) / 'design.json'
        path.write_text(json.dumps({'schema': 'edit.assembly-selection/v2', 'clips': [self.row, twin]}))
        with self.assertRaisesRegex(ValueError, 'share an identical'):
            compiler.compile_design(path)

    def test_replay_of_compiled_revision_skips_template_check(self):
        path = Path(self.temp.name) / 'design.json'
        path.write_text(json.dumps({'schema': 'edit.assembly-selection/v2', 'clips': [self.row]}))
        out = Path(self.temp.name) / 'compiled.json'
        out.write_text(json.dumps(compiler.compile_design(path)))
        for index in (1, 3, 5):
            self.row['paper_cut'][index]['reason'] = 'Stamped later'
        path.write_text(json.dumps({'schema': 'edit.assembly-selection/v2', 'clips': [self.row]}))
        out.write_text(json.dumps(compiler.compile_design(path, check_templates=False)))
        self.assertEqual(compiler.validate_compiled(out)['clips'][0]['id'], 'clip')


    def test_each_new_clip_needs_its_own_brain_preflight(self):
        self.row.pop('brain_preflight')
        with self.assertRaisesRegex(ValueError, 'brain_preflight is required'):
            self.compile()

    def test_stale_brain_preflight_is_rejected(self):
        old = datetime.now(timezone.utc) - timedelta(hours=7)
        self.row['brain_preflight'] = write_receipt(Path(self.temp.name) / 'old.json', old)
        with self.assertRaisesRegex(ValueError, 'fetched 7.0 h ago'):
            self.compile()

    def test_tampered_brain_preflight_is_rejected(self):
        path = Path(self.row['brain_preflight'])
        data = json.loads(path.read_text())
        data['playbooks'][0]['body'] = 'edited after fetch'
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'does not match its receipt hash'):
            self.compile()

    def test_receipt_cannot_be_reused_for_another_clip_but_same_clip_may_revise(self):
        self.compile()
        self.compile()  # revising the same clip reuses its own fresh reading
        self.row['id'] = 'another-clip'
        with self.assertRaisesRegex(ValueError, "already used to design \\['clip'\\]"):
            self.compile()

    def test_two_clips_in_one_design_cannot_share_a_receipt(self):
        twin = json.loads(json.dumps(self.row))
        twin['id'] = 'clip-2'
        twin['editorial_intent'] = 'A different intent for the second clip'
        for decision in twin['paper_cut']:
            if decision.get('reason'):
                decision['reason'] += ' (clip 2)'
        path = Path(self.temp.name) / 'design.json'
        path.write_text(json.dumps({'schema': 'edit.assembly-selection/v2', 'clips': [self.row, twin]}))
        with self.assertRaisesRegex(ValueError, 'shares a brain_preflight'):
            compiler.compile_design(path)


if __name__ == '__main__':
    unittest.main()
