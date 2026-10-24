import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shlex
import signal
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
INGEST = ROOT / 'distribution/skills/live-clip/scripts/live_ingest.py'
COMMON = ROOT / 'distribution/skills/live-clip/scripts/live_common.py'
spec = importlib.util.spec_from_file_location('portable_live_common', COMMON)
common = importlib.util.module_from_spec(spec)
spec.loader.exec_module(common)


class LiveCaptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory(prefix='acq live capture ')
        cls.root = Path(cls.folder.name)
        cls.source = cls.root / 'source with spaces.mp4'
        subprocess.run(['ffmpeg', '-v', 'error', '-n', '-f', 'lavfi', '-i',
                        'testsrc2=size=160x90:rate=25:duration=3', '-f', 'lavfi', '-i',
                        'sine=frequency=440:sample_rate=48000:duration=3',
                        '-c:v', 'libx264', '-g', '25', '-c:a', 'aac', '-shortest',
                        str(cls.source)], check=True, capture_output=True)
        cls.transport = cls.root / 'stream.ts'
        subprocess.run(['ffmpeg', '-v', 'error', '-n', '-i', str(cls.source),
                        '-c', 'copy', str(cls.transport)], check=True, capture_output=True)

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=self.root)
        self.base = Path(self.temp.name)
        self.work = self.base / '10_WORK' / 'live capture'

    def tearDown(self):
        self.temp.cleanup()

    def command(self, *extra):
        return [sys.executable, str(INGEST), 'simulate', str(self.source),
                '--work', str(self.work), '--speed', '0', '--chunk', '1', *extra]

    def run_capture(self, command=None, **kwargs):
        return subprocess.run(command or self.command(), capture_output=True, text=True,
                              timeout=20, **kwargs)

    def state(self):
        return json.loads((self.work / 'ingest-state.json').read_text())

    def assert_no_completion(self):
        self.assertFalse((self.work / 'chunks/INGEST_DONE').exists())

    def test_real_segmenter_completion_and_repeat_preserve_original_bytes(self):
        source_hash = hashlib.sha256(self.source.read_bytes()).hexdigest()
        result = self.run_capture()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.state()['status'], 'succeeded')
        self.assertEqual(self.state()['parameters']['mode'], 'simulate')
        self.assertEqual(self.state()['parameters']['source'], str(self.source))
        self.assertEqual(self.state()['parameters']['chunkSeconds'], 1)
        chunks = common.closed_chunks(self.work)
        self.assertEqual(len(chunks), 3)
        for chunk in chunks:
            subprocess.run(['ffmpeg', '-v', 'error', '-i', str(chunk), '-f', 'null', '-'],
                           check=True, capture_output=True)
        before = {str(p.relative_to(self.work)): p.read_bytes() for p in self.work.rglob('*') if p.is_file()}
        retry = self.run_capture()
        self.assertNotEqual(retry.returncode, 0)
        self.assertIn('use a new work directory', retry.stderr)
        self.assertEqual(before, {str(p.relative_to(self.work)): p.read_bytes() for p in self.work.rglob('*') if p.is_file()})
        self.assertEqual(hashlib.sha256(self.source.read_bytes()).hexdigest(), source_hash)

    def test_real_ffmpeg_failure_does_not_mark_done(self):
        bad = self.base / 'invalid.mp4'
        bad.write_bytes(b'not media')
        command = self.command()
        command[3] = str(bad)
        result = self.run_capture(command)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.state()['status'], 'failed')
        self.assertNotEqual(self.state()['processes'][0]['returncode'], 0)
        self.assert_no_completion()

    def test_failed_downloader_cannot_be_hidden_by_successful_ffmpeg(self):
        binary = self.base / 'bin'
        binary.mkdir()
        producer = self.base / 'producer.py'
        producer.write_text('import pathlib,sys\nsys.stdout.buffer.write(pathlib.Path(' + repr(str(self.transport)) + ').read_bytes())\nsys.stdout.buffer.flush()\nsys.exit(7)\n')
        fake = binary / 'yt-dlp'
        fake.write_text('#!/bin/sh\nexec ' + shlex.quote(sys.executable) + ' ' + shlex.quote(str(producer)) + ' "$@"\n')
        fake.chmod(0o700)
        result = self.run_capture([sys.executable, str(INGEST), 'live', 'https://www.youtube.com/watch?v=fixture',
                                   '--pipe', '--work', str(self.work), '--chunk', '1'],
                                  env={**os.environ, 'PATH': str(binary) + os.pathsep + os.environ['PATH']})
        self.assertNotEqual(result.returncode, 0)
        state = self.state()
        self.assertEqual({p['role']: p['returncode'] for p in state['processes']}, {'downloader': 7, 'segmenter': 0})
        self.assertEqual(state['status'], 'failed')
        self.assert_no_completion()
        self.assertEqual(len(common.closed_chunks(self.work)), 2)  # incomplete tail stays out

    def test_termination_reaps_owned_segmenter_without_completion(self):
        process = subprocess.Popen(self.command('--speed', '0.05'), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                state_path = self.work / 'ingest-state.json'
                if state_path.exists():
                    state = self.state()
                    if any(p['status'] == 'running' for p in state['processes']):
                        break
                if process.poll() is not None:
                    self.fail('Capture exited before interruption test')
                time.sleep(.025)
            else:
                self.fail('Segmenter never started')
            process.terminate()
            process.communicate(timeout=15)
            self.assertEqual(process.returncode, 130)
            self.assertEqual(self.state()['status'], 'interrupted')
            for child in self.state()['processes']:
                self.assertEqual(child['status'], 'exited')
                with self.assertRaises(ProcessLookupError):
                    os.kill(child['pid'], 0)
            self.assert_no_completion()
        finally:
            if process.poll() is None:
                process.terminate()
                process.communicate(timeout=15)

    def test_legacy_or_changed_completion_is_refused(self):
        result = self.run_capture()
        self.assertEqual(result.returncode, 0, result.stderr)
        marker = self.work / 'chunks/INGEST_DONE'
        original = marker.read_bytes()
        marker.write_text('')
        with self.assertRaises(ValueError):
            common.closed_chunks(self.work)
        marker.write_bytes(original)
        state = self.state()
        state['status'] = 'failed'
        (self.work / 'ingest-state.json').write_text(json.dumps(state))
        with self.assertRaisesRegex(RuntimeError, 'receipt differs'):
            common.closed_chunks(self.work)

    def test_killed_owner_leaves_journal_and_refuses_replay(self):
        process = subprocess.Popen(self.command('--speed', '0.05'), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        children = []
        try:
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                if (self.work / 'ingest-state.json').exists():
                    children = [p['pid'] for p in self.state()['processes'] if p['status'] == 'running']
                    if children:
                        break
                if process.poll() is not None:
                    self.fail('Capture exited before kill test')
                time.sleep(.025)
            self.assertTrue(children, 'Segmenter did not launch')
            process.kill()
            process.communicate(timeout=5)
            before = (self.work / 'ingest-state.json').read_bytes()
            for pid in children:
                os.kill(pid, 0)  # Orphan is genuinely live, not inferred from a stale journal.
            retry = self.run_capture()
            self.assertNotEqual(retry.returncode, 0)
            self.assertEqual((self.work / 'ingest-state.json').read_bytes(), before)
            self.assertEqual(self.state()['status'], 'running')
            self.assert_no_completion()
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=5)
            for pid in children:
                try:
                    os.killpg(pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass

    def test_missing_or_changed_tail_is_not_accepted_as_closed(self):
        result = self.run_capture()
        self.assertEqual(result.returncode, 0, result.stderr)
        tail = common.closed_chunks(self.work)[-1]
        tail.write_bytes(tail.read_bytes()[:-188])
        with self.assertRaisesRegex(RuntimeError, 'receipt differs'):
            common.closed_chunks(self.work)
        tail.rename(tail.with_name('seg_00004.ts'))
        with self.assertRaisesRegex(RuntimeError, 'not contiguous'):
            common.closed_chunks(self.work)

    def test_bad_arguments_create_no_capture_and_orphan_reservation_is_preserved(self):
        for args in [('--chunk', '0'), ('--speed', 'nan'), ('--dur', '-1')]:
            self.assertNotEqual(self.run_capture(self.command(*args)).returncode, 0)
            self.assertFalse(self.work.exists())
        self.work.mkdir(parents=True)
        reservation = self.work / 'ingest-reservation.json'
        reservation.write_text('{"status":"unknown launch outcome"}')
        before = reservation.read_bytes()
        self.assertNotEqual(self.run_capture().returncode, 0)
        self.assertEqual(reservation.read_bytes(), before)
        self.assertFalse((self.work / 'chunks').exists())


if __name__ == '__main__':
    unittest.main()
