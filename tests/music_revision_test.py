import copy, sys, unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'python'))
from music_revision import compare_plans, filmcraft_items, verify_filmcraft_replacement, validate_sources, TICKS


class MusicRevisionTests(unittest.TestCase):
    def fixture(self):
        source = {'id': 'a', 'path': '/project/old.wav', 'sha256': 'old'}
        bed = {'id': 'bed', 'sourceId': 'a', 'startFrame': 5, 'sourceInSample': 48000,
               'samples': 76800, 'gainDb': -12, 'fadeInSamples': 9600, 'fadeOutSamples': 9600,
               'receiptPath': '/project/old.json', 'receiptSha256': 'old-receipt'}
        old = {'fps': {'numerator': 25, 'denominator': 1}, 'sampleRate': 48000,
               'cuts': ['unchanged'], 'sources': [source], 'audio': {'gainDb': -3, 'music': [bed]}}
        new = copy.deepcopy(old)
        new['sources'].append({'id': 'b', 'path': '/project/new.wav', 'sha256': 'new'})
        new['audio']['music'][0].update(sourceId='b', receiptPath='/project/new.json', receiptSha256='new-receipt')
        def media(i, path):
            return {'id': i, 'label': 'Rose', 'kind': {'Media': {'media': {'File': {'path': path}}}}}
        clip = {'id': 3, 'item': 2, 'name': 'Custom music', 'label': 'Rose', 'start': TICKS // 5,
                'duration': TICKS * 8 // 5, 'source_in': TICKS, 'speed': 1, 'reverse': False,
                'frame_hold': None, 'link': None, 'group': None, 'source_channels': [],
                'effects': [{'effect': 'time_remap', 'params': {'speed': {'value': {'Float': 100.0}}}},
                            {'effect': 'volume', 'params': {'level': {'value': {'Float': -12},
                             'keyframes': [{'time': TICKS, 'value': {'Float': -96}}, {'time': TICKS * 6 // 5, 'value': {'Float': -12}}]}}}]}
        seq = {'video_tracks': [{'items': ['picture/captions untouched']}],
               'audio_tracks': [{'items': ['dialogue untouched']}, {'items': [clip]}]}
        before = {'view': {'active_sequence': 1}, 'project': {'name': 'parent',
                  'root': {'name': 'parent', 'children': [{'Item': 1}, {'Item': 2}]}, 'next_id': 4,
                  'items': {'1': {'kind': {'Sequence': seq}}, '2': media(2, '/project/old.wav')}}}
        after = copy.deepcopy(before); p = after['project']; p['name'] = p['root']['name'] = 'revision'
        p['next_id'] = 5; p['items']['4'] = media(4, '/project/new.wav'); p['root']['children'].append({'Item': 4})
        p['items']['1']['kind']['Sequence']['audio_tracks'][1]['items'][0]['item'] = 4
        return old, new, before, after

    def test_plan_preserves_cuts_timing_receipts_and_existing_sources(self):
        old, new, _, _ = self.fixture(); self.assertEqual(compare_plans(old, new, [0]), [0])
        for indices in [[], [True], [0, 0], [-1], [1]]:
            with self.subTest(indices=indices), self.assertRaises(RuntimeError): compare_plans(old, new, indices)
        for field in ['cuts', 'sourceInSample', 'samples', 'gainDb', 'fadeInSamples', 'receiptPath', 'source']:
            changed = copy.deepcopy(new)
            if field == 'cuts': changed['cuts'] = []
            elif field == 'source': changed['sources'][0]['sha256'] = 'changed'
            elif field == 'receiptPath': changed['audio']['music'][0][field] = old['audio']['music'][0][field]
            else: changed['audio']['music'][0][field] += 1
            with self.subTest(field=field), self.assertRaises(RuntimeError): compare_plans(old, changed, [0])

    def test_native_replacement_preserves_automation_and_all_other_state(self):
        old, new, before, after = self.fixture()
        verify_filmcraft_replacement(before, after, old, new, [0], 'revision')
        for field in ['automation', 'dialogue', 'routing', 'name', 'old-source', 'bin']:
            changed = copy.deepcopy(after); p = changed['project']; seq = p['items']['1']['kind']['Sequence']; clip = seq['audio_tracks'][1]['items'][0]
            if field == 'automation': clip['effects'][1]['params']['level']['keyframes'][0]['time'] += 1
            elif field == 'dialogue': seq['audio_tracks'][0]['items'] = []
            elif field == 'routing': clip['source_channels'] = [1]
            elif field == 'name': clip['name'] = 'reset'
            elif field == 'old-source': p['items']['2']['label'] = 'Violet'
            else: p['root']['children'].reverse()
            with self.subTest(field=field), self.assertRaises(RuntimeError): verify_filmcraft_replacement(before, changed, old, new, [0], 'revision')

    def test_unsafe_native_targets_refused(self):
        old, _, before, _ = self.fixture()
        plain = copy.deepcopy(before)
        plain['project']['items']['1']['kind']['Sequence']['audio_tracks'][1]['items'][0]['effects'].pop(0)
        filmcraft_items(plain, old, [0])  # Native audio does not have an intrinsic time-remap effect.
        for key, value in [('link', 7), ('group', 7), ('speed', 2), ('reverse', True), ('frame_hold', {}), ('source_channels', [0])]:
            changed = copy.deepcopy(before); changed['project']['items']['1']['kind']['Sequence']['audio_tracks'][1]['items'][0][key] = value
            with self.subTest(key=key), self.assertRaises(RuntimeError): filmcraft_items(changed, old, [0])

    def test_preflight_refuses_short_non_pcm_or_changed_channel_sources(self):
        old, new, _, _ = self.fixture()
        stream = {'codec_name': 'pcm_s24le', 'sample_rate': '48000', 'channels': 2, 'duration_ts': 124800, 'time_base': '1/48000'}
        with patch('music_revision.probe_source', return_value=stream), patch('music_revision.subprocess.run') as decode, patch('music_revision.sha', return_value='new'):
            validate_sources(old, new, [0]); decode.assert_called_once()
        for field, value in [('duration_ts', 124799), ('codec_name', 'aac'), ('channels', 1), ('sample_rate', '44100'), ('duration_ts', None)]:
            changed = {**stream, field: value}
            with self.subTest(field=field, value=value), patch('music_revision.probe_source', side_effect=[stream, changed]), patch('music_revision.subprocess.run') as decode:
                with self.assertRaises(RuntimeError): validate_sources(old, new, [0])
                decode.assert_not_called()


if __name__ == '__main__': unittest.main()
