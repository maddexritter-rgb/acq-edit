#!/usr/bin/env python3
"""Capture source chunks into a new, exclusively owned live work directory.

This helper captures media only. It does not select cuts, run an editing agent,
publish clips, or switch the project's editing backend. A failed/interrupted run
is retained; retry into a new work directory after inspecting existing processes.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import uuid
from urllib.parse import urlparse


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def atomic_json(path, value):
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    with temporary.open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def segment_cmd(inputs, chunk, chunks):
    return ['ffmpeg', '-hide_banner', '-nostdin', '-n', '-loglevel', 'warning',
            *inputs, '-c', 'copy', '-f', 'segment', '-segment_time', str(chunk),
            '-reset_timestamps', '1', str(chunks / 'seg_%05d.ts')]


class Capture:
    def __init__(self, work, parameters):
        self.work = work
        self.children = []
        self.state = {'schema': 'acq-edit/live-capture-v1', 'id': str(uuid.uuid4()),
                      'ownerPid': os.getpid(), 'createdAt': now(),
                      'status': 'starting', 'parameters': parameters, 'processes': []}
        work.mkdir(parents=True, exist_ok=True)
        # Never delete a done flag or reuse a segmenter's output directory.
        if any((work / name).exists() or (work / name).is_symlink() for name in
               ['chunks', 'manifest.json', 'ingest.log', 'ingest-state.json']):
            raise RuntimeError('Capture work already exists; preserve it and use a new work directory')
        reservation = work / 'ingest-reservation.json'
        with reservation.open('x') as stream:
            json.dump(self.state, stream)
            stream.flush()
            os.fsync(stream.fileno())
        # Reservation is permanent evidence, including after success or a kill.
        self.write()
        self.chunks = work / 'chunks'
        self.chunks.mkdir()
        self.log = (work / 'ingest.log').open('xb')

    def write(self):
        self.state['updatedAt'] = now()
        atomic_json(self.work / 'ingest-state.json', self.state)

    def spawn(self, role, args, **kwargs):
        entry = {'role': role, 'status': 'launching', 'pid': None}
        self.state['processes'].append(entry)
        self.write()  # Unknown launch outcomes must never be silently replayed.
        child = subprocess.Popen(args, start_new_session=True, stderr=self.log, **kwargs)
        self.children.append((child, entry))
        entry.update(status='running', pid=child.pid)
        self.state['status'] = 'running'
        self.write()
        return child

    def exited(self, child):
        entry = next(entry for process, entry in self.children if process is child)
        entry.update(status='exited', returncode=child.returncode)
        self.write()
        return child.returncode

    def wait(self, child):
        child.wait()
        return self.exited(child)

    def hls(self, url):
        for fmt in ['best[protocol*=m3u8][height<=1080]', 'best[protocol*=m3u8]']:
            child = self.spawn('resolve-hls', ['yt-dlp', '--ignore-config', '--no-playlist',
                               '--no-warnings', '-g', '-f', fmt, '--', url], stdout=subprocess.PIPE)
            try:
                output, _ = child.communicate(timeout=90)
            except subprocess.TimeoutExpired:
                self.stop_child(child)
                continue
            self.exited(child)
            lines = output.decode().strip().splitlines()
            if child.returncode == 0 and len(lines) == 1:
                parsed = urlparse(lines[0])
                if parsed.scheme == 'https' and parsed.netloc and '.m3u8' in parsed.path:
                    return lines[0]
        return None

    def stop_child(self, child):
        if child.poll() is None:
            try:
                os.killpg(child.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                child.wait(timeout=5)
        self.exited(child)

    def stop(self):
        # Segmenter first, then downloader, so a broken pipe cannot leave it alive.
        for child, _ in reversed(self.children):
            self.stop_child(child)

    def finish(self):
        chunks = sorted(self.chunks.glob('seg_*.ts'))
        if not chunks or any(not p.is_file() or p.is_symlink() or p.stat().st_size == 0 for p in chunks):
            raise RuntimeError('Capture returned no complete nonempty source chunks')
        expected = [f'seg_{i:05d}.ts' for i in range(len(chunks))]
        if [p.name for p in chunks] != expected:
            raise RuntimeError('Capture chunk numbering is not contiguous')
        self.state['status'] = 'succeeded'
        self.state['finishedAt'] = now()
        self.write()
        receipt = {'schema': 'acq-edit/live-completion-v1', 'captureId': self.state['id'],
                   'stateSha256': hashlib.sha256((self.work / 'ingest-state.json').read_bytes()).hexdigest(),
                   'chunks': [{'file': p.name, 'bytes': p.stat().st_size} for p in chunks]}
        # Completion is the final write, only after every required producer succeeds.
        atomic_json(self.chunks / 'INGEST_DONE', receipt)


def arguments(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['live', 'simulate'])
    parser.add_argument('source')
    parser.add_argument('--work', required=True)
    parser.add_argument('--chunk', type=int, default=120)
    parser.add_argument('--speed', type=float, default=30)
    parser.add_argument('--dur', type=float, default=0)
    parser.add_argument('--pipe', action='store_true')
    args = parser.parse_args(argv)
    if args.chunk <= 0 or not math.isfinite(args.speed) or args.speed < 0 or not math.isfinite(args.dur) or args.dur < 0:
        parser.error('Chunk duration must be positive; speed/duration must be finite and nonnegative')
    if args.mode == 'live':
        url = urlparse(args.source)
        if url.scheme != 'https' or url.hostname not in ['youtube.com', 'www.youtube.com', 'm.youtube.com', 'youtu.be'] or url.username or url.password or url.port:
            parser.error('Provide a YouTube HTTPS URL without embedded credentials')
        if args.dur:
            parser.error('--dur is available only for simulation; it cannot imply a completed live stream')
    elif not Path(args.source).expanduser().is_file():
        parser.error('Simulation source must be an existing media file')
    return args


def main(argv=None):
    args = arguments(argv)
    capture = Capture(Path(args.work).expanduser().absolute(), {
        'mode': args.mode, 'source': args.source if args.mode == 'live' else str(Path(args.source).expanduser().absolute()),
        'chunkSeconds': args.chunk, 'simulationSpeed': args.speed if args.mode == 'simulate' else None,
        'simulationDurationLimit': args.dur if args.mode == 'simulate' else None,
        'forcePipe': args.pipe,
    })
    handlers = {}

    def interrupted(signum, _frame):
        raise InterruptedError(f'Capture interrupted by signal {signum}')

    for sig in [signal.SIGINT, signal.SIGTERM]:
        handlers[sig] = signal.signal(sig, interrupted)
    try:
        if args.mode == 'simulate':
            inputs = ['-readrate', str(args.speed)] if args.speed else []
            if args.dur:
                inputs += ['-t', str(args.dur)]
            inputs += ['-i', str(Path(args.source).expanduser().absolute())]
            child = capture.spawn('segmenter', segment_cmd(inputs, args.chunk, capture.chunks), stdout=capture.log)
            if capture.wait(child) != 0:
                raise RuntimeError('FFmpeg capture failed; inspect ingest.log')
        else:
            hls = None if args.pipe else capture.hls(args.source)
            if hls:
                child = capture.spawn('segmenter', segment_cmd(['-live_start_index', '0', '-rw_timeout', '30000000', '-i', hls], args.chunk, capture.chunks), stdout=capture.log)
                if capture.wait(child) != 0:
                    raise RuntimeError('HLS capture failed; inspect ingest.log')
            else:
                downloader = capture.spawn('downloader', ['yt-dlp', '--ignore-config', '--no-playlist', '--no-simulate', '--live-from-start', '-f', 'b', '--no-part', '--no-progress', '-o', '-', '--', args.source], stdout=subprocess.PIPE)
                segmenter = capture.spawn('segmenter', segment_cmd(['-i', 'pipe:0'], args.chunk, capture.chunks), stdin=downloader.stdout, stdout=capture.log)
                downloader.stdout.close()
                if capture.wait(segmenter) != 0:
                    raise RuntimeError('Piped FFmpeg capture failed; inspect ingest.log')
                if capture.wait(downloader) != 0:
                    raise RuntimeError('Downloader failed; retained chunks are not a completed stream')
        capture.finish()
        print(json.dumps({'status': 'succeeded', 'work': str(capture.work), 'captureId': capture.state['id']}))
        return 0
    except BaseException as error:
        # Ignore subsequent termination signals while cleaning up our own children.
        for sig in handlers:
            signal.signal(sig, signal.SIG_IGN)
        capture.stop()
        capture.state.update(status='interrupted' if isinstance(error, (InterruptedError, KeyboardInterrupt)) else 'failed', error=str(error), finishedAt=now())
        capture.write()
        print(str(error), file=sys.stderr)
        return 130 if capture.state['status'] == 'interrupted' else 1
    finally:
        capture.log.close()
        for sig, handler in handlers.items():
            signal.signal(sig, handler)


if __name__ == '__main__':
    sys.exit(main())
