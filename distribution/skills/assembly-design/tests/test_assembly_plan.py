import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'assembly_plan.py'
spec = importlib.util.spec_from_file_location('assembly_plan', SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class AssemblyTests(unittest.TestCase):
    def test_pinned_uses_guarded_digest_cache_and_rejects_stale_pin(self):
        with tempfile.TemporaryDirectory() as td:
            evidence = Path(td) / 'large-evidence.bin'
            evidence.write_bytes(b'current')
            with patch.object(m, 'digest', return_value=m.sha(b'current')) as cached:
                self.assertEqual(m.pinned(str(evidence), m.sha(b'current')), evidence)
                cached.assert_called_once_with(evidence)
                with self.assertRaises(ValueError):
                    m.pinned(str(evidence), m.sha(b'stale'))

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.words = [{'word': t, 'start': i, 'end': i+.5, 'spk': 'A'}
                      for i, t in enumerate('Only if demand exists. um Test demand first.'.split())]
        source = self.save('words.json', {'words': self.words})
        self.audio = self.save('synthetic-evidence.json', {'synthetic_test_only': True})
        v = {'schema': 'edit.transcript-verification/v1', 'source_words': str(source),
             'source_sha256': m.sha(source.read_bytes()), 'raw_words': str(source),
             'raw_sha256': m.sha(source.read_bytes()), 'audio_path': str(self.audio),
             'audio_sha256': m.sha(self.audio.read_bytes()), 'checked_words': [[0, 7]],
             'reviewer': 'synthetic-test', 'method': 'fixture, not real listening',
             'unresolved': [], 'corrections': []}
        vp = self.save('verification.json', v)
        self.plan = {'schema': 'edit.assembly-plan/v1', 'clip_id': 'test',
                     'intent': 'Test before committing', 'viewer': 'business owner',
                     'cleanup_review': 'remove hesitation', 'source_words': str(source),
                     'source_sha256': m.sha(source.read_bytes()), 'interaction_words': [0, 7],
                     'profiles': ['monologue'],
                     'segments': [{'words': [5, 7], 'role': 'reward', 'why': 'action'},
                                  {'words': [0, 3], 'role': 'context', 'why': 'condition',
                                   'reorder': {'why': 'lead with action',
                                               'original_relationship': 'condition then action',
                                               'edited_relationship': 'same condition after action'}}],
                     'removals': [{'words': [4, 4], 'reason': 'filler', 'why': 'hesitation'}],
                     'essential': [{'words': [0, 3], 'role': 'context', 'why': 'condition'},
                                   {'words': [5, 7], 'role': 'reward', 'why': 'action'}],
                     'editorial_review': {k: 'synthetic fixture only' for k in
                                         ('promise', 'hook', 'payoff', 'context', 'qualifications',
                                          'omitted_branches', 'reorder_safety',
                                          'ending_continuation', 'alternatives')},
                     'verification': {'path': str(vp), 'sha256': m.sha(vp.read_bytes())}}

    def save(self, name, value):
        p = self.root / name
        p.write_text(json.dumps(value))
        return p

    def resolved(self, spans=None):
        spans = spans or [[5, 7.5], [0, 3.5]]
        report = self.save('synthetic-smc.json', [
            {'start': {'verdict': 'OK'}, 'end': {'verdict': 'OK'}, 'result': span}
            for span in spans])
        return {'schema': 'edit.assembly-resolved/v1', 'plan_sha256': m.fingerprint(self.plan),
                'source_sha256': self.plan['source_sha256'], 'fps': '24',
                'spans': spans,
                'acoustic_evidence': {'path': str(report), 'sha256': m.sha(report.read_bytes())}}

    def test_reordering_and_final_clock(self):
        c = m.compile_assembly(self.plan)
        self.assertEqual(c['assembled_text'], 'Test demand first. Only if demand exists.')
        r = m.reconcile(self.plan, self.resolved())
        self.assertEqual(r['status'], 'WORDS_RECONCILED')
        self.assertEqual([w['source_word_index'] for w in r['words']], [5,6,7,0,1,2,3])
        self.assertEqual(r['words'][3]['start'], 2.5)

    def test_all_profiles_supported(self):
        for profile in ('monologue', 'qa', 'conversation_story'):
            self.plan['profiles'] = [profile]
            self.assertEqual(m.compile_assembly(self.plan)['receipt']['status'], 'STRUCTURE_VALID')

    def test_draft_cannot_compile_even_with_copied_verification(self):
        self.plan['stage'] = 'draft'
        with self.assertRaisesRegex(ValueError, 'unverified draft'):
            m.compile_assembly(self.plan)

    def diagnosis(self):
        self.plan['profiles'] = ['qa', 'l1_diagnosis']
        self.plan['segments'][0]['start_boundary_review'] = {
            'original_phrase': 'um Test demand first.', 'edited_phrase': 'Test demand first.',
            'why_complete': 'Remove hesitation before complete imperative.'}
        self.plan['diagnosis'] = {
            'source_coverage': {'handoff_checked': True,
                'interaction_start_basis': 'Synthetic complete exchange starts at zero.',
                'interaction_end_basis': 'Synthetic exchange ends with action.'},
            'promise': {'kind': 'sub_answer', 'question': 'When to commit?',
                'payoff': 'Test demand first.', 'scope_boundary': 'Readiness, not implementation.'},
            'promise_ranking': [{'rank': 1, 'promise': 'Test demand first.',
                'disposition': 'selected', 'why': 'Only complete answer in synthetic fixture.'}],
            'format_review': {'owner_specific_value': 'Synthetic conditional advice.',
                'host_only_alternative': 'No independent story in fixture.',
                'selection_basis': 'Preserve condition with action.'},
            'opening_review': {'identity': 'Demand-testing owner.', 'tension': 'Whether to commit.',
                'uncertainty_or_condition': 'Only if demand exists.'},
            'ending_review': {'completion': 'Demand condition completes advice.',
                'raw_continuation': 'Synthetic end.', 'moved_reaction_or_thanks': 'None in fixture.'},
            'semantic_evidence': {k: [[0, 3]] for k in ('promise_question', 'opening_identity',
                'opening_tension', 'opening_condition', 'ending_completion')},
            'branch_review': [
                {'label': 'Action', 'source_ranges': [[5, 7]], 'relationship': 'selected_promise',
                 'disposition': 'kept', 'scope_action': 'not_needed',
                 'scope_effect': 'Action retained.', 'retained_evidence': [[5, 7]]},
                {'label': 'Condition', 'source_ranges': [[0, 3]], 'relationship': 'qualifies_selected',
                 'disposition': 'kept', 'scope_action': 'not_needed',
                 'scope_effect': 'Conditional advice remains conditional.', 'retained_evidence': [[0, 3]]}]}
        self.plan['diagnosis']['semantic_evidence']['promise_payoff'] = [[5, 7]]

    def test_mixed_diagnosis_uses_existing_v6_review(self):
        self.diagnosis()
        receipt = m.compile_assembly(self.plan)['receipt']
        self.assertEqual(receipt['profiles'], ['qa', 'l1_diagnosis'])
        self.assertEqual(receipt['construction_review']['branch_review'][1]
                         ['retained_evidence_text'], ['Only if demand exists.'])
        self.assertEqual(len(receipt['boundary_reviews']), 1)

    def test_diagnosis_cannot_silently_use_weak_adapter(self):
        self.plan['profiles'] = ['monologue', 'l1_diagnosis']
        with self.assertRaisesRegex(ValueError, 'complete diagnosis'):
            m.compile_assembly(self.plan)

    def test_diagnosis_cannot_override_source_or_selections(self):
        self.diagnosis()
        self.plan['diagnosis']['segments'] = []
        with self.assertRaisesRegex(ValueError, 'complete diagnosis'):
            m.compile_assembly(self.plan)

    def test_diagnosis_ledger_cannot_lie_about_retention(self):
        self.diagnosis()
        self.plan['diagnosis']['branch_review'][1]['disposition'] = 'removed'
        with self.assertRaisesRegex(ValueError, 'disposition disagrees'):
            m.compile_assembly(self.plan)

    def test_diagnosis_omitted_reversal_requires_scope_action(self):
        self.diagnosis()
        self.plan['diagnosis']['branch_review'].append({
            'label': 'Synthetic reversal', 'source_ranges': [[4, 4]],
            'relationship': 'reverses_selected', 'disposition': 'removed',
            'scope_action': 'not_needed', 'scope_effect': 'Unsafe synthetic omission.'})
        with self.assertRaisesRegex(ValueError, 'explicit safe scope action'):
            m.compile_assembly(self.plan)

    def test_diagnosis_semantic_evidence_must_survive(self):
        self.diagnosis()
        self.plan['diagnosis']['semantic_evidence']['opening_condition'] = [[4, 4]]
        with self.assertRaisesRegex(ValueError, 'evidence is not retained'):
            m.compile_assembly(self.plan)

    def test_diagnosis_requires_matching_profile(self):
        self.diagnosis()
        self.plan['profiles'] = ['qa']
        with self.assertRaisesRegex(ValueError, 'requires l1_diagnosis'):
            m.compile_assembly(self.plan)

    def test_rational_rate(self):
        import math
        fps = 24000/1001
        spans = [[math.floor(5*fps)/fps, math.ceil(7.5*fps)/fps],
                 [0, math.ceil(3.5*fps)/fps]]
        r = self.resolved(spans); r['fps'] = '24000/1001'
        self.assertEqual(m.reconcile(self.plan, r)['status'], 'WORDS_RECONCILED')

    def test_dialogue_preserves_speakers_inside_and_between_selections(self):
        self.words[6]['spk'] = 'B'
        self.words[7].pop('spk')
        source = self.save('words.json', {'words': self.words})
        self.plan['source_sha256'] = m.sha(source.read_bytes())
        vp = Path(self.plan['verification']['path'])
        v = json.loads(vp.read_text())
        v.update(source_sha256=self.plan['source_sha256'], raw_sha256=self.plan['source_sha256'])
        vp.write_text(json.dumps(v))
        self.plan['verification']['sha256'] = m.sha(vp.read_bytes())
        c = m.compile_assembly(self.plan)
        self.assertEqual([d['speaker'] for d in c['assembled_dialogue']], ['A', 'B', None, 'A'])
        self.assertEqual([d['source_words'] for d in c['assembled_dialogue']],
                         [[5,5], [6,6], [7,7], [0,3]])
        self.assertEqual(c['assembled_dialogue_text'],
                         'A: Test\nB: demand\nUNKNOWN: first.\nA: Only if demand exists.')

    def test_undocumented_correction(self):
        original = self.save('original.json', {'words': self.words})
        p = Path(self.plan['source_words'])
        changed = copy.deepcopy(self.words); changed[0]['word'] = 'Even'
        p.write_text(json.dumps({'words': changed}))
        self.plan['source_sha256'] = m.sha(p.read_bytes())
        vp = Path(self.plan['verification']['path']); v = json.loads(vp.read_text())
        v.update(source_sha256=self.plan['source_sha256'], raw_words=str(original),
                 raw_sha256=m.sha(original.read_bytes()))
        vp.write_text(json.dumps(v)); self.plan['verification']['sha256'] = m.sha(vp.read_bytes())
        with self.assertRaisesRegex(ValueError, 'evidenced corrections'):
            m.compile_assembly(self.plan)

    def test_split_merge_insert_correction_mappings(self):
        # Contract verification accepts changed token counts only inside evidenced
        # mappings; this fixture tests provenance, not transcription accuracy.
        for replacement in (['Onlyif'], ['Only', 'really', 'if'], ['Only', 'i', 'f']):
            with self.subTest(replacement=replacement):
                changed = [{'word': t, 'start': j * .2, 'end': j * .2 + .1}
                           for j, t in enumerate(replacement)] + copy.deepcopy(self.words[2:])
                source = self.save('corrected.json', {'words': changed})
                plan = copy.deepcopy(self.plan)
                plan.update(source_words=str(source), source_sha256=m.sha(source.read_bytes()),
                            interaction_words=[0, len(changed)-1])
                v = json.loads(Path(self.plan['verification']['path']).read_text())
                v.update(source_words=str(source), source_sha256=plan['source_sha256'],
                         checked_words=[[0, len(changed)-1]], corrections=[{
                    'raw_words': [0, 1], 'corrected_words': [0, len(replacement)-1],
                    'heard': 'Synthetic fixture only.', 'why': 'Exercise token-count mapping.',
                    'evidence': {'path': str(self.audio), 'sha256': m.sha(self.audio.read_bytes())}}])
                vp = self.save('correction-verification.json', v)
                plan['verification'] = {'path': str(vp), 'sha256': m.sha(vp.read_bytes())}
                self.assertEqual(m.verification(plan, changed), v)
                changed[-1]['word'] = 'Undocumented'
                with self.assertRaisesRegex(ValueError, 'undocumented transcript changes'):
                    m.verification(plan, changed)

    def test_repeated_phrase_cannot_substitute_different_occurrence(self):
        self.words[0]['word'] = 'Test'
        self.words[1]['word'] = 'demand'
        self.words[2]['word'] = 'first.'
        source = self.save('words.json', {'words': self.words})
        self.plan['source_sha256'] = m.sha(source.read_bytes())
        vp = Path(self.plan['verification']['path'])
        v = json.loads(vp.read_text())
        v.update(source_sha256=self.plan['source_sha256'], raw_sha256=self.plan['source_sha256'])
        vp.write_text(json.dumps(v))
        self.plan['verification']['sha256'] = m.sha(vp.read_bytes())
        # Text-equivalent first phrase from another occurrence is not interchangeable.
        with self.assertRaisesRegex(ValueError, 'overlap|retained words changed'):
            m.reconcile(self.plan, self.resolved([[0, 2.5], [0, 3.5]]))

    def test_unwanted_crosstalk_in_selected_time(self):
        self.words[4].update(start=2.1, end=2.3, spk='B')
        p = self.save('words.json', {'words': self.words})
        self.plan['source_sha256'] = m.sha(p.read_bytes())
        vp = Path(self.plan['verification']['path']); v = json.loads(vp.read_text())
        v.update(source_sha256=self.plan['source_sha256'], raw_sha256=self.plan['source_sha256'])
        vp.write_text(json.dumps(v)); self.plan['verification']['sha256'] = m.sha(vp.read_bytes())
        with self.assertRaisesRegex(ValueError, 'different words'):
            m.compile_assembly(self.plan)

    def test_unwanted_word_restored(self):
        with self.assertRaisesRegex(ValueError, 'retained words changed'):
            m.reconcile(self.plan, self.resolved([[4, 7.5], [0, 3.5]]))

    def test_partial_filler_leak_outside_midpoint(self):
        with self.assertRaisesRegex(ValueError, 'partial edge'):
            m.reconcile(self.plan, self.resolved([[4.416666666666667, 7.5], [0, 3.5]]))

    def test_partial_kept_word(self):
        with self.assertRaisesRegex(ValueError, 'partial edge'):
            m.reconcile(self.plan, self.resolved([[5.125, 7.5], [0, 3.5]]))

    def test_missing_qualification(self):
        self.plan['segments'][1]['words'] = [2, 3]
        self.plan['removals'].append({'words': [0,1], 'reason': 'off_arc', 'why': 'bad deletion'})
        with self.assertRaisesRegex(ValueError, 'essential'):
            m.compile_assembly(self.plan)

    def test_source_mutation(self):
        Path(self.plan['source_words']).write_text('{}')
        with self.assertRaisesRegex(ValueError, 'evidence changed'):
            m.compile_assembly(self.plan)

    def test_stale_resolution(self):
        r = self.resolved()
        self.plan['cleanup_review'] = 'a new revision'
        with self.assertRaisesRegex(ValueError, 'stale resolved plan'):
            m.reconcile(self.plan, r)

    def test_chronological_sort_is_not_allowed(self):
        with self.assertRaisesRegex(ValueError, 'retained words changed'):
            m.reconcile(self.plan, self.resolved([[0,3.5], [5,7.5]]))

    def test_overlap(self):
        with self.assertRaisesRegex(ValueError, 'overlap'):
            m.reconcile(self.plan, self.resolved([[5,7.5], [0,5.5]]))

    def test_off_frame(self):
        with self.assertRaisesRegex(ValueError, 'frame grid'):
            m.reconcile(self.plan, self.resolved([[5.001,7.5], [0,3.5]]))

    def test_empty_far_tail(self):
        with self.assertRaisesRegex(ValueError, 'word-empty'):
            m.reconcile(self.plan, self.resolved([[5,7.5], [0,3.5], [1000,1001]]))

    def test_inflated_tail(self):
        with self.assertRaisesRegex(ValueError, 'invalid keep span'):
            m.reconcile(self.plan, self.resolved([[5,1000], [0,3.5]]))

    def test_missing_reorder_review(self):
        del self.plan['segments'][1]['reorder']
        with self.assertRaisesRegex(ValueError, 'relationship review'):
            m.compile_assembly(self.plan)

    def test_unchecked_context(self):
        p = Path(self.plan['verification']['path'])
        v = json.loads(p.read_text()); v['checked_words'] = [[5,7]]
        p.write_text(json.dumps(v)); self.plan['verification']['sha256'] = m.sha(p.read_bytes())
        with self.assertRaisesRegex(ValueError, 'not fully audio-checked'):
            m.compile_assembly(self.plan)

    def test_unknown_issue(self):
        p = Path(self.plan['verification']['path'])
        v = json.loads(p.read_text()); v['unresolved'] = ['unclear negation']
        p.write_text(json.dumps(v)); self.plan['verification']['sha256'] = m.sha(p.read_bytes())
        with self.assertRaisesRegex(ValueError, 'unresolved'):
            m.compile_assembly(self.plan)

    def test_refused_acoustic_boundary(self):
        r = self.resolved()
        p = Path(r['acoustic_evidence']['path'])
        report = json.loads(p.read_text()); report[0]['end']['verdict'] = 'FUSED'
        p.write_text(json.dumps(report)); r['acoustic_evidence']['sha256'] = m.sha(p.read_bytes())
        with self.assertRaisesRegex(ValueError, 'unsafe or unverified'):
            m.reconcile(self.plan, r)

    def test_micro_gap_requires_measured_evidence(self):
        r = self.resolved()
        p = Path(r['acoustic_evidence']['path'])
        report = json.loads(p.read_text())
        report[0]['start'] = {'verdict': 'OK_MICRO_GAP', 'gap_ms': 81,
                              'cut_db': -38.9, 'preceding_word': 'uh',
                              'following_word': 'Test'}
        p.write_text(json.dumps(report)); r['acoustic_evidence']['sha256'] = m.sha(p.read_bytes())
        self.assertEqual(m.reconcile(self.plan, r)['status'], 'WORDS_RECONCILED')
        report[0]['start']['cut_db'] = -20
        p.write_text(json.dumps(report)); r['acoustic_evidence']['sha256'] = m.sha(p.read_bytes())
        with self.assertRaisesRegex(ValueError, 'micro-gap acoustic evidence'):
            m.reconcile(self.plan, r)

    def test_mismatched_acoustic_result(self):
        r = self.resolved()
        p = Path(r['acoustic_evidence']['path'])
        report = json.loads(p.read_text()); report[0]['result'][0] += .1
        p.write_text(json.dumps(report)); r['acoustic_evidence']['sha256'] = m.sha(p.read_bytes())
        with self.assertRaisesRegex(ValueError, 'different boundaries'):
            m.reconcile(self.plan, r)

    def add_performance(self):
        import wave
        media = self.root / 'synthetic-silence.wav'
        with wave.open(str(media), 'wb') as f:
            f.setparams((1, 2, 8000, 0, 'NONE', 'not compressed'))
            f.writeframes(b'\0\0' * 8000 * 12)
        vp = Path(self.plan['verification']['path']); v = json.loads(vp.read_text())
        v.update(audio_path=str(media), audio_sha256=m.sha(media.read_bytes()))
        vp.write_text(json.dumps(v)); self.plan['verification']['sha256'] = m.sha(vp.read_bytes())
        self.plan['segments'][0]['performance'] = {
            'source_seconds': [7.5, 10], 'why': 'synthetic selected reaction tail',
            'evidence': {'path': str(self.audio), 'sha256': m.sha(self.audio.read_bytes())}}

    def test_performance_survives_cut_request_and_reconciliation(self):
        self.add_performance()
        c = m.compile_assembly(self.plan)
        self.assertEqual(c['cut_request']['segments'][0]['out'], 10)
        r = m.reconcile(self.plan, self.resolved([[5,10], [0,3.5]]))
        self.assertEqual(r['performance'][0]['source_seconds'], [7.5,10])

    def test_missing_performance_blocks_even_with_identical_words(self):
        self.add_performance()
        with self.assertRaisesRegex(ValueError, 'performance lost'):
            m.reconcile(self.plan, self.resolved())

    def test_performance_edit_invalidates_resolution(self):
        self.add_performance(); r = self.resolved([[5,10], [0,3.5]])
        self.plan['segments'][0]['performance']['source_seconds'][1] = 9
        with self.assertRaisesRegex(ValueError, 'stale resolved plan'):
            m.reconcile(self.plan, r)

    def test_performance_cannot_restore_unwanted_word(self):
        self.add_performance()
        self.plan['segments'][0]['performance']['source_seconds'] = [4,5]
        with self.assertRaisesRegex(ValueError, 'adds unwanted words'):
            m.compile_assembly(self.plan)

    def test_performance_partial_unwanted_word_blocks_at_compile(self):
        self.add_performance()
        self.plan['segments'][0]['performance']['source_seconds'] = [4.4,5]
        with self.assertRaisesRegex(ValueError, 'partial speech'):
            m.compile_assembly(self.plan)

    def test_performance_outside_media_blocks(self):
        self.add_performance()
        self.plan['segments'][0]['performance']['source_seconds'][1] = 13
        with self.assertRaisesRegex(ValueError, 'invalid keep span'):
            m.compile_assembly(self.plan)

    def test_unselected_silence_no_automatic_extension(self):
        c = m.compile_assembly(self.plan)
        self.assertEqual(c['cut_request']['segments'][0]['out'], 7.5)
        self.assertEqual(c['performance'], [])


if __name__ == '__main__':
    unittest.main()
