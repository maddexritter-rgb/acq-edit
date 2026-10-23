"""Captions must not blank between phrases -- only at a genuinely long pause.

2026-09-22. The profile grouper set `end = min(last_word_end, next_card_start)`,
which only ever clamped DOWN, so every pause at or above the 0.32s grouping
threshold left a hole on the caption track. On a real 52s clip that was 9 gaps /
46 blank frames. Cards split for a non-pause reason (word cap, sentence end,
width) closed up by accident, which is why this went unnoticed.

Alex's rule is the approved one and is now shared: hold until the next card
unless the pause exceeds `caption_hold_through_seconds`, then release
`caption_trailing_hold_seconds` after speech ends.
"""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from caption_profiles import build_profile_manifest, load_profile


def two_phrases(pause, n=5, step=0.3, dur=0.25):
    words, t = [], 0.0
    for i in range(n):
        words.append(dict(word=f'alpha{i}', start=t, end=t + dur)); t += step
    t += pause
    for i in range(n):
        words.append(dict(word=f'beta{i}', start=t, end=t + dur)); t += step
    return words


def gaps(manifest):
    segs = manifest['render_segments']
    return [b['start_frame'] - a['end_frame']
            for a, b in zip(segs, segs[1:]) if b['start_frame'] > a['end_frame']]


class HoldThroughTests(unittest.TestCase):
    def build(self, pause, profile='leila', **kw):
        return build_profile_manifest(two_phrases(pause), load_profile(profile),
                                      fps_num=24, fps_den=1, **kw)

    def test_a_short_pause_does_not_blank_the_track(self):
        for pause in (0.1, 0.35, 0.5):
            with self.subTest(pause=pause):
                self.assertEqual(gaps(self.build(pause)), [],
                                 f'a {pause}s breath blanked the captions')

    def test_a_long_pause_still_releases_the_card(self):
        self.assertTrue(gaps(self.build(2.0)), 'a 2s pause should blank the track')

    def test_the_blank_grows_with_the_pause(self):
        self.assertLess(sum(gaps(self.build(1.0))), sum(gaps(self.build(3.0))))

    def test_the_threshold_is_profile_declared_not_hardcoded(self):
        # a profile that tolerates no pause blanks even a short one
        loose = self.build(0.5)
        tight = build_profile_manifest(two_phrases(0.5), load_profile('leila'),
                                       fps_num=24, fps_den=1, hold_through=0.0)
        self.assertEqual(gaps(loose), [])
        self.assertTrue(gaps(tight))

    def test_both_profiles_share_the_rule(self):
        for pid in ('leila', 'sharran'):
            with self.subTest(profile=pid):
                self.assertEqual(gaps(self.build(0.4, profile=pid)), [])

    def test_cards_never_overlap_after_holding_through(self):
        segs = self.build(0.4)['render_segments']
        for a, b in zip(segs, segs[1:]):
            self.assertLessEqual(a['end_frame'], b['start_frame'],
                                 'holding through must not overlap the next card')

    def test_the_last_card_is_not_extended_past_its_speech(self):
        segs = self.build(0.4)['render_segments']
        last = segs[-1]
        self.assertGreater(last['end_frame'], last['start_frame'])


if __name__ == '__main__':
    unittest.main()
