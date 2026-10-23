import importlib.util
import json
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'resolve_review_edges.py'
spec = importlib.util.spec_from_file_location('resolve_review_edges', SCRIPT)
resolver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(resolver)


class ReviewEdgeResolutionTest(unittest.TestCase):
    def setUp(self):
        self.clip = {'id': 'clip', 'media': 'source.mp4', 'spans': [
            {'word_range': [1, 2], 'asr_start': .5, 'asr_end': 1.4},
            {'word_range': [4, 5], 'asr_start': 2.0, 'asr_end': 2.9}]}
        self.words = [{'word': f'w{i}', 'start': i * .5,
                       'end': i * .5 + .4} for i in range(7)]

    def test_refused_edge_keeps_entire_selected_span_as_provisional(self):
        report = [
            {'source_words': [1, 2], 'result': [.46, 1.46]},
            {'source_words': [4, 5], 'result': 'REFUSED',
             'start': {'verdict': 'FUSED', 'why': 'runs into selected word'},
             'end': {'verdict': 'OK'}}]
        with patch.object(resolver, 'provisional_edge', side_effect=[(48, {'frame': 48}), (71, {'frame': 71})]):
            frames, issues = resolver.review_frames(self.clip, report, Fraction(24), self.words)
        self.assertEqual(len(frames), 2)
        self.assertEqual(frames[1], [48, 71])
        self.assertEqual(issues[0]['word_range'], [4, 5])
        self.assertEqual(issues[0]['code'], 'FUSED')

    def test_measured_edges_are_used_unchanged_in_purpose(self):
        report = [
            {'source_words': [1, 2], 'result': [.46, 1.46]},
            {'source_words': [4, 5], 'result': [1.95, 2.95]}]
        frames, issues = resolver.review_frames(self.clip, report, Fraction(24), self.words)
        self.assertEqual(frames, [[11, 35], [47, 71]])
        self.assertEqual(issues, [])

    def test_successful_opposite_edge_survives_refused_span(self):
        report = [
            {'source_words': [1, 2], 'result': [.46, 1.46]},
            {'source_words': [4, 5], 'result': 'REFUSED',
             'start': {'verdict': 'FUSED'},
             'end': {'verdict': 'OK', 'cut_time': 2.95}}]
        with patch.object(resolver, 'provisional_edge', return_value=(48, {'frame': 48})) as fallback:
            frames, issues = resolver.review_frames(self.clip, report, Fraction(24), self.words)
        self.assertEqual(frames[1], [48, 71])
        self.assertEqual(fallback.call_count, 1)
        self.assertEqual(len(issues), 1)

    def test_word_identity_change_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'word IDs changed'):
            resolver.review_frames(self.clip, [
                {'source_words': [0, 2], 'result': [.46, 1.46]},
                {'source_words': [4, 5], 'result': [1.95, 2.95]}],
                Fraction(24), self.words)

    def test_review_receipt_retains_every_compiled_span(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            words_path = root / 'words.json'
            words_path.write_text(json.dumps({'words': self.words}))
            clip = {**self.clip, 'media': str(root / 'source.mp4'),
                    'source_words': str(words_path)}
            compiled = {'schema': 'edit.compiled-assembly/v1', 'clips': [clip]}
            compiled_path = root / 'compiled.json'
            compiled_path.write_text(json.dumps(compiled))
            report = [{'source_words': [1, 2], 'result': [.46, 1.46]},
                      {'source_words': [4, 5], 'result': 'REFUSED',
                       'start': {'verdict': 'FUSED'}, 'end': {'verdict': 'OK', 'cut_time': 2.95}}]
            with patch.object(resolver, 'validate_compiled', return_value=compiled), \
                 patch.object(resolver, 'source_fps', return_value=Fraction(24)), \
                 patch.object(resolver, 'provisional_edge', return_value=(48, {'frame': 48})):
                result = resolver.resolve(compiled_path, {'clip': report})
            row = result['clips'][0]
            self.assertEqual(len(row['source_frames']), 2)
            self.assertEqual(row['status'], 'PROVISIONAL_SEAM')
            self.assertIn('span 2 start FUSED', row['note'])


if __name__ == '__main__':
    unittest.main()
