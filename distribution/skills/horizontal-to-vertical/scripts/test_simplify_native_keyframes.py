import unittest

from simplify_native_keyframes import simplify, simplify_plan


class SimplifyNativeKeyframesTests(unittest.TestCase):
    def test_linear_motion_collapses_to_endpoints(self):
        keys = [[0, 0.4, 0.5], [1, 0.5, 0.5], [2, 0.6, 0.5]]
        self.assertEqual(simplify(keys, 0.001), [keys[0], keys[-1]])

    def test_direction_change_is_preserved(self):
        keys = [[0, 0.4, 0.5], [1, 0.5, 0.55], [2, 0.6, 0.5]]
        self.assertEqual(simplify(keys, 0.001), keys)

    def test_static_run_becomes_one_key(self):
        keys = [[0, 0.5, 0.5], [1, 0.5002, 0.5], [2, 0.5001, 0.5]]
        self.assertEqual(simplify(keys, 0.001), [keys[0]])

    def test_hold_then_move_keeps_timing(self):
        keys = [[0, 0.4, 0.5], [9, 0.4, 0.5], [10, 0.6, 0.5]]
        self.assertEqual(simplify(keys, 0.001), keys)

    def test_speed_change_on_straight_path_is_preserved(self):
        keys = [[0, 0.4, 0.5], [1, 0.59, 0.5], [10, 0.6, 0.5]]
        self.assertEqual(simplify(keys, 0.001), keys)

    def test_invalid_clock_rejected(self):
        with self.assertRaises(ValueError):
            simplify([[0, 0.4, 0.5], [0, 0.6, 0.5]], 0.001)

    def test_records_never_merge_across_cuts(self):
        plan = {"records": [
            {"anchor_keys": [[0, 0.4, 0.5], [1, 0.5, 0.5]]},
            {"anchor_keys": [[0, 0.7, 0.5], [1, 0.8, 0.5]]},
        ]}
        result = simplify_plan(plan, 0.001)
        self.assertEqual(len(result["records"]), 2)
        self.assertEqual(result["records"][0]["anchor_keys"][0][1], 0.4)
        self.assertEqual(result["records"][1]["anchor_keys"][0][1], 0.7)


if __name__ == "__main__":
    unittest.main()
