#!/usr/bin/env python3
"""Regression tests for structural cut-map and packet promotion gates."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from validate_cut_map import validate as validate_map
from validate_packet import validate as validate_packet


def map_fixture():
    digest = "a" * 64
    return {
        "schema": "editorial-brain.cut-map/v1", "case_id": "case-1",
        "certification": "development", "project_sha256": digest,
        "final_asset_sha256": "b" * 64, "sequence_uid": "native-sequence-1",
        "timebase": {"ticks_per_second": 254016000000, "frame_rate_num": 30000,
                     "frame_rate_den": 1001, "frame_ticks": 8475667200,
                     "final_duration_frames": 60},
        "raw_sources": [{"source_id": "mic", "uri": "/source.wav", "sha256": digest,
                         "sample_rate": 48000, "sample_count": 96000}],
        "kept": [{"passage_id": "p1", "native_item_id": "item-1", "source_id": "mic",
                  "source_start_sample": 0, "source_end_sample": 48000,
                  "timeline_start_ticks": 0, "timeline_end_ticks": 30 * 8475667200,
                  "final_start_frame": 0, "final_end_frame": 30, "audible_role": "primary",
                  "delivery_audio_lineage": [], "final_audio_match": "unresolved",
                  "start_edge_error_frames": None, "end_edge_error_frames": None,
                  "evidence_uri": "/native-item.json"}],
        "omissions": [], "reordered": [], "joins": [], "transitions": [],
        "verification": {"final_native_identity_receipt_uri": None,
                         "audible_coverage": "partial", "boundary_review_receipt_uri": None,
                         "editorial_comparison_receipt_uri": None,
                         "unresolved": ["final audio not matched"]},
    }


def packet_fixture():
    return {
        "schema": "editorial-brain.packet/v1", "packet_id": "case-1-cut-v1",
        "card_id": "case-1-cut", "revision": 1, "stage": "assembly",
        "status": "verified_final", "evidence_kind": "raw_native_study",
        "evidence_class": "RAW_NATIVE_FINAL", "source": {
            "case_id": "case-1", "project_uri": "/project.prproj",
            "project_sha256": "a" * 64, "raw_media_uri": "/source.wav",
            "raw_media_sha256": "a" * 64, "final_asset_uri": "/final.mp4",
            "final_asset_sha256": "b" * 64, "premiere_sequence": "native-sequence-1",
            "source_locator": "samples 0-48000", "timeline_locator": "frames 0-30"},
        "decision": {"title": "Example", "problem": "Question depends on context",
                     "observed_choice": "Keep context", "alternatives": ["Omit context"],
                     "transferable_lesson": "Check referents", "exception_note": "Self-contained answer",
                     "applicable_formats": ["q_and_a"]},
        "verification": {"native_source_mapping": True, "visible_final_match": True,
                         "captions_checked": True, "audio_checked": True,
                         "method": "Matched the exact captioned export to the native sequence and source audio.",
                         "gaps": []},
        "provenance": {"author_type": "researcher", "source_uri": "/research.md",
                       "created_at": "2026-09-24"},
    }


def add_second_passage(data, start_frame):
    passage = dict(data["kept"][0])
    passage.update(passage_id="p2", native_item_id="item-2",
                   source_start_sample=48000, source_end_sample=96000,
                   timeline_start_ticks=start_frame * 8475667200,
                   timeline_end_ticks=60 * 8475667200,
                   final_start_frame=start_frame, final_end_frame=60)
    data["kept"].append(passage)
    return data


class CutValidationTests(unittest.TestCase):
    def test_development_map_passes_without_pretending_to_verify_audio(self):
        self.assertEqual(validate_map(map_fixture()), [])

    def test_frame_reviewed_rejects_unheard_seams(self):
        data = map_fixture()
        data["certification"] = "frame_reviewed"
        self.assertTrue(any("frame_reviewed" in error for error in validate_map(data)))

    def test_development_overlap_is_not_an_audible_join(self):
        data = add_second_passage(map_fixture(), 20)
        data["transitions"] = [{"left_passage_id": "p1", "right_passage_id": "p2",
                                "kind": "overlap", "final_frame": 20,
                                "listening_status": "unresolved", "edge_error_frames": None,
                                "evidence_uri": "/overlap-review.json"}]
        self.assertEqual(validate_map(data), [])

    def test_overlap_cannot_be_mislabeled_as_serial_seam(self):
        data = add_second_passage(map_fixture(), 20)
        data["transitions"] = [{"left_passage_id": "p1", "right_passage_id": "p2",
                                "kind": "serial_seam", "final_frame": 20,
                                "listening_status": "pass", "edge_error_frames": 0,
                                "evidence_uri": "/review.json"}]
        self.assertTrue(any("disagrees with timeline intervals" in e for e in validate_map(data)))

    def test_frame_reviewed_requires_typed_transition_not_legacy_join(self):
        data = add_second_passage(map_fixture(), 30)
        data["certification"] = "frame_reviewed"
        data["joins"] = [{"left_passage_id": "p1", "right_passage_id": "p2",
                          "final_frame": 30, "listening_status": "pass",
                          "edge_error_frames": 0, "evidence_uri": "/join.json"}]
        errors = validate_map(data)
        self.assertTrue(any("requires serial_seam transition p1 -> p2" in e for e in errors), errors)

    def test_gap_is_distinct_from_overlap(self):
        data = add_second_passage(map_fixture(), 40)
        data["transitions"] = [{"left_passage_id": "p1", "right_passage_id": "p2",
                                "kind": "gap", "final_frame": 40,
                                "listening_status": "unresolved", "edge_error_frames": None,
                                "evidence_uri": "/gap-review.json"}]
        self.assertEqual(validate_map(data), [])

    def test_verified_packet_rejects_development_map_even_when_pinned(self):
        data = map_fixture()
        packet = packet_fixture()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cut-map.json"
            raw = json.dumps(data).encode()
            path.write_bytes(raw)
            packet["source"]["cut_map_uri"] = str(path)
            packet["source"]["cut_map_sha256"] = hashlib.sha256(raw).hexdigest()
            errors = validate_packet(packet)
        self.assertTrue(any("frame_reviewed cut map" in error for error in errors), errors)

    def test_verified_packet_rejects_changed_map_bytes(self):
        data = map_fixture()
        packet = packet_fixture()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cut-map.json"
            path.write_text(json.dumps(data))
            packet["source"]["cut_map_uri"] = str(path)
            packet["source"]["cut_map_sha256"] = "0" * 64
            errors = validate_packet(packet)
        self.assertTrue(any("does not match cut map" in error for error in errors), errors)

    def test_structurally_reviewed_map_and_pinned_packet_pass(self):
        data = map_fixture()
        data["certification"] = "frame_reviewed"
        data["timebase"]["final_duration_frames"] = 30
        data["kept"][0].update(final_audio_match="confirmed", start_edge_error_frames=0.2,
                               end_edge_error_frames=0.4)
        packet = packet_fixture()
        with tempfile.TemporaryDirectory() as directory:
            for name in ("final_native_identity", "boundary_review", "editorial_comparison"):
                receipt = Path(directory) / f"{name}.json"
                raw_receipt = json.dumps({"case_id": "case-1", "kind": name}).encode()
                receipt.write_bytes(raw_receipt)
                data["verification"][f"{name}_receipt_uri"] = str(receipt)
                data["verification"][f"{name}_receipt_sha256"] = hashlib.sha256(raw_receipt).hexdigest()
            data["verification"].update(audible_coverage="complete", unresolved=[])
            self.assertEqual(validate_map(data), [])
            path = Path(directory) / "cut-map.json"
            raw = json.dumps(data).encode()
            path.write_bytes(raw)
            packet["source"]["cut_map_uri"] = str(path)
            packet["source"]["cut_map_sha256"] = hashlib.sha256(raw).hexdigest()
            self.assertEqual(validate_packet(packet), [])

    def test_reviewed_parallel_overlap_passes_without_fake_join(self):
        data = add_second_passage(map_fixture(), 20)
        data["certification"] = "frame_reviewed"
        for passage in data["kept"]:
            passage.update(final_audio_match="confirmed", start_edge_error_frames=0,
                           end_edge_error_frames=0)
        data["transitions"] = [{"left_passage_id": "p1", "right_passage_id": "p2",
                                "kind": "overlap", "final_frame": 20,
                                "listening_status": "pass", "edge_error_frames": 0.5,
                                "evidence_uri": "/actual-listening-review.json"}]
        with tempfile.TemporaryDirectory() as directory:
            for name in ("final_native_identity", "boundary_review", "editorial_comparison"):
                receipt = Path(directory) / f"{name}.json"
                raw = json.dumps({"case_id": "case-1", "kind": name}).encode()
                receipt.write_bytes(raw)
                data["verification"][f"{name}_receipt_uri"] = str(receipt)
                data["verification"][f"{name}_receipt_sha256"] = hashlib.sha256(raw).hexdigest()
            data["verification"].update(audible_coverage="complete", unresolved=[])
            self.assertEqual(validate_map(data), [])


if __name__ == "__main__":
    unittest.main()
