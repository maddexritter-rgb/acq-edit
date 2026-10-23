import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).with_name("premiere_native_reframe.py")
SPEC = importlib.util.spec_from_file_location("premiere_native_reframe", MODULE_PATH)
native = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(native)


class NativeReframeTests(unittest.TestCase):
    @staticmethod
    def picture_item(start, end, source_in, source_out, path="same-camera", track=0):
        return {"name": "test", "start": start, "end": end, "source_in": source_in, "source_out": source_out,
                "media_path": path, "track_index": track, "speed": 100, "item_index": 0}

    @staticmethod
    def new_record(keys, fallback=False, scale=150):
        return {"anchor_keys": [list(key) for key in keys], "scale_percent": scale,
                "tracking": {"width": 1920, "fallback": fallback}}

    @staticmethod
    def keyed_motion(start_x, end_x, scale=150):
        return {"anchor": [start_x, 0.5], "position": [0.5, 0.5], "scale": scale,
                "anchor_time_varying": True, "position_time_varying": False,
                "scale_time_varying": False,
                "anchor_keys": [{"ticks": "100", "value": [start_x, 0.5]},
                                {"ticks": "200", "value": [end_x, 0.5]}],
                "anchor_display_start": [start_x, 0.5], "anchor_display_end": [end_x, 0.5]}

    def test_rdp_preserves_endpoints_and_turn(self):
        keys = [[0, 0.4, 0.5], [1, 0.5, 0.5], [2, 0.4, 0.5]]
        self.assertEqual(native.rdp(keys, 0.01), keys)

    def test_rdp_simplifies_linear_path(self):
        keys = [[0, 0.4, 0.5], [1, 0.5, 0.5], [2, 0.6, 0.5]]
        self.assertEqual(native.rdp(keys, 0.0001), [keys[0], keys[-1]])

    def test_crop_safe_margin_prevents_source_edge_reveal(self):
        self.assertAlmostEqual(native.crop_safe_margin(1920, 720, 1920 / 720 * 1.6), 0.3125)

    def test_crop_bounds_account_for_native_position(self):
        self.assertEqual(native.crop_safe_x_bounds(1080, 1920, 1.5, 0.5), (0.1875, 0.8125))
        self.assertEqual(native.crop_safe_x_bounds(1080, 1920, 1.5, 0.4), (0.15000000000000002, 0.775))

    def test_new_same_camera_seam_matches_x_and_preserves_tracking(self):
        items = [self.picture_item(0, 1, 0, 1), self.picture_item(1, 2, 4, 5)]
        records = [self.new_record([[0, 0.50, 0.4], [1, 0.55, 0.4]]),
                   self.new_record([[0, 0.48, 0.3], [1, 0.53, 0.3]])]
        faces = [{"face_x": [0.50, 0.55]}, {"face_x": [0.55, 0.60]}]
        seams = native.reconcile_new_plan_x(items, records, faces, 1080, 1.0)
        self.assertEqual(seams[0]["status"], "aligned_x_render_check_required")
        self.assertAlmostEqual(records[1]["anchor_keys"][0][1], 0.55)
        self.assertAlmostEqual(records[1]["anchor_keys"][1][1], 0.60)
        self.assertEqual([k[2] for k in records[1]["anchor_keys"]], [0.3, 0.3])

    def test_equal_anchor_values_flag_source_subject_jump_without_camera_shift(self):
        items = [self.picture_item(0, 1, 0, 1), self.picture_item(1, 2, 4, 5)]
        records = [self.new_record([[0, 0.50, 0.4]]), self.new_record([[0, 0.50, 0.4]])]
        faces = [{"face_x": [0.45]}, {"face_x": [0.55]}]
        seams = native.reconcile_new_plan_x(items, records, faces, 1080, 1.0)
        self.assertEqual(seams[0]["status"], "anchor_continuous_subject_shift_render_check_required")
        self.assertAlmostEqual(records[1]["anchor_keys"][0][1], 0.50)

    def test_new_x_seams_do_not_cross_camera_panel_or_gap(self):
        left = self.picture_item(0, 1, 0, 1)
        rec = [self.new_record([[0, 0.55, 0.4]]), self.new_record([[0, 0.40, 0.4]])]
        faces = [{"face_x": [0.55]}, {"face_x": [0.55]}]
        for right in (self.picture_item(1, 2, 0, 1, path="other-camera"),
                      self.picture_item(1, 2, 0, 1, track=1),
                      self.picture_item(1.2, 2.2, 0, 1)):
            self.assertEqual(native.reconcile_new_plan_x([left, right], rec, faces, 1080, 1.0), [])
            self.assertEqual(rec[1]["anchor_keys"][0][1], 0.40)

    def test_new_x_seam_reports_crop_limit_instead_of_exposing_edge(self):
        items = [self.picture_item(0, 1, 0, 1), self.picture_item(1, 2, 4, 5)]
        records = [self.new_record([[0, 0.78, 0.4]]), self.new_record([[0, 0.60, 0.4], [1, 0.70, 0.4]])]
        faces = [{"face_x": [0.78]}, {"face_x": [0.78]}]
        self.assertEqual(native.reconcile_new_plan_x(items, records, faces, 1080, 1.0)[0]["status"], "unresolved_crop_limit")
        self.assertEqual(records[1]["anchor_keys"][1][1], 0.70)

    def test_build_plan_includes_rendered_subject_seam_alignment(self):
        first = self.picture_item(0, 1, 0, 1, __file__)
        second = self.picture_item(1, 2, 4, 5, __file__)
        first["item_index"], second["item_index"] = 0, 1
        motion = {"anchor_time_varying": False, "position_time_varying": False, "scale_time_varying": False,
                  "anchor": [0.5, 0.5], "position": [0.5, 0.5], "scale": 100}
        first["motion"] = second["motion"] = motion
        inspection = {"project_path": "/weekly.prproj", "sequence_name": "REVIEW", "sequence_id": "seq",
                      "width": 1080, "height": 1920, "video_tracks": [{"clips": [first, second]}]}
        def tracked(face_x):
            return {"width": 1920, "height": 2160, "fps": 24, "relative_times": [0.0, 0.9],
                    "face_x": face_x, "face_y": [0.4, 0.4], "face_y_median": 0.4,
                    "detections": 2, "samples": 2, "fallback": False, "miss_rate": 0,
                    "edge_face_seen": [True, True]}
        with patch.object(native, "track_item", side_effect=[tracked([0.50, 0.50]), tracked([0.60, 0.60])]):
            plan = native.build_plan(inspection, "podcast", 0.5, 1.0)
        self.assertEqual(plan["x_seams"][0]["status"], "aligned_anchor_subject_shift_render_check_required")
        self.assertAlmostEqual(plan["records"][1]["anchor_keys"][0][1], 0.50)

    def test_content_groups_split_on_gap_or_camera_change(self):
        items = [
            {"start": 0, "end": 1, "track_index": 0, "media_path": "a"},
            {"start": 1, "end": 2, "track_index": 0, "media_path": "a"},
            {"start": 3, "end": 4, "track_index": 0, "media_path": "a"},
            {"start": 4, "end": 5, "track_index": 0, "media_path": "b"},
        ]
        self.assertEqual(native.content_groups(items), [[0, 1], [2], [3]])

    def test_capcut_sections_share_parent_group(self):
        items = [
            {"start": 0, "end": 1, "track_index": 3, "media_path": "/x/alex clip 6-1.mp4"},
            {"start": 1, "end": 2, "track_index": 3, "media_path": "/x/alex clip 6-2.mp4"},
            {"start": 2, "end": 3, "track_index": 3, "media_path": "/x/alex clip 7-1.mp4"},
        ]
        self.assertEqual(native.content_groups(items), [[0, 1], [2]])

    def test_face_gate_rejects_tall_phantom(self):
        # bbox, ten YuNet landmark coordinates, final confidence.
        faces = [[100, 10, 100, 500] + [0] * 10 + [0.99]]
        self.assertIsNone(native.select_face(faces, None, (0, 0, 1, 1), 1280, 720))

    def test_profile_rescue_requires_continuity(self):
        faces = [[500, 100, 80, 100] + [0] * 10 + [0.50]]
        self.assertIsNotNone(native.select_face(faces, 540, (0, 0, 1, 1), 1280, 720))
        self.assertIsNone(native.select_face(faces, 100, (0, 0, 1, 1), 1280, 720))

    def test_stage_roi_never_rescues_large_audience_face(self):
        faces = [[1000, 300, 160, 180] + [0] * 10 + [0.99]]
        self.assertIsNone(native.select_face(faces, None, (0.35, 0.05, 0.65, 0.55), 1280, 720))

    def test_center_stage_does_not_hardcode_project_fallback(self):
        self.assertNotIn("fallback_y", native.PRESETS["center-stage"])

    def test_y_reframe_is_two_holds_with_short_transition(self):
        data = {"face_y": [0.30, 0.30, 0.31, 0.40, 0.49, 0.50, 0.50], "fallback": False, "detections": 7, "samples": 7}
        values, _ = native.discrete_y_values(data, 0, 1)
        self.assertIsNotNone(values)
        self.assertEqual(values[:2], [values[0], values[0]])
        self.assertEqual(values[-2:], [values[-1], values[-1]])
        self.assertIsNone(native.discrete_y_values(data, 1, 1)[0])
        data["face_y"] = [0.40, 0.41, 0.42, 0.41]
        self.assertIsNone(native.discrete_y_values(data, 0, 1)[0])

    def test_existing_motion_animation_fails_closed(self):
        inspection = {
            "height": 1920,
            "video_tracks": [{"clips": [{
                "track_index": 0, "item_index": 0, "name": "x", "media_path": __file__,
                "start": 0, "end": 1, "source_in": 0, "source_out": 1, "speed": 100,
                "motion": {"anchor_time_varying": True, "position_time_varying": False,
                           "scale_time_varying": False},
            }]}],
        }
        with self.assertRaisesRegex(RuntimeError, "Existing native Motion animation"):
            native.build_plan(inspection, "alex-stage", 1.0, 8.0)

    def test_existing_keyed_repair_preserves_y_key_times_and_edit(self):
        path = __file__
        first = self.picture_item(0, 1, 0, 1, path)
        second = self.picture_item(1, 2, 5, 6, path)
        first["item_index"], second["item_index"] = 0, 1
        first["motion"] = self.keyed_motion(0.50, 0.54)
        second["motion"] = self.keyed_motion(0.46, 0.49)
        inspection = {"project_path": "/weekly.prproj", "sequence_name": "REVIEW", "sequence_id": "seq",
                      "width": 1080, "height": 1920, "video_tracks": [{"clips": [first, second]}]}
        observed = {(0, 0, "end"): 0.52, (0, 1, "start"): 0.52}
        plan = native.build_existing_seam_plan(inspection, {path: 1920}, boundary_faces=observed)
        self.assertEqual(plan["seams"][0]["status"], "aligned_x_render_check_required")
        self.assertEqual(len(plan["records"]), 1)
        self.assertEqual(plan["records"][0]["new_anchor_keys"],
                         [{"ticks": "100", "value": [0.54, 0.5]}, {"ticks": "200", "value": [0.57, 0.5]}])
        self.assertEqual(plan["records"][0]["source_in"], 5)
        self.assertEqual(second["motion"]["anchor_keys"][0]["value"], [0.46, 0.5])

    def test_existing_repair_is_per_panel_and_fails_on_crop_limit(self):
        path = __file__
        first = self.picture_item(0, 1, 0, 1, path)
        second = self.picture_item(1, 2, 2, 3, path)
        first["item_index"], second["item_index"] = 0, 1
        first["motion"] = self.keyed_motion(0.79, 0.80)
        second["motion"] = self.keyed_motion(0.60, 0.70)
        inspection = {"project_path": "/weekly.prproj", "sequence_name": "PANEL", "sequence_id": "seq",
                      "width": 1080, "height": 1920, "video_tracks": [{"clips": [first, second]}]}
        observed = {(0, 0, "end"): 0.80, (0, 1, "start"): 0.80}
        plan = native.build_existing_seam_plan(inspection, {path: 1920}, boundary_faces=observed)
        self.assertEqual(plan["seams"][0]["status"], "unresolved_crop_limit")
        self.assertEqual(plan["records"], [])
        second["track_index"] = 1
        inspection["video_tracks"] = [{"clips": [first]}, {"clips": [second]}]
        self.assertEqual(native.build_existing_seam_plan(inspection, {path: 1920}, boundary_faces=observed)["seams"], [])

    def test_overlapping_split_panels_require_independent_source_sequences(self):
        path = __file__
        top = self.picture_item(0, 1, 0, 1, path, track=0)
        bottom = self.picture_item(0, 1, 0, 1, path, track=1)
        top["motion"] = bottom["motion"] = self.keyed_motion(0.5, 0.5)
        inspection = {"project_path": "/weekly.prproj", "sequence_name": "COMPOSITE", "sequence_id": "seq",
                      "width": 1080, "height": 1920, "video_tracks": [{"clips": [top]}, {"clips": [bottom]}]}
        with self.assertRaisesRegex(RuntimeError, "Overlapping source-linked picture tracks"):
            native.build_existing_seam_plan(inspection, {path: 1920})

    def test_existing_repair_preserves_hidden_trim_keys_and_reports_missing_face(self):
        path = __file__
        first = self.picture_item(0, 1, 2, 3, path)
        second = self.picture_item(1, 2, 8, 9, path)
        first["item_index"], second["item_index"] = 0, 1
        first["motion"] = self.keyed_motion(0.50, 0.50)
        second["motion"] = self.keyed_motion(0.45, 0.55)
        second["motion"]["anchor_display_start"] = [0.52, 0.5]  # first visible frame is after a hidden handle key
        inspection = {"project_path": "/weekly.prproj", "sequence_name": "REVIEW", "sequence_id": "seq",
                      "width": 1080, "height": 1920, "video_tracks": [{"clips": [first, second]}]}
        observed = {(0, 0, "end"): 0.50, (0, 1, "start"): 0.50}
        plan = native.build_existing_seam_plan(inspection, {path: 1920}, boundary_faces=observed)
        self.assertEqual([key["ticks"] for key in plan["records"][0]["new_anchor_keys"]], ["100", "200"])
        self.assertEqual(plan["records"][0]["new_anchor_keys"][0]["value"], [0.43, 0.5])
        observed[(0, 1, "start")] = None
        missing = native.build_existing_seam_plan(inspection, {path: 1920}, boundary_faces=observed)
        self.assertEqual(missing["seams"][0]["status"], "unresolved_no_boundary_face")
        self.assertEqual(missing["records"], [])


if __name__ == "__main__":
    unittest.main()
