import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

MODULE = Path(__file__).parents[1] / "scripts" / "evidence.py"
spec = importlib.util.spec_from_file_location("edit_evidence", MODULE)
evidence = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evidence)


def record(case_id="1001", action="keep the complete mechanism"):
    return {"case_id": case_id, "stage": "assembly", "classification": "retrievable_precedent",
            "situation": "A procedural answer risks losing the method", "alternatives": ["shorten", "retain"],
            "chosen_action": action, "reasoning": "The steps are the payoff.",
            "evidence_paths": [{"path": __file__, "locator": "fixture"}], "exceptions": ["Do not retain repetition."],
            "confidence": .8, "owning_skill": "assembly-design", "promotion_status": "not_candidate"}


class EvidenceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        self.db = self.root / "memory.sqlite3"; self.ledger = self.root / "evidence.jsonl"; self.cx = evidence.connect(self.db)
    def tearDown(self): self.cx.close(); self.tmp.cleanup()
    def certify(self, decision_id, path=None):
        proof = {"proof_type": "captioned_final_timeline", "captions_visible": True,
                 "final_asset_path": str(path or (self.root / "captioned_final.mp4")),
                 "final_timeline_path": str(self.root / "final.prproj#sequence=FINAL"),
                 "timeline_verification": {"project_path": str(self.root / "final.prproj"),
                    "sequence_name": "FINAL", "sequence_id": "sequence-1",
                    "verified_against_export": True, "verification_method": "duration+audio+frames+captions",
                    "draft_sequences_excluded": True, "premiere_inspection_complete": True},
                 "analysis_chain_complete": True,
                 "stages_completed": ["cuts", "camera_reformatting", "captions"],
                 "raw_source_paths": [str(self.root / "raw.mp4")],
                 "frame_accurate_transcript_path": str(self.root / "raw.words.json"),
                 "case_study_manifest_path": str(self.root / "case-study.json")}
        return evidence.append_eligibility(self.cx, self.ledger, decision_id,
                                           "verified_captioned_final", "Visible captions prove the reference final.", proof)
    def test_append_is_idempotent_and_query_excludes_holdout(self):
        first, inserted = evidence.append_record(self.cx, self.ledger, record())
        again, inserted_again = evidence.append_record(self.cx, self.ledger, record())
        second, _ = evidence.append_record(self.cx, self.ledger, record("1002", "retain the procedural steps and remove repeated setup"))
        self.certify(first); self.certify(second)
        self.assertEqual(first, again); self.assertTrue(inserted); self.assertFalse(inserted_again)
        results = evidence.query(self.cx, "assembly", "procedural steps method", {"1001"}, 5, .3)
        self.assertTrue(results); self.assertTrue(all(r["case_id"] != "1001" for r in results)); self.assertTrue(results[0]["evidence_paths"])
    def test_holdout_filter_rejects_generic_record_that_mentions_case(self):
        leaked = record("FINDINGS", "Case #1001 keeps the complete mechanism")
        leaked["reasoning"] = "Aggregate synthesis cites 1001 as its supporting example."
        leaked_id, _ = evidence.append_record(self.cx, self.ledger, leaked)
        clean = record("1002", "Keep the complete mechanism after checking its dependencies")
        clean_id, _ = evidence.append_record(self.cx, self.ledger, clean)
        self.certify(leaked_id); self.certify(clean_id)
        results = evidence.query(self.cx, "assembly", "complete mechanism dependencies", {"1001"}, 5, .3)
        self.assertEqual(["1002"], [item["case_id"] for item in results])
    def test_holdout_filter_recovers_case_from_markdown_ancestry(self):
        study = self.root / "corpus.md"
        study.write_text("""# Corpus\n\n## Case 1001 - Hidden\n\n### Native selected story\n\nKeep the training mechanism through the concrete payoff.\n\n## Case 1002 - Visible\n\n### Native selected story\n\nKeep the pricing mechanism through the conditional payoff.\n""")
        hidden = record("corpus", "Keep the training mechanism through the concrete payoff.")
        hidden["evidence_paths"] = [{"path": str(study), "locator": "heading=Native selected story"}]
        visible = record("corpus-visible", "Keep the pricing mechanism through the conditional payoff.")
        visible["evidence_paths"] = [{"path": str(study), "locator": "heading=Native selected story"}]
        hidden_id, _ = evidence.append_record(self.cx, self.ledger, hidden)
        visible_id, _ = evidence.append_record(self.cx, self.ledger, visible)
        self.certify(hidden_id); self.certify(visible_id)
        results = evidence.query(self.cx, "assembly", "keep mechanism payoff", {"1001"}, 5, .3)
        self.assertEqual(["corpus-visible"], [item["case_id"] for item in results])
    def test_query_deduplicates_copied_findings(self):
        first = record("1002", "Keep the complete mechanism and its payoff")
        second = record("corpus", "Keep the complete mechanism and its payoff")
        first_id, _ = evidence.append_record(self.cx, self.ledger, first)
        second_id, _ = evidence.append_record(self.cx, self.ledger, second)
        self.certify(first_id); self.certify(second_id)
        results = evidence.query(self.cx, "assembly", "complete mechanism payoff", set(), 5, .3)
        self.assertEqual(1, len(results))
    def test_manifest_lock_fails_closed(self):
        manifest = self.root / "manifest.json"; manifest.write_text(json.dumps({"case": "1001"}))
        receipt = self.root / "lock.json"; evidence.lock_manifest(manifest, receipt, "baseline", "1001", ["1001"], [])
        with self.assertRaises(FileExistsError): evidence.lock_manifest(manifest, receipt, "baseline", "1001", ["1001"], [])
        self.assertFalse(json.loads(receipt.read_text())["reference_revealed"])
    def test_uncertified_and_nonfinal_records_never_retrieve(self):
        unresolved_id, _ = evidence.append_record(self.cx, self.ledger, record("1002", "unverified draft idea"))
        draft_id, _ = evidence.append_record(self.cx, self.ledger, record("1003", "working sequence idea"))
        evidence.append_eligibility(self.cx, self.ledger, draft_id, "quarantined_nonfinal",
                                    "Working sequence is a draft.", {"observed_path": "draft.prproj"})
        self.assertEqual("unresolved_final_identity", evidence.latest_eligibility(self.cx, unresolved_id)["status"])
        self.assertEqual([], evidence.query(self.cx, "assembly", "draft working idea", set(), 5, .0))
    def test_final_label_without_caption_proof_is_rejected(self):
        decision_id, _ = evidence.append_record(self.cx, self.ledger, record())
        with self.assertRaises(ValueError):
            evidence.append_eligibility(self.cx, self.ledger, decision_id, "verified_captioned_final",
                                        "Filename says FINAL.", {"proof_type": "captioned_export", "captions_visible": False,
                                                               "final_asset_path": "something_FINAL.mp4"})
    def test_final_only_observation_without_end_to_end_chain_does_not_retrieve(self):
        decision_id, _ = evidence.append_record(self.cx, self.ledger, record())
        proof = {"proof_type": "captioned_export", "captions_visible": True,
                 "final_asset_path": "captioned-final.mp4", "analysis_chain_complete": False}
        evidence.append_eligibility(self.cx, self.ledger, decision_id, "verified_captioned_final",
                                    "Final is verified but raw-to-final analysis is incomplete.", proof)
        self.assertEqual([], evidence.query(self.cx, "assembly", "complete mechanism", set(), 5, .0))
    def test_export_only_chain_cannot_be_marked_complete(self):
        decision_id, _ = evidence.append_record(self.cx, self.ledger, record())
        proof = {"proof_type": "captioned_export", "captions_visible": True,
                 "final_asset_path": "captioned-final.mp4", "analysis_chain_complete": True,
                 "stages_completed": ["cuts", "camera_reformatting", "captions"],
                 "raw_source_paths": ["raw.mp4"], "frame_accurate_transcript_path": "raw.words.json",
                 "case_study_manifest_path": "case-study.json"}
        with self.assertRaisesRegex(ValueError, "Premiere timeline"):
            evidence.append_eligibility(self.cx, self.ledger, decision_id, "verified_captioned_final",
                                        "Export-only inference is preliminary.", proof)
    def test_captioned_final_certification_enables_retrieval(self):
        decision_id, _ = evidence.append_record(self.cx, self.ledger, record())
        self.certify(decision_id)
        results = evidence.query(self.cx, "assembly", "complete mechanism", set(), 5, .3)
        self.assertEqual([decision_id], [item["id"] for item in results])
        self.assertEqual("verified_captioned_final", results[0]["final_eligibility"]["status"])
    def test_complete_case_can_activate_only_cleared_stages(self):
        cut_record = record("1444", "preserve the mechanism-bearing cut")
        cut_record["stage"] = "cuts"; cut_record["owning_skill"] = "cut"
        audio_record = record("1444", "copy the delivered close tail")
        audio_record["stage"] = "audio"; audio_record["owning_skill"] = "audit-audio"
        cut_id, _ = evidence.append_record(self.cx, self.ledger, cut_record)
        audio_id, _ = evidence.append_record(self.cx, self.ledger, audio_record)
        proof = {"proof_type": "captioned_final_timeline", "captions_visible": True,
                 "final_asset_path": str(self.root / "captioned_final.mp4"),
                 "final_timeline_path": str(self.root / "final.prproj#sequence=FINAL"),
                 "timeline_verification": {"project_path": str(self.root / "final.prproj"),
                    "sequence_name": "FINAL", "sequence_id": "sequence-1",
                    "verified_against_export": True, "verification_method": "duration+audio+frames+captions",
                    "draft_sequences_excluded": True, "premiere_inspection_complete": True},
                 "analysis_chain_complete": True,
                 "stages_completed": ["cuts", "camera_reformatting", "captions", "audio", "qa"],
                 "eligible_stages": ["cuts"],
                 "raw_source_paths": [str(self.root / "raw.mp4")],
                 "frame_accurate_transcript_path": str(self.root / "raw.words.json"),
                 "case_study_manifest_path": str(self.root / "case-study.json")}
        for decision_id in (cut_id, audio_id):
            evidence.append_eligibility(self.cx, self.ledger, decision_id, "verified_captioned_final",
                                        "Only the cuts stage cleared its independent gate.", proof)
        self.assertEqual([cut_id], [item["id"] for item in evidence.query(self.cx, "cuts", "mechanism cut", set(), 5, .0)])
        self.assertEqual([], evidence.query(self.cx, "audio", "close tail", set(), 5, .0))


if __name__ == "__main__": unittest.main()
