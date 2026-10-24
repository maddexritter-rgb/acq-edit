"""Toolkit lifecycle adapter tests with an explicitly simulated host."""
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'python'))
from common import sha, fingerprint
from premiere_session import open_project, inspect_result


class PremiereSessionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='acq session ')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.project = {'id': 'project-id', 'root': str(self.root), 'backend': 'premiere'}
        (self.root / 'project.json').write_text(json.dumps(self.project))
        (self.root / '10_WORK').mkdir()
        self.runtime = self.root / 'toolkit-runtime'
        (self.runtime / 'lab/runtime').mkdir(parents=True)
        self.native = self.root / '10_WORK/edit.prproj'
        self.packet = {'mode': 'create', 'nativeProject': str(self.native),
                       'receipt': str(self.root / '10_WORK/lifecycle.json'), 'ownershipConfirmed': True}
        self.workspace = {'state': {'version': '26.3.0', 'openProjects': [], 'activePath': None}, 'revision': 'a' * 64}
        self.state = {'projectPath': str(self.native), 'sequenceId': None, 'tracks': []}
        self.requests = []
        self.unknown = False
        owner = self
        class Client:
            def __init__(self, profile): pass
            def inspect(self, name, args):
                owner.assertEqual(name, 'lab_snapshot')
                return owner.state
            def _call(self, name, args):
                owner.requests.append(name)
                if name == 'lab_inspect_toolkit_workspace': return owner.workspace, False
                owner.assertEqual(name, 'lab_toolkit_project')
                if args['mode'] == 'create': owner.native.write_bytes(b'simulated native project')
                return {'status': 'unknown' if owner.unknown else 'committed_unverified', 'request': args,
                        'projectId': owner.project['id'], 'nativeSha256': sha(owner.native)}, False
            def close(self): owner.requests.append('close')
        self.client = Client
        self.adapter = types.SimpleNamespace(profile=types.SimpleNamespace(cwd=str(self.runtime)),
            inspect=lambda project, packet: inspect_result(project, self.native, self.state))

    def run_open(self):
        return open_project(self.adapter, self.project, self.packet, self.client)

    def prepare_reopen(self):
        self.native.write_bytes(b'original saved project')
        self.packet.update(mode='open', reopen=inspect_result(self.project, self.native, self.state)['reopen'])

    def test_create_keeps_scope_and_host_receipt_and_returns_exact_reopen_identity(self):
        result = self.run_open()
        self.assertEqual(result['status'], 'inspected_native_session')
        self.assertFalse(result['nativeWorkflowQualified'])
        self.assertTrue(result['requiresStageScope'])
        self.assertEqual(result['inspection']['reopen']['nativeSha256'], sha(self.native))
        scope = json.loads(next((self.runtime / 'lab/runtime/toolkit-scopes').iterdir()).read_text())
        self.assertEqual(scope['projectManifestSha256'], sha(self.root / 'project.json'))
        self.assertEqual(scope['projectPath'], str(self.native))
        self.assertTrue(scope['ownershipConfirmed'])
        self.assertEqual(self.requests, ['lab_inspect_toolkit_workspace', 'lab_toolkit_project', 'close'])
        with self.assertRaisesRegex(RuntimeError, 'Fresh lifecycle receipt'): self.run_open()

    def test_reopen_checks_saved_bytes_and_full_native_state_without_saving(self):
        self.prepare_reopen()
        original = self.native.read_bytes()
        result = self.run_open()
        self.assertEqual(result['inspection']['fingerprint'], self.packet['reopen']['expectedFingerprint'])
        self.assertEqual(self.native.read_bytes(), original)

    def test_same_active_target_is_inspected_without_lifecycle_dispatch(self):
        self.prepare_reopen()
        self.workspace['state'].update(activePath=str(self.native), openProjects=[{'path': str(self.native)}])
        result = self.run_open()
        self.assertEqual(result['status'], 'verified_existing_session')
        self.assertEqual(result['nativeMutations'], 0)
        self.assertEqual(self.requests, ['lab_inspect_toolkit_workspace', 'close'])
        self.assertFalse((self.runtime / 'lab/runtime/toolkit-scopes').exists())

    def test_occupied_workspace_or_missing_ownership_never_creates_scope_or_dispatches(self):
        for occupied in (True, False):
            self.requests.clear()
            self.workspace['state']['activePath'] = '/unrelated.prproj' if occupied else None
            self.packet['ownershipConfirmed'] = False
            with self.assertRaisesRegex(RuntimeError, 'another open|exclusive Premiere ownership'): self.run_open()
            self.assertEqual(self.requests, ['lab_inspect_toolkit_workspace', 'close'])
            self.assertFalse(self.native.exists())
            self.assertFalse((self.runtime / 'lab/runtime/toolkit-scopes').exists())

    def test_saved_and_unsaved_edits_are_preserved_and_refused(self):
        self.prepare_reopen()
        self.native.write_bytes(b'user saved changes')
        with self.assertRaisesRegex(RuntimeError, 'Saved Premiere project changed'): self.run_open()
        self.assertEqual(self.requests, [])
        self.assertEqual(self.native.read_bytes(), b'user saved changes')
        self.packet['reopen']['nativeSha256'] = sha(self.native)
        self.workspace['state']['activePath'] = str(self.native)
        self.state['manualEdit'] = True
        with self.assertRaisesRegex(RuntimeError, 'intervening edits'): self.run_open()
        self.assertNotIn('lab_toolkit_project', self.requests)

    def test_malformed_reopen_fingerprint_never_contacts_host(self):
        self.prepare_reopen()
        self.packet['reopen']['expectedFingerprint'] = 'invalid'
        with self.assertRaisesRegex(RuntimeError, 'complete Premiere reopening fingerprint'): self.run_open()
        self.assertEqual(self.requests, [])

    def test_unknown_native_result_retains_receipt_and_never_replays(self):
        self.unknown = True
        with self.assertRaisesRegex(RuntimeError, 'reconciliation'): self.run_open()
        self.assertEqual(json.loads(Path(self.packet['receipt']).read_text())['status'], 'unknown')
        self.assertEqual(self.requests.count('lab_toolkit_project'), 1)
        with self.assertRaisesRegex(RuntimeError, 'Fresh lifecycle receipt'): self.run_open()
        self.assertEqual(self.requests.count('lab_toolkit_project'), 1)

    def test_reopened_wrong_snapshot_leaves_original_bytes_and_receipt_for_reconciliation(self):
        self.prepare_reopen()
        original = self.native.read_bytes()
        self.state['tracks'] = [{'manualEdit': True}]
        with self.assertRaisesRegex(RuntimeError, 'Reopened Premiere state differs'): self.run_open()
        self.assertEqual(self.native.read_bytes(), original)
        self.assertTrue(Path(self.packet['receipt']).is_file())
