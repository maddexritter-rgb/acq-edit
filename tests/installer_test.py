import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import materialize
import install_engine


class MaterializationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='acq install spaces ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.assets = self.root / 'private assets'
        (self.root / 'docs').mkdir()
        (self.root / materialize.CONTRACT).write_text('Toolkit execution contract')
        self.source = self.root / 'distribution/skills'
        self.entries = []
        for name, content in [('edit/SKILL.md', 'Use __ACQ_SKILLS__ and __ACQ_ASSETS__'),
                              ('helper/script.py', 'print("__ACQ_LEGACY_HOME__")')]:
            p = self.source / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
            self.entries.append({'path': name, 'distribution_sha256': hashlib.sha256(p.read_bytes()).hexdigest()})
        self.write_manifest()

    def write_manifest(self):
        (self.root / 'distribution/SOURCE_MANIFEST.json').write_text(json.dumps(
            {'schema': 'acq-edit/source-manifest-v1', 'files': self.entries}))

    def build(self):
        return materialize.materialize(self.root, self.assets)

    def test_repeat_is_verified_without_overwriting_and_records_provenance(self):
        first = self.build()
        target = self.root / '.local/skills/edit/SKILL.md'
        before = target.stat().st_mtime_ns
        second = self.build()
        self.assertEqual(first, second)
        self.assertEqual(before, target.stat().st_mtime_ns)
        self.assertIn(str(self.assets), target.read_text())
        self.assertIn('ACQ Edit Agent MCP', target.read_text())
        self.assertIn('mcp__premiere_pro', target.read_text())
        self.assertIn('never fall back', target.read_text())
        receipt = json.loads(Path(first['receipt']).read_text())
        self.assertEqual(receipt['blockedReferences'], ['helper/script.py'])
        self.assertEqual(receipt['files']['edit/SKILL.md'], hashlib.sha256(target.read_bytes()).hexdigest())

    def test_late_corrupt_source_writes_no_runtime(self):
        (self.source / self.entries[-1]['path']).write_text('corrupt')
        with self.assertRaisesRegex(RuntimeError, 'hash mismatch'):
            self.build()
        self.assertFalse((self.root / '.local').exists())

    def test_direct_skill_routing_preserves_yaml_and_body_and_pins_contract(self):
        original='---\r\nname: caption-clips\r\ndescription: |\r\n  Prepare captions.\r\n---\r\n\n# Canonical captions\nUse the legacy host executor only in its mode.\n'
        target=self.source/'caption-clips/SKILL.md';target.parent.mkdir();target.write_bytes(original.encode())
        self.entries.append({'path':'caption-clips/SKILL.md','distribution_sha256':hashlib.sha256(target.read_bytes()).hexdigest()});self.write_manifest()
        result=self.build();runtime=(self.root/'.local/skills/caption-clips/SKILL.md').read_bytes().decode()
        prefix,body=original.split('---\r\n\n',1)
        self.assertTrue(runtime.startswith(prefix+'---\r\n'))
        self.assertTrue(runtime.endswith('\n'+body))
        self.assertLess(runtime.index('#native-execution-routing'),runtime.index('# Canonical captions'))
        self.assertIn('acq%20install%20spaces%20',runtime)
        self.assertEqual(target.read_bytes(),original.encode())
        receipt=json.loads(Path(result['receipt']).read_text())
        self.assertEqual(set(receipt['executionContract']['entrypoints']),{'edit/SKILL.md','caption-clips/SKILL.md'})
        self.assertEqual(receipt['executionContract']['sha256'],hashlib.sha256((self.root/materialize.CONTRACT).read_bytes()).hexdigest())
        before=(self.root/'.local/skills/edit/SKILL.md').read_bytes()
        (self.root/materialize.CONTRACT).write_text('Changed routing')
        with self.assertRaisesRegex(RuntimeError,'different distribution'):self.build()
        self.assertEqual((self.root/'.local/skills/edit/SKILL.md').read_bytes(),before)

    def test_bad_frontmatter_or_missing_contract_never_exposes_runtime(self):
        target=self.source/'edit/SKILL.md';target.write_text('---\nname: edit\nMissing closing delimiter')
        self.entries[0]['distribution_sha256']=hashlib.sha256(target.read_bytes()).hexdigest();self.write_manifest()
        with self.assertRaisesRegex(RuntimeError,'frontmatter'):self.build()
        self.assertFalse((self.root/'.local').exists())
        (self.root/materialize.CONTRACT).unlink()
        with self.assertRaises(FileNotFoundError):self.build()
        self.assertFalse((self.root/'.local').exists())

    def test_health_check_is_read_only_and_detects_stage_or_contract_drift(self):
        self.build();target=self.root/'.local/skills/edit/SKILL.md'
        original=target.read_bytes();before=target.stat().st_mtime_ns
        result=materialize.verify(self.root)
        self.assertTrue(result['ready']);self.assertEqual(result['routedEntrypoints'],1)
        self.assertFalse(result['nativeWorkflowQualified']);self.assertEqual(target.stat().st_mtime_ns,before)
        target.write_text('local edits')
        with self.assertRaisesRegex(RuntimeError,'changed or extra'):materialize.verify(self.root)
        self.assertEqual(target.read_text(),'local edits');target.write_bytes(original)
        (self.root/materialize.CONTRACT).write_text('changed')
        with self.assertRaisesRegex(RuntimeError,'different distribution'):materialize.verify(self.root)

    def test_path_traversal_and_duplicate_refused_before_writes(self):
        for name in ['../outside', '/tmp/outside', 'edit/../outside', 'edit//SKILL.md', 'edit/SKILL.md']:
            with self.subTest(name=name):
                self.entries[-1]['path'] = name
                self.write_manifest()
                with self.assertRaisesRegex(RuntimeError, 'Invalid or duplicate'):
                    self.build()
                self.assertFalse((self.root / '.local').exists())

    def test_edited_missing_or_extra_runtime_is_preserved(self):
        self.build()
        target = self.root / '.local/skills/edit/SKILL.md'
        target.write_text('user work')
        with self.assertRaisesRegex(RuntimeError, 'changed or extra'):
            self.build()
        self.assertEqual(target.read_text(), 'user work')
        target.unlink()
        with self.assertRaisesRegex(RuntimeError, 'incomplete'):
            self.build()

    def test_asset_change_or_unreceipted_runtime_is_preserved(self):
        self.build()
        with self.assertRaisesRegex(RuntimeError, 'different distribution'):
            materialize.materialize(self.root, self.root / 'other assets')
        (self.root / '.local/skills' / materialize.RECEIPT).unlink()
        with self.assertRaisesRegex(RuntimeError, 'no installation receipt'):
            self.build()

    def test_source_and_destination_symlinks_refused(self):
        target = self.source / self.entries[-1]['path']
        other = self.root / 'outside.py'
        target.rename(other)
        target.symlink_to(other)
        with self.assertRaisesRegex(RuntimeError, 'Symlink'):
            self.build()
        target.unlink()
        other.rename(target)
        (self.root / '.local').symlink_to(self.root / 'outside')
        with self.assertRaisesRegex(RuntimeError, 'Symlink'):
            self.build()

    def test_reservation_refuses_parallel_or_interrupted_install(self):
        local = self.root / '.local'
        local.mkdir()
        lock = local / 'materialize.lock'
        lock.write_text('{"pid": 123}')
        with self.assertRaisesRegex(RuntimeError, 'reservation exists'):
            self.build()
        self.assertTrue(lock.exists())
        self.assertFalse((local / 'skills').exists())

    def test_failed_staging_never_exposes_partial_live_runtime(self):
        original = Path.write_bytes
        def fail(p, data):
            if p.name == 'script.py':
                raise OSError('simulated full disk')
            return original(p, data)
        with patch.object(Path, 'write_bytes', fail):
            with self.assertRaisesRegex(OSError, 'full disk'):
                self.build()
        self.assertFalse((self.root / '.local/skills').exists())
        self.assertTrue(list((self.root / '.local').glob('skills-stage-*')))
        self.build()


class EnginePreflightTests(unittest.TestCase):
    def test_dirty_filmcraft_never_rechecks_out_or_materializes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / '.local/filmcraft/.git').mkdir(parents=True)
            changed = root / '.local/filmcraft/user-work.txt'
            changed.write_text('keep this')
            with patch.object(install_engine, 'ROOT', root), patch.object(install_engine, 'preflight', return_value={'errors': []}), patch.object(install_engine, 'output', return_value=' M Cargo.toml'), patch.object(install_engine, 'materialize') as build, patch.object(install_engine, 'run') as run:
                with self.assertRaisesRegex(RuntimeError, 'local changes'):
                    install_engine.install('filmcraft', root / 'assets',source_build=True)
                build.assert_not_called()
                run.assert_not_called()
            self.assertEqual(changed.read_text(), 'keep this')
            self.assertFalse((root / 'assets').exists())

    def test_resolve_requires_no_other_editor_build_tools(self):
        requested = []
        def which(name):
            requested.append(name)
            return '/tools/' + name
        with patch.object(install_engine.shutil, 'which', which), patch.object(install_engine, 'output', return_value='v24.0.0'), patch.object(Path, 'is_file', return_value=True):
            result = install_engine.preflight('resolve')
        self.assertTrue(result['prerequisitesPresent'])
        self.assertEqual(requested, ['node', 'ffmpeg', 'ffprobe'])
        self.assertFalse(result['nativeWorkflowQualified'])

    def test_missing_selected_prerequisite_prevents_install_writes(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(install_engine, 'ROOT', Path(tmp)), patch.object(install_engine.shutil, 'which', return_value=None):
            with self.assertRaisesRegex(RuntimeError, 'Missing executable'):
                install_engine.install('premiere', Path(tmp) / 'assets')
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_old_node_and_rust_are_specific_failures(self):
        with patch.object(install_engine.sys, 'platform', 'linux'), patch.object(install_engine.shutil, 'which', side_effect=lambda name: name), patch.object(install_engine, 'output', side_effect=lambda args: 'v22.0.0' if args[0] == 'node' else 'rustc 1.94.0'):
            result = install_engine.preflight('filmcraft',source_build=True)
        self.assertFalse(result['prerequisitesPresent'])
        self.assertEqual(len(result['errors']), 2)

    def test_macos_build_requires_apple_sdk_not_linux_pkg_config(self):
        def output(args):
            return {'node':'v24.0.0','rustc':'rustc 1.95.0'}.get(args[0], '/tools/clang' if args[-1]=='clang' else '/tools/MacOSX.sdk')
        with patch.object(install_engine.sys, 'platform', 'darwin'), patch.object(install_engine.shutil, 'which', side_effect=lambda name: None if name=='pkg-config' else name), patch.object(install_engine, 'output', output), patch.object(Path,'is_file',return_value=True), patch.object(Path,'is_dir',return_value=True):
            result=install_engine.preflight('filmcraft',source_build=True)
        self.assertTrue(result['prerequisitesPresent']);self.assertNotIn('pkg-config',result['executables'])
        self.assertEqual(result['nativeBuildTools'],{'clang':'/tools/clang','sdk':'/tools/MacOSX.sdk'})

    def test_missing_macos_sdk_stops_before_installation(self):
        def output(args):
            return 'v24.0.0' if args[0]=='node' else 'rustc 1.95.0' if args[0]=='rustc' else '/absent'
        with patch.object(install_engine.sys, 'platform', 'darwin'), patch.object(install_engine.shutil, 'which', side_effect=lambda name:name), patch.object(install_engine, 'output', output), patch.object(Path,'is_file',return_value=False):
            result=install_engine.preflight('filmcraft',source_build=True)
        self.assertFalse(result['prerequisitesPresent']);self.assertIn('macOS SDK',result['errors'][0])


    def test_filmcraft_build_receipts_pin_real_inputs_and_preserve_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);dest=root/'.local/filmcraft';(dest/'target/release').mkdir(parents=True)
            for name,content in [('Cargo.toml','manifest'),('Cargo.lock','locked'),('target/release/filmcraft-cli','native binary')]:
                (dest/name).write_text(content)
            def output(args,cwd=None):
                if args[:2]==['git','rev-parse']:return install_engine.PIN
                if args[:2]==['git','status']:return ''
                if args[:2]==['git','remote']:return 'https://github.com/storytold/filmcraft.git'
                return 'verified tool output'
            with patch.object(install_engine,'ROOT',root),patch.object(install_engine,'output',output):
                first=install_engine.record_filmcraft_build(dest,{'executables':{'rustc':'rustc','cargo':'cargo'}})
                original=first.read_bytes();second=install_engine.record_filmcraft_build(dest,{'executables':{'rustc':'rustc','cargo':'cargo'}})
            receipt=json.loads(first.read_text());self.assertNotEqual(first,second);self.assertEqual(first.read_bytes(),original)
            self.assertEqual(receipt['source']['commit'],install_engine.PIN)
            self.assertEqual(receipt['source']['cargoLockSha256'],install_engine.digest(dest/'Cargo.lock'))
            self.assertEqual(receipt['binary']['sha256'],install_engine.digest(dest/'target/release/filmcraft-cli'))
            self.assertFalse(receipt['nativeWorkflowQualified'])

    def test_changed_filmcraft_sources_cannot_receive_a_success_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            with patch.object(install_engine,'ROOT',root),patch.object(install_engine,'output',side_effect=[install_engine.PIN,' M Cargo.lock']):
                with self.assertRaisesRegex(RuntimeError,'sources changed'):
                    install_engine.record_filmcraft_build(root/'filmcraft',{'executables':{'rustc':'rustc','cargo':'cargo'}})
            self.assertFalse((root/'.local/filmcraft-builds').exists())


if __name__ == '__main__':
    unittest.main()
