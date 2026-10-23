"""Regression checks for crop drift across removed source passages."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from filmcraft_smooth_x import make_plan, TICKS


class FramingContinuityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name) / 'fixture.fcproj'
        self.project.write_text('{}')
        ft = TICKS // 24
        self.inspection = {'settings': {'par': [1, 1],
            'frame_rate': {'num': 24, 'den': 1}, 'width': 1080, 'height': 1920},
            'video': [{'items': []}]}
        self.tracking = {'width': 4000, 'height': 2200, 'fps': 24., 'items': []}
        for i, x in enumerate((.4, .6)):
            c = {'clip': i + 1, 'item': 10, 'durationFrames': 12,
                 'duration': 12 * ft, 'start': i * 12 * ft,
                 'end': (i + 1) * 12 * ft, 'startFrame': i * 12,
                 'endFrame': (i + 1) * 12, 'sourceIn': i * 24 * ft,
                 'sourceOut': (i * 24 + 12) * ft, 'speed': 1, 'reverse': False,
                 'effects': [{'effect': 'motion', 'params': {
                     'position': {'keyframes': 0,
                         'value': 'Vec2(Vec2 { x: 540.0, y: 960.0 })'},
                     'scale': {'keyframes': 0, 'value': 'Float(100.0)'}}}]}
            self.inspection['video'][0]['items'].append(c)
            self.tracking['items'].append({**{k: c[k] for k in
                ('clip', 'startFrame', 'endFrame', 'sourceIn', 'sourceOut')},
                'samples': 12, 'face': [[x, .3]] * 12})

    def tearDown(self):
        self.temp.cleanup()

    def plan(self, **kw):
        return make_plan(self.project, self.inspection, self.tracking,
                         1100., 100., 10., **kw)

    def test_default_is_static_and_recentered_per_cut(self):
        p = self.plan()
        self.assertEqual(p['motion_mode'], 'fixed')
        self.assertEqual(p['key_count'], 0)
        self.assertEqual([i['anchor'] for i in p['items']],
                         [[1600., 1100.], [2400., 1100.]])

    def test_camera_flag_cannot_blend_a_source_jump(self):
        p = self.plan(single_run=True, motion_mode='track')
        self.assertEqual(p['runs'], [[0], [1]])
        for item, expected in zip(p['items'], (1600., 2400.)):
            self.assertTrue(all(k['value'] == [expected, 1100.] for k in item['keys']))

    def test_source_continuous_subdivision_can_share_filter(self):
        c = self.inspection['video'][0]['items']
        c[1]['sourceIn'] = c[0]['sourceOut']
        c[1]['sourceOut'] = c[1]['sourceIn'] + c[1]['duration']
        self.tracking['items'][1].update(sourceIn=c[1]['sourceIn'], sourceOut=c[1]['sourceOut'])
        self.assertEqual(self.plan(single_run=True, motion_mode='track')['runs'], [[0, 1]])

    def test_continuous_subdivision_keeps_one_fixed_crop(self):
        c = self.inspection['video'][0]['items']
        c[1]['sourceIn'] = c[0]['sourceOut']
        c[1]['sourceOut'] = c[1]['sourceIn'] + c[1]['duration']
        self.tracking['items'][1].update(sourceIn=c[1]['sourceIn'], sourceOut=c[1]['sourceOut'])
        p = self.plan()
        self.assertEqual(p['runs'], [[0, 1]])
        self.assertEqual(p['key_count'], 0)
        self.assertEqual([i['anchor'] for i in p['items']], [[2000., 1100.], [2000., 1100.]])

    def test_other_media_starts_a_new_filter(self):
        c = self.inspection['video'][0]['items']
        c[1].update(item=11, sourceIn=c[0]['sourceOut'])
        c[1]['sourceOut'] = c[1]['sourceIn'] + c[1]['duration']
        self.tracking['items'][1].update(sourceIn=c[1]['sourceIn'], sourceOut=c[1]['sourceOut'])
        self.assertEqual(self.plan(single_run=True, motion_mode='track')['runs'], [[0], [1]])

    def test_animated_scale_remains_unsupported(self):
        self.inspection['video'][0]['items'][0]['effects'][0]['params']['scale']['keyframes'] = 2
        with self.assertRaises(AssertionError):
            self.plan()


if __name__ == '__main__':
    unittest.main()
