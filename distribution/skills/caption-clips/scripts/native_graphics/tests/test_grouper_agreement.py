"""The two groupers must agree on the timing rules they SHARE.

There are two card groupers, by design:

  * resolve_cards.resolve            -- Alex (single-line cadence cards)
  * caption_profiles.build_profile_manifest -- Leila/Sharran (phrase cards)

They legitimately differ on grouping and layout. They must NOT differ on shared
presentation timing. They did: Alex held a card through a short pause while the
profile grouper blanked the track at every pause over its grouping threshold --
9 gaps / 46 blank frames on a real 52s clip. Nothing asserted they agreed, so the
divergence was invisible until it showed up on a timeline.

These tests feed one word stream to both and compare the behaviour that is
supposed to be common.
"""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from caption_profiles import build_profile_manifest, load_profile
from resolve_cards import resolve, style_from_profile

ALEX_STYLE = dict(frame_rate=dict(numerator=24, denominator=1), timeline_end_frame=2000,
                  voices=dict(host=dict(color='FFFFFF', italic=False)),
                  max_words_per_card=3,
                  # vendored faces so this runs with no Adobe font installed
                  fonts={'base': 'Inter-Regular', 'base_italic': 'Inter-Italic', 'strong': 'Inter-SemiBold', 'strong_italic': 'Inter-Italic', 'emphasis': 'Inter-SemiBold', 'emphasis_italic': 'Inter-Italic', 'payoff': 'Inter-SemiBold', 'payoff_italic': 'Inter-Italic'})


def two_phrases(pause, n=5, step=0.3, dur=0.25):
    words, t = [], 0.0
    for i in range(n):
        words.append(dict(word=f'alpha{i}', text=f'alpha{i}', start=t, end=t + dur,
                          source_indices=[len(words)], physical_speaker='host',
                          sentence_end=False)); t += step
    t += pause
    for i in range(n):
        words.append(dict(word=f'beta{i}', text=f'beta{i}', start=t, end=t + dur,
                          source_indices=[len(words)], physical_speaker='host',
                          sentence_end=False)); t += step
    return words


def has_gap_alex(pause):
    style = style_from_profile(load_profile('alex'), dict(ALEX_STYLE))
    segs = resolve(two_phrases(pause), [], style, None, None)['render_segments']
    return any(b['start_frame'] > a['end_frame'] for a, b in zip(segs, segs[1:]))


def has_gap_profile(pause, pid='leila'):
    segs = build_profile_manifest(two_phrases(pause), load_profile(pid),
                                  fps_num=24, fps_den=1)['render_segments']
    return any(b['start_frame'] > a['end_frame'] for a, b in zip(segs, segs[1:]))



def last_end_alex(pause, profile=None):
    p = profile or load_profile('alex')
    style = style_from_profile(p, dict(ALEX_STYLE))
    return resolve(two_phrases(pause), [], style, None, None)['render_segments'][-1]['end_frame']


def last_end_profile(pause, pid='leila', profile=None):
    p = profile or load_profile(pid)
    return build_profile_manifest(two_phrases(pause), p,
                                  fps_num=24, fps_den=1)['render_segments'][-1]['end_frame']


def gaps_alex(pause, profile, group_gap=0.3):
    # Alex's GROUPING gap is deliberately wider than the profile grouper's, so a
    # pause that splits a Leila card may sit mid-card for Alex -- and a card with no
    # boundary at the pause can never blank there. Narrow the grouping gap so both
    # groupers have a boundary at the same place; only then is the hold-vs-blank
    # decision comparable, which is the part that must agree.
    style = style_from_profile(profile, dict(ALEX_STYLE, gap_threshold_seconds=group_gap))
    segs = resolve(two_phrases(pause), [], style, None, None)['render_segments']
    return [b['start_frame'] - a['end_frame']
            for a, b in zip(segs, segs[1:]) if b['start_frame'] > a['end_frame']]


def gaps_profile(pause, profile):
    segs = build_profile_manifest(two_phrases(pause), profile,
                                  fps_num=24, fps_den=1)['render_segments']
    return [b['start_frame'] - a['end_frame']
            for a, b in zip(segs, segs[1:]) if b['start_frame'] > a['end_frame']]


class GroupersAgreeOnTheFinalCard(unittest.TestCase):
    """The LAST card was outside the gap comparison, and diverged there.

    Interior gaps were asserted; the final card's end was not. Alex held its last
    card a trailing hold past the final word while the profile grouper cut at
    exactly speech end, so the closing caption snapped off on the last syllable.
    """

    def test_both_hold_the_last_card_past_the_final_word(self):
        words = two_phrases(0.3)
        speech_end_frame = words[-1]['end'] * 24
        for name, end in (('alex', last_end_alex(0.3)),
                          ('leila', last_end_profile(0.3, 'leila')),
                          ('sharran', last_end_profile(0.3, 'sharran'))):
            with self.subTest(profile=name):
                self.assertGreater(end, speech_end_frame,
                                   f'{name} ends its last card at speech end')

    def test_the_two_groupers_hold_the_last_card_equally(self):
        self.assertEqual(last_end_alex(0.3), last_end_profile(0.3, 'leila'))
        self.assertEqual(last_end_alex(0.3), last_end_profile(0.3, 'sharran'))


class SharedThresholdsAreHonouredByBoth(unittest.TestCase):
    """Both groupers must read the SAME profile fields for the shared decision.

    They did not: this grouper read `caption_hold_through_seconds` from the profile
    while Alex's read `gap_threshold_seconds` from the job style. The two agreed
    only because those defaults happened to be equal, so every test at default
    values passed while tuning the field changed one grouper and not the other.
    """

    def test_tuning_the_threshold_moves_both_groupers(self):
        for value, pause, expect_gap in ((0.2, 0.5, True), (1.2, 0.5, False)):
            with self.subTest(hold_through=value, pause=pause):
                alex = load_profile('alex'); alex['caption_hold_through_seconds'] = value
                leila = load_profile('leila'); leila['caption_hold_through_seconds'] = value
                a, l = gaps_alex(pause, alex), gaps_profile(pause, leila)
                self.assertEqual(bool(a), expect_gap, f'alex gaps={a}')
                self.assertEqual(bool(l), expect_gap, f'leila gaps={l}')
                self.assertEqual(bool(a), bool(l),
                                 f'groupers disagree at hold_through={value}: {a} vs {l}')

    def test_the_field_is_not_silently_ignored_by_either(self):
        """A threshold below the pause must blank; above it must hold. Both sides."""
        low = load_profile('alex'); low['caption_hold_through_seconds'] = 0.2
        high = load_profile('alex'); high['caption_hold_through_seconds'] = 1.2
        self.assertTrue(gaps_alex(0.5, low), 'alex ignored a lowered threshold')
        self.assertFalse(gaps_alex(0.5, high), 'alex ignored a raised threshold')
        # And the grouping gap is a separate knob: it decides WHERE cards split,
        # never whether a split blanks the track.
        self.assertFalse(gaps_alex(0.5, high, group_gap=0.1),
                         'a narrow grouping gap must not by itself blank the track')
        lo = load_profile('leila'); lo['caption_hold_through_seconds'] = 0.2
        hi = load_profile('leila'); hi['caption_hold_through_seconds'] = 1.2
        self.assertTrue(gaps_profile(0.5, lo), 'leila ignored a lowered threshold')
        self.assertFalse(gaps_profile(0.5, hi), 'leila ignored a raised threshold')


class GroupersAgreeOnHoldThrough(unittest.TestCase):
    def test_a_short_pause_blanks_neither_grouper(self):
        for pause in (0.1, 0.3, 0.5):
            with self.subTest(pause=pause):
                self.assertFalse(has_gap_alex(pause), f'Alex blanked at {pause}s')
                self.assertFalse(has_gap_profile(pause), f'profile blanked at {pause}s')

    def test_a_long_pause_blanks_both_groupers(self):
        for pause in (1.5, 3.0):
            with self.subTest(pause=pause):
                self.assertTrue(has_gap_alex(pause), f'Alex held through {pause}s')
                self.assertTrue(has_gap_profile(pause), f'profile held through {pause}s')

    def test_the_two_groupers_agree_across_the_threshold(self):
        # the exact boundary may differ by a frame; the DECISION must not
        for pause in (0.1, 0.3, 0.5, 1.5, 3.0):
            with self.subTest(pause=pause):
                self.assertEqual(has_gap_alex(pause), has_gap_profile(pause),
                                 f'groupers disagree on whether {pause}s blanks the track')

    def test_both_profiles_using_the_shared_grouper_agree(self):
        for pause in (0.3, 2.0):
            self.assertEqual(has_gap_profile(pause, 'leila'),
                             has_gap_profile(pause, 'sharran'))

    def test_neither_grouper_ever_overlaps_cards(self):
        for pause in (0.1, 0.5, 2.0):
            for segs in (resolve(two_phrases(pause), [],
                                 {**style_from_profile(load_profile('alex'), dict(ALEX_STYLE)),
                                  '_profile': load_profile('alex')}, None, None)['render_segments'],
                         build_profile_manifest(two_phrases(pause), load_profile('leila'),
                                                fps_num=24, fps_den=1)['render_segments']):
                for a, b in zip(segs, segs[1:]):
                    self.assertLessEqual(a['end_frame'], b['start_frame'])


if __name__ == '__main__':
    unittest.main()
