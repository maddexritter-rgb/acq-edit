import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
import numpy as np

spec = importlib.util.spec_from_file_location('sync_audio', Path(__file__).resolve().parents[1] / 'distribution/skills/edit/scripts/sync_audio.py')
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)


class SourceClockTests(unittest.TestCase):
    def test_local_scan_preserves_absolute_source_clock(self):
        rng = np.random.default_rng(42)
        probe = rng.normal(size=100)
        scan = rng.normal(scale=.00001, size=500)
        scan[230:330] = probe * .01
        # A much louder, unrelated impulse used to beat the quieter true match.
        scan[80] = 100
        with patch.object(sync.librosa, 'load', side_effect=[(probe, 100), (scan, 100)]) as load:
            offset, score = sync.find_offset(Path('picture'), Path('mic'), 100, 1000, 1, 5, 90)
        self.assertAlmostEqual(offset, -907.7)
        self.assertGreater(score, 1)
        self.assertEqual(load.call_args.kwargs['offset'], 90)

    def test_invalid_windows_fail_before_decode(self):
        with patch.object(sync.librosa, 'load') as load:
            for args in [(0, 1, 1, 5, 0), (100, -1, 1, 5, 0), (100, 1, 5, 1, 0), (100, 1, 1, 5, float('nan'))]:
                with self.assertRaises(ValueError):
                    sync.find_offset(Path('p'), Path('a'), *args)
            load.assert_not_called()

    def test_short_actual_decode_cannot_invent_a_match(self):
        with patch.object(sync.librosa, 'load', side_effect=[(np.ones(100), 100), (np.ones(50), 100)]):
            with self.assertRaises(ValueError):
                sync.find_offset(Path('p'), Path('a'), 100, 0, 1, 5)


if __name__ == '__main__':
    unittest.main()
