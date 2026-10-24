"""Camera receipts and independent source clocks are required before native mutation."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'python'))
from common import fingerprint, sha
from framing_plan import validate_framing, verify_filmcraft_framing_data
from panel_layout import panel_spec


class PanelLayoutTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); receipt = self.root/'framing.json'; receipt.write_text('{}')
        self.project = {'root': str(self.root)}
        self.spec = {'backend': 'filmcraft', 'width': 360, 'height': 640, 'sampleRate': 48000, 'fps': {'numerator': 25, 'denominator': 1},
                     'cuts': [{'id': 'cut', 'sourceId': 'a', 'sourceInFrame': 40, 'recordFrame': 10, 'frames': 25}],
                     'sources': [{'id': i, 'sha256': i, 'path': i+'.mp4'} for i in ['a', 'b']],
                     'framing': {'schema': 'acq-edit/framing-v1', 'receiptPath': str(receipt), 'receiptSha256': sha(receipt), 'shots': {}}}
        self.layout = {'mode': 'panel-layout', 'cameraReceiptPath': str(self.root/'camera.json'), 'cameraReceiptSha256': '', 'panels': []}
        for index, source in enumerate(['a', 'b']):
            self.layout['panels'].append({'id': source, 'sourceRange': {'sourceId': source, 'sha256': source, 'inFrame': 40+index*10, 'frames': 25},
                'rect': {'x': 0, 'y': index*320, 'width': 360, 'height': 320},
                'crop': {'mode': 'fixed-crop', 'sourceWidth': 640, 'sourceHeight': 360, 'x': 80, 'y': 20, 'width': 360, 'height': 320}})
        self.spec['framing']['shots']['cut'] = self.layout
        self.pin_camera()
        self.video = {'width': 640, 'height': 360, 'nb_frames': '100', 'r_frame_rate': '25/1', 'avg_frame_rate': '25/1', 'sample_aspect_ratio': '1:1'}

    def pin_camera(self):
        value = {'schema': 'acq-edit/camera-layout-v1', 'owner': 'assembly-design', 'cutsSha256': fingerprint(self.spec['cuts']),
                 'width': 360, 'height': 640, 'fps': self.spec['fps'],
                 'layouts': {'cut': [{k: v for k, v in p.items() if k != 'crop'} for p in self.layout['panels']]}}
        path = Path(self.layout['cameraReceiptPath']); path.write_text(json.dumps(value)); self.layout['cameraReceiptSha256'] = sha(path)

    def validate(self):
        with patch('panel_layout.subprocess.check_output', return_value=json.dumps({'streams': [self.video]}).encode()):
            return validate_framing(self.project, self.spec)

    def test_panels_keep_independent_camera_clocks_and_panel_geometry(self):
        self.validate()
        child = panel_spec(self.spec, self.spec['cuts'][0], self.layout['panels'][1])
        self.assertEqual((child['width'], child['height']), (360, 320))
        self.assertEqual((child['cuts'][0]['sourceId'], child['cuts'][0]['sourceInFrame'], child['cuts'][0]['recordFrame']), ('b', 50, 0))
        self.assertEqual(self.spec['cuts'][0]['sourceInFrame'], 40)

    def test_camera_changes_require_new_assembly_receipt(self):
        self.layout['panels'][1]['sourceRange']['inFrame'] += 1
        with self.assertRaisesRegex(RuntimeError, 'differ from Assembly Design'): self.validate()
        self.pin_camera(); self.validate()
        self.spec['cuts'][0]['recordFrame'] += 1
        with self.assertRaisesRegex(RuntimeError, 'bound to current assembly'): self.validate()

    def test_panel_layout_cannot_hide_gaps_overlaps_or_out_of_bounds(self):
        original = copy.deepcopy(self.layout['panels'])
        for rect in [{'x': 0, 'y': 319, 'width': 360, 'height': 320},
                     {'x': 0, 'y': 321, 'width': 360, 'height': 319},
                     {'x': 1, 'y': 320, 'width': 360, 'height': 320},
                     {'x': False, 'y': 320, 'width': 360, 'height': 320}]:
            self.layout['panels'] = copy.deepcopy(original); self.layout['panels'][1]['rect'] = rect; self.pin_camera()
            with self.assertRaises(RuntimeError): self.validate()

    def test_source_hash_duration_and_coverage_are_not_guessed(self):
        original = copy.deepcopy(self.layout['panels'])
        for field, value in [('sha256', 'changed'), ('frames', 24), ('inFrame', -1), ('inFrame', 90)]:
            self.layout['panels'] = copy.deepcopy(original); self.layout['panels'][1]['sourceRange'][field] = value; self.pin_camera()
            with self.assertRaises(RuntimeError): self.validate()

    def test_panel_tracking_is_bound_to_its_camera_not_the_dialogue_cut(self):
        panel = self.layout['panels'][1]
        panel['crop'].update(mode='tracked-crop', xByFrame=[80+.25*i for i in range(25)], sourceRange=copy.deepcopy(panel['sourceRange']))
        self.validate()
        panel['crop']['sourceRange']['inFrame'] = 40
        with self.assertRaisesRegex(RuntimeError, 'Tracking source range changed'): self.validate()

    def test_other_engines_and_rate_conversion_fail_explicitly(self):
        self.spec['backend'] = 'resolve'; self.validate()
        for backend in ['premiere']:
            self.spec['backend'] = backend
            with self.assertRaisesRegex(RuntimeError, 'never convert or switch'): self.validate()
        self.spec['backend'] = 'filmcraft'; self.video['avg_frame_rate'] = '30/1'
        with self.assertRaisesRegex(RuntimeError, 'rates differ'): self.validate()

    def native(self):
        def item(source, start, source_in, width, height, anchor=None, position=None):
            params = {'anchor': {'Vec2': dict(zip(['x', 'y'], anchor or [width/2, height/2]))},
                      'position': {'Vec2': dict(zip(['x', 'y'], position or [width/2, height/2]))},
                      'scale': {'Float': 100}, 'scale_width': {'Float': 100}, 'rotation': {'Float': 0},
                      'anti_flicker': {'Float': 0}, 'uniform_scale': {'Bool': True}}
            effects = []
            for name, fields in [('motion', params), ('opacity', {'blend': {'Choice': 0}, 'opacity': {'Float': 100}}), ('time_remap', {'speed': {'Float': 100}})]:
                effects.append({'effect': name, 'enabled': True, 'params': {k: {'value': v} for k, v in fields.items()}})
            return {'item': source, 'start': start, 'source_in': source_in, 'duration': 250, 'enabled': True, 'speed': 1, 'reverse': False, 'effects': effects}
        def sequence(width, height, pictures):
            return {'kind': {'Sequence': {'settings': {'width': width, 'height': height, 'frame_rate': {'num': 25, 'den': 1}, 'sample_rate': 48000, 'par': [1, 1]},
                'video_tracks': [{'enabled': True, 'solo': False, 'items': [p]} for p in pictures], 'audio_tracks': []}}}
        return {'view': {'active_sequence': 1}, 'project': {'items': {
            '1': sequence(360, 640, [item(2, 100, 0, 360, 640)]),
            '2': sequence(360, 640, [item(3, 0, 0, 360, 320), item(4, 0, 0, 360, 320, position=[180, 480])]),
            '3': sequence(360, 320, [item(5, 0, 400, 360, 320, anchor=[260, 180])]),
            '4': sequence(360, 320, [item(6, 0, 500, 360, 320, anchor=[260, 180])]),
            '5': {'kind': {'Media': {'media': {'File': {'path': 'a.mp4'}}}}},
            '6': {'kind': {'Media': {'media': {'File': {'path': 'b.mp4'}}}}}}}}

    def test_native_panels_verify_source_clocks_and_reject_hidden_or_retimed_picture(self):
        data = self.native(); verify_filmcraft_framing_data(data, self.spec, 10)
        for kind in ['track', 'audio', 'source', 'clock', 'opacity', 'mask', 'rotation']:
            changed = copy.deepcopy(data); container = changed['project']['items']['2']['kind']['Sequence']; nest = container['video_tracks'][0]['items'][0]
            if kind == 'track': container['video_tracks'][0]['enabled'] = False
            elif kind == 'audio': container['audio_tracks'].append({})
            elif kind == 'source': changed['project']['items']['6']['kind']['Media']['media']['File']['path'] = 'a.mp4'
            elif kind == 'clock': changed['project']['items']['4']['kind']['Sequence']['video_tracks'][0]['items'][0]['source_in'] += 10
            elif kind == 'opacity': nest['effects'][1]['params']['opacity']['value'] = {'Float': 50}
            elif kind == 'mask': nest['effects'][0]['masks'] = [{}]
            else: nest['effects'][0]['params']['rotation']['value'] = {'Float': 90}
            with self.subTest(kind=kind), self.assertRaises(RuntimeError): verify_filmcraft_framing_data(changed, self.spec, 10)

    def test_native_panels_cannot_be_flattened_or_share_editable_nests(self):
        data = self.native(); container = data['project']['items']['2']['kind']['Sequence']
        container['video_tracks'][1]['items'][0]['item'] = 3
        with self.assertRaisesRegex(RuntimeError, 'share editable'): verify_filmcraft_framing_data(data, self.spec, 10)
        data = self.native(); data['project']['items']['2'] = data['project']['items']['5']
        with self.assertRaisesRegex(RuntimeError, 'flattened'): verify_filmcraft_framing_data(data, self.spec, 10)


if __name__ == '__main__': unittest.main()
