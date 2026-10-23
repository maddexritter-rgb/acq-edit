import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from resolve_cards import resolve, load_words, load_cuts, group
from native_graphics.caption_style_review import validate as validate_style

FPS = dict(numerator=24000, denominator=1001)
STYLE = dict(frame_rate=FPS, y_pct=50.0, font_size_px=160, timeline_end_frame=400,
             gap_threshold_seconds=0.75, trailing_hold_seconds=0.35, max_words_per_card=3,
             size_tiers={'base': 1.0, 'emph': 1.05, 'strong': 1.10, 'peak': 1.15},
             voices=dict(host=dict(color='FFFFFF', italic=False),
                         guest=dict(color='FED90F', italic=True)),
             fonts=dict(base='Base', strong='Strong',
                        base_italic='BaseIt', strong_italic='StrongIt'),
             emit_font_postscript=True)


def words(spec):
    """spec: list of (text, start, end, speaker)"""
    return [dict(text=t, start=s, end=e, source_indices=[i], physical_speaker=v)
            for i, (t, s, e, v) in enumerate(spec)]


def stream(n, speaker='host', step=0.3):
    return words([(f'w{i}', i * step, i * step + 0.2, speaker) for i in range(n)])


class GroupingTests(unittest.TestCase):
    def test_word_cap_splits(self):
        m = resolve(stream(7), [], STYLE, None, 'demo')
        self.assertEqual([len(c['words']) for c in m['cards']], [3, 3, 1])

    def test_long_gap_splits(self):
        w = words([('a', 0.0, 0.2, 'host'), ('b', 2.0, 2.2, 'host')])
        self.assertEqual(len(resolve(w, [], STYLE, None, 'demo')['cards']), 2)

    def test_speaker_change_splits_and_maps_face_and_colour(self):
        w = words([('a', 0.0, 0.2, 'host'), ('b', 0.3, 0.5, 'guest')])
        cards = resolve(w, [], STYLE, None, 'demo')['cards']
        self.assertEqual(len(cards), 2)
        self.assertEqual((cards[0]['speaker'], cards[0]['words'][0]['font_postscript'],
                          cards[0]['words'][0]['color'], cards[0]['words'][0]['italic']),
                         ('host', 'Base', 'FFFFFF', False))
        self.assertEqual((cards[1]['speaker'], cards[1]['words'][0]['font_postscript'],
                          cards[1]['words'][0]['color'], cards[1]['words'][0]['italic']),
                         ('guest', 'BaseIt', 'FED90F', True))

    def test_a_cut_between_words_splits_the_card(self):
        w = words([('a', 0.0, 0.2, 'host'), ('b', 0.3, 0.5, 'host')])
        # 0.3s at 23.976fps is frame 7; a cut at 5 falls between the two word onsets
        self.assertEqual(len(resolve(w, [5], STYLE, None, 'demo')['cards']), 2)

    def test_group_ends_override_the_word_cap(self):
        w = stream(6)
        ed = dict(group_ends=[1, 3])
        sizes = [len(c['words']) for c in resolve(w, [], STYLE, ed, 'demo')['cards']]
        self.assertEqual(sizes, [2, 2, 2])

    def test_group_is_pure_on_its_inputs(self):
        w = stream(5)
        before = [dict(x) for x in w]
        group(w, [], lambda s: 0, 0.75, 3, None)
        self.assertEqual(w, before)


class TimingTests(unittest.TestCase):
    def test_short_gap_holds_until_the_next_card(self):
        w = words([('a', 0.0, 0.2, 'host'), ('b', 0.5, 0.7, 'host')])
        style = dict(STYLE, max_words_per_card=1)
        cards = resolve(w, [], style, None, 'demo')['cards']
        self.assertEqual(cards[0]['end_frame'], cards[1]['start_frame'])

    def test_long_gap_releases_after_a_trailing_hold(self):
        w = words([('a', 0.0, 0.2, 'host'), ('b', 5.0, 5.2, 'host')])
        cards = resolve(w, [], dict(STYLE, max_words_per_card=1), None, 'demo')['cards']
        self.assertLess(cards[0]['end_frame'], cards[1]['start_frame'])
        self.assertEqual(cards[0]['end_frame'], cards[0]['speech_end_frame'] + 8)

    def test_every_card_lasts_at_least_one_frame(self):
        w = words([('a', 0.0, 0.0, 'host')])
        card = resolve(w, [], STYLE, None, 'demo')['cards'][0]
        self.assertGreaterEqual(card['end_frame'] - card['start_frame'], 1)

    def test_cards_are_ordered_and_nonoverlapping(self):
        cards = resolve(stream(20), [], STYLE, None, 'demo')['cards']
        for a, b in zip(cards, cards[1:]):
            self.assertLessEqual(a['end_frame'], b['start_frame'])


class PartitionAndCoverageTests(unittest.TestCase):
    def test_continuation_segment_repeats_text_with_animation_offset(self):
        w = words([('a', 0.0, 1.2, 'host')])
        m = resolve(w, [10], STYLE, None, 'demo')
        segs = m['render_segments']
        self.assertEqual(len(segs), 2)
        self.assertEqual(segs[0]['text'], segs[1]['text'])
        self.assertEqual((segs[0]['continuation'], segs[1]['continuation']), (False, True))
        self.assertEqual((segs[0]['source_coverage_owner'], segs[1]['source_coverage_owner']),
                         (True, False))
        self.assertEqual(segs[1]['animation_elapsed_frames'],
                         segs[1]['start_frame'] - segs[0]['start_frame'])

    def test_no_render_segment_spans_a_cut(self):
        m = resolve(stream(30), [10, 40, 90, 150], STYLE, None, 'demo')
        for s in m['render_segments']:
            for c in m['cut_frames']:
                self.assertFalse(s['start_frame'] < c < s['end_frame'])

    def test_multi_source_word_keeps_every_index_owned_once(self):
        w = words([('door-to-door', 0.0, 0.5, 'host')])
        w[0]['source_indices'] = [0, 1, 2]
        m = resolve(w, [], STYLE, None, 'demo')
        owned = [i for s in m['render_segments'] if s['source_coverage_owner']
                 for x in s['words'] for i in x['source_indices']]
        self.assertEqual(sorted(owned), [0, 1, 2])
        self.assertEqual(m['evidence']['source_words'], 3)

    def test_card_text_is_exactly_its_words_space_joined(self):
        # premiere_native_cards.build() rejects any other joining
        for card in resolve(stream(9), [], STYLE, None, 'demo')['render_segments']:
            self.assertEqual(card['text'], ' '.join(w['text'] for w in card['words']))


class StyleReviewTests(unittest.TestCase):
    def test_uniform_request_is_recorded_verbatim_and_passes_the_gate(self):
        m = resolve(stream(6), [], STYLE, None, 'the user asked for uniform styling')
        self.assertEqual(m['style_review']['mode'], 'uniform_requested')
        self.assertEqual(validate_style(m)['status'], 'EXPLICIT_UNIFORM_STYLE')

    def test_editorial_emphasis_produces_passing_targets(self):
        m = resolve(stream(6), [], STYLE, dict(emphasis_source_indices=[2]), None)
        self.assertEqual(validate_style(m)['status'],
                         'STYLE_PLAN_PRESENT_AND_TARGETS_MATCH_NOT_VISUAL_APPROVAL')
        self.assertEqual(m['style_review']['weight']['status'], 'applied')
        target = m['style_review']['weight']['targets'][0]
        seg = next(s for s in m['render_segments'] if s['id'] == target['segment_id'])
        self.assertEqual(seg['words'][target['word_index']]['weight'], 'strong')
        self.assertEqual(seg['words'][target['word_index']]['font_postscript'], 'Strong')

    def test_no_emphasis_reports_weight_not_applicable_never_a_fake_target(self):
        m = resolve(stream(6), [], STYLE, None, None)
        self.assertEqual(m['style_review']['weight']['status'], 'not_applicable')
        self.assertNotIn('targets', m['style_review']['weight'])
        self.assertEqual(validate_style(m)['status'],
                         'STYLE_PLAN_PRESENT_AND_TARGETS_MATCH_NOT_VISUAL_APPROVAL')

    def test_size_is_never_claimed_as_editorial(self):
        # width fitting must not masquerade as an intentional tier
        m = resolve(stream(6), [], STYLE, None, None)
        self.assertEqual(m['style_review']['size']['status'], 'not_applicable')

    def test_guest_italic_is_reported_as_an_italic_decision(self):
        m = resolve(stream(3, speaker='guest'), [], STYLE, None, None)
        self.assertEqual(m['style_review']['italic']['status'], 'applied')
        self.assertTrue(all(t['value'] is True for t in m['style_review']['italic']['targets']))

    def test_uniform_and_emphasis_together_are_refused(self):
        with self.assertRaises(ValueError):
            resolve(stream(3), [], STYLE, dict(emphasis_source_indices=[0]), 'uniform please')


class InputValidationTests(unittest.TestCase):
    def test_position_and_size_come_from_the_style_config(self):
        m = resolve(stream(3), [], dict(STYLE, y_pct=42.5, font_size_px=120), None, 'demo')
        self.assertTrue(all(c['y_pct'] == 42.5 for c in m['render_segments']))
        self.assertTrue(all(c['font_size_px'] == 120 for c in m['render_segments']))

    def test_empty_word_list_is_refused(self):
        with self.assertRaises((ValueError, KeyError, IndexError)):
            resolve([], [], STYLE, None, 'demo')

    def test_zero_word_cap_is_refused(self):
        with self.assertRaises(ValueError):
            resolve(stream(3), [], dict(STYLE, max_words_per_card=0), None, 'demo')

    def test_load_words_requires_text_and_integer_indices(self):
        import json, tempfile
        for payload in ([dict(start=0, end=1, source_indices=[0])],
                        [dict(text='a', start=0, end=1, source_indices=['x'])],
                        [dict(text='a', start=1, end=0, source_indices=[0])]):
            with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False) as f:
                json.dump(payload, f)
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                load_words(f.name)

    def test_load_cuts_accepts_both_shapes_and_rejects_bad_frames(self):
        import json, tempfile
        def write(obj):
            with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False) as f:
                json.dump(obj, f)
            return f.name
        self.assertEqual(load_cuts(write(dict(cuts=[dict(frame=3), dict(frame=1)]))), [1, 3])
        self.assertEqual(load_cuts(write(dict(cut_frames=[5, 5, 2]))), [2, 5])
        self.assertEqual(load_cuts(write([7, 4])), [4, 7])
        self.assertEqual(load_cuts(None), [])
        with self.assertRaises(ValueError):
            load_cuts(write([-1]))




class SizeTierTests(unittest.TestCase):
    """Card-level editorial size, and the rule that a width shrink can never pose as it."""

    def test_tier_applies_to_the_whole_card_and_passes_the_gate(self):
        m = resolve(stream(6), [], STYLE,
                    dict(size_tiers=[dict(source_index=4, tier='peak')]), None)
        tiered = [c for c in m['render_segments'] if c['size_tier'] != 'base']
        self.assertTrue(tiered)
        for c in tiered:
            self.assertEqual(c['font_size_px'], round(160 * 1.15))
        self.assertEqual(m['style_review']['size']['status'], 'applied')
        self.assertEqual(validate_style(m)['status'],
                         'STYLE_PLAN_PRESENT_AND_TARGETS_MATCH_NOT_VISUAL_APPROVAL')

    def test_size_is_never_attached_to_one_word_inside_a_cue(self):
        m = resolve(stream(6), [], STYLE,
                    dict(size_tiers=[dict(source_index=4, tier='peak')]), None)
        for c in m['render_segments']:
            self.assertFalse(any('font_size_px' in w or 'size_tier' in w for w in c['words']))

    def test_strongest_requested_tier_wins_within_one_card(self):
        m = resolve(stream(3), [], STYLE,
                    dict(size_tiers=[dict(source_index=0, tier='emph'),
                                     dict(source_index=2, tier='peak')]), None)
        self.assertEqual(m['render_segments'][0]['size_tier'], 'peak')

    def test_requested_tier_and_size_are_persisted_alongside_the_live_size(self):
        m = resolve(stream(3), [], STYLE,
                    dict(size_tiers=[dict(source_index=1, tier='strong')]), None)
        c = m['render_segments'][0]
        self.assertEqual((c['requested_size_tier'], c['requested_font_size_px']),
                         ('strong', round(160 * 1.10)))

    def test_a_later_width_shrink_makes_the_gate_refuse(self):
        # The review targets the tiered size. Shrinking the card afterwards -- exactly
        # what width fitting does -- must fail validation, not pass as emphasis.
        m = resolve(stream(3), [], STYLE,
                    dict(size_tiers=[dict(source_index=1, tier='peak')]), None)
        self.assertEqual(validate_style(m)['status'],
                         'STYLE_PLAN_PRESENT_AND_TARGETS_MATCH_NOT_VISUAL_APPROVAL')
        for c in m['render_segments']:
            if c['size_tier'] != 'base':
                c['font_size_px'] = 120          # a width fit
        with self.assertRaisesRegex(ValueError, 'Planned size styling lost'):
            validate_style(m)

    def test_dropping_the_tier_but_keeping_the_size_also_refuses(self):
        m = resolve(stream(3), [], STYLE,
                    dict(size_tiers=[dict(source_index=1, tier='peak')]), None)
        for c in m['render_segments']:
            c['size_tier'] = 'base'
        with self.assertRaisesRegex(ValueError, 'Planned size styling lost'):
            validate_style(m)

    def test_base_is_not_an_editorial_tier(self):
        with self.assertRaises(ValueError):
            resolve(stream(3), [], STYLE, dict(size_tiers=[dict(source_index=0, tier='base')]), None)

    def test_a_tier_absent_from_the_style_config_is_refused(self):
        with self.assertRaises(ValueError):
            resolve(stream(3), [], STYLE, dict(size_tiers=[dict(source_index=0, tier='huge')]), None)

    def test_a_tier_needs_an_integer_source_index(self):
        with self.assertRaises(ValueError):
            resolve(stream(3), [], STYLE, dict(size_tiers=[dict(tier='peak')]), None)

    def test_uniform_and_size_tiers_together_are_refused(self):
        with self.assertRaises(ValueError):
            resolve(stream(3), [], STYLE,
                    dict(size_tiers=[dict(source_index=0, tier='peak')]), 'uniform please')

    def test_untiered_clip_still_reports_size_not_applicable(self):
        m = resolve(stream(6), [], STYLE, dict(emphasis_source_indices=[1]), None)
        self.assertEqual(m['style_review']['size']['status'], 'not_applicable')
        self.assertTrue(all(c['size_tier'] == 'base' for c in m['render_segments']))


if __name__ == '__main__':
    unittest.main()
