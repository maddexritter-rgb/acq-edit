"""Geometry and evidence regression tests; no editorial or native-host claims."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import json

import render_hook as hook


class HookTests(unittest.TestCase):
    def setUp(self):
        self.m = {'selected_text': 'A supported headline', 'display_lines': ['A supported', 'headline'],
                  'existing_hook': 'none', 'delivery_platform': 'custom',
                  'safe_rect': [96, 96, 888, 1584], 'caption_bottom_px': 1100,
                  'font_path': str(Path.home()/'Library/Fonts/Poppins-Bold.ttf'),
                  'protected_rects': [[200, 150, 600, 700]]}

    def test_readable_fit_below_captions(self):
        _, result = hook.layout(self.m, 1080, 1920)
        x, y, w, h = result['bounds']
        self.assertGreaterEqual(y, 1124)
        self.assertLessEqual(y+h, 1680)
        self.assertEqual(x, (1080-w)//2)
        self.assertGreaterEqual(result['font_size_px'], 84)

    def test_geometry_refusals(self):
        cases = [dict(caption_bottom_px=1650), dict(existing_hook='burned'),
                 dict(display_lines=['Changed words']),
                 dict(selected_text='A supported headline.', display_lines=['A supported', 'headline.']),
                 dict(selected_text='x'*300, display_lines=['x'*300]),
                 dict(protected_rects=[[0, 1100, 1080, 700]])]
        for change in cases:
            with self.subTest(change=change), self.assertRaises(ValueError):
                hook.layout(dict(self.m, **change), 1080, 1920)

    def test_reels_zone_is_symmetric_and_cannot_be_relaxed(self):
        m = dict(self.m, delivery_platform='instagram_reels', safe_rect=[0, 0, 1080, 1920])
        self.assertEqual(hook.effective_safe_rect(m, 1080, 1920), [65, 269, 950, 979])
        self.assertEqual(hook.effective_safe_rect(dict(m, safe_rect=[0, 0, 720, 1280]),
                                                  720, 1280), [44, 180, 632, 652])
        with self.assertRaisesRegex(ValueError, 'Placement conflict'):
            hook.layout(m, 1080, 1920)

    def test_reels_above_caption_fallback_stays_centered(self):
        m = dict(self.m, delivery_platform='instagram_reels', safe_rect=[0, 0, 720, 1280],
                 selected_text='Sell more', display_lines=['Sell more'],
                 protected_rects=[[0, 0, 720, 448]])
        caption = [100, 750, 520, 100]
        _, result = hook.layout(m, 720, 1280, caption_bounds=caption)
        x, y, w, h = result['bounds']
        self.assertEqual(result['anchor_side'], 'above')
        self.assertEqual(x, (720-w)//2)
        self.assertGreaterEqual(x, 44)
        self.assertLessEqual(x+w, 676)
        self.assertGreaterEqual(y, 180)
        self.assertLessEqual(y+h, 832)
        self.assertLessEqual(y+h+result['gap_px'], caption[1])

    def test_reels_refuses_crowded_caption_and_face(self):
        m = dict(self.m, delivery_platform='instagram_reels', safe_rect=[0, 0, 720, 1280],
                 selected_text='Sell more', display_lines=['Sell more'],
                 protected_rects=[[0, 0, 720, 448]])
        with self.assertRaisesRegex(ValueError, 'Placement conflict'):
            hook.layout(m, 720, 1280, caption_bounds=[100, 500, 520, 310])

    def test_caption_replacement_needs_measured_safe_position(self):
        m = dict(self.m, delivery_platform='instagram_reels',
                 safe_rect=[65, 269, 950, 979], caption_strategy='replace',
                 replacement_hook_top_px=1000, protected_rects=[[120, 80, 840, 850]])
        _, result = hook.layout(m, 1080, 1920, caption_bounds=[120, 1230, 840, 220])
        self.assertEqual(result['anchor_side'], 'replace')
        self.assertEqual(result['bounds'][1], 1000)
        self.assertEqual(result['bounds'][0], (1080-result['bounds'][2])//2)
        with self.assertRaisesRegex(ValueError, 'Placement conflict'):
            hook.layout(dict(m, replacement_hook_top_px=1150), 1080, 1920,
                        caption_bounds=[120, 1230, 840, 220])

    def test_reels_reduces_each_fitted_size_about_fifteen_percent(self):
        m = dict(self.m, delivery_platform='instagram_reels', style={'id':'approved'})
        self.assertEqual(hook.fitted_font_size(m, 720, 1280, 68), (58, .85))
        self.assertEqual(hook.fitted_font_size(m, 720, 1280, 43), (37, .85))
        with self.assertRaisesRegex(ValueError, 'multiplier'):
            hook.fitted_font_size(dict(m, font_size_multiplier=.2), 720, 1280, 68)

    def test_stale_source_and_transcript(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, transcript = root/'clip', root/'transcript.txt'
            source.write_bytes(b'fixture'); transcript.write_text('The trial may help some people.')
            m = {**self.m, 'schema': 'text-hook/v1', 'clip_id': 'C01', 'transcript_revision': 'v1',
                 'source': str(source), 'transcript': str(transcript),
                 'source_sha256': hook.digest(source), 'transcript_sha256': hook.digest(transcript),
                 'supporting_passages': [{'quote': 'The trial may help some people.'}],
                 'geometry_evidence': 'fixture geometry'}
            for field in ['source_sha256', 'transcript_sha256']:
                changed = dict(m, **{field: 'stale'})
                manifest = root/'manifest.json'; manifest.write_text(json.dumps(changed))
                with self.assertRaisesRegex(ValueError, 'Stale'):
                    hook.build(manifest, root/'out')
                self.assertFalse((root/'out').exists())
            m['supporting_passages'] = [{'quote': 'The trial will help everyone.'}]
            manifest.write_text(json.dumps(m))
            with self.assertRaisesRegex(ValueError, 'Support quote absent'):
                hook.build(manifest, root/'out')


if __name__ == '__main__':
    unittest.main()
