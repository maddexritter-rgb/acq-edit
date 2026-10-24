"""Caption handoff and mutations against saved native synthetic caption tracks."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'python'))
sys.path.insert(0, str(ROOT / 'distribution/skills/caption-clips/scripts'))
import caption_plan
from common import sha, fingerprint


class CaptionPlanTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.patch = patch.object(caption_plan, 'SKILLS', ROOT / 'distribution/skills')
        self.patch.start(); self.addCleanup(self.patch.stop)
        self.project = {'id': 'project', 'root': str(self.root), 'backend': 'filmcraft'}
        self.spec = {'backend': 'filmcraft', 'clipId': 'clip', 'width': 640, 'height': 360,
                     'fps': {'numerator': 25, 'denominator': 1}, 'cuts': [{'recordFrame': 0, 'frames': 25}, {'recordFrame': 25, 'frames': 50}]}
        self.profile = self.root / 'profile.json'
        self.profile.write_text(json.dumps({'allow_quote_italics': True, 'guest_turn_italics': False,
            'caption_hold_through_seconds': .75, 'caption_trailing_hold_seconds': .35, 'filmcraft_caption_motion': 'measured_fast_settle'}))
        style = {'font': 'Arial', 'fontStyle': 'Bold', 'italicStyle': 'Bold Italic', 'size': 36,
                 'renderedFontPx': 36, 'position': [320, 220], 'color': '#ffffff'}
        self.handoff = {'schema': 'acq-edit/caption-handoff-v1', 'owner': 'caption-clips',
            'projectId': 'project', 'clipId': 'clip', 'cutsFingerprint': fingerprint(self.spec['cuts']),
            'profile': {'path': str(self.profile), 'sha256': sha(self.profile)}, 'cards': [
                {'id': 'narration', 'start_frame': 0, 'speech_end': .45, 'text': 'i can do this.', 'quote': False, 'style': copy.deepcopy(style)},
                {'id': 'quote', 'start_frame': 15, 'speech_end': 1.15, 'text': 'i can do this?', 'quote': True, 'style': copy.deepcopy(style)},
                {'id': 'payoff', 'start_frame': 40, 'speech_end': 2.6, 'text': "that's what I said.", 'quote': False, 'style': copy.deepcopy(style)}]}
        self.native = json.loads((ROOT / 'tests/fixtures/filmcraft-caption-native.json').read_text())

    def derive(self):
        file = self.root / 'handoff.json'; file.write_text(json.dumps(self.handoff))
        reference = {'path': str(file), 'sha256': sha(file)}
        return caption_plan.derive(self.project, self.spec, reference), reference

    def verify(self):
        derived, _ = self.derive()
        file = self.root / 'native.fcproj'; file.write_text(json.dumps(self.native))
        return caption_plan.verify_native(file, self.spec, derived, 254016000000 // 25)

    def params(self, track=1, card=0, effect='graphic_text'):
        item = self.native['project']['items']['1']['kind']['Sequence']['video_tracks'][track]['items'][card]
        return next(e['params'] for e in item['effects'] if e['effect'] == effect)

    def test_canonical_text_quotes_holds_and_saved_native_animation(self):
        derived, reference = self.derive()
        self.assertEqual([c['text'] for c in derived['captions']], ['I can do this', '“I can do this?”', "that's what I said"])
        self.assertEqual([c['endFrame'] for c in derived['captions']], [15, 40, 74])
        self.assertEqual(self.verify()['status'], 'NATIVE_CAPTION_CONTRACT_VALID')
        self.spec.update(captions=derived['captions'], captionContract={**reference, 'helperHashes': derived['helperHashes']})
        self.assertEqual(caption_plan.validate(self.project, self.spec)['shadowProfile'], 'filmcraft-visible-two-layer-v1')
        self.spec['captionContract']['helperHashes']['filmcraft_shadow.py'] = 'stale'
        with self.assertRaisesRegex(RuntimeError, 'helpers changed'):
            caption_plan.validate(self.project, self.spec)

    def test_stale_cut_clock_profile_or_backend_refuses(self):
        original = copy.deepcopy(self.spec)
        self.spec['cuts'][0]['frames'] = 24
        with self.assertRaisesRegex(RuntimeError, 'stale cut clocks'): self.derive()
        self.spec = original; self.spec['backend'] = 'resolve'
        with self.assertRaisesRegex(RuntimeError, 'FilmCraft native adapter'): self.derive()
        self.spec['backend'] = 'filmcraft'; self.profile.write_text('{}')
        with self.assertRaisesRegex(RuntimeError, 'profile changed'): self.derive()

    def test_unclassified_quote_unknown_effect_and_overlapping_speech_refuse(self):
        original = copy.deepcopy(self.handoff)
        del self.handoff['cards'][1]['quote']
        with self.assertRaisesRegex(ValueError, 'explicit quote'): self.derive()
        self.handoff = copy.deepcopy(original); self.handoff['cards'][0]['style']['stroke'] = True
        with self.assertRaisesRegex(RuntimeError, 'Unsupported caption style'): self.derive()
        self.handoff = copy.deepcopy(original); self.handoff['cards'][0]['speech_end'] = .8
        with self.assertRaisesRegex(RuntimeError, 'Overlapping spoken cards'): self.derive()
        self.handoff = copy.deepcopy(original); del self.handoff['cards'][1]['style']['italicStyle']
        with self.assertRaisesRegex(RuntimeError, 'Real italic face'): self.derive()

    def test_meaning_bearing_omission_is_not_silently_removed(self):
        self.handoff['omissions'] = [{'word': 'not', 'start': .5, 'end': .6}]
        with self.assertRaisesRegex(ValueError, 'Meaning-bearing'): self.derive()

    def test_native_apostrophe_rewrite_or_wrong_quote_face_refuses(self):
        original = copy.deepcopy(self.native)
        self.params(card=2)['text']['value']['Text'] = 'that’s what I said'
        with self.assertRaisesRegex(ValueError, 'punctuation'): self.verify()
        self.native = original; self.params(card=1)['font_style']['value']['Text'] = 'Bold'
        with self.assertRaisesRegex(ValueError, 'italic'): self.verify()

    def test_native_shadow_foreground_and_transform_changes_refuse(self):
        original = copy.deepcopy(self.native)
        self.params()['shadow_opacity']['value']['Float'] = 30
        with self.assertRaisesRegex(RuntimeError, 'shadow differs'): self.verify()
        self.native = copy.deepcopy(original); self.params(track=3)['fill_color']['value']['Color'] = [0, 0, 0, 1]
        with self.assertRaisesRegex(RuntimeError, 'foreground color'): self.verify()
        self.native = copy.deepcopy(original)
        for track in [1, 2, 3]: self.params(track=track, effect='motion')['scale']['value']['Float'] = 150
        with self.assertRaisesRegex(RuntimeError, 'clip transform'): self.verify()

    def test_matching_but_wrong_animation_curves_are_rejected(self):
        for track in [1, 2, 3]:
            keys = self.params(track=track, effect='motion')['position']['keyframes']
            keys[1]['time'] += 100
        with self.assertRaisesRegex(RuntimeError, 'arrival curve'): self.verify()

    def test_hidden_native_caption_lane_refuses(self):
        self.native['project']['items']['1']['kind']['Sequence']['video_tracks'][3]['enabled'] = False
        with self.assertRaisesRegex(RuntimeError, 'lane visibility'): self.verify()

    def test_animated_shadow_property_cannot_pass_on_its_base_value(self):
        self.params()['shadow_opacity']['keyframes'] = [{'time': 100, 'value': {'Float': 0}, 'interp': 'Linear'}]
        with self.assertRaisesRegex(RuntimeError, 'Animated graphic properties'): self.verify()


if __name__ == '__main__': unittest.main()
