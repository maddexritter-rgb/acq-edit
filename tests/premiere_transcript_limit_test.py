import hashlib
import importlib.util
from pathlib import Path
import sys
import tempfile
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
bootstrap = types.ModuleType('acq_edit_runtime')
bootstrap.skill_scripts = lambda: ROOT / '.local/skills'
sys.modules.setdefault('acq_edit_runtime', bootstrap)
spec = importlib.util.spec_from_file_location('assembly_validator', ROOT / 'integrations/premiere-agent/scripts/validate-assembly-import.py')
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


class TranscriptLimitTests(unittest.TestCase):
    def test_large_transcript_keeps_hash_check_and_xml_limit(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            source = root / 'words.json'
            data = b' ' * 8_000_001
            source.write_bytes(data)
            digest = hashlib.sha256(data).hexdigest()
            self.assertEqual(validator.checked(source, digest, root, transcript=True), data)
            with self.assertRaisesRegex(ValueError, 'XML/receipt size limit'):
                validator.checked(source, digest, root)
            with self.assertRaisesRegex(ValueError, 'hash changed'):
                validator.checked(source, '0' * 64, root, transcript=True)

    def test_transcript_is_still_bounded(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            source = root / 'words.json'
            with source.open('wb') as stream:
                stream.truncate(32_000_001)
            with self.assertRaisesRegex(ValueError, 'transcript size limit'):
                validator.checked(source, '0' * 64, root, transcript=True)


if __name__ == '__main__':
    unittest.main()
