"""The donor-position regression: never overwrite an approved baked position.

2026-09-22. Every card used to be forced to x=0.5, y=y_pct. That is correct for
the style-donor profiles (their donor position is a calibration seed) but it
shifted the Alex donor -- whose text box is top-left-anchored at x=0.0903,
y=0.35, with the text centered INSIDE the box -- right by ~40% of frame width,
clipping it off the frame edge. Measured on a real build: caption ink centre went
from 49.8% (correct) to 84.7% with the text clipped at the right edge.
"""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from premiere_native_cards import position_mode

LEGACY = dict(donors=dict(host=dict(item_id='1', runs=dict(base=0)),
                          guest=dict(item_id='2', runs=dict(base=0))), y_pct=50.0)
STYLE = dict(donors_by_style=dict(regular=dict(item_id='96', runs=dict(base=0)),
                                  italic=dict(item_id='98', runs=dict(base=0))), y_pct=69.0)


class PositionModeTests(unittest.TestCase):
    def test_legacy_speaker_donor_profile_preserves_the_donor_position(self):
        # Alex's shape. Its donor position IS the approved look.
        self.assertEqual(position_mode(LEGACY), 'donor')

    def test_style_donor_profile_places_each_card_explicitly(self):
        # Leila/Sharran's shape. Their donor position is only a seed.
        self.assertEqual(position_mode(STYLE), 'explicit_centered')

    def test_an_explicit_mode_overrides_the_shape_default(self):
        self.assertEqual(position_mode(dict(LEGACY, text_position_mode='explicit_centered')),
                         'explicit_centered')
        self.assertEqual(position_mode(dict(STYLE, text_position_mode='donor')), 'donor')

    def test_an_unknown_mode_is_refused_rather_than_guessed(self):
        with self.assertRaisesRegex(ValueError, 'Unknown text_position_mode'):
            position_mode(dict(LEGACY, text_position_mode='centred'))
        with self.assertRaisesRegex(ValueError, 'Unknown text_position_mode'):
            position_mode(dict(STYLE, text_position_mode=True))

    def test_the_two_conventions_do_not_collapse_into_one(self):
        # A single hardcoded policy is exactly what caused the regression.
        self.assertNotEqual(position_mode(LEGACY), position_mode(STYLE))


if __name__ == '__main__':
    unittest.main()
