"""The five-axis style contract: full ladder, and axes that stay independent.

These pin the behaviour the narrow base|strong contract used to prevent, and the
independence rules that a quote-implies-guest shortcut used to break.
"""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from resolve_cards import resolve, style_counts, LADDER
from premiere_native_cards import donor_run_offset
from native_graphics.caption_style_review import validate as validate_style
from native_graphics.resolve_director_style import resolve as resolve_director

FPS = dict(numerator=24000, denominator=1001)
FACES = {
    'base': 'ProximaNova-Medium', 'base_italic': 'ProximaNova-MediumIt',
    'strong': 'ProximaNova-Bold', 'strong_italic': 'ProximaNova-BoldIt',
    'emphasis': 'ProximaNova-Extrabld', 'emphasis_italic': 'ProximaNova-ExtrabldIt',
    'payoff': 'ProximaNova-Black', 'payoff_italic': 'ProximaNova-BlackIt',
}
# Faces that SHIP with the skill, so width measurement works on a fresh
# machine and in CI where no Adobe font is installed.
VENDORED = {'base': 'Inter-Regular', 'base_italic': 'Inter-Italic', 'strong': 'Inter-SemiBold', 'strong_italic': 'Inter-Italic', 'emphasis': 'Inter-SemiBold', 'emphasis_italic': 'Inter-Italic', 'payoff': 'Inter-SemiBold', 'payoff_italic': 'Inter-Italic'}

STYLE = dict(frame_rate=FPS, y_pct=50.0, font_size_px=160, timeline_end_frame=900,
             gap_threshold_seconds=0.75, trailing_hold_seconds=0.35, max_words_per_card=4,
             size_tiers={'base': 1.0, 'emph': 1.10, 'strong': 1.15, 'peak': 1.20},
             voices=dict(host=dict(color='FFFFFF', italic=False),
                         guest=dict(color='FED90F', italic=True)),
             # faces are stamped into the manifest only on request; these tests
             # assert the weight->face mapping, so they opt in explicitly
             fonts=FACES, emit_font_postscript=True)
# A donor exposing upright+italic for every rung, as the V3 contract requires.
NESTED_DONOR = dict(item_id='1', color='FFFFFF',
                    runs={w: {'upright': 2 * i, 'italic': 2 * i + 1}
                          for i, w in enumerate(LADDER)})


def words(spec):
    return [dict(text=t, start=i * 0.3, end=i * 0.3 + 0.2, source_indices=[i],
                 physical_speaker=v)
            for i, (t, v) in enumerate(spec)]


def host(n):
    return words([(f'w{i}', 'host') for i in range(n)])


class FullLadderTests(unittest.TestCase):
    def test_four_weights_map_to_four_exact_faces(self):
        ed = dict(emphasis_source_indices=[
            dict(source_index=1, weight='strong'),
            dict(source_index=2, weight='emphasis'),
            dict(source_index=3, weight='payoff')])
        m = resolve(host(4), [], dict(STYLE, max_words_per_card=4), ed, None)
        card = m['render_segments'][0]
        self.assertEqual([w['weight'] for w in card['words']],
                         ['base', 'strong', 'emphasis', 'payoff'])
        self.assertEqual([w['font_postscript'] for w in card['words']],
                         ['ProximaNova-Medium', 'ProximaNova-Bold',
                          'ProximaNova-Extrabld', 'ProximaNova-Black'])
        self.assertEqual(len({w['font_postscript'] for w in card['words']}), 4)

    def test_every_rung_has_a_distinct_italic_face(self):
        ed = dict(emphasis_source_indices=[dict(source_index=i, weight=w)
                                           for i, w in enumerate(LADDER[1:], start=1)],
                  italic_spans=[[0, 3]])
        m = resolve(host(4), [], STYLE, ed, None)
        faces = [w['font_postscript'] for w in m['render_segments'][0]['words']]
        self.assertEqual(faces, ['ProximaNova-MediumIt', 'ProximaNova-BoldIt',
                                 'ProximaNova-ExtrabldIt', 'ProximaNova-BlackIt'])

    def test_a_weight_absent_from_the_style_fonts_is_refused(self):
        slim = dict(STYLE, fonts={'base': 'ProximaNova-Medium'})
        with self.assertRaisesRegex(ValueError, 'no face for'):
            resolve(host(2), [], slim, dict(emphasis_source_indices=[1]), None)

    def test_base_is_not_an_emphasis_weight(self):
        with self.assertRaises(ValueError):
            resolve(host(2), [], STYLE,
                    dict(emphasis_source_indices=[dict(source_index=1, weight='base')]), None)

    def test_an_unknown_weight_is_refused(self):
        with self.assertRaises(ValueError):
            resolve(host(2), [], STYLE,
                    dict(emphasis_source_indices=[dict(source_index=1, weight='heavy')]), None)


class AxisIndependenceTests(unittest.TestCase):
    def test_one_card_mixes_upright_and_italic_without_changing_colour(self):
        m = resolve(host(4), [], STYLE, dict(italic_source_indices=[1, 2]), None)
        card = m['render_segments'][0]
        self.assertEqual([w['italic'] for w in card['words']], [False, True, True, False])
        self.assertEqual({w['color'] for w in card['words']}, {'FFFFFF'})
        self.assertEqual(card['speaker'], 'host')

    def test_a_host_inner_thought_stays_host_white_while_italic(self):
        m = resolve(host(3), [], STYLE, dict(italic_spans=[[0, 2]]), None)
        for card in m['render_segments']:
            self.assertEqual(card['speaker'], 'host')
            for w in card['words']:
                self.assertEqual(w['color'], 'FFFFFF')
                self.assertTrue(w['italic'])

    def test_a_quote_alone_changes_neither_colour_nor_slant(self):
        m = resolve(host(3), [], STYLE, dict(quote_spans=[[0, 2]]), None)
        card = m['render_segments'][0]
        self.assertEqual(card['speaker'], 'host')
        self.assertTrue(all(w['color'] == 'FFFFFF' for w in card['words']))
        self.assertTrue(all(w['italic'] is False for w in card['words']))
        self.assertTrue(card['words'][0]['text'].startswith('“'))
        self.assertEqual(m['quoted_spans'][0]['from'], 0)

    def test_quoted_terminology_can_stay_upright_inside_an_italic_voice(self):
        spec = words([('a', 'guest'), ('b', 'guest'), ('c', 'guest')])
        m = resolve(spec, [], STYLE,
                    dict(quote_spans=[[1, 1]], italic_source_indices=[
                        dict(source_index=1, italic=False)]), None)
        flat = [w for c in m['render_segments'] for w in c['words']]
        self.assertEqual([w['italic'] for w in flat], [True, False, True])
        self.assertTrue(all(w['color'] == 'FED90F' for w in flat))

    def test_a_role_played_other_voice_is_independently_yellow_quoted_and_italic(self):
        m = resolve(host(5), [], STYLE,
                    dict(represented_voice_spans=[dict(**{'from': 2, 'to': 3}, voice='guest')],
                         quote_spans=[[2, 3]], italic_spans=[[2, 3]]), None)
        inner = [w for c in m['render_segments'] for w in c['words']
                 if any(i in (2, 3) for i in w['source_indices'])]
        outer = [w for c in m['render_segments'] for w in c['words']
                 if not any(i in (2, 3) for i in w['source_indices'])]
        self.assertTrue(inner and outer)
        self.assertTrue(all(w['color'] == 'FED90F' and w['italic'] for w in inner))
        self.assertTrue(all(w['color'] == 'FFFFFF' and not w['italic'] for w in outer))
        self.assertTrue(any(w['text'].startswith('“') for w in inner))
        # colour is a card property, so the represented span became its own card
        self.assertEqual(len({c['speaker'] for c in m['render_segments']}), 2)

    def test_represented_voice_needs_a_declared_voice(self):
        with self.assertRaises(ValueError):
            resolve(host(3), [], STYLE,
                    dict(represented_voice_spans=[dict(**{'from': 0, 'to': 1},
                                                       voice='narrator')]), None)


class CardLevelSizeTests(unittest.TestCase):
    def test_a_size_tier_is_uniform_across_every_word_of_its_card(self):
        m = resolve(host(8), [], STYLE,
                    dict(size_tiers=[dict(source_index=1, tier='peak')]), None)
        tiered = [c for c in m['render_segments'] if c['size_tier'] == 'peak']
        self.assertTrue(tiered)
        for c in tiered:
            self.assertEqual(c['font_size_px'], round(160 * 1.20))
            self.assertFalse(any('font_size_px' in w or 'size_tier' in w for w in c['words']))
        self.assertTrue(any(c['size_tier'] == 'base' for c in m['render_segments']))

    def test_a_shrink_after_review_cannot_pose_as_a_tier(self):
        m = resolve(host(3), [], STYLE,
                    dict(size_tiers=[dict(source_index=1, tier='peak')]), None)
        self.assertEqual(validate_style(m)['status'],
                         'STYLE_PLAN_PRESENT_AND_TARGETS_MATCH_NOT_VISUAL_APPROVAL')
        for c in m['render_segments']:
            if c['size_tier'] != 'base':
                c['font_size_px'] = 120
        with self.assertRaisesRegex(ValueError, 'Planned size styling lost'):
            validate_style(m)


class DonorRunSelectionTests(unittest.TestCase):
    def test_nested_donor_selects_upright_and_italic_per_weight(self):
        for i, weight in enumerate(LADDER):
            self.assertEqual(donor_run_offset(NESTED_DONOR,
                                              dict(weight=weight, italic=False)), 2 * i)
            self.assertEqual(donor_run_offset(NESTED_DONOR,
                                              dict(weight=weight, italic=True)), 2 * i + 1)

    def test_a_weight_the_donor_lacks_fails_instead_of_becoming_base(self):
        donor = dict(item_id='1', color='FFFFFF',
                     runs={'base': {'upright': 0, 'italic': 1}})
        with self.assertRaisesRegex(ValueError, 'Donor lacks requested weight'):
            donor_run_offset(donor, dict(weight='payoff', italic=False))

    def test_a_missing_italic_run_fails_instead_of_flattening_to_upright(self):
        donor = dict(item_id='1', color='FFFFFF', runs={'strong': {'upright': 2}})
        with self.assertRaisesRegex(ValueError, 'Donor lacks requested italic run'):
            donor_run_offset(donor, dict(weight='strong', italic=True))

    def test_legacy_single_offset_donor_only_serves_its_own_italic_state(self):
        legacy = dict(item_id='1', color='FFFFFF', italic=False, runs={'base': 0, 'strong': 2})
        self.assertEqual(donor_run_offset(legacy, dict(weight='strong', italic=False)), 2)
        with self.assertRaisesRegex(ValueError, 'Unsupported italic change'):
            donor_run_offset(legacy, dict(weight='strong', italic=True))


class DirectorStreamTests(unittest.TestCase):
    """The canonical {words:{idx:{w,s,i,q,c}}} stream, applied to a resolved manifest."""

    def base_manifest(self, spec=None, **kw):
        return resolve(spec or host(4), [], dict(STYLE, **kw), None, None)

    def stream(self, words_spec, mode='api'):
        return dict(words=words_spec, voice_spans=[],
                    style_provenance=dict(engine='caption_director', mode=mode,
                                          model='claude-sonnet-4-5'))

    def test_director_weights_and_italics_reach_the_manifest(self):
        m = self.base_manifest()
        out = resolve_director(m, self.stream({'1': {'w': 'emphasis'}, '2': {'i': True}}), 160)
        flat = [w for c in out['render_segments'] for w in c['words']]
        self.assertEqual(flat[1]['weight'], 'emphasis')
        self.assertTrue(flat[2]['italic'])
        self.assertEqual(out['style_review']['weight']['status'], 'applied')
        self.assertEqual(out['style_review']['italic']['status'], 'applied')

    def test_director_aliases_map_onto_the_approved_ladder(self):
        m = self.base_manifest()
        out = resolve_director(m, self.stream({'1': {'w': 'bold'}, '2': {'w': 'black'}}), 160)
        flat = [w for c in out['render_segments'] for w in c['words']]
        self.assertEqual((flat[1]['weight'], flat[2]['weight']), ('strong', 'payoff'))

    def test_director_stream_survives_merged_display_words(self):
        # One display word owning three source indices, as normalization produces
        # for a hyphenated compound. Its style index is the DISPLAY position.
        spec = host(3)
        spec[1]['source_indices'] = [1, 2, 3]
        spec[2]['source_indices'] = [4]
        m = resolve(spec, [], dict(STYLE, max_words_per_card=3), None, None)
        self.assertEqual(m['cards'][0]['normalized_indices'], [0, 1, 2])
        out = resolve_director(m, self.stream({'1': {'w': 'payoff'}}), 160)
        flat = [w for c in out['render_segments'] for w in c['words']]
        self.assertEqual(flat[1]['weight'], 'payoff')
        self.assertEqual(flat[1]['source_indices'], [1, 2, 3])
        self.assertEqual([w['weight'] for w in flat], ['base', 'payoff', 'base'])

    def test_a_card_size_comes_from_a_uniform_cue_proposal(self):
        m = self.base_manifest(host(2), max_words_per_card=2)
        out = resolve_director(m, self.stream({'0': {'s': 'peak'}, '1': {'s': 'peak'}}), 160)
        card = out['render_segments'][0]
        self.assertEqual(card['size_tier'], 'peak')
        self.assertEqual(card['font_size_px'], 192.0)

    def test_a_mixed_per_word_size_proposal_drops_back_to_base(self):
        m = self.base_manifest(host(2), max_words_per_card=2)
        out = resolve_director(m, self.stream({'0': {'s': 'peak'}}), 160)
        self.assertEqual(out['render_segments'][0]['size_tier'], 'base')

    def test_deterministic_fallback_is_refused_by_default(self):
        m = self.base_manifest()
        with self.assertRaisesRegex(ValueError, 'deterministic'):
            resolve_director(m, self.stream({'1': {'w': 'strong'}}, mode='deterministic'), 160)

    def test_deterministic_fallback_needs_an_explicit_allowance(self):
        m = self.base_manifest()
        out = resolve_director(m, self.stream({'1': {'w': 'strong'}}, mode='deterministic'),
                               160, allow_deterministic=True)
        self.assertEqual(out['style_resolution']['source']['mode'], 'deterministic')

    def test_a_stream_without_provenance_is_refused(self):
        m = self.base_manifest()
        with self.assertRaisesRegex(ValueError, 'style_provenance'):
            resolve_director(m, dict(words={'1': {'w': 'strong'}}, voice_spans=[]), 160)

    def test_a_missing_director_is_not_an_implicit_uniform_request(self):
        # No decisions at all must report not_applicable, never a uniform approval.
        m = self.base_manifest()
        self.assertEqual(m['style_review']['mode'], 'editorial')
        self.assertEqual(m['style_review']['weight']['status'], 'not_applicable')
        self.assertNotEqual(m['style_review'].get('mode'), 'uniform_requested')

    def test_uniform_requires_an_explicit_nonempty_request(self):
        m = self.base_manifest()
        m['style_review'] = dict(mode='uniform_requested', user_request='  ')
        with self.assertRaisesRegex(ValueError, 'explicit user request'):
            validate_style(m)


class StyleSummaryTests(unittest.TestCase):
    def test_summary_counts_every_axis(self):
        m = resolve(host(6), [], STYLE,
                    dict(emphasis_source_indices=[dict(source_index=1, weight='payoff')],
                         italic_spans=[[2, 2]],
                         size_tiers=[dict(source_index=4, tier='emph')],
                         quote_spans=[[0, 1]]), None)
        counts = style_counts(m)
        self.assertEqual(counts['weights']['payoff'], 1)
        self.assertEqual(counts['quoted_spans'], 1)
        self.assertIn('emph', counts['size_tiers'])
        self.assertTrue(any(k.endswith('_italic') for k in counts['runs_by_voice_and_slant']))

    def test_a_flat_summary_is_visible_as_flat(self):
        """A totally flat result must be legible as flat, so it can be caught."""
        counts = style_counts(resolve(host(4), [], STYLE, None, None))
        self.assertEqual(set(counts['weights']), {'base'})
        self.assertEqual(set(counts['size_tiers']), {'base'})
        self.assertEqual(counts['quoted_spans'], 0)
        self.assertEqual(counts['represented_voice_spans'], 0)
        self.assertEqual(counts['style_source'], 'NONE_ALL_BASE_WEIGHT_UPRIGHT')




class ReviewRegressionTests(unittest.TestCase):
    """Pins the four defects a code-review pass found on 2026-09-18."""

    def test_a_span_matching_no_word_is_refused_not_silently_recorded(self):
        # It used to be ignored AND still written into the manifest, so the
        # pre-build summary reported a represented voice that never existed.
        for decisions in (dict(represented_voice_spans=[[900, 901]]),
                          dict(italic_spans=[[900, 901]]),
                          dict(quote_spans=[[900, 901]])):
            with self.subTest(decisions=decisions), self.assertRaises(ValueError):
                resolve(host(6), [], STYLE, decisions, None)

    def test_a_partially_overlapping_span_is_still_accepted(self):
        m = resolve(host(6), [], STYLE, dict(italic_spans=[[4, 900]]), None)
        self.assertTrue(any(w['italic'] for c in m['render_segments'] for w in c['words']))

    def test_editorial_group_ends_are_not_overridden_by_the_word_cap(self):
        m = resolve(host(6), [], dict(STYLE, max_words_per_card=3),
                    dict(group_ends=[5]), None)
        self.assertEqual([len(c['words']) for c in m['cards']], [6])

    def test_the_word_cap_still_applies_when_no_group_ends_are_given(self):
        m = resolve(host(6), [], dict(STYLE, max_words_per_card=3), None, None)
        self.assertEqual([len(c['words']) for c in m['cards']], [3, 3])

    def test_a_cut_still_splits_even_inside_an_editorial_group(self):
        # physical facts about the footage outrank the grouping decision
        m = resolve(host(6), [], dict(STYLE, max_words_per_card=6),
                    dict(group_ends=[5]), None)
        self.assertEqual(len(m['cards']), 1)
        m = resolve(host(6), [10], dict(STYLE, max_words_per_card=6),
                    dict(group_ends=[5]), None)
        self.assertGreater(len(m['cards']), 1)

    def test_expected_face_reports_a_weightless_word_instead_of_crashing(self):
        from verify_style_readback import expected_face
        profile = dict(donors=dict(host=dict(faces={'base': 'ProximaNova-Medium'})))
        self.assertIsNone(expected_face(profile, dict(speaker='host'), dict(text='x')))
        self.assertEqual(
            expected_face(profile, dict(speaker='host'), dict(weight='base')),
            'ProximaNova-Medium')

    def test_a_profile_that_declares_no_faces_is_refused_not_guessed(self):
        # 'strong' meant Extrabold under the old contract and Bold on the ladder,
        # so weight names must never be used to infer faces.
        import json, tempfile
        from pathlib import Path
        from caption_font_preflight import fonts_from_profile
        p = Path(tempfile.mkdtemp()) / 'legacy.json'
        p.write_text(json.dumps(dict(donors=dict(
            host=dict(item_id='1', runs=dict(base=0, strong=2), italic=False)))))
        with self.assertRaises(SystemExit):
            fonts_from_profile(p)

    def test_a_profile_declaring_faces_reports_exactly_those(self):
        import json, tempfile
        from pathlib import Path
        from caption_font_preflight import fonts_from_profile
        p = Path(tempfile.mkdtemp()) / 'nested.json'
        p.write_text(json.dumps(dict(donors=dict(host=dict(
            item_id='1', faces={'base': 'ProximaNova-Medium',
                                'payoff_italic': 'ProximaNova-BlackIt'})))))
        self.assertEqual(fonts_from_profile(p),
                         {'ProximaNova-Medium', 'ProximaNova-BlackIt'})


class SingleLineWidthTests(unittest.TestCase):
    """A single-line profile must never hand Premiere a card that wraps.

    2026-09-22. Alex is max_lines:1, but nothing enforced a width budget, so
    'even fucking communicating?' (2235px against a 1650px budget) was re-flowed
    by Premiere onto a second line and read as scrambled word order on screen.
    """

    def wide_stream(self, n=6):
        # long tokens so a 3-word card certainly exceeds any small budget
        return [dict(text='communicating', start=i * 0.3, end=i * 0.3 + 0.2,
                     source_indices=[i], physical_speaker='host', sentence_end=False)
                for i in range(n)]

    def test_no_budget_means_the_word_cap_alone_decides(self):
        m = resolve(self.wide_stream(6), [], dict(STYLE, max_words_per_card=3), None, None)
        self.assertEqual([len(c['words']) for c in m['cards']], [3, 3])

    def test_a_width_budget_splits_before_a_card_can_overflow(self):
        # vendored faces: ship with the skill, so this measures on any machine
        narrow = dict(STYLE, max_words_per_card=3, max_text_width_px=400,
                      fonts=VENDORED)
        m = resolve(self.wide_stream(6), [], narrow, None, None)
        self.assertTrue(all(len(c['words']) < 3 for c in m['cards']),
                        f"budget did not split: {[c['text'] for c in m['cards']]}")

    def test_a_budget_without_faces_is_refused_rather_than_ignored(self):
        bad = dict(STYLE, max_text_width_px=400)
        bad.pop('fonts')
        with self.assertRaisesRegex(ValueError, 'style.fonts'):
            resolve(self.wide_stream(4), [], bad, None, None)

    def test_a_single_word_is_never_split_away_to_satisfy_the_budget(self):
        # one token wider than the budget still has to ship as its own card
        tiny = dict(STYLE, max_words_per_card=3, max_text_width_px=10,
                    fonts=VENDORED)
        m = resolve(self.wide_stream(3), [], tiny, None, None)
        self.assertEqual([len(c['words']) for c in m['cards']], [1, 1, 1])
        owned = [i for s in m['render_segments'] if s['source_coverage_owner']
                 for w in s['words'] for i in w['source_indices']]
        self.assertEqual(sorted(owned), [0, 1, 2])

    def test_faces_are_not_stamped_unless_requested(self):
        # a stamped face would contradict the weight a director assigns later
        plain = dict(STYLE); plain.pop('emit_font_postscript')
        m = resolve(self.wide_stream(3), [], plain, None, None)
        self.assertTrue(all('font_postscript' not in w
                            for c in m['render_segments'] for w in c['words']))


if __name__ == '__main__':
    unittest.main()
