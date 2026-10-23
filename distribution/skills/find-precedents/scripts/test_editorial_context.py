import hashlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from editorial_context import BrainUnavailable, fetch_context, save_context, validate_cards


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


class EditorialContextTests(unittest.TestCase):
    def setUp(self):
        config_dir = tempfile.TemporaryDirectory()
        self.addCleanup(config_dir.cleanup)
        self.config_dir = Path(config_dir.name)
        self.env = patch.dict(os.environ, {
            "EDITORIAL_BRAIN_FUNCTION_URL": "https://projectref.supabase.co/functions/v1/editorial-search",
            "EDITORIAL_BRAIN_READ_KEY": "test-key",
            "EDITORIAL_BRAIN_PROJECT_REF": "projectref",
            "EDITORIAL_BRAIN_CONFIG_DIR": config_dir.name,
        })
        self.env.start()
        self.addCleanup(self.env.stop)

    def response(self, *, body="A useful playbook with enough content to design a source-faithful clip.",
                 cards=None, required_reading=False, corrupt_reading=False,
                 project_prefix=None, held_out=None):
        sha = hashlib.sha256(body.encode()).hexdigest()
        payload = {
            "schema": "editorial-brain.context/v1", "project_ref": "projectref",
            "query": {"problem": "assembly preflight" if required_reading else "question context",
                      "format": "q_and_a", "limit": 5, "includeDevelopment": False,
                      "currentProjectPrefix": project_prefix, "heldOutSourcePrefixes": held_out or [],
                      "includeRequiredReading": required_reading, "readingOverlays": []},
            "playbooks": [
                {"format": "universal", "body": body, "body_sha256": sha, "version": 1},
                {"format": "q_and_a", "body": body, "body_sha256": sha, "version": 1},
            ], "cards": cards if cards is not None else [],
        }
        if required_reading:
            policies = []
            for profile, ordinal in (("universal", 1), ("q_and_a", 2)):
                policies.append({
                    "policy_id": f"assembly-{profile}-required", "format": profile,
                    "version": 1, "priority_note": "Read before design.",
                    "documents": [{"ordinal": 1, "source_id": f"source-{ordinal}",
                                   "source_title": f"{profile}.md", "source_body": body,
                                   "source_sha256": sha}],
                })
            if corrupt_reading:
                policies[1]["documents"][0]["source_sha256"] = "0" * 64
            payload["required_reading"] = {"policies": policies}
        return Response(json.dumps(payload).encode())

    def test_live_context_validated(self):
        with patch("urllib.request.urlopen", return_value=self.response()) as urlopen:
            result = fetch_context(problem="question context", fmt="q_and_a")
        self.assertEqual(len(result["playbooks"]), 2)
        request = urlopen.call_args.args[0]
        self.assertEqual(request.headers["Authorization"], "Bearer test-key")

    def test_missing_playbook_fails_closed(self):
        with patch("urllib.request.urlopen", return_value=self.response()):
            with self.assertRaises(BrainUnavailable):
                fetch_context(problem="question context", fmt="monologue")

    def test_required_batch_reading_is_requested_and_validated(self):
        with patch("urllib.request.urlopen", return_value=self.response(required_reading=True)) as urlopen:
            result = fetch_context(problem="assembly preflight", fmt="q_and_a", required_reading=True)
        self.assertEqual(len(result["required_reading"]["policies"]), 2)
        payload = json.loads(urlopen.call_args.args[0].data)
        self.assertTrue(payload["include_required_reading"])
        self.assertEqual(payload["reading_overlays"], [])

    def test_required_batch_reading_fails_closed_when_missing_or_corrupt(self):
        for response in (self.response(), self.response(required_reading=True, corrupt_reading=True)):
            with self.subTest(response=response.getvalue()[:80]):
                with patch("urllib.request.urlopen", return_value=response):
                    with self.assertRaises(BrainUnavailable):
                        fetch_context(problem="assembly preflight", fmt="q_and_a", required_reading=True)

    def test_overlay_requires_batch_preflight_and_matching_format(self):
        with self.assertRaises(BrainUnavailable):
            fetch_context(problem="question context", fmt="q_and_a", reading_overlays=["l1"])
        with self.assertRaises(BrainUnavailable):
            fetch_context(problem="assembly preflight", fmt="monologue",
                          required_reading=True, reading_overlays=["l1"])

    def test_no_configuration_fails_closed(self):
        os.environ.pop("EDITORIAL_BRAIN_READ_KEY")
        with self.assertRaises(BrainUnavailable):
            fetch_context(problem="question context", fmt="q_and_a")

    def test_secure_file_configuration(self):
        for name in ("EDITORIAL_BRAIN_FUNCTION_URL", "EDITORIAL_BRAIN_READ_KEY", "EDITORIAL_BRAIN_PROJECT_REF"):
            os.environ.pop(name)
        (self.config_dir / "context.json").write_text(json.dumps({
            "function_url": "https://projectref.supabase.co/functions/v1/editorial-search",
            "project_ref": "projectref",
        }))
        token_file = self.config_dir / "read_token"
        token_file.write_text("test-key\n")
        token_file.chmod(0o600)
        with patch("urllib.request.urlopen", return_value=self.response()) as urlopen:
            fetch_context(problem="question context", fmt="q_and_a")
        self.assertEqual(urlopen.call_args.args[0].headers["Authorization"], "Bearer test-key")

    def test_world_readable_token_fails_closed(self):
        os.environ.pop("EDITORIAL_BRAIN_READ_KEY")
        token_file = self.config_dir / "read_token"
        token_file.write_text("test-key\n")
        token_file.chmod(0o644)
        with self.assertRaises(BrainUnavailable):
            fetch_context(problem="question context", fmt="q_and_a")

    def test_wrong_project_fails_closed(self):
        os.environ["EDITORIAL_BRAIN_PROJECT_REF"] = "anotherproject"
        with self.assertRaises(BrainUnavailable):
            fetch_context(problem="question context", fmt="q_and_a")

    def test_bad_playbook_hash_fails_closed(self):
        response = self.response()
        payload = json.loads(response.getvalue())
        payload["playbooks"][0]["body_sha256"] = "0" * 64
        with patch("urllib.request.urlopen", return_value=Response(json.dumps(payload).encode())):
            with self.assertRaises(BrainUnavailable):
                fetch_context(problem="question context", fmt="q_and_a")

    def test_missing_playbook_version_fails_closed(self):
        response = self.response()
        payload = json.loads(response.getvalue())
        del payload["playbooks"][0]["version"]
        with patch("urllib.request.urlopen", return_value=Response(json.dumps(payload).encode())):
            with self.assertRaises(BrainUnavailable):
                fetch_context(problem="question context", fmt="q_and_a")

    def test_query_excludes_current_and_held_out_cases(self):
        with patch("urllib.request.urlopen", return_value=self.response(
                project_prefix="/current/project/", held_out=["/held-out/"])) as urlopen:
            fetch_context(problem="question context", fmt="q_and_a",
                          project_prefix="/current/project/", held_out=["/held-out/"])
        request = urlopen.call_args.args[0]
        payload = json.loads(request.data)
        self.assertEqual(payload["current_project_prefix"], "/current/project/")
        self.assertEqual(payload["held_out_source_prefixes"], ["/held-out/"])
        self.assertFalse(payload["include_development"])

    def test_response_query_must_match_request(self):
        response = self.response()
        payload = json.loads(response.getvalue())
        payload['query']['problem'] = 'another problem'
        with patch('urllib.request.urlopen', return_value=Response(json.dumps(payload).encode())):
            with self.assertRaises(BrainUnavailable):
                fetch_context(problem='question context', fmt='q_and_a')

    def test_card_evidence_format_and_exclusions_are_checked(self):
        card = {'card_id': 'condition', 'title': 'Keep condition', 'problem': 'Missing condition',
                'observed_choice': 'Kept condition', 'transferable_lesson': 'Keep necessary conditions',
                'exception_note': 'Answer may restate it', 'evidence_class': 'SOP_GUIDANCE',
                'source_uri': 'https://example.org/sop/1', 'verification_note': 'SOP only',
                'status': 'calibration', 'revision': 1, 'applicable_formats': ['q_and_a']}
        validate_cards([card], 'q_and_a', False, [])
        validate_cards([], 'q_and_a', False, [])
        for key, value in [('status', 'development'), ('status', 'retired'),
                           ('applicable_formats', ['monologue']), ('source_uri', ''),
                           ('exception_note', ''), ('revision', 0)]:
            with self.subTest(key=key, value=value), self.assertRaises(BrainUnavailable):
                validate_cards([{**card, key: value}], 'q_and_a', False, [])
        with self.assertRaises(BrainUnavailable):
            validate_cards([card], 'q_and_a', False, ['https://example.org/sop/'])
        with self.assertRaises(BrainUnavailable):
            validate_cards([card, card], 'q_and_a', False, [])
        validate_cards([{**card, 'status': 'development'}], 'q_and_a', True, [])

    def test_saved_receipt_pins_response_and_refuses_replacement(self):
        data = json.loads(self.response().getvalue())
        out = self.config_dir / 'context.json'
        saved = save_context(data, out)
        receipt = saved.pop('client_receipt')
        self.assertEqual(saved, data)
        encoded = json.dumps(saved, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
        self.assertEqual(receipt['response_sha256'], hashlib.sha256(encoded.encode()).hexdigest())
        original = out.read_bytes()
        with self.assertRaises(FileExistsError): save_context(data, out)
        self.assertEqual(out.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
