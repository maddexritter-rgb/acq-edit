import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "design_quality_gate.py"
SPEC = importlib.util.spec_from_file_location("design_quality_gate", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class DesignQualityGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.words = self.root / "words.json"
        self.words.write_text(json.dumps({"words": [
            {"word": word} for word in
            "what is wrong with growth the problem is churn because customers leave fix onboarding and retention improves".split()
        ]}))

    def tearDown(self):
        self.temp.cleanup()

    def make_clip(self, name="clip_a", segments=None, justification=""):
        segments = segments or [[0, 4], [5, 9], [10, 13], [14, 16]]
        clip = self.root / name
        clip.mkdir()
        plan = {
            "source_words": str(self.words),
            "interaction_words": [0, 16],
            "segments": [{"words": item} for item in segments],
            "editorial_review": {
                "hook": f"{name} specific question and tension",
                "payoff": f"{name} resolves with a concrete retention result",
                "context": f"{name} preserves the customer-loss context",
                "qualifications": f"{name} makes no unsupported universal claim",
                "omitted_branches": f"{name} removes no competing diagnosis",
                "reorder_safety": f"{name} keeps causal order intact",
                "ending_continuation": f"{name} ends after the result",
                "alternatives": f"{name} rejects the weaker chronological opening",
            },
        }
        plan_path = clip / "assembly_plan.json"
        plan_path.write_text(json.dumps(plan))
        quote = lambda ranges: " ".join(
            json.loads(self.words.read_text())["words"][i]["word"]
            for first, last in ranges for i in range(first, last + 1))
        comparison = {
            "schema": MODULE.SCHEMA,
            "reviewed_plan": {
                "path": "assembly_plan.json",
                "sha256": hashlib.sha256(plan_path.read_bytes()).hexdigest(),
            },
            "interaction": {"word_range": [0, 16], "text": quote([[0, 16]])},
            "unedited_baseline": {"word_ranges": [[0, 16]], "text": quote([[0, 16]])},
            "selected_assembly": {"word_ranges": segments, "text": quote(segments)},
            "hook": {"word_ranges": [segments[0]], "quote": quote([segments[0]]),
                     "why": f"{name} opens on the exact viewer problem immediately"},
            "retention_path": {"word_ranges": [segments[min(1, len(segments) - 1)]],
                               "quote": quote([segments[min(1, len(segments) - 1)]]),
                               "why": f"{name} names the causal mechanism that earns attention"},
            "payoff": {"word_ranges": [segments[-1]], "quote": quote([segments[-1]]),
                       "why": f"{name} lands on the concrete result promised at opening"},
            "content_unit": {
                "viewer": f"{name} serves an owner whose growth is constrained by churn",
                "promise": f"{name} promises to identify the growth constraint and corrective action",
                "reward": f"{name} delivers onboarding as the action tied to improved retention",
                "cold_viewer": f"{name} supplies the problem before the diagnosis without outside context",
                "goodwill": f"{name} gives a usable diagnostic and action without requiring an offer",
                "value_compression": f"{name} keeps the causal chain while removing no required reasoning",
                "audience_growth": f"{name} earns sharing from owners facing the same retention constraint",
            },
            "decisions": [
                {"scope": "opening", "word_ranges": [segments[0]],
                 "why": f"{name} starts with the direct question instead of throat clearing"},
                {"scope": "body", "word_ranges": [segments[min(1, len(segments) - 1)]],
                 "why": f"{name} retains the diagnosis required to understand the solution"},
                {"scope": "ending", "word_ranges": [segments[-1]],
                 "why": f"{name} stops on the result before conversational tail begins"},
            ],
            "single_span": len(segments) == 1,
            "clean_source_justification": justification,
            "alternative_review": {
                "meaningful_alternative": False,
                "why": f"{name} has no second arrangement that preserves a clearer causal chain",
            },
        }
        (clip / "design_comparison.json").write_text(json.dumps(comparison))
        return clip

    def test_valid_designed_clip_passes(self):
        self.make_clip()
        result = MODULE.evaluate_batch(self.root)
        self.assertEqual("PASS", result[0]["status"])

    def test_valid_editorial_worksheet_is_identity_checked(self):
        clip = self.make_clip()
        plan = json.loads((clip / "assembly_plan.json").read_text())
        ranges = [row["words"] for row in plan["segments"]]
        quote = lambda selected: " ".join(
            json.loads(self.words.read_text())["words"][i]["word"]
            for first, last in selected for i in range(first, last + 1))
        note = "Source-specific synthetic editorial reasoning long enough for structural validation."
        worksheet = {
            "schema": MODULE.WORKSHEET_SCHEMA,
            "source_words": {"path": str(self.words),
                             "sha256": plan.get("source_sha256")},
            "interaction_words": [0, 16],
            "interaction_text": quote([[0, 16]]),
            "source_read": note,
            "question_and_revealed_problem": note,
            "branch_ledger": [{"words": [0, 16], "disposition": "selected", "why": note}],
            "ranked_promises": [{"rank": 1, "promise": note, "why": note}],
            "selected_promise": note,
            "question_policy": {"policy": "retain", "why": note},
            "reasoning_ladder": [{"words": ranges[0], "why": note}],
            "payoff": {"words": ranges[-1], "quote": quote([ranges[-1]]), "why": note},
            "omissions": [{"words": [0, 0], "why": note}],
            "reorder_checks": [{"words": ranges[0], "why": note}],
            "proposed_assembly": {"word_ranges": ranges, "text": quote(ranges)},
            "cold_read": note,
            "meaningful_alternative": {"exists": False, "why": note},
        }
        # The fixture plan omits a source hash; use the same absent value to test identity.
        (clip / "editorial_worksheet.json").write_text(json.dumps(worksheet))
        self.assertEqual(MODULE.evaluate_clip(clip)["status"], "PASS")
        worksheet["proposed_assembly"]["word_ranges"] = [[0, 16]]
        (clip / "editorial_worksheet.json").write_text(json.dumps(worksheet))
        self.assertTrue(any("worksheet proposed ranges" in error
                            for error in MODULE.evaluate_clip(clip)["errors"]))

    def test_missing_comparison_fails(self):
        clip = self.make_clip()
        (clip / "design_comparison.json").unlink()
        result = MODULE.evaluate_batch(self.root)
        self.assertIn("design_comparison.json missing", result[0]["errors"])

    def test_single_span_requires_substantive_justification(self):
        self.make_clip(segments=[[0, 16]], justification="clean")
        result = MODULE.evaluate_batch(self.root)
        self.assertTrue(any("single-span" in error for error in result[0]["errors"]))

    def test_complete_clean_source_is_not_rejected_for_keep_ratio(self):
        self.make_clip(segments=[[0,16]], justification=(
            'The complete source is one compact question, causal explanation and action; '
            'there is no repeated setup or unrelated branch to remove in this fixture.'))
        self.assertEqual(MODULE.evaluate_batch(self.root)[0]['status'], 'PASS')

    def test_selected_ranges_must_match_plan(self):
        clip = self.make_clip()
        path = clip / "design_comparison.json"
        data = json.loads(path.read_text())
        data["selected_assembly"]["word_ranges"] = [[0, 16]]
        path.write_text(json.dumps(data))
        result = MODULE.evaluate_batch(self.root)
        self.assertTrue(any("do not exactly match" in error for error in result[0]["errors"]))

    def test_missing_content_unit_judgment_fails(self):
        clip = self.make_clip()
        path = clip / "design_comparison.json"
        data = json.loads(path.read_text())
        data["content_unit"].pop("reward")
        path.write_text(json.dumps(data))
        result = MODULE.evaluate_batch(self.root)
        self.assertTrue(any("content_unit reward" in error for error in result[0]["errors"]))

    def test_buried_hook_cannot_certify_setup_before_it(self):
        clip = self.make_clip()
        path = clip / 'design_comparison.json'
        data = json.loads(path.read_text())
        data['hook']['word_ranges'] = [[5,9]]
        data['hook']['quote'] = 'the problem is churn because'
        path.write_text(json.dumps(data))
        result = MODULE.evaluate_clip(clip)
        self.assertTrue(any('actual opening prefix' in e for e in result['errors']))

    def test_hook_cannot_reverse_opening_word_order(self):
        clip = self.make_clip()
        path = clip / 'design_comparison.json'
        data = json.loads(path.read_text())
        data['hook']['word_ranges'] = [[1,4],[0,0]]
        data['hook']['quote'] = 'is wrong with growth what'
        path.write_text(json.dumps(data))
        result = MODULE.evaluate_clip(clip)
        self.assertTrue(any('actual opening prefix' in e for e in result['errors']))

    def test_duplicate_editorial_evidence_blocks_batch(self):
        first = self.make_clip("clip_a")
        second = self.make_clip("clip_b")
        plan_a = json.loads((first / "assembly_plan.json").read_text())
        plan_b_path = second / "assembly_plan.json"
        plan_b = json.loads(plan_b_path.read_text())
        plan_b["editorial_review"] = plan_a["editorial_review"]
        plan_b_path.write_text(json.dumps(plan_b))
        comparison_b_path = second / "design_comparison.json"
        comparison_b = json.loads(comparison_b_path.read_text())
        comparison_b["reviewed_plan"]["sha256"] = hashlib.sha256(plan_b_path.read_bytes()).hexdigest()
        comparison_a = json.loads((first / "design_comparison.json").read_text())
        for key in ("hook", "retention_path", "payoff"):
            comparison_b[key] = comparison_a[key]
        comparison_b_path.write_text(json.dumps(comparison_b))
        result = MODULE.evaluate_batch(self.root)
        self.assertTrue(all(row["status"] == "FAIL" for row in result))
        self.assertTrue(any("templated duplicate" in error
                            for row in result for error in row["errors"]))


if __name__ == "__main__":
    unittest.main()
