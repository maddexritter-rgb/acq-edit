"""Direct helper calls must not inherit or construct another Premiere transport."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import premiere_installation_test as installation_fixture

ROOT = Path(__file__).resolve().parents[1]


class ConnectorLock(unittest.TestCase):
    def setUp(self):
        installation_fixture.PremiereInstallationTests.setUp(self)
        source = (ROOT/'distribution/skills/_shared/premiere_bridge.py').read_text().replace('__ACQ_TOOLKIT__', str(self.toolkit))
        target = self.toolkit/'locked_bridge.py'; target.write_text(source)
        name = 'acq_locked_bridge_fixture'
        spec = importlib.util.spec_from_file_location(name, target)
        self.bridge = importlib.util.module_from_spec(spec)
        sys.modules[name] = self.bridge
        self.addCleanup(lambda: sys.modules.pop(name, None))
        spec.loader.exec_module(self.bridge)

    def test_default_resolves_toolkit_and_never_reads_home_default(self):
        with patch.dict('os.environ', {}, clear=True), patch.object(Path, 'home', side_effect=AssertionError('global default read')):
            profile = self.bridge.Profile.load()
        self.assertEqual(profile.cwd, str(self.runtime))

    def test_global_environment_or_explicit_old_profile_refused_before_spawn(self):
        foreign = self.toolkit/'legacy.json'; foreign.write_text('must never parse')
        with patch.object(self.bridge.subprocess, 'Popen') as spawn:
            with patch.dict('os.environ', {'PREMIERE_AGENT_PROFILE': str(foreign)}):
                with self.assertRaisesRegex(self.bridge.BridgeError, 'external or legacy'): self.bridge.Profile.load()
            with self.assertRaisesRegex(self.bridge.BridgeError, 'external or legacy'): self.bridge.Profile.load(foreign)
        spawn.assert_not_called()
        self.assertEqual(foreign.read_text(), 'must never parse')

    def test_explicit_toolkit_profile_overrides_stale_environment(self):
        with patch.dict('os.environ', {'PREMIERE_AGENT_PROFILE': '/old/profile.json'}):
            profile = self.bridge.Profile.load(self.profile)
            self.bridge._verified_toolkit_profile(profile)
        self.assertEqual(profile.cwd, str(self.runtime))

    def test_handcrafted_same_name_legacy_transport_is_refused_before_spawn(self):
        data = copy.deepcopy(self.profile_data); data.pop('schema')
        data['command'] = (sys.executable, '/legacy/server.py')
        profile = self.bridge.Profile(**data)
        with patch.object(self.bridge.subprocess, 'Popen') as spawn:
            with self.assertRaisesRegex(self.bridge.BridgeError, 'supplied transport differs'):
                self.bridge.StdioMcp(profile)
        spawn.assert_not_called()

    def test_missing_toolkit_profile_never_uses_existing_legacy_profile(self):
        self.profile.unlink()
        with patch.dict('os.environ', {}, clear=True), patch.object(self.bridge.subprocess, 'Popen') as spawn:
            with self.assertRaisesRegex(self.bridge.BridgeError, 'unavailable'): self.bridge.Profile.load()
        spawn.assert_not_called()

    def test_valid_transport_reaches_only_the_verified_toolkit_command(self):
        profile = self.bridge.Profile.load(self.profile)
        with patch.object(self.bridge.subprocess, 'Popen', side_effect=OSError('fixture stop before process')) as spawn:
            with self.assertRaisesRegex(OSError, 'fixture stop'):
                self.bridge.StdioMcp(profile)
        self.assertEqual(spawn.call_args.args[0], tuple(self.profile_data['command']))
        self.assertEqual(spawn.call_args.kwargs['cwd'], str(self.runtime))

    def test_global_panel_identity_and_production_port_are_refused(self):
        config = self.runtime/'lab/runtime/config.json'
        data = json.loads(config.read_text()); data['port'] = 17877; config.write_text(json.dumps(data))
        with self.assertRaisesRegex(self.bridge.BridgeError, 'unavailable'): self.bridge.Profile.load(self.profile)




    def test_2652_uses_bound_installed_host_without_relaxing_connector_identity(self):
        import plistlib
        from premiere_compatibility import bind_host
        app=self.toolkit/'Adobe Premiere Pro.app';(app/'Contents').mkdir(parents=True)
        (app/'Contents/Info.plist').write_bytes(plistlib.dumps({'CFBundleShortVersionString':'26.5.2'}))
        bind_host(self.toolkit,{'application':str(app),'observedVersion':'26.5.2'})
        self.profile_data['host_version']='26.5.2';self.profile.write_text(json.dumps(self.profile_data))
        profile=self.bridge.Profile.load(self.profile);self.assertEqual(profile.host_version,'26.5.2')
        changed=copy.deepcopy(self.profile_data);changed['host_version']='26.3.0';self.profile.write_text(json.dumps(changed))
        with self.assertRaises(self.bridge.BridgeError):self.bridge.Profile.load(self.profile)
