"""A sentence end must split a caption card, even after punctuation is stripped.

2026-09-22. Display normalization removes routine terminal punctuation, so the
boundary survives only as oliver_format's `sentence_end` flag. The Alex native
grouper ignored it and welded the end of one sentence onto the start of the next
-- a real build produced the card "fucking communicating? are", which Premiere
then wrapped so it read as scrambled word order on screen.
"""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from resolve_cards import resolve, load_words

STYLE = dict(frame_rate=dict(numerator=24, denominator=1), y_pct=50.0, font_size_px=160,
             timeline_end_frame=400, max_words_per_card=3,
             voices=dict(host=dict(color='FFFFFF', italic=False)))


def stream(spec):
    """spec: [(text, sentence_end), ...] evenly spaced so no gap rule fires."""
    return [dict(text=t, start=i * 0.3, end=i * 0.3 + 0.2, source_indices=[i],
                 physical_speaker='host', sentence_end=e)
            for i, (t, e) in enumerate(spec)]


class SentenceBoundaryTests(unittest.TestCase):
    def test_a_stripped_sentence_end_still_splits_the_card(self):
        w = stream([('even', False), ('fucking', False), ('communicating', True),
                    ('are', False), ('we', False)])
        cards = resolve(w, [], STYLE, None, None)['cards']
        texts = [c['text'] for c in cards]
        self.assertIn('even fucking communicating', texts)
        self.assertFalse(any('communicating are' in t for t in texts),
                         f'a card welded across the sentence end: {texts}')

    def test_a_visible_question_mark_also_splits(self):
        w = stream([('communicating?', True), ('are', False), ('we', False)])
        cards = resolve(w, [], STYLE, None, None)['cards']
        self.assertEqual(cards[0]['text'], 'communicating?')

    def test_the_split_does_not_lose_or_duplicate_a_word(self):
        w = stream([('a', False), ('b', True), ('c', False), ('d', True), ('e', False)])
        m = resolve(w, [], STYLE, None, None)
        owned = [i for s in m['render_segments'] if s['source_coverage_owner']
                 for x in s['words'] for i in x['source_indices']]
        self.assertEqual(sorted(owned), [0, 1, 2, 3, 4])

    def test_a_stream_with_no_sentence_ends_is_unchanged(self):
        w = stream([(f'w{i}', False) for i in range(6)])
        self.assertEqual([len(c['words']) for c in resolve(w, [], STYLE, None, None)['cards']],
                         [3, 3])

    def test_load_words_defaults_the_flag_off_rather_than_crashing(self):
        import json, tempfile
        p = Path(tempfile.mkdtemp()) / 'w.json'
        p.write_text(json.dumps([dict(text='a', start=0, end=0.2, source_indices=[0])]))
        self.assertFalse(load_words(p)[0]['sentence_end'])




class SingleLineWidthTests(unittest.TestCase):
    """A single-line profile must never hand Premiere a card that wraps.

    2026-09-22. Alex is max_lines:1, but no width budget was enforced, so
    'even fucking communicating?' (2235px against the approved 1650px budget) was
    re-flowed onto a second line by Premiere and read as scrambled word order.
    Regrouping is the approved response; shrinking past the floor is not.
    """

    # Vendored faces: these ship with the skill, so width tests run on a
    # fresh machine and in CI without any Adobe font installed.
    FACES = {'base': 'Inter-Regular',    'base_italic': 'Inter-Italic',
             'strong': 'Inter-SemiBold',  'strong_italic': 'Inter-Italic',
             'emphasis': 'Inter-SemiBold','emphasis_italic': 'Inter-Italic',
             'payoff': 'Inter-SemiBold',  'payoff_italic': 'Inter-Italic'}

    def words(self, n=6):
        return [dict(text='communicating', start=i * 0.3, end=i * 0.3 + 0.2,
                     source_indices=[i], physical_speaker='host', sentence_end=False)
                for i in range(n)]

    def test_without_a_budget_only_the_word_cap_applies(self):
        m = resolve(self.words(6), [], dict(STYLE, max_words_per_card=3), None, None)
        self.assertEqual([len(c['words']) for c in m['cards']], [3, 3])

    def test_a_budget_splits_before_a_card_can_overflow(self):
        narrow = dict(STYLE, max_words_per_card=3, max_text_width_px=400,
                      fonts=self.FACES)
        m = resolve(self.words(6), [], narrow, None, None)
        self.assertTrue(all(len(c['words']) < 3 for c in m['cards']),
                        f"budget did not split: {[c['text'] for c in m['cards']]}")

    def test_a_budget_without_faces_is_refused_rather_than_ignored(self):
        with self.assertRaisesRegex(ValueError, 'style.fonts'):
            resolve(self.words(4), [], dict(STYLE, max_text_width_px=400), None, None)

    def test_one_overlong_word_still_ships_as_its_own_card(self):
        tiny = dict(STYLE, max_words_per_card=3, max_text_width_px=10, fonts=self.FACES)
        m = resolve(self.words(3), [], tiny, None, None)
        self.assertEqual([len(c['words']) for c in m['cards']], [1, 1, 1])

    def test_faces_are_not_stamped_into_the_manifest_unless_requested(self):
        # a stamped face contradicts the weight a director assigns afterwards
        m = resolve(self.words(3), [], dict(STYLE, fonts=self.FACES), None, None)
        self.assertTrue(all('font_postscript' not in w
                            for c in m['render_segments'] for w in c['words']))


if __name__ == '__main__':
    unittest.main()
