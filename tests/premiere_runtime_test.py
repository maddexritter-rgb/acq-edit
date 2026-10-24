"""Packaging failure boundaries; full packaged MCP startup is also checked during installation."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
import shutil
import os
import subprocess
import hashlib
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from prepare_premiere_runtime import copy_resources, check_transport, REQUIRED_TOOLS, prepare_helpers, verify_helpers
from materialize import materialize
from package_premiere import package

REPO = Path(__file__).resolve().parents[1]


class PremiereSnapshotTests(unittest.TestCase):
    def test_missing_helper_or_changed_patch_never_partially_overwrites_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'upstream'
            for name in ('src', 'cep-plugin', 'uxp-plugin', 'registry', 'scripts'):
                (source / name).mkdir(parents=True)
            names = ('package.json', 'package-lock.json', 'tsconfig.json', 'LICENSE',
                     'scripts/lab-prepare.mjs', 'scripts/validate-assembly-import.py',
                     'scripts/validate-master-import.py', 'scripts/assembly-master-compiler.py',
                     'scripts/prepare-assembly-coverage.py')
            for name in names:
                (source / name).write_text('fixture source')
            dest = root / 'integrations/premiere-agent'
            dest.mkdir(parents=True)
            (dest / 'package.json').write_text('retained dependency patch')
            sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
            overrides = root / 'integrations/premiere-distribution-overrides.json'
            overrides.write_text(json.dumps({'files': [{'path': 'package.json',
                'originalSourceSha256': sha(source / 'package.json'),
                'distributionSha256': sha(dest / 'package.json')}]}))
            missing = source / names[-1]
            missing.unlink()
            with self.assertRaisesRegex(RuntimeError, 'Missing required'):
                package(source, root)
            self.assertEqual(list(dest.iterdir()), [dest / 'package.json'])
            missing.write_text('fixture source')
            package(source, root)
            self.assertEqual((dest / 'package.json').read_text(), 'retained dependency patch')
            before = {str(p.relative_to(dest)): p.read_bytes() for p in dest.rglob('*') if p.is_file()}
            (source / 'package.json').write_text('upstream changed')
            with self.assertRaisesRegex(RuntimeError, 'needs review'):
                package(source, root)
            self.assertEqual(before, {str(p.relative_to(dest)): p.read_bytes() for p in dest.rglob('*') if p.is_file()})


class PremiereHelperTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='acq helper spaces ')
        self.addCleanup(self.tmp.cleanup)
        self.toolkit = Path(self.tmp.name).resolve() / 'toolkit'
        self.toolkit.mkdir()
        for name in ('scripts', 'distribution', 'docs'):
            shutil.copytree(REPO / name, self.toolkit / name, ignore=shutil.ignore_patterns('__pycache__'))
        (self.toolkit / 'integrations').mkdir()
        for name in ('premiere-source-manifest.json', 'premiere-distribution-overrides.json'):
            shutil.copyfile(REPO / 'integrations' / name, self.toolkit / 'integrations' / name)
        materialize(self.toolkit, self.toolkit / 'assets')
        self.runtime = self.toolkit / '.local/premiere-agent'
        shutil.copytree(REPO / 'integrations/premiere-agent/scripts', self.runtime / 'scripts',
                        ignore=shutil.ignore_patterns('__pycache__'))

    def test_real_helper_and_compiler_imports_need_no_global_skill_tree(self):
        home = Path(self.tmp.name) / 'empty home'
        home.mkdir()
        with patch.dict(os.environ, {'HOME': str(home)}):
            hashes = prepare_helpers(self.runtime, self.toolkit)
        self.assertEqual(len(hashes), 5)
        self.assertEqual(hashes, verify_helpers(self.runtime, self.toolkit))
        self.assertEqual(list(home.iterdir()), [])
        original = (self.runtime / 'scripts/acq_edit_runtime.py').read_bytes()
        with self.assertRaises(FileExistsError):
            prepare_helpers(self.runtime, self.toolkit)
        self.assertEqual((self.runtime / 'scripts/acq_edit_runtime.py').read_bytes(), original)

    def test_changed_packaged_helper_is_preserved_and_refused(self):
        target = self.runtime / 'scripts/validate-master-import.py'
        target.write_text('user changes')
        with self.assertRaisesRegex(RuntimeError, 'hash mismatch'):
            prepare_helpers(self.runtime, self.toolkit)
        self.assertEqual(target.read_text(), 'user changes')

    def test_modified_local_compiler_cannot_pass_setup(self):
        target = self.toolkit / '.local/skills/edit/scripts/compile_assembly.py'
        target.write_text('user compiler')
        with self.assertRaises(subprocess.CalledProcessError):
            prepare_helpers(self.runtime, self.toolkit)
        self.assertEqual(target.read_text(), 'user compiler')

    def test_exact_compiler_replay_rejects_changed_source_ranges(self):
        prepare_helpers(self.runtime, self.toolkit)
        target = self.runtime / 'lab/runtime/fixtures/replay'
        result = subprocess.run([sys.executable, '-B', str(REPO / 'scripts/premiere_assembly_fixture.py'),
                                 '--runtime', str(self.runtime), '--output', str(target)],
                                check=True, text=True, capture_output=True)
        report = json.loads(result.stdout)
        self.assertFalse(report['nativeHostCalled'])
        self.assertFalse(report['editorialApproved'])
        self.assertEqual(report['verification'], 'canonical_v2_selection_recompiled_and_exact_xml_reproduced')
        xml = Path(report['xml']).read_bytes()
        resolved = Path(report['resolved'])
        changed = json.loads(resolved.read_text())
        changed['clips'][0]['source_frames'][0] = [1, 25]
        resolved.write_text(json.dumps(changed))
        args = report['validationArguments']
        args[6] = hashlib.sha256(resolved.read_bytes()).hexdigest()
        failed = subprocess.run([sys.executable, '-B', str(self.runtime / 'scripts/validate-assembly-import.py'),
                                 '--compiled', *args], capture_output=True, text=True)
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn('XML is not the exact existing writer output', failed.stderr)
        self.assertEqual(Path(report['xml']).read_bytes(), xml)


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
