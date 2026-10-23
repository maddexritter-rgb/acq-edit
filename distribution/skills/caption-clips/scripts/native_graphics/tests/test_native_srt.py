import copy
from fractions import Fraction
import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from export_premiere_srt import encode_native_srt as encode, TICKS


class ReviewSrtTests(unittest.TestCase):
    def fixture(self):
        manifest = {'frame_rate': {'numerator': 24000, 'denominator': 1001},
                    'render_segments': [dict(start_frame=0, end_frame=24, text='first'),
                                        dict(start_frame=24, end_frame=48, text='second')]}
        receipt = {'cards': [dict(text=s['text'], timing={
            'start_ticks': str(int(Fraction(s['start_frame'] * 1001 * TICKS, 24000))),
            'end_ticks': str(int(Fraction(s['end_frame'] * 1001 * TICKS, 24000)))})
            for s in manifest['render_segments']]}
        return manifest, receipt

    def test_boundary_and_no_mutation(self):
        m, r = self.fixture(); before = copy.deepcopy((m, r))
        output = encode(m, r, [24])
        self.assertIn('00:00:00,000 --> 00:00:01,001\nfirst', output)
        self.assertIn('00:00:01,001 --> 00:00:02,002\nsecond', output)
        self.assertEqual((m, r), before)

    def test_cut_crossing_fails(self):
        m, r = self.fixture()
        with self.assertRaisesRegex(ValueError, 'crosses'): encode(m, r, [12])

    def test_receipt_text_drift_fails(self):
        m, r = self.fixture(); r['cards'][0]['text'] = 'wrong'
        with self.assertRaisesRegex(ValueError, 'text mismatch'): encode(m, r, [])

    def test_receipt_timing_drift_fails(self):
        m, r = self.fixture(); r['cards'][0]['timing']['end_ticks'] = '1'
        with self.assertRaisesRegex(ValueError, 'timing mismatch'): encode(m, r, [])

    def test_missing_card_fails(self):
        m, r = self.fixture(); r['cards'].pop()
        with self.assertRaisesRegex(ValueError, 'count mismatch'): encode(m, r, [])

    def test_overlap_fails(self):
        m, r = self.fixture(); m['render_segments'][1]['start_frame'] = 23
        with self.assertRaisesRegex(ValueError, 'overlapping'): encode(m, r, [])

    def test_native_definition_line_is_preserved(self):
        for separator in ('\r', '\r\n', '\n'):
            m, r = self.fixture()
            m['render_segments'][0]['text'] = r['cards'][0]['text'] = 'DTC'+separator+'(direct to consumer)'
            before = copy.deepcopy((m, r))
            output = encode(m, r, [24])
            self.assertIn('DTC\n(direct to consumer)', output)
            self.assertNotIn('\r', output)
            self.assertEqual((m, r), before)

    def test_line_adapter_cannot_mask_native_drift(self):
        m, r = self.fixture()
        m['render_segments'][0]['text'] = 'DTC\r(definition)'
        r['cards'][0]['text'] = 'DTC\n(definition)'
        with self.assertRaisesRegex(ValueError, 'text mismatch'): encode(m, r, [])

    def test_blank_definition_lines_rejected(self):
        for text in ('main\r\r(gloss)', 'main\n  \n(gloss)', '\rmain', 'main\r'):
            m, r = self.fixture()
            m['render_segments'][0]['text'] = r['cards'][0]['text'] = text
            with self.assertRaisesRegex(ValueError, 'Empty lines'): encode(m, r, [])

    def test_bracketed_substitution_keeps_display_text(self):
        m, r = self.fixture()
        m['render_segments'][0]['text'] = r['cards'][0]['text'] = '[revenue]'
        self.assertIn('\n[revenue]\n', encode(m, r, []))


if __name__ == '__main__': unittest.main()
