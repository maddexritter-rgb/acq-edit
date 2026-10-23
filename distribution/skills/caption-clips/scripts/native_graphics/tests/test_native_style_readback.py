"""End-to-end proof that weight, italic and card size reach the SAVED project.

This is the test the style contract actually needs: it builds a manifest carrying a
strong-weight word, an italic voice and a non-base size tier, runs the real builder
against a real prepared donor project, then decodes the styling back out of the
saved .prproj and compares it to the manifest run by run.

A donor project cannot be committed (licensed fonts and brand presets live inside
it), so this skips unless both are provided:

    NATIVE_DONOR_PROJECT=/path/to/prepared.prproj
    NATIVE_DONOR_PROFILE=/path/to/native_style_profile.json

The profile must match that project's hash, as the builder requires anyway. An
absent fixture is reported as a skip, never as a pass.
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import premiere_native_cards as native
from verify_style_readback import collect


def fixture_paths():
    project, profile = os.environ.get('NATIVE_DONOR_PROJECT'), os.environ.get('NATIVE_DONOR_PROFILE')
    if not project or not profile:
        raise unittest.SkipTest('Set NATIVE_DONOR_PROJECT and NATIVE_DONOR_PROFILE '
                                'to a prepared donor project and its matching profile')
    project, profile = Path(project), Path(profile)
    if not project.exists() or not profile.exists():
        raise unittest.SkipTest('Donor fixture paths do not exist')
    return project, profile


class StyleReachesTheSavedProjectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.project, cls.profile_path = fixture_paths()
        cls.profile = json.loads(cls.profile_path.read_text())
        donors = cls.profile['donors']
        if 'host' not in donors:
            raise unittest.SkipTest('Profile needs at least a host donor')
        cls.donors = donors
        cls.root = native.load(cls.project)
        cls.shared = native.pool(cls.root)
        cls.ids = native.objects(cls.root)

    def faces(self, voice, italic=False):
        """The exact faces this donor carries, per weight, for one slant.

        Handles both profile shapes: a legacy flat {weight: index} and the nested
        {weight: {upright: i, italic: i}} the full-ladder donor uses.
        """
        from native_graphics.decode_graphic_text import decode_runs
        d = self.donors[voice]
        runs = decode_runs(native.payload(native.text_node(self.root, self.ids[d['item_id']]),
                                          self.shared))
        out = {}
        for weight, mapping in d['runs'].items():
            if isinstance(mapping, dict):
                index = mapping.get('italic' if italic else 'upright')
                if index is None:
                    continue
            else:
                index = mapping
            out[weight] = runs[index]['font_postscript']
        return out

    def card(self, cid, voice, words, start, end, size_px, tier, italic=None):
        d = self.donors[voice]
        slant = d.get('italic', False) if italic is None else italic
        faces = self.faces(voice, italic=bool(slant))
        out = []
        for n, (text, weight) in enumerate(words):
            out.append(dict(text=text, weight=weight, font_postscript=faces[weight],
                            color=d['color'], italic=bool(slant), source_indices=[n]))
        return dict(id=cid, start_frame=start, end_frame=end, semantic_card_id=cid,
                    animation_elapsed_frames=0, continuation=False,
                    source_coverage_owner=True, speaker=voice,
                    y_pct=self.profile['y_pct'], size_tier=tier, font_size_px=size_px,
                    text=' '.join(t for t, _ in words), words=out)

    def build_varied(self, tmp):
        """One base card, one card with a strong word, and a non-base size tier."""
        voices = [v for v in ('host', 'guest') if v in self.donors]
        heavy = next(w for w in ('payoff', 'emphasis', 'strong')
                     if w in self.faces(voices[0]))
        nested = isinstance(self.donors[voices[0]]['runs'].get('base'), dict)
        segs = [
            self.card('card-000', voices[0], [('plain', 'base'), ('words', 'base')], 0, 24, 160, 'base'),
            self.card('card-001', voices[0], [('this', 'base'), ('matters', heavy)], 24, 48, 160, 'base'),
            self.card('card-002', voices[-1], [('bumped', 'base')], 48, 72, 176, 'peak',
                      italic=True if nested else None),
        ]
        self.heavy = heavy
        review = dict(
            mode='editorial', reviewed=True, segment_ids=[s['id'] for s in segs],
            weight=dict(status='applied', reason='one concrete emphasis for the readback proof',
                        targets=[dict(segment_id='card-001', word_index=1,
                                      text='matters', value=heavy)]),
            size=dict(status='applied', reason='one bumped card for the readback proof',
                      targets=[dict(segment_id='card-002', tier='peak', font_size_px=176)]),
            italic=(dict(status='applied', reason='the donor carries a real italic face',
                         targets=[dict(segment_id='card-002', word_index=0,
                                       text='bumped', value=True)])
                    if (nested or self.donors[voices[-1]].get('italic')) else
                    dict(status='not_applicable', reason='no italic donor in this profile')),
        )
        manifest = dict(frame_rate=dict(numerator=24000, denominator=1001),
                        render_segments=segs, style_review=review)
        mpath = tmp / 'manifest.json'
        mpath.write_text(json.dumps(manifest))
        out = tmp / 'built.prproj'
        receipt = native.build(self.project, self.profile_path, mpath, out, 'style readback proof')
        return manifest, out, receipt

    def test_weight_italic_and_size_all_survive_into_the_saved_project(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            manifest, out, receipt = self.build_varied(tmp)
            findings, faces, sizes, tiers, count, weights, slants = collect(
                out, receipt, manifest, self.profile)

            self.assertEqual(findings, [], f'saved project disagrees with the manifest: {findings[:5]}')
            self.assertEqual(count, 3)
            # Variation must be REAL, not merely consistent: a flattened build would
            # also produce zero mismatches against a flattened manifest.
            self.assertGreaterEqual(len(faces), 2, f'only one face reached the project: {faces}')
            self.assertGreaterEqual(len([s for s in sizes if s]), 2,
                                    f'only one size reached the project: {sizes}')
            self.assertIn('peak', tiers)

    def test_a_flattened_saved_project_is_detected_as_a_mismatch(self):
        """The guard against a test that passes on a flat build."""
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            manifest, out, receipt = self.build_varied(tmp)
            # Claim every word was strong; the saved project has a base run, so this must fail.
            for seg in manifest['render_segments']:
                for w in seg['words']:
                    w['weight'] = self.heavy
                    w['font_postscript'] = self.faces(
                        seg['speaker'], italic=bool(w['italic']))[self.heavy]
            findings, *_ = collect(out, receipt, manifest)
            self.assertTrue(any(f['axis'] == 'font_postscript' for f in findings),
                            'a flattened-vs-styled disagreement went undetected')

    def test_a_size_claim_the_project_does_not_carry_is_detected(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            manifest, out, receipt = self.build_varied(tmp)
            for seg in manifest['render_segments']:
                seg['font_size_px'] = 999
            findings, *_ = collect(out, receipt, manifest)
            self.assertTrue(any(f['axis'] == 'font_size_px' for f in findings))


if __name__ == '__main__':
    unittest.main()
