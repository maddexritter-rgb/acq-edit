"""Round-3 review regressions: the width budget still under-measured.

2026-09-23. Both code findings are in the round-1/round-2 fixes themselves --
the ladder merge silently did nothing when a caller supplied fonts, and the
budget was still measured at the nominal size although size tiers are applied
after grouping. Same class as the original finding: measure the WORST case.
"""
import json
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SCRIPTS))

import resolve_cards
from native_graphics.resolve_director_style import SIZE_TIERS

ALEX = json.loads((SCRIPTS.parent / 'profiles' / 'alex.json').read_text())


class LadderMergeTests(unittest.TestCase):
    """`setdefault` returns the caller's fonts and throws the merge away."""

    def test_a_caller_supplied_font_does_not_drop_the_ladder(self):
        style = resolve_cards.style_from_profile(
            ALEX, dict(fonts={'base': 'ProximaNova-Medium'}))
        for rung in resolve_cards.LADDER:
            self.assertIn(rung, style['fonts'], f'{rung} lost when caller passed fonts')
        self.assertEqual(style['fonts']['payoff'], 'ProximaNova-Black')

    def test_a_caller_override_still_wins_for_its_own_key(self):
        style = resolve_cards.style_from_profile(
            ALEX, dict(fonts={'payoff': 'ProximaNova-BlackIt'}))
        self.assertEqual(style['fonts']['payoff'], 'ProximaNova-BlackIt')
        self.assertEqual(style['fonts']['base'], 'ProximaNova-Medium')


class PeakSizeMeasurementTests(unittest.TestCase):
    """Size tiers are applied AFTER grouping; the director can reach its peak cue
    size without regrouping. A card measured at nominal can still overflow."""

    def _sizes_seen(self, extra_style=None):
        """Run resolve with a stub measurer and record the sizes it was asked for."""
        style = resolve_cards.style_from_profile(ALEX, dict(
            frame_rate=dict(numerator=24, denominator=1), timeline_end_frame=400,
            voices=dict(host=dict(color='FFFFFF', italic=False)), **(extra_style or {})))
        words = [dict(text=t, start=i * 0.3, end=i * 0.3 + 0.2, source_indices=[i],
                      physical_speaker='host', sentence_end=(i == 3))
                 for i, t in enumerate(['we', 'built', 'the', 'thing'])]
        seen, real = [], resolve_cards.width_measurer

        def stub(st):
            def measure(text, face, size_px):
                seen.append(size_px)
                return 1.0 * len(text)
            return measure, st['max_text_width_px']

        resolve_cards.width_measurer = stub
        try:
            resolve_cards.resolve(words, [], style, {}, None)
        finally:
            resolve_cards.width_measurer = real
        return seen

    def test_measurement_uses_the_director_peak_not_the_nominal_size(self):
        nominal = float(ALEX['font_size_px'])
        seen = self._sizes_seen()
        self.assertTrue(seen, 'the measurer was never called')
        self.assertEqual(max(seen), nominal * resolve_cards.DIRECTOR_PEAK_SCALE)
        self.assertNotIn(nominal, seen)

    def test_an_explicit_size_tier_larger_than_the_peak_wins(self):
        nominal = float(ALEX['font_size_px'])
        seen = self._sizes_seen(dict(size_tiers={'base': 1.0, 'huge': 1.5}))
        self.assertEqual(max(seen), nominal * 1.5)

    def test_the_peak_scale_matches_the_director(self):
        self.assertEqual(resolve_cards.DIRECTOR_PEAK_SCALE, max(SIZE_TIERS) / 100)

    def test_the_manifest_reports_the_size_it_measured_at(self):
        style = resolve_cards.style_from_profile(ALEX, dict(
            frame_rate=dict(numerator=24, denominator=1), timeline_end_frame=400,
            voices=dict(host=dict(color='FFFFFF', italic=False))))
        words = [dict(text=t, start=i * 0.3, end=i * 0.3 + 0.2, source_indices=[i],
                      physical_speaker='host', sentence_end=(i == 1))
                 for i, t in enumerate(['short', 'card'])]
        real = resolve_cards.width_measurer
        resolve_cards.width_measurer = lambda st: (
            (lambda text, face, size: 1.0 * len(text)), st['max_text_width_px'])
        try:
            manifest = resolve_cards.resolve(words, [], style, {}, None)
        finally:
            resolve_cards.width_measurer = real
        note = ' '.join(manifest['limitations'])
        expected = float(ALEX['font_size_px']) * resolve_cards.DIRECTOR_PEAK_SCALE
        self.assertIn(f'{expected:.1f}px', note)
        self.assertIn('largest size a card can reach', note)


class ReceiptPathDocsTests(unittest.TestCase):
    """premiere_native_cards uses Path.with_suffix, which REPLACES '.prproj'."""

    def test_the_builder_writes_name_dot_receipt_json(self):
        self.assertEqual(Path('new.prproj').with_suffix('.receipt.json').name,
                         'new.receipt.json')

    def test_no_doc_promises_a_prproj_receipt_json(self):
        root = SCRIPTS.parent
        offenders = [str(p.relative_to(root)) for p in root.rglob('*.md')
                     if 'prproj.receipt.json' in p.read_text()]
        self.assertEqual(offenders, [], f'docs name a file the builder never writes: {offenders}')


if __name__ == '__main__':
    unittest.main()
