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

    def test_profile_case_and_reviewed_emphasis_ranges(self):
        from filmcraft_caption_contract import normalize_profile_case, character_styles
        profile = {'normalization': 'oliver_v2', 'proper_names': ['Steve']}
        self.assertEqual(normalize_profile_case("No Steve I'm the CFO", profile), "no Steve I'm the CFO")
        self.assertEqual(normalize_profile_case('They want fast results', profile), 'they want fast results')
        self.assertEqual(normalize_profile_case('Sentence Case', {}), 'Sentence Case')
        card = {'text': 'sell outcomes', 'italic': False, 'style': {'emphasis': [
            {'start': 5, 'end': 13, 'text': 'outcomes', 'fontStyle': 'Bold', 'italicStyle': 'Bold It',
             'fontPostscript': 'Example-Bold', 'italicPostscript': 'Example-BoldIt'}]}}
        self.assertEqual(character_styles(card)[0]['fontStyle'], 'Bold')
        card['italic'] = True
        self.assertEqual(character_styles(card)[0]['fontStyle'], 'Bold It')
        card['text'] = 'sell anything'
        with self.assertRaisesRegex(ValueError, 'text changed'):
            character_styles(card)

    def test_character_emphasis_must_survive_on_every_native_lane(self):
        profile = json.loads(self.profile.read_text())
        profile['allow_weight_variation'] = True
        self.profile.write_text(json.dumps(profile))
        self.handoff['profile']['sha256'] = sha(self.profile)
        self.handoff['cards'][0]['style']['emphasis'] = [
            {'start': 2, 'end': 5, 'text': 'can', 'fontStyle': 'Black', 'italicStyle': 'Black It',
             'fontPostscript': 'Example-Black', 'italicPostscript': 'Example-BlackIt'}]
        layers = self.native['project']['items']['1']['kind']['Sequence']['video_tracks'][1:4]
        for lane in layers:
            graphic = next(e for e in lane['items'][0]['effects'] if e['effect'] == 'graphic_text')
            graphic['layer'] = {'runs': [{'start': 2, 'end': 5, 'fontStyle': 'Black', 'fauxBold': False, 'fauxItalic': False}]}
        self.assertEqual(self.verify()['status'], 'NATIVE_CAPTION_CONTRACT_VALID')
        graphic['layer']['runs'] = []
        with self.assertRaisesRegex(RuntimeError, 'character emphasis differs'):
            self.verify()

    def test_unrequested_native_character_override_refuses(self):
        item = self.native['project']['items']['1']['kind']['Sequence']['video_tracks'][1]['items'][0]
        graphic = next(e for e in item['effects'] if e['effect'] == 'graphic_text')
        graphic['layer'] = {'runs': [{'start': 0, 'end': 1, 'fontStyle': 'Black'}]}
        with self.assertRaisesRegex(RuntimeError, 'character emphasis differs'):
            self.verify()

    def test_stale_cut_clock_profile_or_backend_refuses(self):
        original = copy.deepcopy(self.spec)
        self.spec['cuts'][0]['frames'] = 24
        with self.assertRaisesRegex(RuntimeError, 'stale cut clocks'): self.derive()
        self.spec = original; self.spec['backend'] = 'premiere'
        with self.assertRaisesRegex(RuntimeError, 'Premiere must use'): self.derive()
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

    def test_abbreviated_real_italic_face_and_unrequested_faux_refuses(self):
        self.handoff['cards'][1]['style']['italicStyle'] = 'Bold It'
        for track in (1, 2, 3):
            self.params(track=track, card=1)['font_style']['value']['Text'] = 'Bold It'
        self.assertEqual(self.verify()['status'], 'NATIVE_CAPTION_CONTRACT_VALID')
        self.params(track=2, card=1)['faux_italic']['value']['Bool'] = True
        with self.assertRaisesRegex(ValueError, 'italic'):
            self.verify()

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


    def visibility(self, rows=None):
        prepared, reference = self.derive()
        self.spec.update(captions=prepared['captions'], captionContract={**reference, 'helperHashes':prepared['helperHashes']})
        previous = copy.deepcopy(self.spec)
        self.spec['captionVisibility'] = {'schema':'acq-edit/caption-visibility-v1','owner':'caption-clips',
            'reason':'Synthetic hook overlap','evidence':'Native caption fixture; not human review',
            'hiddenRanges': rows or [{'startFrame':0,'endFrame':30}]}
        return previous, prepared

    def test_visibility_checks_foreground_and_both_shadows_and_preserves_native_context(self):
        from caption_visibility import targets, verify_protected
        previous, prepared = self.visibility()
        self.native['project'].update(name='fixture',root={'name':'fixture'})
        before = copy.deepcopy(self.native); ft = 254016000000//25
        changes = targets(before, previous, self.spec, prepared, ft)
        for change in changes:
            self.params(change['track'],change['index'],'opacity')['opacity'] = copy.deepcopy(change['new'])
        self.assertEqual(self.verify()['status'],'NATIVE_CAPTION_CONTRACT_VALID')
        verify_protected(before,self.native,changes,before['project']['name'])
        self.native['project']['items']['1']['kind']['Sequence']['manualAudioChange'] = True
        with self.assertRaisesRegex(RuntimeError,'protected native'): verify_protected(before,self.native,changes,before['project']['name'])
        self.params(2,0,'opacity')['opacity']['value']['Float'] = 20
        with self.assertRaisesRegex(RuntimeError,'visibility curve'): self.verify()

    def test_visibility_refuses_unowned_other_backend_invalid_ranges_and_locked_targets(self):
        from caption_visibility import ranges, targets
        previous, prepared = self.visibility()
        original = copy.deepcopy(self.spec['captionVisibility'])
        for invalid in [None, {}, [], False]:
            self.spec['captionVisibility'] = invalid
            with self.assertRaisesRegex(RuntimeError,'handoff required'): ranges(self.spec)
        self.spec['captionVisibility'] = original
        for rows in [[{'startFrame':-1,'endFrame':1}],[{'startFrame':0,'endFrame':76}],
                     [{'startFrame':0,'endFrame':30},{'startFrame':29,'endFrame':40}],
                     [{'startFrame':True,'endFrame':5}],[]]:
            self.spec['captionVisibility']['hiddenRanges'] = rows
            with self.assertRaises(RuntimeError): ranges(self.spec)
        self.spec['captionVisibility']['hiddenRanges'] = [{'startFrame':0,'endFrame':30}]
        self.spec['backend']='premiere'
        with self.assertRaisesRegex(RuntimeError,'FilmCraft or Resolve'): ranges(self.spec)
        self.spec['backend']='filmcraft'
        self.native['project']['items']['1']['kind']['Sequence']['video_tracks'][2]['locked'] = True
        with self.assertRaisesRegex(RuntimeError,'locked'): targets(self.native,previous,self.spec,prepared,254016000000//25)
        del self.spec['captionContract']
        with self.assertRaisesRegex(RuntimeError,'ownership contract'): ranges(self.spec)

    def test_visibility_keeps_fractional_arrival_values_after_a_hidden_window(self):
        from caption_visibility import masked_opacity
        from filmcraft_caption_contract import profile_caption_motion
        ft=254016000000//25
        _, original=profile_caption_motion({'filmcraft_caption_motion':'measured_fast_settle'},ft,10)
        masked=masked_opacity(original,{'start_frame':20,'end_frame':30},[{'startFrame':20,'endFrame':21}],ft)
        self.assertEqual(masked['value'],{'Float':0.})
        self.assertEqual(masked['keyframes'][0]['interp'],'Hold')
        boundary=next(k for k in masked['keyframes'] if k['time']==ft)
        expected=90+10*ft/original['keyframes'][-1]['time']
        self.assertAlmostEqual(boundary['value']['Float'],expected)
        self.assertEqual(masked['keyframes'][-1],original['keyframes'][-1])
        untouched=masked_opacity(original,{'start_frame':40,'end_frame':50},[{'startFrame':0,'endFrame':30}],ft)
        self.assertEqual(untouched,original)

    def test_visibility_prepare_pins_previous_plan_and_forbids_unrelated_or_hook_changes(self):
        from caption_visibility import prepare
        previous, _ = self.visibility()
        prior = self.root/'previous.json'; prior.write_text(json.dumps(previous))
        packet = {'previousPlan':str(prior),'previousPlanSha256':sha(prior),'plan':'new'}
        def check(old, new):
            with patch('caption_visibility.plan',side_effect=[old,new]):
                return prepare(self.project,packet)
        check(previous,self.spec)
        check(self.spec,previous)  # restoration uses the same guarded operation
        with self.assertRaisesRegex(RuntimeError,'makes no change'): check(previous,previous)
        changed=copy.deepcopy(self.spec);changed['width']=720
        with self.assertRaisesRegex(RuntimeError,'cannot change'):check(previous,changed)
        changed=copy.deepcopy(self.spec);changed['hookContract']={'fixture':True}
        with self.assertRaisesRegex(RuntimeError,'pinned toolkit version'):check(previous,changed)
        prior.write_text('changed')
        with self.assertRaisesRegex(RuntimeError,'Previous caption plan changed'):check(previous,self.spec)

    def test_visibility_gates_midcard_without_fading_before_the_hidden_frame(self):
        from caption_visibility import masked_opacity
        ft=254016000000//25
        original={'value':{'Float':100.}}
        masked=masked_opacity(original,{'start_frame':0,'end_frame':75},[{'startFrame':10,'endFrame':20},{'startFrame':30,'endFrame':40}],ft)
        values={k['time']:(k['value']['Float'],k['interp']) for k in masked['keyframes']}
        self.assertEqual(values[10*ft-1],(100.,'Linear'))
        self.assertEqual(values[10*ft],(0.,'Hold'))
        self.assertEqual(values[20*ft],(100.,'Linear'))
        self.assertEqual(values[30*ft],(0.,'Hold'))
        self.assertEqual(values[40*ft],(100.,'Linear'))

    def test_visibility_is_not_mistaken_for_forbidden_arrival_on_a_static_profile(self):
        from filmcraft_caption_contract import profile_caption_motion
        profile=json.loads(self.profile.read_text());profile['filmcraft_caption_motion']='none';self.profile.write_text(json.dumps(profile))
        self.handoff['profile']['sha256']=sha(self.profile)
        previous,prepared=self.visibility()
        ft=254016000000//25
        for i,card in enumerate(prepared['cards']):
            motion,opacity=profile_caption_motion(profile,ft,card['end_frame']-card['start_frame'],center=(320,180),canvas_height=360)
            for track in [1,2,3]:
                self.params(track,i,'motion')['position']=motion
                self.params(track,i,'opacity')['opacity']=caption_plan.opacity_for(self.spec,prepared,card,ft)
        self.assertEqual(self.verify()['status'],'NATIVE_CAPTION_CONTRACT_VALID')


if __name__ == '__main__': unittest.main()
