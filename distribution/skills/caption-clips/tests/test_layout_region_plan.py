#!/usr/bin/env python3

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from layout_region_plan import bounds_with_regions, is_split, layout_for_region, load_regions


class LayoutRegionPlanTest(unittest.TestCase):
    def test_camera_regions_add_exact_boundaries_and_preserve_layout(self):
        payload = {"segments": [
            {"start_i": 0, "end_i": 425, "layout": "split"},
            {"start_i": 426, "end_i": 964, "layout": "full"},
        ]}
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "plan.json"
            path.write_text(json.dumps(payload))
            regions = load_regions(str(path), 965)
        self.assertEqual(bounds_with_regions([], regions, 965), [0, 426, 965])
        self.assertEqual(layout_for_region(regions, 0, 426), "split")
        self.assertEqual(layout_for_region(regions, 426, 965), "full")
        self.assertTrue(is_split("split"))
        self.assertFalse(is_split("full"))

    def test_overlapping_regions_fail_closed(self):
        payload = {"segments": [
            {"start_i": 0, "end_i": 10, "layout": "split"},
            {"start_i": 10, "end_i": 20, "layout": "full"},
        ]}
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "plan.json"
            path.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError, "overlapping"):
                load_regions(str(path), 21)


if __name__ == "__main__":
    unittest.main()
