"""Consumer regressions: preserve detector sample timing before frame decisions."""
import contextlib
import argparse
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import wave

import numpy as np

SHARED = Path(__file__).resolve().parents[2] / '_shared'
spec = importlib.util.spec_from_file_location('shared_vad_precision_test', SHARED / 'silero_vad.py')
vad = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vad)
sys.path.insert(0, str(SHARED))
import speech_map_cut


class VadPrecisionTests(unittest.TestCase):
    def test_exact_rational_fps_is_accepted(self):
        self.assertAlmostEqual(speech_map_cut.parse_fps('24000/1001'), 24000/1001)
        with self.assertRaises(argparse.ArgumentTypeError):
            speech_map_cut.parse_fps('0/0')

    def test_fps_probe_uses_source_rate_instead_of_thirty(self):
        output = types.SimpleNamespace(stdout=json.dumps({
            'streams': [{'avg_frame_rate': '24000/1001', 'r_frame_rate': '24/1'}]}))
        with patch.object(speech_map_cut.subprocess, 'run', return_value=output) as run:
            self.assertAlmostEqual(speech_map_cut.probe_fps('/source.mp4'), 24000/1001)
        self.assertEqual(run.call_args.args[0][-1], '/source.mp4')

    def test_short_rms_verified_interword_gap_can_rescue_merged_vad(self):
        words = [{'word': 'uh', 'start': .80, 'end': 1.00},
                 {'word': 'question', 'start': 1.09, 'end': 1.36}]
        env = np.full(400, -18.)
        env[202:218] = -43.  # 1.01–1.09s, shorter than the main VAD merge window
        point, detail = speech_map_cut.micro_gap_boundary(24, 'start', words, 1, env, 0)
        self.assertAlmostEqual(point, 25/24)
        self.assertEqual(detail['verdict'], 'OK_MICRO_GAP')
        self.assertEqual(detail['preceding_word'], 'uh')

    def test_micro_gap_rejects_loud_or_overlapping_speech(self):
        words = [{'word': 'uh', 'start': .80, 'end': 1.00},
                 {'word': 'question', 'start': 1.09, 'end': 1.36}]
        loud = np.full(400, -18.)
        point, detail = speech_map_cut.micro_gap_boundary(24, 'start', words, 1, loud, 0)
        self.assertIsNone(point)
        self.assertEqual(detail['verdict'], 'REFUSED')
        words[1]['start'] = .99
        point, detail = speech_map_cut.micro_gap_boundary(24, 'start', words, 1, loud, 0)
        self.assertIsNone(point)
        self.assertEqual(detail['verdict'], 'REFUSED')

    def test_worker_preserves_samples_without_tenth_second_rounding(self):
        seen = {}
        def timestamps(audio, model, **kwargs):
            seen.update(kwargs)
            return [{'start': 1697, 'end': 5643}]
        package = types.SimpleNamespace(load_silero_vad=lambda: object(),
                                        get_speech_timestamps=timestamps)
        torch = types.SimpleNamespace(from_numpy=lambda x: x)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'fixture.wav'
            with wave.open(str(path), 'wb') as f:
                f.setnchannels(1)
                f.setsampwidth(2)
                f.setframerate(16000)
                f.writeframes(bytes(16000))
            output = io.StringIO()
            old_path = sys.path[:]
            try:
                with patch.dict(sys.modules, {'silero_vad': package, 'torch': torch}), contextlib.redirect_stdout(output):
                    self.assertEqual(vad._worker(str(path), .5, 100, 25), 0)
            finally:
                sys.path[:] = old_path
        self.assertIs(seen['return_seconds'], False)
        self.assertEqual(json.loads(output.getvalue()), [[1697/16000, 5643/16000]])
        self.assertEqual(seen['threshold'], .5)
        self.assertEqual(seen['speech_pad_ms'], 25)

    def test_rounding_can_manufacture_legal_gap(self):
        env = np.full(400, -60.)
        accurate = [(0.2, 1.049), (1.111, 1.4)]
        rounded = [(round(s, 1), round(e, 1)) for s, e in accurate]
        actual, info = speech_map_cut.boundary(24, 'end', accurate, env, 0, 2, .8)
        self.assertIsNone(actual)
        self.assertEqual(info['verdict'], 'REFUSED')
        false_cut, false_info = speech_map_cut.boundary(24, 'end', rounded, env, 0, 2, .8)
        self.assertIsNotNone(false_cut)
        self.assertEqual(false_info['verdict'], 'OK')


if __name__ == '__main__':
    unittest.main()
