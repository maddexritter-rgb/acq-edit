import hashlib
import importlib.util
import json
import tempfile
import unittest
import wave
from pathlib import Path

import numpy as np

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'


def module(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f'{name}.py')
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


we = module('word_evidence')
seams = module('gemini_seams')
jc = module('join_check')
RATE = 48000
# word, start, end; tone is continuous across 0.0-0.6 (fused) and silent elsewhere.
WORDS = [('so', 0.0, 0.3), ('um', 0.3, 0.6), ('the', 1.0, 1.3), ('answer', 1.3, 1.7), ('works.', 2.4, 2.9)]


def write_audio(path):
    x = np.zeros(int(3.5 * RATE), np.float32)
    t = np.arange(len(x)) / RATE
    for a, b in ((0.0, 0.6), (1.0, 1.7), (2.4, 2.9)):
        m = (t >= a) & (t < b)
        x[m] = 0.3 * np.sin(2 * np.pi * 220 * t[m])
    x += np.random.default_rng(0).normal(0, 0.0005, len(x)).astype(np.float32)
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype('<i2').tobytes())


class WordEvidenceTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.audio = self.root / 'd.wav'
        write_audio(self.audio)
        self.words = self.root / 'words.json'
        self.words.write_text(json.dumps({'words': [
            {'word': w, 'start': a, 'end': b, 'speaker': 'B', 'confidence': 0.9} for w, a, b in WORDS]}))

    def delivery_map(self, status='OK', tags=()):
        path = self.root / f'map-{status}.json'
        path.write_text(json.dumps({
            'source': {'words_sha256': hashlib.sha256(self.words.read_bytes()).hexdigest()},
            'coverage': {'status': 'COMPLETE' if status == 'OK' else 'UNAVAILABLE'},
            'chunks': [{'word_range': [0, 4], 'status': status}], 'tags': list(tags)}))
        return path

    def test_waveform_separates_clean_and_fused_joins(self):
        t = we.build(self.words, self.audio, self.root / 'c')
        states = [(r['word'], (r['after'] or {}).get('state')) for r in t['words']]
        self.assertEqual(states, [('so', 'fused'), ('um', 'clean'), ('the', 'fused'), ('answer', 'clean'),
                                  ('works.', None)])

    def test_gemini_tags_land_on_words_and_disagreements_are_flagged(self):
        tag = {'word_first': 1, 'word_last': 1, 'type': 'phantom_word', 'confidence': 'high', 'note': 'not audible'}
        t = we.build(self.words, self.audio, self.root / 'c', self.delivery_map('OK', [tag]))
        um = t['words'][1]
        self.assertEqual(um['gemini'][0]['type'], 'phantom_word')
        self.assertIn('gemini_says_not_audible', um['flags'])
        text = we.view(t, 0, 4)
        self.assertIn('1:um* ‖', text)
        self.assertIn("phantom_word(high): not audible", text)

    def test_unavailable_gemini_adds_no_guesses(self):
        t = we.build(self.words, self.audio, self.root / 'c', self.delivery_map('UNAVAILABLE'))
        self.assertEqual(t['words'][1]['flags'], [])
        self.assertIn('Gemini: UNAVAILABLE', we.view(t, 0, 4))

    def test_map_from_another_transcript_is_rejected(self):
        path = self.delivery_map()
        doc = json.loads(path.read_text())
        doc['source']['words_sha256'] = '0' * 64
        path.write_text(json.dumps(doc))
        with self.assertRaisesRegex(ValueError, 'different transcript'):
            we.build(self.words, self.audio, self.root / 'c', path)

    def paired(self, spans, kept):
        path = self.root / 'paired.json'
        path.write_text(json.dumps({'sample_rate': RATE, 'source_samples': [[int(a * RATE), int(b * RATE)] for a, b in spans]}))
        sel = self.root / 'sel.json'
        sel.write_text(json.dumps({'clips': [{'id': 'c1', 'kept_word_ranges': kept}]}))
        return path, sel

    def test_seams_checks_only_risky_joins_in_one_call(self):
        table = self.root / 'ev.json'
        table.write_text(json.dumps(we.build(self.words, self.audio, self.root / 'c')))
        calls = []

        def caller(audio, prompt, **kw):
            calls.append(prompt)
            return {'status': 'OK', 'usd': 0.02, 'result': {'joins': [
                {'join': 1, 'heard': 'leaked_sound', 'confidence': 'high', 'note': 'start of um'}]}}
        # Join 1 cuts inside the fused so|um; join 2 cuts in clean silence after "answer".
        paired, sel = self.paired([(0.0, 0.3), (1.0, 1.7), (2.4, 2.9)], [[0, 0], [2, 3], [4, 4]])
        r = seams.run(paired, sel, 'c1', self.audio, table, self.root / 'c',
                      self.root / 'seams.json', caller=caller, encoder=lambda x, rate: b'mp3')
        self.assertEqual(len(calls), 1)
        self.assertEqual([c['join'] for c in r['checked']], [1])
        self.assertEqual(r['heard'][0]['heard'], 'leaked_sound')

    def test_seams_treat_clean_as_not_flagged_never_proof(self):
        table = self.root / 'ev.json'
        table.write_text(json.dumps(we.build(self.words, self.audio, self.root / 'c')))
        paired, sel = self.paired([(0.0, 0.3), (1.0, 1.7), (2.4, 2.9)], [[0, 0], [2, 3], [4, 4]])
        r = seams.run(paired, sel, 'c1', self.audio, table, self.root / 'c', self.root / 'seams2.json',
                      caller=lambda *a, **k: {'status': 'OK', 'model': 'm', 'result': {'joins': [
                          {'join': 1, 'heard': 'clean', 'confidence': 'high'}]}}, encoder=lambda x, rate: b'mp3')
        self.assertEqual((r['heard'], r['not_flagged']), ([], [1]))

    def join_check(self, spans, kept, accept=()):
        paired, sel = self.paired(spans, kept)
        # MFA stand-in: word bounds equal the synthetic tone bursts.
        bounds = {i: (a, b) for i, (_, a, b) in enumerate(WORDS)}
        return jc.check(paired, sel, 'c1', self.words, self.audio, self.root / 'c', accept,
                        aligner=lambda idx: {i: bounds[i] for i in idx if i in bounds})

    def test_join_check_passes_cuts_in_silence(self):
        r = self.join_check([(0.95, 1.75), (2.35, 2.95)], [[2, 3], [4, 4]])
        self.assertEqual(r['status'], 'JOINS_MEASURED_CLEAR')

    def test_join_check_blocks_clipped_ending_and_onset(self):
        r = self.join_check([(0.95, 1.60), (2.48, 2.95)], [[2, 3], [4, 4]])
        blocked = {e['edge']: e['blocking'] for e in r['edges'] if e['blocking']}
        self.assertIn('tail1', blocked)
        self.assertIn('CUT_INSIDE_WORD', blocked['tail1'][0])
        self.assertIn('head2', blocked)
        self.assertEqual(r['status'], 'CUT_REPAIR_REQUIRED')

    def test_join_check_blocks_audible_leak_of_removed_word(self):
        # Head of "the" starts inside the removed, still-sounding "um".
        r = self.join_check([(0.45, 1.75)], [[2, 3]])
        self.assertIn('LEAKS_EXCLUDED_WORD', r['edges'][0]['blocking'][0])

    def test_join_check_silent_slice_is_a_note_and_accept_overrides(self):
        quiet = self.join_check([(0.95, 1.75), (2.35, 2.95)], [[2, 3], [4, 4]])
        self.assertFalse(quiet['blocking_edges'])
        r = self.join_check([(0.95, 1.60), (2.35, 2.95)], [[2, 3], [4, 4]], accept=['tail1:editor kept for pacing'])
        self.assertEqual(r['status'], 'JOINS_MEASURED_CLEAR')
        self.assertEqual(r['edges'][1]['accepted_by_editor'], 'editor kept for pacing')

    def test_kept_word_disputes_are_reported_never_applied(self):
        table = we.build(self.words, self.audio, self.root / 'c')
        r = we.check_kept(table, [[2, 4]], self.audio, self.root / 'c',
                          transcriber=lambda *a: 'so um the answer jerks',
                          caller=lambda *a, **k: {'status': 'OK', 'model': 'm', 'usd': 0.0,
                                                  'result': {'snippets': [{'n': 1, 'choice': 'B'}]}},
                          encoder=lambda pcm: b'mp3')
        self.assertEqual([(d['assemblyai'], d['whisper'], d['status']) for d in r['disputes']],
                         [('works.', 'jerks', 'VERIFY_2_OF_3_SAY_WHISPER')])
        self.assertEqual(json.loads(self.words.read_text())['words'][4]['word'], 'works.')

    def test_join_check_ignores_mfa_on_the_wrong_occurrence(self):
        # MFA put "the" on an earlier repeat 0.6 s away; the check must fall back, not block on it.
        paired, sel = self.paired([(0.95, 1.75), (2.35, 2.95)], [[2, 3], [4, 4]])
        bounds = {i: (a, b) for i, (_, a, b) in enumerate(WORDS)}
        bounds[2] = (0.4, 0.6)
        r = jc.check(paired, sel, 'c1', self.words, self.audio, self.root / 'c',
                     aligner=lambda idx: {i: bounds[i] for i in idx if i in bounds})
        head = r['edges'][0]
        self.assertEqual(head['evidence'], 'asr_only_mfa_disagreed')
        # Disagreement blocks until resolved by ear/waveform - neither locator silently wins.
        self.assertIn('LOCATORS_DISAGREE', head['blocking'][0])
        r = jc.check(paired, sel, 'c1', self.words, self.audio, self.root / 'c',
                     accept=['head1:waveform shows the onset at 1.0 s'],
                     aligner=lambda idx: {i: bounds[i] for i in idx if i in bounds})
        self.assertEqual(r['status'], 'JOINS_MEASURED_CLEAR')

    def stretched_join_check(self, mfa_the):
        # AssemblyAI stretched "the" back over the 0.6-1.0 s pause; MFA places it as given.
        words = json.loads(self.words.read_text())
        words['words'][2]['start'] = 0.65
        self.words.write_text(json.dumps(words))
        paired, sel = self.paired([(0.95, 1.75), (2.35, 2.95)], [[2, 3], [4, 4]])
        bounds = {i: (a, b) for i, (_, a, b) in enumerate(WORDS)}
        bounds[2] = mfa_the
        return jc.check(paired, sel, 'c1', self.words, self.audio, self.root / 'c',
                        aligner=lambda idx: {i: bounds[i] for i in idx if i in bounds})

    def test_join_check_trusts_mfa_inside_a_stretched_asr_label(self):
        # MFA sits inside the stretched label: same occurrence, so MFA bounds judge the cut.
        r = self.stretched_join_check((1.0, 1.3))
        head = r['edges'][0]
        self.assertEqual(head['evidence'], 'mfa')
        self.assertEqual(head['word_bounds_s'], [1.0, 1.3])
        self.assertFalse(head['blocking'])
        self.assertEqual(r['status'], 'JOINS_MEASURED_CLEAR')

    def test_join_check_still_blocks_far_mfa_outside_a_stretched_label(self):
        # MFA on a sound outside the stretched label is another occurrence: still blocks.
        r = self.stretched_join_check((2.4, 2.7))
        head = r['edges'][0]
        self.assertEqual(head['evidence'], 'asr_only_mfa_disagreed')
        self.assertIn('LOCATORS_DISAGREE', head['blocking'][0])
        self.assertEqual(r['status'], 'CUT_REPAIR_REQUIRED')

    def test_join_check_spells_numbers_for_alignment(self):
        self.assertEqual(jc.norm('$200,000-ish,'), 'two hundred thousand ish')
        self.assertEqual(jc.norm('80%'), 'eighty percent')
        self.assertEqual(jc.norm('$1.5M'), 'one point five million')
        self.assertEqual(jc.norm('$10K'), 'ten thousand')

    def test_seams_without_risky_joins_never_calls_gemini(self):
        table = self.root / 'ev.json'
        table.write_text(json.dumps(we.build(self.words, self.audio, self.root / 'c')))
        paired, sel = self.paired([(1.0, 1.7), (2.4, 2.9)], [[2, 3], [4, 4]])
        r = seams.run(paired, sel, 'c1', self.audio, table, self.root / 'c', self.root / 's.json',
                      caller=lambda *a, **k: self.fail('should not call Gemini'))
        self.assertEqual(r['status'], 'NO_RISKY_JOINS')


if __name__ == '__main__':
    unittest.main()
