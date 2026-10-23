"""Packaging failure boundaries; full packaged MCP startup is also checked during installation."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from prepare_premiere_runtime import copy_resources, check_transport, REQUIRED_TOOLS


class PremiereRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='acq runtime spaces ')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'src/resources').mkdir(parents=True)
        (self.root / 'lab').mkdir()
        self.source = self.root / 'src/resources/adobe-uxp-coverage.json'
        self.source.write_text('{"entries":[]}')
        self.cli = self.root / 'fixture.py'

    def test_resources_preserve_bytes_and_refuse_conflicts_before_copy(self):
        hashes = copy_resources(self.root)
        target = self.root / 'dist/resources/adobe-uxp-coverage.json'
        self.assertEqual(target.read_bytes(), self.source.read_bytes())
        self.assertEqual(copy_resources(self.root), hashes)
        target.write_text('{"user":"change"}')
        (self.root / 'src/resources/new.json').write_text('{}')
        with self.assertRaisesRegex(RuntimeError, 'Conflicting'):
            copy_resources(self.root)
        self.assertFalse((self.root / 'dist/resources/new.json').exists())
        self.assertEqual(json.loads(target.read_text()), {'user': 'change'})

    def test_bad_json_never_creates_runtime_resources(self):
        (self.root / 'src/resources/invalid.json').write_text('invalid')
        with self.assertRaises(json.JSONDecodeError):
            copy_resources(self.root)
        self.assertFalse((self.root / 'dist/resources').exists())

    def test_startup_failure_or_missing_capability_never_writes_success_receipt(self):
        for script in ['raise RuntimeError("missing module")', 'print(\'{"count":0,"tools":[]}\')']:
            self.cli.write_text(script)
            with self.assertRaises(RuntimeError):
                check_transport(self.root, self.root / 'profile.json', self.cli, {})
            self.assertFalse((self.root / 'lab/runtime-preparation.json').exists())

    def test_receipt_records_transport_only_and_preserves_existing_receipt(self):
        catalog = {'count': len(REQUIRED_TOOLS), 'tools': sorted(REQUIRED_TOOLS)}
        self.cli.write_text('import sys\nassert sys.argv[-1] == "tools"\nprint(' + repr(json.dumps(catalog)) + ')')
        result = check_transport(self.root, self.root / 'profile.json', self.cli, copy_resources(self.root))
        self.assertTrue(result['transportInitialized'])
        self.assertFalse(result['hostToolsCalled'])
        self.assertFalse(result['hostQualified'])
        target = self.root / 'lab/runtime-preparation.json'
        before = target.read_bytes()
        with self.assertRaises(FileExistsError):
            check_transport(self.root, self.root / 'profile.json', self.cli, {})
        self.assertEqual(target.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
