import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('dialogue_conform', Path(__file__).resolve().parents[1] / 'python/dialogue_conform.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class DialogueConformTest(unittest.TestCase):
    def test_clock_mapping_keeps_original_occurrence_and_excludes_partial_words(self):
        source = {'words': [{'word': 'before', 'start': 0, 'end': 0.8},
                            {'word': 'inside', 'start': 1.1, 'end': 1.8, 'speaker': 'A'},
                            {'word': 'crossing', 'start': 1.9, 'end': 2.1}]}
        words, excluded = module.map_words(source, -48000, 48000, 48000)
        self.assertEqual(excluded, [0, 2])
        self.assertEqual(words[0]['source_word_index'], 1)
        self.assertEqual(words[0]['start'], .1)
        self.assertEqual(words[0]['original_start'], 1.1)
        self.assertEqual(source['words'][1]['start'], 1.1)

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg required')
    def test_prepared_pcm_has_exact_trim_and_weighted_samples(self):
        import wave
        import array
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            routes = []
            for name, amplitude, start in [('one', 1000, 480), ('two', 3000, 960)]:
                path = root / (name + '.wav')
                with wave.open(str(path), 'wb') as out:
                    out.setparams((1, 2, 48000, 0, 'NONE', 'not compressed'))
                    out.writeframes(array.array('h', [0] * start + [amplitude] * 4800).tobytes())
                routes.append({'path': str(path), 'sha256': module.digest(path), 'sourceStartSample': start, 'gain': .5})
            transcript = root / 'transcript.json'; transcript.write_text(json.dumps({'words': [{'word': 'test', 'start': .02, 'end': .04}]}))
            evidence = root / 'clock.json'; evidence.write_text('{"qualification":"generated fixture"}')
            request = {'schema': 'acq-edit/dialogue-conform-v1', 'sampleRate': 48000, 'durationSamples': 4800,
                       'transcriptOffsetSamples': 0, 'microphones': routes,
                       'transcript': {'path': str(transcript), 'sha256': module.digest(transcript)},
                       'clockEvidence': {'path': str(evidence), 'sha256': module.digest(evidence)}}
            result = module.prepare(request, root / 'output')
            raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', result['media'], '-f', 's16le', '-'])
            decoded = array.array('h'); decoded.frombytes(raw)
            self.assertEqual(len(decoded), 4800)
            self.assertEqual(set(decoded), {2000})
            with self.assertRaises(FileExistsError): module.prepare(request, root / 'output')
            routes[0]['sha256'] = '0' * 64
            with self.assertRaisesRegex(ValueError, 'Pinned input changed'): module.prepare(request, root / 'changed')

if __name__ == '__main__': unittest.main()
