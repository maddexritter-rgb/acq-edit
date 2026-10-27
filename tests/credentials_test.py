import contextlib
import http.client
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from credentials import KEYS, make_server, save_keys

FIXTURE = dict(zip(KEYS, ['fixture-assembly-secret', 'fixture-gemini-secret']))


class Credentials(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'config'

    def test_atomic_save_preserves_other_credentials_and_private_permissions(self):
        self.root.mkdir()
        target = self.root / 'credentials.json'
        target.write_text(json.dumps({'EDITORIAL_BRAIN_READ_KEY': 'fixture-brain'}))
        save_keys(self.root, FIXTURE)
        data = json.loads(target.read_text())
        self.assertEqual(data, {**FIXTURE, 'EDITORIAL_BRAIN_READ_KEY': 'fixture-brain'})
        self.assertEqual(target.stat().st_mode & 0o777, 0o600)
        save_keys(self.root, {KEYS[0]: ' ', KEYS[1]: ' replacement '})
        self.assertEqual(json.loads(target.read_text())[KEYS[0]], FIXTURE[KEYS[0]])
        self.assertEqual(json.loads(target.read_text())[KEYS[1]], 'replacement')
        self.assertEqual(list(self.root.glob('.credentials-*')), [])

    def test_invalid_or_partial_first_entry_does_not_write_credentials(self):
        for values in ({}, {KEYS[0]: 'one'}, {**FIXTURE, 'unknown': 'value'}, {KEYS[0]: []}, {KEYS[0]: 'two words'}, {KEYS[0]: 'x' * 4097}, []):
            with self.subTest(values=type(values)):
                with self.assertRaises(ValueError): save_keys(self.root, values)
                self.assertFalse((self.root / 'credentials.json').exists())

    def test_failed_replace_preserves_old_values_and_removes_staging(self):
        save_keys(self.root, FIXTURE)
        before = (self.root / 'credentials.json').read_bytes()
        with patch('credentials.os.replace', side_effect=OSError('fixture failure')):
            with self.assertRaises(OSError): save_keys(self.root, {KEYS[0]: 'new'})
        self.assertEqual((self.root / 'credentials.json').read_bytes(), before)
        self.assertEqual(list(self.root.glob('.credentials-*')), [])

    def test_symlink_target_is_rejected(self):
        self.root.mkdir()
        other = self.root / 'other'; other.write_text('{}')
        (self.root / 'credentials.json').symlink_to(other)
        with self.assertRaises(ValueError): save_keys(self.root, FIXTURE)
        self.assertEqual(other.read_text(), '{}')

    def server(self):
        server, url = make_server(self.root)
        self.addCleanup(server.server_close)
        token = url.split('#')[1]
        self.assertEqual(server.server_address[0], '127.0.0.1')
        return server, {'Origin': 'http://' + server.address, 'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'}

    def request(self, server, method='POST', path='/save', headers=None, body=None):
        thread = threading.Thread(target=server.handle_request)
        thread.start()
        connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=5)
        try:
            connection.request(method, path, body if body is not None else json.dumps(FIXTURE), headers or {})
            response = connection.getresponse()
            return response.status, response.read().decode(), dict(response.getheaders())
        finally:
            connection.close(); thread.join(6)
            self.assertFalse(thread.is_alive())

    def test_page_contains_password_form_without_existing_secrets(self):
        save_keys(self.root, FIXTURE)
        server, headers = self.server()
        status, body, response = self.request(server, 'GET', '/', body='')
        self.assertEqual(status, 200)
        self.assertEqual(body.count('type="password"'), 2)
        self.assertIn('Save keys', body)
        for secret in FIXTURE.values(): self.assertNotIn(secret, body)
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertIn("frame-ancestors 'none'", response['Content-Security-Policy'])
        self.assertEqual(self.request(server, 'GET', '/credentials.json')[0], 404)

    def test_cross_origin_missing_auth_wrong_host_and_content_type_rejected(self):
        server, headers = self.server()
        for changes in ({'Origin': 'https://elsewhere.example'}, {'Origin': ''}, {'Authorization': ''}, {'Authorization': 'Bearer wrong'}, {'Authorization': 'Bearer é'}, {'Host': 'evil.example'}, {'Content-Type': 'text/plain'}):
            status, body, _ = self.request(server, headers={**headers, **changes})
            self.assertIn(status, (400, 403))
            self.assertIsNone(server.result)
            self.assertFalse((self.root / 'credentials.json').exists())
            for secret in FIXTURE.values(): self.assertNotIn(secret, body)

    def test_save_response_and_logs_never_echo_keys(self):
        server, headers = self.server()
        logs = io.StringIO()
        with contextlib.redirect_stdout(logs), contextlib.redirect_stderr(logs):
            status, body, _ = self.request(server, headers=headers)
        self.assertEqual(status, 200)
        self.assertEqual(server.result, 'saved')
        self.assertEqual(json.loads((self.root / 'credentials.json').read_text()), FIXTURE)
        for secret in FIXTURE.values(): self.assertNotIn(secret, body + logs.getvalue())

    def test_bad_json_and_incomplete_entry_allow_retry(self):
        server, headers = self.server()
        for body in ('{invalid', '{}', '[]', json.dumps({KEYS[0]: 'only-one'})):
            self.assertEqual(self.request(server, headers=headers, body=body)[0], 400)
            self.assertIsNone(server.result)
        self.assertEqual(self.request(server, headers=headers)[0], 200)

    def test_cancel_preserves_existing_keys(self):
        save_keys(self.root, FIXTURE)
        before = (self.root / 'credentials.json').read_bytes()
        server, headers = self.server()
        self.assertEqual(self.request(server, path='/cancel', headers=headers, body='{}')[0], 200)
        self.assertEqual(server.result, 'cancelled')
        self.assertEqual((self.root / 'credentials.json').read_bytes(), before)

    def test_expiry_closes_listener_and_preserves_existing_keys(self):
        import credentials
        save_keys(self.root, FIXTURE)
        before = (self.root / 'credentials.json').read_bytes()
        server, url = make_server(self.root)
        with patch.object(credentials, 'make_server', return_value=(server, url)), patch.object(credentials.time, 'monotonic', side_effect=[0, 901]), patch.object(sys, 'argv', ['credentials.py', str(self.root), '--no-open']), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(ValueError, 'expired'): credentials.main()
        self.assertEqual(server.fileno(), -1)
        self.assertEqual((self.root / 'credentials.json').read_bytes(), before)

    def test_terminal_fallback_refuses_noninteractive_input(self):
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/credentials.py'), str(self.root), '--terminal'], input='must-not-be-read\n', capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('must-not-be-read', result.stdout + result.stderr)
        self.assertFalse((self.root / 'credentials.json').exists())


if __name__ == '__main__': unittest.main()
