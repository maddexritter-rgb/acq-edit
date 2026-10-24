"""Connector isolation tests. Generated receipts do not certify a licensed host."""
import copy
import json
import hashlib
from pathlib import Path
import sys
import unittest
import premiere_runtime_test as fixture

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'python'))
from premiere_installation import verify
from prepare_premiere_runtime import prepare_helpers, compiled_hashes, REQUIRED_TOOLS


class PremiereInstallationTests(unittest.TestCase):
    def setUp(self):
        fixture.PremiereHelperTests.setUp(self)
        helpers = prepare_helpers(self.runtime, self.toolkit)
        (self.runtime / 'dist/lab').mkdir(parents=True)
        (self.runtime / 'dist/lab/index.js').write_text('// simulated compiled entrypoint')
        (self.runtime / 'lab/runtime').mkdir(parents=True)
        (self.runtime / 'lab/node-path.txt').write_text(sys.executable + '\n')
        self.profile = self.toolkit / '.local/premiere-profile.json'
        self.config = {'premiereProfile': str(self.profile)}
        self.profile_data = {
            'schema': 'edit.premiere-bridge-profile/v1',
            'command': [sys.executable, str(self.toolkit / '.local/skills/assembly-design/scripts/precision_bridge.mjs'), str(self.runtime)],
            'cwd': str(self.runtime), 'fixture_root': str(self.runtime / 'lab/runtime/fixtures'),
            'connector': 'premiere-agent-lab', 'host_version': '26.3.0', 'mode': 'scoped-edit',
            'project_authorization': str(self.runtime / 'lab/runtime/edit-project-authorization.json'),
        }
        self.profile.write_text(json.dumps(self.profile_data))
        self.receipt = self.runtime / 'lab/runtime-preparation.json'
        self.receipt.write_text(json.dumps({'schema': 'acq-edit/premiere-runtime-v2',
            'transportInitialized': True, 'requiredTools': sorted(REQUIRED_TOOLS),
            'helperHashes': helpers, 'compiledHashes': compiled_hashes(self.runtime)}))
        packages = self.runtime / 'lab/packages'
        hashes = {}
        for name in ('ACQEditAgentCEP', 'ACQEditAgentUXP'):
            (packages / name).mkdir(parents=True)
            file = packages / name / 'test.js'
            file.write_text('// simulated panel')
            hashes[file.relative_to(packages).as_posix()] = hashlib.sha256(file.read_bytes()).hexdigest()
        (self.runtime / 'lab/panel-preparation.json').write_text(json.dumps({
            'runtime': str(self.runtime / 'lab/runtime'), 'mailbox': str(self.runtime / 'lab/runtime/mailbox'),
            'cepId': 'com.acqedit.premiere.bridge', 'uxpId': 'com.acqedit.premiere.uxp', 'port': 17878,
            'packageHashes': hashes}))
        (self.runtime / 'lab/runtime/config.json').write_text(json.dumps({'port': 17878, 'token': 'private fixture token'}))

    def test_matching_installation_returns_only_compact_nonsecret_evidence(self):
        result = verify(self.config, self.toolkit)
        self.assertTrue(result['verified'])
        self.assertFalse(result['hostQualified'])
        self.assertEqual(result['helperFiles'], 5)
        self.assertNotIn('token', json.dumps(result))

    def test_external_profile_and_redirected_local_profile_refused(self):
        external = self.toolkit / 'production.json'
        external.write_text('must not be read or executed')
        with self.assertRaisesRegex(RuntimeError, 'production profiles are refused'):
            verify({'premiereProfile': str(external)}, self.toolkit)
        self.profile.unlink()
        self.profile.symlink_to(external)
        with self.assertRaisesRegex(RuntimeError, 'redirected'):
            verify(self.config, self.toolkit)
        self.assertEqual(external.read_text(), 'must not be read or executed')

    def test_profile_fields_cannot_redirect_command_scope_or_mailbox(self):
        for key, value in [('command', [sys.executable, 'production-server.py']),
                           ('cwd', str(self.toolkit)), ('mode', 'lab'),
                           ('fixture_root', str(self.toolkit)), ('project_authorization', '/external/scope.json')]:
            with self.subTest(key=key):
                data = copy.deepcopy(self.profile_data)
                data[key] = value
                self.profile.write_text(json.dumps(data))
                with self.assertRaisesRegex(RuntimeError, 'profile differs'):
                    verify(self.config, self.toolkit)
                self.assertEqual(json.loads(self.profile.read_text()), data)

    def test_compiled_changes_or_added_executables_are_preserved_and_rejected(self):
        file = self.runtime / 'dist/lab/index.js'
        original = file.read_bytes()
        file.write_text('user changes')
        with self.assertRaisesRegex(RuntimeError, 'differs from its installation receipt'):
            verify(self.config, self.toolkit)
        self.assertEqual(file.read_text(), 'user changes')
        file.write_bytes(original)
        extra = self.runtime / 'dist/injected.js'
        extra.write_text('extra executable')
        with self.assertRaisesRegex(RuntimeError, 'differs from its installation receipt'):
            verify(self.config, self.toolkit)
        self.assertTrue(extra.is_file())

    def test_old_receipt_and_production_panel_port_require_fresh_installation(self):
        original = self.receipt.read_bytes()
        data = json.loads(original)
        data['schema'] = 'acq-edit/premiere-runtime-v1'
        self.receipt.write_text(json.dumps(data))
        with self.assertRaisesRegex(RuntimeError, 'predates compiled-code'):
            verify(self.config, self.toolkit)
        self.receipt.write_bytes(original)
        config = self.runtime / 'lab/runtime/config.json'
        config.write_text(json.dumps({'port': 17877}))
        with self.assertRaisesRegex(RuntimeError, 'panel isolation'):
            verify(self.config, self.toolkit)
        self.assertEqual(json.loads(config.read_text()), {'port': 17877})

    def test_changed_prepared_panel_is_not_treated_as_the_isolated_connector(self):
        file = self.runtime / 'lab/packages/ACQEditAgentCEP/test.js'
        file.write_text('// changed mailbox route')
        with self.assertRaisesRegex(RuntimeError, 'panel changed'):
            verify(self.config, self.toolkit)
        self.assertEqual(file.read_text(), '// changed mailbox route')
