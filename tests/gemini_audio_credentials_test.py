import importlib.util
import os
from pathlib import Path
import unittest
from unittest.mock import patch


class ListenerCredentialTests(unittest.TestCase):
    def setUp(self):
        path = Path(__file__).resolve().parents[1]/'distribution/skills/_shared/gemini_audio.py'
        spec = importlib.util.spec_from_file_location('listener_credentials_test', path)
        self.listener = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.listener)

    def test_configured_key_is_used_without_private_files(self):
        with patch.dict(os.environ, {'GEMINI_API_KEY': ' test-paid ', 'GEMINI_FALLBACK_API_KEY': 'test-fallback'}, clear=True), patch.object(Path, 'read_text', side_effect=AssertionError('private credential read')):
            self.assertEqual(self.listener.credential(), 'test-paid')
            self.assertEqual(self.listener.credential('fallback'), 'test-fallback')

    def test_missing_keys_and_unknown_slots_fail_without_filesystem_fallback(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(Path, 'read_text', side_effect=AssertionError('private credential read')):
            for slot in ['paid', 'fallback', 'unexpected']:
                with self.assertRaises(ValueError):
                    self.listener.credential(slot)


if __name__ == '__main__':
    unittest.main()
