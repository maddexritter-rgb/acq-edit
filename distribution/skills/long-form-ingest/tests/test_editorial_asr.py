import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ASR_PATH = Path(__file__).resolve().parents[2] / "_shared" / "asr.py"
SPEC = importlib.util.spec_from_file_location("shared_asr", ASR_PATH)
ASR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ASR)


class EditorialAsrTests(unittest.TestCase):
    def audio(self):
        temp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        temp.write(b"fixture")
        temp.close()
        self.addCleanup(lambda: Path(temp.name).unlink(missing_ok=True))
        return temp.name

    def test_editorial_profile_prefers_assemblyai(self):
        path = self.audio()
        result = {"engine": "assemblyai", "words": [{"word": "um"}], "segments": []}
        with patch.object(ASR, "_wav16", return_value=path), \
                patch.object(ASR, "assemblyai_key", return_value="key"), \
                patch.object(ASR, "_assemblyai", return_value=result) as assembly, \
                patch.object(ASR, "_groq") as groq:
            actual = ASR.transcribe(path, use_cache=False, profile="editorial_ingest")
        assembly.assert_called_once()
        groq.assert_not_called()
        self.assertEqual(actual["engine"], "assemblyai")
        self.assertEqual(actual["evidence_status"], "FULL")

    def test_whisper_fallback_is_partial_editorial_evidence(self):
        path = self.audio()
        result = {"engine": "groq", "words": [{"word": "hello"}], "segments": []}
        with patch.object(ASR, "_wav16", return_value=path), \
                patch.object(ASR, "assemblyai_key", return_value="key"), \
                patch.object(ASR, "_assemblyai", return_value=None), \
                patch.object(ASR, "groq_key", return_value="key"), \
                patch.object(ASR, "_groq", return_value=result):
            actual = ASR.transcribe(path, use_cache=False, profile="editorial_ingest")
        self.assertEqual(actual["evidence_status"], "PARTIAL")
        self.assertTrue(actual["limitations"])

    def fake_assemblyai(self, outcomes):
        calls = []

        def fake(wav, key, prompt, keyterms):
            calls.append(key)
            error, result = outcomes[len(calls) - 1]
            ASR._LAST_AAI_ERROR = error
            return result
        return fake, calls

    def test_account_refusal_rotates_to_backup_key(self):
        path = self.audio()
        good = {"engine": "assemblyai", "words": [{"word": "hi"}], "segments": []}
        fake, calls = self.fake_assemblyai([
            ("HTTPStatusError: 400 {\"error\": \"Your current account balance is negative.\"}", None),
            ("", good)])
        with patch.object(ASR, "_wav16", return_value=path), \
                patch.object(ASR, "assemblyai_keys", return_value=["primary", "backup"]), \
                patch.object(ASR, "_assemblyai", side_effect=fake), \
                patch.object(ASR, "_groq") as groq:
            actual = ASR.transcribe(path, use_cache=False, profile="editorial_ingest")
        self.assertEqual(calls, ["primary", "backup"])
        groq.assert_not_called()
        self.assertEqual(actual["evidence_status"], "FULL")

    def test_timeout_does_not_rotate_keys(self):
        path = self.audio()
        fallback = {"engine": "groq", "words": [{"word": "hi"}], "segments": []}
        fake, calls = self.fake_assemblyai([("RuntimeError: transcription poll timed out", None)])
        with patch.object(ASR, "_wav16", return_value=path), \
                patch.object(ASR, "assemblyai_keys", return_value=["primary", "backup"]), \
                patch.object(ASR, "_assemblyai", side_effect=fake), \
                patch.object(ASR, "groq_key", return_value="key"), \
                patch.object(ASR, "_groq", return_value=fallback):
            actual = ASR.transcribe(path, use_cache=False, profile="editorial_ingest")
        self.assertEqual(calls, ["primary"])
        self.assertEqual(actual["evidence_status"], "PARTIAL")

    def test_audit_profile_does_not_call_assemblyai(self):
        path = self.audio()
        result = {"engine": "groq", "words": [{"word": "hello"}], "segments": []}
        with patch.object(ASR, "_wav16", return_value=path), \
                patch.object(ASR, "_assemblyai") as assembly, \
                patch.object(ASR, "groq_key", return_value="key"), \
                patch.object(ASR, "_groq", return_value=result):
            actual = ASR.transcribe(path, use_cache=False, profile="audit")
        assembly.assert_not_called()
        self.assertEqual(actual["engine"], "groq")


if __name__ == "__main__":
    unittest.main()
