import copy
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('handoff', ROOT / 'distribution/skills/caption-clips/scripts/premiere_caption_handoff.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class MultilineHandoffTests(unittest.TestCase):
    def packet(self):
        ticks = str(254016000000 // 24)
        card = {'id': 'card/state', 'item_id': '1', 'text': 'first line\rsecond line',
                'expected_runs': [{'text': 'first line\r'}, {'text': 'second line'}],
                'timing': {'start_ticks': '0', 'end_ticks': ticks, 'source_in_ticks': '0',
                           'source_out_ticks': ticks, 'animation_elapsed_ticks': '0'}}
        segment = {'id': 'card/state', 'semantic_card_id': 'card', 'text': 'first line\nsecond line',
                   'start_frame': 0, 'end_frame': 1, 'animation_elapsed_frames': 0}
        return {'cards': [card]}, {'frame_rate': {'numerator': 24, 'denominator': 1}, 'render_segments': [segment]}

    def test_native_paragraph_break_matches_shared_line_break(self):
        receipt, manifest = self.packet()
        before = copy.deepcopy((receipt, manifest))
        self.assertEqual(m.bind_segments(receipt, manifest)[0]['expected_text'], 'first line\rsecond line')
        self.assertEqual((receipt, manifest), before)

    def test_missing_break_or_changed_word_still_fails(self):
        for changed in ('first line second line', 'first line\nwrong line'):
            receipt, manifest = self.packet()
            manifest['render_segments'][0]['text'] = changed
            with self.assertRaisesRegex(ValueError, 'text mismatch'):
                m.bind_segments(receipt, manifest)


if __name__ == '__main__':
    unittest.main()
