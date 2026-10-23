import importlib.util
import json
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'


def module(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f'{name}.py')
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


compiler = module('compile_assembly')
timeline = module('review_xml')


class CompiledHandoffTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.media = root / 'source.mp4'
        self.media.touch()
        self.words = root / 'words.json'
        self.words.write_text(json.dumps({'words': [
            {'word': f'w{i}', 'start': i * 0.5, 'end': i * 0.5 + 0.3}
            for i in range(30)]}))
        self.design = root / 'design.json'
        self.design.write_text(json.dumps({'schema': 'edit.assembly-selection/v1',
            'clips': [{'id': 'clip_1', 'source_words': str(self.words),
                       'media': str(self.media), 'interaction_word_range': [0, 29],
                       'hook_word_range': [2, 3],
                       'reasoning_word_range': [8, 9],
                       'payoff_word_range': [20, 21],
                       'kept_word_ranges': [[2, 9], [20, 21]],
                       'editorial_intent': 'A complete source-backed point'}]}))
        self.compiled = root / 'compiled.json'
        self.compiled.write_text(json.dumps(compiler.compile_design(self.design)))
        self.resolved = root / 'resolved.json'
        self.resolved.write_text(json.dumps({'schema': 'edit.resolved-assembly/v1',
            'compiled_path': str(self.compiled),
            'compiled_sha256': compiler.digest(self.compiled),
            'clips': [{'id': 'clip_1', 'source_frames': [[24, 112], [239, 253]]}]}))

    def test_exact_selected_words_reach_timeline(self):
        compiled = compiler.validate_compiled(self.compiled)
        self.assertEqual(compiled['clips'][0]['playback_text'],
                         'w2 w3 w4 w5 w6 w7 w8 w9 w20 w21')
        with patch.object(timeline, 'probe', return_value=(3840, 2160, Fraction(24), 30.0)), patch.object(timeline, 'probe_audio', return_value=(2, 44100, 16)):
            clips = timeline.designed_clips(self.resolved)
        self.assertEqual(clips[0]['frames'], [[24, 112], [239, 253]])

    def test_rejects_old_topic_window(self):
        self.resolved.write_text(json.dumps({'schema': 'edit.moments/v1', 'clips': []}))
        with self.assertRaisesRegex(ValueError, 'raw moment/window manifests are refused'):
            timeline.designed_clips(self.resolved)

    def test_rejects_stale_source_words(self):
        words = json.loads(self.words.read_text())
        words['words'][2]['word'] = 'different'
        self.words.write_text(json.dumps(words))
        with self.assertRaisesRegex(ValueError, 'stale'):
            compiler.validate_compiled(self.compiled)

    def test_rejects_dropped_internal_span(self):
        resolved = json.loads(self.resolved.read_text())
        resolved['clips'][0]['source_frames'] = [[24, 253]]
        self.resolved.write_text(json.dumps(resolved))
        with patch.object(timeline, 'probe', return_value=(3840, 2160, Fraction(24), 30.0)), patch.object(timeline, 'probe_audio', return_value=(2, 44100, 16)):
            with self.assertRaisesRegex(ValueError, 'every designed span'):
                timeline.designed_clips(self.resolved)

    def test_rejects_frame_window_far_from_selected_words(self):
        resolved = json.loads(self.resolved.read_text())
        resolved['clips'][0]['source_frames'][1] = [400, 450]
        self.resolved.write_text(json.dumps(resolved))
        with patch.object(timeline, 'probe', return_value=(3840, 2160, Fraction(24), 30.0)), patch.object(timeline, 'probe_audio', return_value=(2, 44100, 16)):
            with self.assertRaisesRegex(ValueError, 'do not match selected source words'):
                timeline.designed_clips(self.resolved)

    def test_provisional_seam_is_visible_in_review_marker(self):
        resolved = json.loads(self.resolved.read_text())
        resolved['clips'][0].update({
            'status': 'PROVISIONAL_SEAM',
            'boundary_issues': [{'span': 1, 'edge': 'start', 'code': 'FUSED'}],
            'note': 'Editor review: span 1 start FUSED; listening pending'})
        self.resolved.write_text(json.dumps(resolved))
        with patch.object(timeline, 'probe', return_value=(3840, 2160, Fraction(24), 30.0)), patch.object(timeline, 'probe_audio', return_value=(2, 44100, 16)):
            clips = timeline.designed_clips(self.resolved)
            self.assertEqual(clips[0]['status'], 'PROVISIONAL_SEAM')
            xml_path = Path(self.temp.name) / 'review.xml'
            timeline.build([], 'REVIEW', xml_path, assemblies_path=self.resolved)
        self.assertIn('PROVISIONAL_SEAM', xml_path.read_text())
        self.assertIn('span 1 start FUSED', xml_path.read_text())
        import xml.etree.ElementTree as ET
        media_audio = ET.parse(xml_path).find('.//file/media/audio')
        self.assertEqual(media_audio.findtext('channelcount'), '2')
        self.assertEqual(media_audio.findtext('samplecharacteristics/samplerate'), '44100')
        self.assertIsNone(media_audio.find('samplecharacteristics/channelcount'))



if __name__ == '__main__':
    unittest.main()
