"""The profile is the source of truth, and an unhonoured declaration is an ERROR.

2026-09-22. Three Alex bugs shipped on one clip -- captions shoved off-frame,
scrambled word order, and two-line wrapping -- and all three had the same cause:
`profiles/alex.json` declared a contract that the grouper never read. It took a
parallel hand-written style file instead, so `max_lines: 1` and
`normalization: oliver_v2` were declared and silently ignored.

Fixing the three symptoms does not fix that. These tests pin the structural rule:
anything a profile declares is either honoured here, honoured by the other
grouper, purely descriptive, or a hard failure. Adding a profile field without
teaching a grouper what it means now breaks the build instead of being ignored.
"""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from resolve_cards import (resolve, style_from_profile, check_profile_contract,
                           PROFILE_DESCRIPTIVE, PROFILE_HONOURED, PROFILE_OTHER_GROUPER)
from caption_profiles import load_profile

# Faces that SHIP with the skill. These tests exercise the CONTRACT, not the
# Alex brand faces, so using vendored ones keeps them runnable on a fresh
# machine and in CI where no Adobe font is installed.
FACES = {'base': 'Inter-Regular', 'base_italic': 'Inter-Italic', 'strong': 'Inter-SemiBold', 'strong_italic': 'Inter-Italic', 'emphasis': 'Inter-SemiBold', 'emphasis_italic': 'Inter-Italic', 'payoff': 'Inter-SemiBold', 'payoff_italic': 'Inter-Italic'}
BASE = dict(frame_rate=dict(numerator=24, denominator=1), timeline_end_frame=400,
            voices=dict(host=dict(color='FFFFFF', italic=False)), fonts=FACES,
            max_words_per_card=3, font_size_px=160, max_text_width_px=1650)


def words(with_flag=True, weight=None):
    out = []
    for i in range(4):
        w = dict(text='communicating', start=i * 0.3, end=i * 0.3 + 0.2,
                 source_indices=[i], physical_speaker='host')
        if with_flag:
            w['sentence_end'] = False
        if weight:
            w['weight'] = weight
        out.append(w)
    return out


def run(profile, style, w):
    st = style_from_profile(profile, style)
    st['_profile'] = profile
    return resolve(w, [], st, None, None)


class EveryDeclaredFieldIsAccountedFor(unittest.TestCase):
    def test_every_shipped_profile_is_fully_classified(self):
        known = PROFILE_DESCRIPTIVE | PROFILE_HONOURED | PROFILE_OTHER_GROUPER
        for pid in ('alex', 'leila', 'sharran'):
            unknown = set(load_profile(pid)) - known
            self.assertEqual(unknown, set(),
                             f'{pid}.json declares {sorted(unknown)} that no grouper claims')

    def test_an_unimplemented_field_is_refused_not_ignored(self):
        p = dict(load_profile('alex'), mystery_knob=True)
        with self.assertRaisesRegex(ValueError, 'does not implement'):
            run(p, dict(BASE), words())

    def test_the_three_classifications_do_not_overlap(self):
        self.assertFalse(PROFILE_DESCRIPTIVE & PROFILE_HONOURED)
        self.assertFalse(PROFILE_HONOURED & PROFILE_OTHER_GROUPER)
        self.assertFalse(PROFILE_DESCRIPTIVE & PROFILE_OTHER_GROUPER)


class DeclaredConstraintsAreEnforced(unittest.TestCase):
    def test_oliver_v2_requires_word_level_normalization(self):
        # the string-level formatter drops sentence_end, so boundaries are lost
        with self.assertRaisesRegex(ValueError, 'sentence_end'):
            run(load_profile('alex'), dict(BASE), words(with_flag=False))

    def test_word_level_normalization_passes(self):
        m = run(load_profile('alex'), dict(BASE), words())
        self.assertTrue(m['cards'])

    def test_max_lines_one_requires_a_width_budget(self):
        # alex.json now DECLARES the budget, so strip it from both sources: the
        # guard must fire when neither the profile nor the caller supplies one.
        p = {k: v for k, v in load_profile('alex').items()
             if k not in ('max_text_width_pct', 'frame_width_px')}
        style = dict(BASE); style.pop('max_text_width_px')
        with self.assertRaisesRegex(ValueError, 'max_lines 1'):
            run(p, style, words())

    def test_the_profile_alone_satisfies_the_budget_requirement(self):
        # no per-job style file needed: the contract is self-describing
        style = dict(BASE); style.pop('max_text_width_px')
        m = run(load_profile('alex'), style, words())
        self.assertTrue(m['cards'])

    def test_allow_weight_variation_false_refuses_emphasis(self):
        p = dict(load_profile('alex'), allow_weight_variation=False)
        with self.assertRaisesRegex(ValueError, 'allow_weight_variation'):
            run(p, dict(BASE), words(weight='payoff'))


class ProfileDrivesTheConfig(unittest.TestCase):
    def test_y_pct_comes_from_the_profile_not_a_parallel_file(self):
        self.assertEqual(style_from_profile(load_profile('alex'), {})['y_pct'], 50.0)
        self.assertEqual(style_from_profile(load_profile('leila'), {})['y_pct'], 69.0)

    def test_a_width_budget_is_derived_from_the_profile_when_declared(self):
        # leila declares max_text_width_pct 80 of frame_width_px 1080
        self.assertAlmostEqual(
            style_from_profile(load_profile('leila'), {})['max_text_width_px'], 864.0)

    def test_the_profile_supplies_its_declared_faces(self):
        fonts = style_from_profile(load_profile('alex'), {})['fonts']
        self.assertEqual(fonts['base'], 'ProximaNova-Medium')
        self.assertEqual(fonts['base_italic'], 'ProximaNova-MediumIt')

    def test_an_explicit_override_still_wins(self):
        style = style_from_profile(load_profile('alex'), dict(y_pct=41.0))
        self.assertEqual(style['y_pct'], 41.0)


if __name__ == '__main__':
    unittest.main()
