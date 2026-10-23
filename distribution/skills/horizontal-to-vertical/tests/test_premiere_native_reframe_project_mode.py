"""Offline tests for project selection; never connect to the Premiere bridge."""

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "premiere_native_reframe.py"
SPEC = importlib.util.spec_from_file_location("premiere_native_reframe", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ProjectModeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        home_patch = patch.object(Path, "home", return_value=Path(self.temp.name))
        home_patch.start()
        self.addCleanup(home_patch.stop)
        self.project = Path(self.temp.name) / "weekly.prproj"
        self.source = {"project_path": str(self.project), "sequence_id": "source-uid"}

    def test_default_clones_sequence_without_saving_new_project(self):
        with patch.object(MODULE, "bridge_call", return_value={"project_path": str(self.project)}) as call:
            MODULE.duplicate_vertical(self.source, None, "VERTICAL_REVIEW")
        jsx = call.call_args.args[1]
        self.assertIn("SEQUENCE_CLONE_FAILED", jsx)
        self.assertIn("DEST_SEQUENCE_EXISTS", jsx)
        self.assertNotIn("saveAs(", jsx)
        self.assertFalse(self.project.exists())

    def test_explicit_copy_keeps_recovery_route(self):
        copy = Path(self.temp.name) / "backup-only.prproj"
        with patch.object(MODULE, "bridge_call", return_value={}) as call:
            MODULE.duplicate_vertical(self.source, copy, "VERTICAL_REVIEW")
        self.assertIn("saveAs(", call.call_args.args[1])
        self.assertIn(str(copy), call.call_args.args[1])

    def test_copy_cannot_overwrite_current_or_existing_project(self):
        with self.assertRaises(ValueError):
            MODULE.duplicate_vertical(self.source, self.project, "VERTICAL_REVIEW")
        other = Path(self.temp.name) / "existing.prproj"
        other.touch()
        with self.assertRaises(FileExistsError):
            MODULE.duplicate_vertical(self.source, other, "VERTICAL_REVIEW")

    def test_cli_default_passes_no_project_copy(self):
        inspection = {
            **self.source,
            "sequence_name": "SOURCE",
            "width": 3840,
            "height": 2160,
            "video_tracks": [],
        }
        vertical = {**inspection, "sequence_name": "SOURCE_NATIVE_VERTICAL_REVIEW", "width": 1080, "height": 1920}
        args = [str(SCRIPT), "--work-dir", str(Path(self.temp.name) / "report")]
        with (
            patch.object(sys, "argv", args),
            patch.object(MODULE, "inspect_active", side_effect=[inspection, vertical]),
            patch.object(MODULE, "duplicate_vertical") as duplicate,
            patch.object(MODULE, "build_plan", return_value={"records": []}),
            patch.object(MODULE, "apply_plan", return_value={}),
            patch.object(MODULE, "verify", return_value={"bad_records": [], "keyed_items": 0}),
        ):
            MODULE.main()
        self.assertIsNone(duplicate.call_args.args[1])

    def test_existing_seam_mode_only_writes_a_plan(self):
        work = Path(self.temp.name) / "seams"
        plan = {"schema": "premiere-native-x-seam-repair/v1", "records": [], "seams": []}
        args = [str(SCRIPT), "--repair-existing-seams", "--work-dir", str(work)]
        with (
            patch.object(sys, "argv", args),
            patch.object(MODULE, "inspect_active", return_value=self.source),
            patch.object(MODULE, "build_existing_seam_plan", return_value=plan),
            patch.object(MODULE, "duplicate_vertical") as duplicate,
            patch.object(MODULE, "apply_existing_seam_plan") as apply,
        ):
            MODULE.main()
        self.assertTrue((work / "existing_x_seam_plan.json").is_file())
        duplicate.assert_not_called()
        apply.assert_not_called()

    def test_existing_seam_apply_never_duplicates_or_rebuilds(self):
        plan_path = Path(self.temp.name) / "repair.json"
        plan_path.write_text(json.dumps({"schema": "premiere-native-x-seam-repair/v1", "records": [], "seams": []}))
        args = [str(SCRIPT), "--apply-repair-plan", str(plan_path)]
        with (
            patch.object(sys, "argv", args),
            patch.object(MODULE, "inspect_active", return_value=self.source),
            patch.object(MODULE, "duplicate_vertical") as duplicate,
            patch.object(MODULE, "apply_existing_seam_plan", return_value={"bad_keys": [], "changed_items": 0}) as apply,
            patch.object(MODULE, "apply_plan") as rebuild,
        ):
            MODULE.main()
        self.assertEqual(apply.call_count, 1)
        duplicate.assert_not_called()
        rebuild.assert_not_called()

    def test_existing_repair_script_preflights_keys_before_x_only_write(self):
        plan = {"schema": "premiere-native-x-seam-repair/v1", "records": [{}], "baseline_items": [{}]}
        with patch.object(MODULE, "bridge_call", return_value={}) as call:
            MODULE.apply_existing_seam_plan(Path(self.temp.name) / "repair.json", plan)
        jsx = call.call_args.args[1]
        self.assertLess(jsx.index("var checked=[]"), jsx.index("row.anchor.setValueAtKey"))
        self.assertIn("ACTIVE_SEQUENCE_CHANGED", jsx)
        self.assertIn("EDIT_CHANGED", jsx)
        self.assertIn("KEY_CHANGED", jsx)
        self.assertIn("row.record.new_anchor_keys[j].value", jsx)
        self.assertNotIn("clone()", jsx)
        self.assertNotIn("setSettings(", jsx)
        self.assertNotIn("prop(c,'Position').setValue", jsx)


if __name__ == "__main__":
    unittest.main()
