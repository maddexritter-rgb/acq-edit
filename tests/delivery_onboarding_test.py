import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'distribution/skills/monday/scripts'))
spec = importlib.util.spec_from_file_location('delivery_connect', ROOT / 'distribution/skills/monday/scripts/connect.py')
connect = importlib.util.module_from_spec(spec); spec.loader.exec_module(connect)
sys.path.insert(0, str(ROOT / 'scripts'))
import credentials
import onboard

ROUTE = {'content_code': 'SF', 'frame': {'account_id': 'account', 'project_id': 'project', 'project_name': 'Project', 'folder_id': 'folder', 'folder_name': 'Exports'},
         'monday': {'board_id': 'board', 'board_name': 'Board', 'group_id': 'review', 'group_name': 'Review', 'revision_group_id': 'review', 'revision_group_name': 'Review', 'status_column_id': 'status', 'link_column_id': 'link', 'status_label': 'For Review', 'revision_status_label': 'For Review'}}
VALUES = {'MONDAY_TOKEN': 'fixture-monday', 'FRAME_CLIENT_ID': 'fixture-id', 'FRAME_CLIENT_SECRET': 'fixture-secret'}


class Frame:
    def get(self, path):
        if path == '/v4/me': return {'data': {'name': 'Fixture'}}
        if path.endswith('/folders/folder'): return {'data': {'name': 'Exports', 'project_id': 'project'}}
        if path.endswith('/projects/project'): return {'data': {'name': 'Project'}}
        raise AssertionError('Unexpected endpoint')


class Monday:
    def gql(self, query):
        if 'mutation' in query: raise AssertionError('Setup must never mutate')
        return {'me': {'name': 'Fixture', 'account': {'name': 'Fixture'}}}
    def board(self, board_id):
        return {'name': 'Board', 'groups': [{'id': 'review', 'title': 'Review'}], 'columns': [
            {'id': 'link', 'type': 'link'}, {'id': 'status', 'type': 'status', 'settings_str': json.dumps({'labels': {'0': 'For Review'}})}]}


class DeliveryOnboarding(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def configured(self):
        connect.save_credentials(self.root, VALUES)
        (self.root / 'frameio/token.json').write_text('{"access_token":"fixture-token"}')
        (self.root / 'routes.json').write_text(json.dumps({'editor': 'ED', 'brands': {'brand': {'code': 'BRAND', 'routes': {'shorts': ROUTE}}}}))

    def check(self): return connect.check(self.root, Frame, Monday)

    def test_credentials_form_storage_preserves_blanks_and_mode(self):
        connect.save_credentials(self.root, VALUES)
        connect.save_credentials(self.root, dict.fromkeys(VALUES, ''))
        self.assertEqual(json.loads((self.root / 'monday.json').read_text())['token'], VALUES['MONDAY_TOKEN'])
        for file in ('monday.json', 'frameio/credentials.json'):
            self.assertEqual((self.root / file).stat().st_mode & 0o777, 0o600)
        page = credentials.form_page('Delivery', 'Connect', [(key, key, 'Help', 'https://example.com') for key in VALUES])
        self.assertEqual(page.count('type="password"'), 3)
        self.assertIn('Object.fromEntries', page)
        self.assertNotIn('id="assembly"', page)
        self.assertNotIn('fixture-secret', page)

    def test_incomplete_entry_does_not_partially_save(self):
        with self.assertRaises(ValueError): connect.save_credentials(self.root, {'MONDAY_TOKEN': 'only-one'})
        self.assertFalse((self.root / 'monday.json').exists())
        self.assertFalse((self.root / 'frameio/credentials.json').exists())

    def test_changed_adobe_app_requires_matching_secret_and_new_login(self):
        self.configured()
        with self.assertRaises(ValueError): connect.save_credentials(self.root, {'FRAME_CLIENT_ID': 'new-id'})
        self.assertTrue((self.root / 'frameio/token.json').exists())
        connect.save_credentials(self.root, {'FRAME_CLIENT_ID': 'new-id', 'FRAME_CLIENT_SECRET': 'new-secret'})
        self.assertFalse((self.root / 'frameio/token.json').exists())
        self.assertEqual(len(list((self.root / 'frameio').glob('token.previous-*'))), 1)
        self.assertFalse(connect.readiness(self.root)['ready'])

    def test_missing_configuration_reports_delivery_pending(self):
        result = connect.readiness(self.root)
        self.assertFalse(result['ready'])
        self.assertIn('frameio/token.json', result['missing'])
        self.assertFalse((self.root / 'connection-check.json').exists())

    def test_identities_alone_do_not_finish_onboarding(self):
        connect.save_credentials(self.root, VALUES)
        result = self.check()
        self.assertFalse(result['ready'])
        self.assertEqual(result['failedStep'], 'saved destinations')

    def test_valid_accounts_and_routes_are_read_verified_without_upload(self):
        self.configured()
        result = self.check()
        self.assertTrue(result['ready'])
        self.assertEqual(len(result['routes']), 1)
        self.assertIn('not proven', result['qualification'])
        self.assertTrue(connect.readiness(self.root)['ready'])
        saved = (self.root / 'connection-check.json').read_text()
        for secret in VALUES.values(): self.assertNotIn(secret, saved)

    def test_invalid_destination_or_empty_brand_routes_keeps_pending(self):
        self.configured()
        path = self.root / 'routes.json'
        for profile in ({'code': 'BRAND', 'routes': {}}, {'code': 'BRAND', 'routes': {'shorts': {**ROUTE, 'monday': {**ROUTE['monday'], 'status_label': 'Missing'}}}}):
            path.write_text(json.dumps({'editor': 'ED', 'brands': {'brand': profile}}))
            self.assertFalse(self.check()['ready'])

    def test_changed_configuration_or_expired_check_invalidates_readiness(self):
        self.configured(); self.check()
        with patch.object(connect.time, 'time', return_value=9999999999):
            self.assertFalse(connect.readiness(self.root)['ready'])
        (self.root / 'monday.json').write_text('{"token":"changed"}')
        self.assertFalse(connect.readiness(self.root)['ready'])

    def test_failed_recheck_replaces_prior_ready_and_redacts_provider_error(self):
        self.configured(); self.check()
        class Broken(Frame):
            def get(self, path): raise RuntimeError('fixture-secret')
        result = connect.check(self.root, Broken, Monday)
        self.assertFalse(result['ready'])
        self.assertNotIn('fixture-secret', json.dumps(result))
        self.assertFalse(connect.readiness(self.root)['ready'])

    def test_concurrent_account_change_cannot_mark_new_credentials_verified(self):
        self.configured()
        root = self.root
        class Changing(Frame):
            def get(self, path):
                (root/'monday.json').write_text('{"token":"different"}')
                return super().get(path)
        self.assertFalse(connect.check(self.root, Changing, Monday)['ready'])

    def test_standard_onboarding_launches_credentials_then_frame_login(self):
        with patch.object(onboard, 'HOME', self.root), patch.object(onboard, 'execute') as execute:
            onboard.delivery_connections()
        commands = execute.call_args_list
        self.assertEqual(len(commands), 2)
        self.assertEqual(Path(commands[0].args[0][1]).name, 'connect.py')
        self.assertEqual(commands[0].args[0][2], 'credentials')
        self.assertEqual(Path(commands[1].args[0][1]).name, 'setup_frameio_oauth.py')

    def test_existing_connections_are_not_prompted_again(self):
        delivery = self.root / 'delivery'
        connect.save_credentials(delivery, VALUES)
        (delivery/'frameio/token.json').write_text('{}')
        with patch.object(onboard, 'HOME', self.root), patch.object(onboard, 'execute') as execute:
            onboard.delivery_connections()
        execute.assert_not_called()

    def test_onboarding_checkpoint_records_pending_then_verified(self):
        from subprocess import CompletedProcess
        for ready in (False, True):
            output = CompletedProcess([], 0 if ready else 2, stdout=json.dumps({'ready': ready}), stderr='')
            with patch.object(onboard, 'ROOT', self.root), patch.object(onboard.subprocess, 'run', return_value=output), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(onboard.finish_delivery(), ready)
            state = json.loads((self.root / '.local/onboarding.json').read_text())
            self.assertEqual(state['steps']['delivery'], 'read-verified' if ready else 'pending')
            self.assertNotIn('engine', state['steps'])


if __name__ == '__main__': unittest.main()
