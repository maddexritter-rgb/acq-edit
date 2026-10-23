"""build() gates that fire BEFORE the project is parsed.

These need no donor project, because premiere_native_cards.build() is ordered to
refuse early: the style review runs first, then the output-collision check, then
the project hash. Anything that requires a real styled-text donor payload is
covered by the live runs recorded in the skill's UAT, not here -- a synthetic
Premiere Source Text FlatBuffer is not yet part of this repo's fixtures.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import premiere_native_cards as native

REVIEWED = dict(mode='uniform_requested', user_request='the user asked for uniform styling')


def manifest(**over):
    card = dict(id='card-000', start_frame=0, end_frame=10, y_pct=50.0, font_size_px=160,
                speaker='host', text='a b',
                words=[dict(text='a', weight='base', font_postscript='F', color='FFFFFF',
                            italic=False, source_indices=[0]),
                       dict(text='b', weight='base', font_postscript='F', color='FFFFFF',
                            italic=False, source_indices=[1])])
    m = dict(frame_rate=dict(numerator=24000, denominator=1001),
             render_segments=[card], style_review=dict(REVIEWED))
    m.update(over)
    return m


def profile(**over):
    p = dict(project_sha256='0' * 64, sequence_uid='seq', track_index=5,
             expected_item_ids=['1'], y_pct=50.0,
             donors=dict(host=dict(item_id='1', runs=dict(base=0, strong=1),
                                   color='FFFFFF', italic=False)))
    p.update(over)
    return p


class BuildGateTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.project = self.dir / 'prepared.prproj'
        self.project.write_bytes(b'not a real project')
        self.profile = self.dir / 'profile.json'
        self.manifest = self.dir / 'manifest.json'
        self.profile.write_text(json.dumps(profile()))
        self.manifest.write_text(json.dumps(manifest()))
        self.out = self.dir / 'out.prproj'

    def build(self):
        return native.build(self.project, self.profile, self.manifest, self.out, 'seq name')

    def test_refuses_when_the_output_already_exists(self):
        self.out.write_bytes(b'')
        with self.assertRaises(FileExistsError):
            self.build()

    def test_refuses_when_only_the_receipt_already_exists(self):
        self.out.with_suffix('.receipt.json').write_text('{}')
        with self.assertRaises(FileExistsError):
            self.build()

    def test_missing_style_review_refuses_before_writing_anything(self):
        m = manifest()
        del m['style_review']
        self.manifest.write_text(json.dumps(m))
        with self.assertRaisesRegex(ValueError, 'Missing editorial style review'):
            self.build()
        self.assertFalse(self.out.exists())
        self.assertFalse(self.out.with_suffix('.receipt.json').exists())

    def test_uniform_mode_without_a_user_request_refuses(self):
        self.manifest.write_text(json.dumps(
            manifest(style_review=dict(mode='uniform_requested', user_request='   '))))
        with self.assertRaisesRegex(ValueError, 'explicit user request'):
            self.build()

    def test_style_review_is_checked_before_the_project_hash(self):
        # Both are wrong; the style review must be the reported failure.
        m = manifest()
        del m['style_review']
        self.manifest.write_text(json.dumps(m))
        self.profile.write_text(json.dumps(profile(project_sha256='f' * 64)))
        with self.assertRaisesRegex(ValueError, 'Missing editorial style review'):
            self.build()

    def test_stale_project_hash_refuses_before_writing_anything(self):
        self.profile.write_text(json.dumps(profile(project_sha256='f' * 64)))
        with self.assertRaisesRegex(ValueError, 'Prepared project changed'):
            self.build()
        self.assertFalse(self.out.exists())

    def test_hash_mismatch_is_reported_before_the_project_is_parsed(self):
        # The project bytes are not valid Premiere XML at all; if the hash gate did
        # not fire first this would surface as a parse error instead.
        self.profile.write_text(json.dumps(profile(project_sha256='f' * 64)))
        with self.assertRaises(ValueError) as caught:
            self.build()
        self.assertIn('Prepared project changed', str(caught.exception))


class VerifyGateTests(unittest.TestCase):
    def test_verify_rejects_a_receipt_whose_project_is_unreadable(self):
        d = Path(tempfile.mkdtemp())
        project = d / 'x.prproj'
        project.write_bytes(b'not a real project')
        receipt = d / 'x.receipt.json'
        receipt.write_text(json.dumps(dict(sequence_uid='seq', track_index=5,
                                           sequence_name='n', cards=[])))
        with self.assertRaises(Exception):
            native.verify(project, receipt)


if __name__ == '__main__':
    unittest.main()
