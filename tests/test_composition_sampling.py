import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('sampling', Path(__file__).resolve().parents[1] / 'scripts/sample_composition.py')
sampling = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sampling)


class SamplingTest(unittest.TestCase):
    def test_required_frames_and_max_gap(self):
        for count in (1, 2, 23, 24, 241, 1001):
            frames = sampling.sample_frames(count, 24000 / 1001)
            self.assertEqual(frames, sorted(set(frames)))
            self.assertTrue({0, count // 2, count - 1} <= set(frames))
            self.assertTrue(all(b-a <= 12 for a, b in zip(frames, frames[1:])))

    def test_invalid_clock(self):
        for args in ((0, 24), (20, 0), (20, 24, 0)):
            with self.assertRaises(ValueError):
                sampling.sample_frames(*args)


if __name__ == '__main__':
    unittest.main()
