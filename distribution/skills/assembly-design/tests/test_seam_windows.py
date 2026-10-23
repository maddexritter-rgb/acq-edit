from fractions import Fraction
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np

SCRIPTS = Path(__file__).parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f'{name}.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


seams, pairs, coverage, join_check = (load(n) for n in
                                      ('seam_windows', 'pair_audio_seams', 'validate_paired_word_coverage', 'join_check'))

R = 48000


def w(word, start, end):
    return {'word': word, 'start': start, 'end': end}


class SameOccurrenceTests(unittest.TestCase):
    def test_near_stretched_and_zero_length_labels_match(self):
        self.assertTrue(join_check.same_occurrence((1.0, 1.3), (1.05, 1.28)))
        self.assertTrue(join_check.same_occurrence((0.2, 1.4), (1.1, 1.3)))    # stretched over a pause
        self.assertTrue(join_check.same_occurrence((1.2, 1.2), (1.1, 1.3)))    # zero-length inside the word

    def test_other_occurrence_does_not_match(self):
        self.assertFalse(join_check.same_occurrence((3.0, 3.2), (1.1, 1.3)))
        self.assertFalse(join_check.same_occurrence((1.6, 1.6), (1.1, 1.3)))


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.words = [w('a', .1, .4), w('b', .4, .8), w('uh', 1.0, 1.2), w('c', 1.4, 1.8), w('d', 1.8, 2.2),
                      w('e', 2.203, 2.5), w('f', 2.7, 3.0), w('g', 3.0, 3.3)]
        self.kept = [[0, 1], [3, 4], [6, 7]]
        env = np.full(800, 60.0)
        for lo, hi in ((0.0, .1), (.8, 1.0), (1.2, 1.4), (2.5, 2.7), (3.3, 4.0)):
            env[int(lo * 200):int(hi * 200)] = 20.0
        env[180] = env[266] = env[530] = 10.0   # 0.90 s, 1.33 s, 2.65 s
        self.env = env

    def plan(self, **kw):
        return seams.plan(self.words, self.kept, {}, self.env, R, Fraction(30), 'fixture', **kw)

    def test_gap_join_prefers_quietest_point_inside_gap(self):
        d, log = self.plan()
        j = d['joins'][0]
        self.assertEqual(j['out_window'], [round(.8 * R), round(.95 * R)])     # 150 ms reach
        self.assertEqual(j['in_window'], [round(1.28 * R), round(1.4 * R)])    # 120 ms reach
        self.assertEqual(j['preferred_out'], round(.9025 * R))
        self.assertEqual(j['preferred_in'], round(1.3325 * R))
        self.assertEqual(len(log), 2)

    def test_fused_join_gets_four_ms_window(self):
        j = self.plan()[0]['joins'][1]
        self.assertEqual(j['out_window'], [round(2.2 * R), round(2.204 * R)])
        self.assertEqual(j['preferred_out'], round(2.203 * R))
        self.assertEqual(j['preferred_in'], round(2.6525 * R))

    def test_decisions_compile_into_continuous_audio(self):
        r = pairs.compile_pairs(self.plan()[0])
        for a, b in zip(r['timeline_samples'], r['timeline_samples'][1:]):
            self.assertEqual(a[1], b[0])

    def test_inspected_windows_override_measurement(self):
        d, _ = self.plan(inspected_in={3: (1.30, 1.35, 1.39)}, inspected_out={1: (.81, .85, .9)})
        j = d['joins'][0]
        self.assertEqual([j['out_window'], j['preferred_out']], [[round(.81 * R), round(.9 * R)], round(.85 * R)])
        self.assertEqual([j['in_window'], j['preferred_in']], [[round(1.3 * R), round(1.39 * R)], round(1.35 * R)])

    def test_word_at_source_start_never_goes_negative(self):
        self.words[0] = w('a', 0.0, .4)
        d, _ = self.plan()
        self.assertGreaterEqual(d['first_source_sample'], 0)

    def test_mfa_on_other_occurrence_falls_back_to_asr(self):
        trusted = seams.trusted_bounds(self.words, {1: (.45, .78), 3: (3.1, 3.3)})
        self.assertEqual(trusted, {1: (.45, .78)})

    def test_load_inspected_accepts_legacy_and_rejects_bad_window(self):
        ins, outs = seams.load_inspected('{"in": {"3": [1.4, 1.3, 1.35, 1.39]}, "out": {"1": [0.81, 0.85, 0.9]}}')
        self.assertEqual((ins, outs), ({3: (1.3, 1.35, 1.39)}, {1: (.81, .85, .9)}))
        with self.assertRaisesRegex(ValueError, 'preference'):
            seams.load_inspected('{"out": {"1": [0.81, 0.95, 0.9]}}')


class SqueezedLabelCoverageTests(unittest.TestCase):
    """An ASR label squeezed past the cut by a stretched neighbour is not a missing word when MFA has it."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.words = self.tmp / 'words.json'
        self.words.write_text(json.dumps({'words': [w('with', 0.2, 1.0), w('it,', 1.0, 1.0)]}))
        self.selection = self.tmp / 'selection.json'
        self.selection.write_text(json.dumps({'schema': 'edit.assembly-selection/v2', 'clips': [
            {'id': 'c1', 'source_words': str(self.words), 'kept_word_ranges': [[0, 1]]}]}))
        self.paired = {'schema': 'edit.paired-seam-result/v1', 'sample_rate': R, 'source_samples': [[0, round(.96 * R)]]}

    def phonemes(self, start, end):
        p = self.tmp / f'bounds-{start}.json'
        p.write_text(json.dumps({'words': {'1': {'word_index': 1, 'word': 'it,', 'aligned_start': start,
                                                 'aligned_end': end}}}))
        return p

    def test_without_mfa_still_refuses(self):
        r = coverage.validate(self.selection, self.paired, 'c1')
        self.assertEqual(r['status'], 'SELECTED_WORD_OUTSIDE_AUDIO')

    def test_mfa_on_same_occurrence_decides_containment(self):
        r = coverage.validate(self.selection, self.paired, 'c1', self.phonemes(.84, .93))
        self.assertEqual((r['status'], r['wholly_outside_word_count']), ('BOUNDARY_REVIEW_REQUIRED', 0))
        squeezed = next(i for i in r['issues'] if i['word_index'] == 1)
        self.assertEqual(squeezed['conflicts'][0]['superseded_by'], 'phoneme')

    def test_mfa_on_other_occurrence_still_refuses(self):
        r = coverage.validate(self.selection, self.paired, 'c1', self.phonemes(.30, .40))
        self.assertEqual(r['status'], 'SELECTED_WORD_OUTSIDE_AUDIO')

    def test_pair_audio_seams_compiles_with_mfa_bounds(self):
        decisions = self.tmp / 'decisions.json'
        decisions.write_text(json.dumps({'schema': 'edit.paired-seam-decisions/v1', 'sample_rate': R, 'fps': '30',
                                         'span_count': 1, 'first_source_frame': 0, 'last_source_frame': 29,
                                         'last_source_sample': round(.96 * R), 'outer_edge_evidence': 'fixture',
                                         'joins': []}))
        out = self.tmp / 'paired.json'
        run = subprocess.run([sys.executable, str(SCRIPTS / 'pair_audio_seams.py'), str(decisions), '--out', str(out),
                              '--selection', str(self.selection), '--clip-id', 'c1',
                              '--phonemes', str(self.phonemes(.84, .93))], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(json.loads(out.read_text())['word_coverage']['status'], 'BOUNDARY_REVIEW_REQUIRED')


if __name__ == '__main__':
    unittest.main()
