"""Canvas contract regressions (2026-09-23 sandbox, three-profile native build).

A paragraph-text donor authored on a 2160x3840 template and cloned into a
1080x1920 sequence (a) rendered off to the right and (b) could not be clicked to
edit, while every text/run/timing readback passed. Also covers the empty caption
track, the director's dropped represented-voice colour, and canvas-scaled profiles.
"""
import struct
import sys
import unittest
import xml.etree.ElementTree as E
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from native_graphics.decode_graphic_text import document_box, scale_text_boxes, text_boxes
from native_graphics.native_canvas import geometry_problems, sequence_canvas
from native_graphics.native_caption_batch_graph import insert_batch
from native_graphics.resolve_director_style import resolve as resolve_style
from resolve_cards import (director_voice_runs, style_from_profile, with_director_voice_spans,
                           _spans)
from caption_profiles import load_profile


def payload(box=None, copies=0):
    """A minimal Source Text FlatBuffer: magic, root -> document, optional box fields."""
    fields = 4 if box else 2
    buf = bytearray(8) + b'\x44\x33\x22\x11'
    buf += struct.pack('<I', 4)                      # 12: root at 16
    buf += struct.pack('<i', 16 - 24)                # 16: root vtable at 24
    buf += struct.pack('<I', 20)                     # 20: document at 40
    buf += struct.pack('<HHH', 6, 8, 4) + b'\0\0'    # 24: root vtable
    buf += bytearray(8)                              # 32
    tables = [40] + [72 + 16 * k for k in range(copies)]
    vtable = 56
    body = bytearray(max(max(tables) + 16, vtable + 16) - len(buf))
    buf += body
    struct.pack_into('<' + 'H' * (2 + fields), buf, vtable, 4 + 2 * fields, 12,
                     *((0, 0, 4, 8) if box else (0, 0)))
    for t in tables:
        struct.pack_into('<i', buf, t, t - vtable)
        if box:
            struct.pack_into('<ff', buf, t + 4, *box)
    return bytes(buf)


class TextBoxDecode(unittest.TestCase):
    def test_paragraph_box_is_read_by_schema_and_every_copy_scales(self):
        data = payload(box=(1770.0, 1152.0), copies=2)
        self.assertEqual(document_box(data), (1770.0, 1152.0))
        self.assertEqual(len(text_boxes(data)), 3)
        scaled, n = scale_text_boxes(data, 0.5, 0.5)
        self.assertEqual(n, 3)
        self.assertEqual({(b['width'], b['height']) for b in text_boxes(bytes(scaled))}, {(885.0, 576.0)})

    def test_point_text_has_no_box(self):
        self.assertIsNone(document_box(payload()))
        self.assertEqual(text_boxes(payload()), [])


class Geometry(unittest.TestCase):
    CANVAS = (1080, 1920)

    def problems(self, **kw):
        base = dict(canvas=self.CANVAS, media=(1080, 1920), position=(0.0902777761, 0.35000002),
                    box=(885.0, 576.0), mode='donor', y_pct=50.0)
        base.update(kw)
        return geometry_problems(**base)

    def test_retargeted_donor_passes(self):
        self.assertEqual(self.problems(), [])

    def test_unscaled_2160_donor_is_refused(self):
        # v1: rendered at ~(982, 1248) on 1080x1920, off to the right.
        p = self.problems(media=(2160, 3840), box=(1770.0, 1152.0))
        self.assertTrue(any('media is 2160x3840' in x for x in p))
        self.assertTrue(any('982.5' in x for x in p))

    def test_moving_the_anchor_is_not_a_fix(self):
        # v2: centred render, but a 1770px box hanging off the frame -> uneditable.
        p = self.problems(media=(2160, 3840), box=(1770.0, 1152.0), position=(-0.33194, 0.2))
        self.assertTrue(any('larger than the 1080x1920 frame' in x for x in p))
        self.assertTrue(any('extends off' in x for x in p))

    def test_scaling_only_the_box_is_not_a_fix(self):
        # v3: centred render, edit box drawn through the 2160 media frame.
        p = self.problems(media=(2160, 3840))
        self.assertEqual(len(p), 1)
        self.assertIn('Program Monitor edit box', p[0])

    def test_point_text_style_donor_in_explicit_mode_needs_only_matching_media(self):
        self.assertEqual(self.problems(box=None, mode='explicit_centered', position=(0.37, 0.4)), [])
        self.assertTrue(self.problems(box=None, mode='explicit_centered', media=(2160, 3840)))

    def test_paragraph_box_in_explicit_mode_is_refused(self):
        self.assertTrue(any('explicit_centered' in x for x in self.problems(mode='explicit_centered')))

    def test_legacy_receipt_without_intent_still_checks_media_and_fit(self):
        self.assertEqual(self.problems(y_pct=None), [])
        self.assertTrue(self.problems(y_pct=None, media=(2160, 3840)))


class SequenceCanvas(unittest.TestCase):
    def test_reads_premiere_saved_frame_rect(self):
        root = E.fromstring('<Project><Sequence ObjectUID="s"><TrackGroups><TrackGroup><Second ObjectRef="1"/>'
                            '</TrackGroup></TrackGroups></Sequence><VideoTrackGroup ObjectID="1">'
                            '<FrameRect>0,0,1080,1920</FrameRect></VideoTrackGroup></Project>')
        self.assertEqual(sequence_canvas(root, 's'), (1080, 1920))

    def test_missing_frame_rect_fails_closed(self):
        root = E.fromstring('<Project><Sequence ObjectUID="s"><TrackGroups><TrackGroup><Second ObjectRef="1"/>'
                            '</TrackGroup></TrackGroups></Sequence><VideoTrackGroup ObjectID="1"/></Project>')
        with self.assertRaisesRegex(ValueError, 'FrameRect'):
            sequence_canvas(root, 's')


class EmptyTrack(unittest.TestCase):
    def test_never_used_track_accepts_expected_empty(self):
        # A Premiere track that never held a clip saves ClipItems with no TrackItems.
        root = E.fromstring('''<Project><Sequence ObjectUID="seq"><TrackGroups><TrackGroup>
        <Second ObjectRef="1"/></TrackGroup></TrackGroups></Sequence>
        <VideoTrackGroup ObjectID="1"><TrackGroup><Tracks><Track Index="1" ObjectURef="track"/>
        </Tracks></TrackGroup></VideoTrackGroup><VideoClipTrack ObjectUID="track"><ClipTrack>
        <ClipItems Version="3"><MediaType>x</MediaType><Index>1</Index></ClipItems>
        </ClipTrack></VideoClipTrack><VideoClipTrackItem ObjectID="new"><ClipTrackItem><TrackItem>
        <Start>100</Start><End>200</End></TrackItem></ClipTrackItem></VideoClipTrackItem></Project>''')
        receipt = [dict(item_id='new', timing=dict(start_ticks='100', end_ticks='200'))]
        result = insert_batch(root, sequence_uid='seq', track_index=1, expected_old_item_ids=[],
                              receipts=receipt)
        self.assertEqual(result['inserted_count'], 1)
        items = root.find('VideoClipTrack/ClipTrack/ClipItems')
        self.assertEqual(items[0].tag, 'TrackItems')
        self.assertEqual(items[0][0].get('ObjectRef'), 'new')


class CanvasScaledProfile(unittest.TestCase):
    def test_profile_scales_to_the_target_canvas(self):
        style = style_from_profile(load_profile('alex'), {}, (1080, 1920))
        self.assertEqual(style['canvas_px'], [1080, 1920])
        self.assertAlmostEqual(style['font_size_px'], 80.0)
        self.assertAlmostEqual(style['max_text_width_px'], 825.0, places=2)

    def test_hand_sized_job_with_a_target_canvas_is_refused(self):
        with self.assertRaisesRegex(ValueError, 're-declare'):
            style_from_profile(load_profile('alex'), {'font_size_px': 80}, (1080, 1920))

    def test_no_target_records_the_profile_canvas_so_the_builder_can_refuse(self):
        self.assertEqual(style_from_profile(load_profile('alex'), {})['canvas_px'], [2160, 3840])

    def test_aspect_mismatch_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'aspect'):
            style_from_profile(load_profile('alex'), {}, (1920, 1080))


class DirectorVoice(unittest.TestCase):
    WORDS = [dict(text=t, source_indices=[i]) for i, t in
             enumerate('simply by saying we are going to get it'.split())]
    STREAM = {'words': {'3': {'c': 'guest'}, '4': {'c': 'guest'}, '5': {'c': 'guest', 'i': True},
                        '0': {'w': 'strong'}}, 'voice_spans': []}

    def test_per_word_colour_becomes_a_source_span(self):
        self.assertEqual(director_voice_runs(self.STREAM, self.WORDS), [(3, 5)])
        spans = with_director_voice_spans(None, self.STREAM, self.WORDS)['represented_voice_spans']
        self.assertEqual([(s['from'], s['to'], s['voice']) for s in spans], [(3, 5, 'guest')])

    def test_stream_from_a_different_normalization_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'different normalization'):
            director_voice_runs({'words': {'40': {'c': 'guest'}}}, self.WORDS)

    def test_style_pass_refuses_a_voice_the_grouping_never_applied(self):
        manifest = {'nominal_font_size_px': 80.0, 'cards': [dict(
            id='c1', speaker='host', normalized_indices=[3, 4],
            words=[dict(text='we'), dict(text='are')])]}
        stream = dict(self.STREAM, style_provenance={'engine': 'caption_director', 'mode': 'claude_cli'})
        with self.assertRaisesRegex(ValueError, 'director-style'):
            resolve_style(manifest, stream)

    def test_base_size_defaults_to_the_canvas_scaled_nominal_and_refuses_a_mismatch(self):
        manifest = {'nominal_font_size_px': 80.0, 'canvas_px': [1080, 1920], 'cards': [dict(
            id='c1', speaker='host', normalized_indices=[0], words=[dict(text='simply')])]}
        stream = dict(self.STREAM, style_provenance={'engine': 'caption_director', 'mode': 'claude_cli'})
        self.assertEqual(resolve_style(manifest, stream)['render_segments'][0]['font_size_px'], 80.0)
        with self.assertRaisesRegex(ValueError, 'differs from the manifest nominal'):
            resolve_style(manifest, stream, 160)


class SpanKeys(unittest.TestCase):
    def test_start_end_alias(self):
        self.assertEqual(_spans([{'start': 2, 'end': 4}], 'x')[0][:2], (2, 4))


if __name__ == '__main__':
    unittest.main()
