import copy
import unittest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from native_graphics.caption_style_review import validate


class StyleReviewTests(unittest.TestCase):
    def manifest(self):
        return {
            'render_segments': [{'id': 'one', 'start_frame': 12, 'end_frame': 36,
                'size_tier': 'emphasis', 'font_size_px': 176,
                'words': [{'text': 'important', 'weight': 'strong', 'italic': True}]}],
            'style_review': {'mode': 'editorial', 'reviewed': True, 'segment_ids': ['one'],
                'weight': {'status': 'applied', 'reason': 'Key contrast word', 'targets': [
                    {'segment_id': 'one', 'word_index': 0, 'text': 'important', 'value': 'strong'}]},
                'italic': {'status': 'applied', 'reason': 'Reported speech', 'targets': [
                    {'segment_id': 'one', 'word_index': 0, 'text': 'important', 'value': True}]},
                'size': {'status': 'applied', 'reason': 'Short payoff card', 'targets': [
                    {'segment_id': 'one', 'tier': 'emphasis', 'font_size_px': 176}]}}}

    def test_valid_does_not_change_timing_text_or_manifest(self):
        manifest = self.manifest()
        before = copy.deepcopy(manifest)
        self.assertEqual(validate(manifest)['segments'], 1)
        self.assertEqual(manifest, before)

    def test_missing_review_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Missing editorial'):
            validate({'cards': []})

    def test_flattened_style_rejected(self):
        for axis, value in [('weight', 'base'), ('italic', False), ('font_size_px', 80)]:
            with self.subTest(axis=axis):
                manifest = self.manifest()
                card = manifest['render_segments'][0]
                (card if axis == 'font_size_px' else card['words'][0])[axis] = value
                with self.assertRaisesRegex(ValueError, 'styling lost'):
                    validate(manifest)

    def test_stale_coverage_rejected(self):
        manifest = self.manifest()
        manifest['style_review']['segment_ids'] = ['old']
        with self.assertRaisesRegex(ValueError, 'does not cover'):
            validate(manifest)

    def test_reviewed_exception_allowed(self):
        manifest = self.manifest()
        manifest['style_review']['italic'] = {
            'status': 'not_applicable', 'reason': 'Literal host speech; no quotation emphasis'}
        validate(manifest)

    def test_uniform_requires_user_request(self):
        with self.assertRaisesRegex(ValueError, 'explicit user request'):
            validate({'style_review': {'mode': 'uniform_requested'}})
        self.assertEqual(validate({'style_review': {'mode': 'uniform_requested',
            'user_request': 'Use uniform captions for this clip'}})['status'], 'EXPLICIT_UNIFORM_STYLE')

    def test_width_fit_is_not_editorial_tier(self):
        manifest = self.manifest()
        manifest['style_review']['size']['targets'][0]['tier'] = 'base'
        with self.assertRaisesRegex(ValueError, 'non-base editorial tier'):
            validate(manifest)


if __name__ == '__main__':
    unittest.main()
