"""Persistent MCP client for explicitly selected Premiere bridge profiles.

The connector remains the sole operation/job journal. This client neither retries
mutations nor promotes handler results to native, persistence or render proof.
Default profile resolves the installed Premiere Agent. Production uses exact-project scopes; research remains isolated.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import sys
import subprocess
import threading
import time


class BridgeError(RuntimeError):
    pass


class TransportUncertain(BridgeError):
    def __init__(self, message, request_id):
        super().__init__(message)
        self.request_id = request_id


def json_bytes(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False,
                      separators=(',', ':')).encode('utf-8')


def _verified_toolkit_profile(profile=None, path=None):
    """Bind even direct helper calls to this release's ACQ Edit Agent transport."""
    root = Path('__ACQ_TOOLKIT__')
    expected_path = root/'.local/premiere-profile.json'
    selected = path or (expected_path if profile is not None else os.environ.get('PREMIERE_AGENT_PROFILE') or expected_path)
    if str(selected) != str(expected_path):
        raise BridgeError('ACQ Edit Agent MCP only: external or legacy Premiere profiles are refused. Repair this toolkit installation; no fallback.')
    sys.path.insert(0, str(root/'python'))
    from premiere_installation import verify_profile
    try:
        data = verify_profile({'premiereProfile': str(expected_path)}, root)
    except (OSError, ValueError, RuntimeError, KeyError) as error:
        raise BridgeError('ACQ Edit Agent MCP is unavailable or its profile differs. Repair the toolkit integration and open the ACQ Edit Agent panel; do not use another bridge.') from error
    if profile is not None:
        actual = dict(vars(profile)); actual['command'] = list(profile.command)
        expected = {key: value for key, value in data.items() if key != 'schema'}
        if actual != expected:
            raise BridgeError('ACQ Edit Agent MCP only: supplied transport differs from the toolkit profile; no process was started.')
    return dict(data)


@dataclass(frozen=True)
class Profile:
    command: tuple[str, ...]
    cwd: str
    fixture_root: str
    connector: str = 'premiere-agent-lab'
    host_version: str = '26.3.0'
    mode: str = 'lab'
    project_authorization: str | None = None

    def __post_init__(self):
        if self.mode not in ('lab', 'scoped-reframe', 'scoped-edit') or self.connector != 'premiere-agent-lab':
            raise BridgeError('Supported Premiere Agent profile required; no fallback')
        if self.mode in ('scoped-reframe', 'scoped-edit') and (not self.project_authorization or not Path(self.project_authorization).is_absolute()):
            raise BridgeError('Scoped editing requires an exact-project authorization file')
        if self.host_version not in ('26.3.0', '27.0.0'):
            raise BridgeError('This integration requires an explicitly supported exact host profile')
        if not self.command or not all(isinstance(s, str) and s for s in self.command):
            raise BridgeError('An explicit executable argument list is required')
        if not all(Path(p).is_absolute() for p in (self.command[0], self.cwd, self.fixture_root)):
            raise BridgeError('Executable, cwd and fixture_root must be absolute paths')

    @classmethod
    def load(cls, path=None):
        data = _verified_toolkit_profile(path=path)
        if data.pop('schema', None) != 'edit.premiere-bridge-profile/v1':
            raise BridgeError('Unknown bridge profile schema')
        data['command'] = tuple(data['command'])
        return cls(**data)


class StdioMcp:
    """One persistent child, bounded newline-delimited JSON-RPC, no auto-replay.

    A timed-out request remains pending. receive(id) waits for that exact reply;
    it never sends the request again. close() refuses unresolved requests.
    """
    MAX_MESSAGE = 8 * 1024 * 1024

    def __init__(self, profile: Profile, timeout=30.0):
        _verified_toolkit_profile(profile)
        self.timeout = timeout
        self.lock = threading.RLock()
        self.pending, self.ready = set(), {}
        self.buffer = bytearray()
        self.next_id = 0
        self.process = subprocess.Popen(profile.command, cwd=profile.cwd,
                                        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.DEVNULL, bufsize=0,
                                        env={**os.environ, 'PREMIERE_AGENT_MODE': profile.mode})
        os.set_blocking(self.process.stdin.fileno(), False)
        os.set_blocking(self.process.stdout.fileno(), False)
        try:
            hello = self.request('initialize', {
                'protocolVersion': '2025-11-25', 'capabilities': {},
                'clientInfo': {'name': 'editing-skills', 'version': '0.1.0'},
            })
            if hello.get('protocolVersion') != '2025-11-25':
                raise BridgeError('Unsupported negotiated MCP protocol')
            if hello.get('serverInfo', {}).get('name') != profile.connector:
                raise BridgeError('Connected server identity differs from selected profile')
            self._write({'jsonrpc': '2.0', 'method': 'notifications/initialized'},
                        time.monotonic() + timeout)
        except Exception:
            # Initialization cannot submit editing work.
            self.process.terminate()
            self.process.wait(timeout=5)
            self._close_pipes()
            raise

    def _write(self, message, deadline):
        payload = json_bytes(message) + b'\n'
        if len(payload) > self.MAX_MESSAGE:
            raise BridgeError('MCP message exceeds the client bound')
        with selectors.DefaultSelector() as selector:
            selector.register(self.process.stdin, selectors.EVENT_WRITE)
            offset = 0
            while offset < len(payload):
                left = deadline - time.monotonic()
                if left <= 0 or not selector.select(left):
                    raise TimeoutError('MCP write timeout; dispatch may be partial')
                try:
                    offset += os.write(self.process.stdin.fileno(), payload[offset:])
                except BlockingIOError:
                    continue

    def request(self, method, params, timeout=None):
        with self.lock:
            if len(self.pending) >= 64:
                raise BridgeError('Too many unresolved MCP requests; reconcile existing IDs')
            # Validate JSON before reserving/sending a request.
            frozen = json.loads(json_bytes(params))
            self.next_id += 1
            rid = self.next_id
            self.pending.add(rid)
            deadline = time.monotonic() + (self.timeout if timeout is None else timeout)
            try:
                self._write({'jsonrpc': '2.0', 'id': rid, 'method': method, 'params': frozen}, deadline)
                return self.receive(rid, max(0, deadline - time.monotonic()))
            except TransportUncertain:
                raise
            except Exception as exc:
                raise TransportUncertain(str(exc), rid) from exc

    def receive(self, request_id, timeout=None):
        with self.lock:
            if request_id not in self.pending:
                raise BridgeError('No pending request with that ID')
            deadline = time.monotonic() + (self.timeout if timeout is None else timeout)
            try:
                while request_id not in self.ready:
                    while b'\n' in self.buffer:
                        line, _, remaining = self.buffer.partition(b'\n')
                        self.buffer = bytearray(remaining)
                        if not line.strip():
                            continue
                        message = json.loads(line)
                        if message.get('jsonrpc') != '2.0':
                            raise BridgeError('Invalid MCP response envelope')
                        if 'method' in message:
                            if 'id' in message:
                                self._write({'jsonrpc': '2.0', 'id': message['id'],
                                             'error': {'code': -32601, 'message': 'Client capability unavailable'}}, deadline)
                            continue
                        rid = message.get('id')
                        if rid not in self.pending or rid in self.ready:
                            raise BridgeError('Unexpected or duplicate MCP response ID')
                        self.ready[rid] = message
                    if request_id in self.ready:
                        break
                    left = deadline - time.monotonic()
                    with selectors.DefaultSelector() as selector:
                        selector.register(self.process.stdout, selectors.EVENT_READ)
                        if left <= 0 or not selector.select(left):
                            raise TimeoutError('MCP response timeout')
                    chunk = os.read(self.process.stdout.fileno(), 65536)
                    if not chunk:
                        raise EOFError('MCP server disconnected')
                    self.buffer.extend(chunk)
                    if len(self.buffer) > self.MAX_MESSAGE:
                        raise BridgeError('MCP response exceeds the client bound')
                response = self.ready.pop(request_id)
                self.pending.remove(request_id)
                if 'error' in response:
                    raise BridgeError('MCP error: ' + json.dumps(response['error']))
                if 'result' not in response:
                    raise BridgeError('MCP response lacks a result')
                return response['result']
            except Exception as exc:
                raise TransportUncertain(str(exc), request_id) from exc

    def call(self, name, arguments):
        return self.request('tools/call', {'name': name, 'arguments': arguments})

    def _close_pipes(self):
        self.process.stdin.close()
        self.process.stdout.close()

    def close(self):
        with self.lock:
            if self.pending:
                raise BridgeError('Pending MCP responses require reconciliation before close')
            self.process.stdin.close()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                self.process.wait(timeout=5)
            self.process.stdout.close()


class PremiereBridge:
    def __init__(self, profile: Profile, transport=None):
        self.profile = profile
        self.transport = transport if transport is not None else StdioMcp(profile)
        self.unsettled = set()

    def _call(self, name, args):
        envelope = self.transport.call(name, args)
        blocks = envelope.get('content', [])
        if len(blocks) != 1 or blocks[0].get('type') != 'text':
            raise BridgeError('Unexpected Lab response; do not infer an outcome')
        return json.loads(blocks[0]['text']), envelope.get('isError', False)

    def inspect(self, name, args):
        if name not in {'lab_snapshot', 'lab_search_capabilities', 'lab_get_operation', 'lab_get_job', 'ping', 'inspect_reframe_state', 'inspect_music_state', 'inspect_project_sequences', 'inspect_assembly_links', 'get_full_sequence_info','lab_inspect_export_state'}:
            capability = self.capability(name)
            if capability.get('authority', {}).get('required') != 'inspect' or capability.get('targetVersionEligible') is not True or capability.get('authorityPermitted') is not True:
                raise BridgeError('Use the guarded submit path for stage operations')
        value, error = self._call(name, args)
        if error or isinstance(value, dict) and value.get('success') is False:
            raise BridgeError('Lab inspection failed: ' + json.dumps(value))
        return value

    def capability(self, name):
        offset = 0
        while True:
            page = self.inspect('lab_search_capabilities', {'query': name, 'offset': offset, 'limit': 100})
            rows = page['operations']
            for row in rows:
                if row['name'] == name:
                    return row
            offset += len(rows)
            if not rows or offset >= page['total']:
                raise BridgeError('Operation is absent from this connector catalog')

    def submit(self, plan):
        """Submit one stage operation; plans and postconditions remain stage-owned."""
        plan = json.loads(json_bytes(plan))
        if plan.get('schema') != 'edit.native-operation/v1':
            raise BridgeError('Unknown native operation plan schema')
        if plan.get('stage') not in {'assembly', 'reframe', 'captions', 'music', 'export'}:
            raise BridgeError('Unknown editing stage')
        op = plan.get('operation_id')
        if not isinstance(op, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', op):
            raise BridgeError('Invalid operation ID')
        if self.unsettled:
            raise BridgeError('This client has unsettled native work; reconcile before another submission')
        args = plan.get('arguments')
        if not isinstance(args, dict) or any(k.startswith('_lab') for k in args):
            raise BridgeError('Arguments must not override Lab guards')
        for field in ('intended_changes', 'protected_state'):
            if not isinstance(plan.get(field), list) or not plan[field]:
                raise BridgeError(f'{field} must declare the stage contract')
        target = plan['target']
        if not isinstance(target, dict) or not {'project_path', 'sequence_id', 'expected_revision'} <= target.keys():
            raise BridgeError('Exact project, explicit sequence identity and snapshot revision are required')
        project = Path(target['project_path'])
        if not project.is_absolute() or project.suffix != '.prproj':
            raise BridgeError('An absolute Premiere project path is required')
        fixture = project.resolve().is_relative_to(Path(self.profile.fixture_root).resolve())
        if not fixture or self.profile.mode == 'scoped-edit':
            if self.profile.mode not in ('scoped-reframe','scoped-edit') or (self.profile.mode == 'scoped-reframe' and plan['stage'] != 'reframe'):
                raise BridgeError('Target must be inside the selected disposable fixture root')
            from datetime import datetime
            auth = json.loads(Path(self.profile.project_authorization).read_text())
            allowed = {'lab_update_static_panel_geometry','lab_export_reframe_frames','lab_reframe_embedded_panels','lab_split_reframe_shots', 'lab_duplicate_vertical_sequence', 'lab_apply_reframe_motion', 'lab_repair_anchor_x_keys', 'save_project', 'set_active_sequence', 'export_frame'}
            if self.profile.mode == 'scoped-edit':
                allowed |= {'lab_import_compiled_assembly','lab_import_prepared_caption_sequence','lab_place_graphic_asset','lab_prepare_music_source','lab_place_music_item','lab_apply_music_envelope','lab_apply_assembly_audio_edges','export_sequence','lab_export_exact_range'}
            schema = 'premiere-agent/edit-project-authorization-v1' if self.profile.mode == 'scoped-edit' else 'premiere-agent/reframe-project-authorization-v1'
            if (auth.get('schema') != schema or
                    auth.get('projectPath') != str(project.resolve()) or
                    datetime.fromisoformat(auth['expiresAt']).timestamp() <= time.time() or
                    plan['tool'] not in allowed or plan['tool'] not in auth.get('tools', [])):
                raise BridgeError('Exact project/tool authorization is missing or expired')
        if not re.fullmatch(r'[a-f0-9]{64}', target.get('expected_revision', '')):
            raise BridgeError('A prior exact snapshot revision is required')
        if target.get('sequence_id') is not None and not isinstance(target.get('sequence_id'), str):
            raise BridgeError('Sequence identity must be a string or null')
        # Inspect prior IDs; do not resubmit or treat another request's receipt as ours.
        prior = self.inspect('lab_get_operation', {'operation_id': op})
        job = self.inspect('lab_get_job', {'job_id': op})
        if prior is not None or job is not None:
            raise BridgeError('Operation ID already exists; reconcile its original receipt, do not resubmit')
        capability = self.capability(plan['tool'])
        if capability.get('authorityPermitted') is not True or capability.get('targetVersionEligible') is not True or capability.get('status') == 'unsupported' or capability.get('labMutationPolicy') == 'blocked_pending_fixture_contract':
            raise BridgeError('Capability is unavailable under the selected profile')
        ping = self.inspect('ping', {}).get('data', {})
        if ping.get('connected') is not True or not re.match(r'^' + re.escape(self.profile.host_version) + r'(?:\D|$)', ping.get('premiereVersion', '')):
            raise BridgeError('Live Premiere version does not match the profile')
        snapshot = self.inspect('lab_snapshot', {})
        if (snapshot.get('projectPath'), snapshot.get('sequenceId'), snapshot.get('revision')) != (str(project), target.get('sequence_id'), target['expected_revision']):
            raise BridgeError('Target or state changed since the stage plan was created')
        guard = dict(operation_id=op, project_path=str(project),
                     sequence_id=target.get('sequence_id'), expected_revision=target['expected_revision'])
        request = {**args, '_lab': guard, '_lab_async': True}
        fingerprint = hashlib.sha256(json.dumps(plan, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
        self.unsettled.add(op)
        try:
            value, error = self._call(plan['tool'], request)
        except Exception as exc:
            return {'operation_id': op, 'plan_sha256': fingerprint, 'status': 'unknown',
                    'request_id': getattr(exc, 'request_id', None), 'error': str(exc),
                    'recovery': 'inspect_original_job_and_operation; never_auto_retry'}
        # Only the matching durable job envelope establishes successful submission.
        if not isinstance(value, dict) or value.get('jobId') != op or value.get('state') not in {'queued', 'running', 'settled'}:
            return {'operation_id': op, 'plan_sha256': fingerprint, 'status': 'unknown',
                    'connector_result': value, 'mcp_error': error,
                    'recovery': 'inspect_original_job_and_operation; never_auto_retry'}
        return {'operation_id': op, 'plan_sha256': fingerprint, 'status': 'submitted',
                'job': value, 'capability_evidence': {
                    k: capability.get(k) for k in ('hostTest', 'persistenceTest', 'visualTest')},
                'evidence': {'execution': 'pending', 'readback': 'not_run',
                             'persistence': 'not_run', 'rendered': 'not_run'}}

    def reconcile(self, operation_id):
        job = self.inspect('lab_get_job', {'job_id': operation_id})
        operation = self.inspect('lab_get_operation', {'operation_id': operation_id})
        # A missing receipt does not prove non-execution. Never auto-retry.
        settled = isinstance(job, dict) and job.get('jobId') == operation_id and job.get('state') == 'settled' and job.get('outcome') in {'failed', 'reported_success', 'committed_unverified'}
        reconciled = settled and (operation is None or isinstance(operation, dict) and
                                 operation.get('operationId') == operation_id and
                                 operation.get('status') in {'failed', 'committed_unverified'})
        if reconciled:
            self.unsettled.discard(operation_id)
        else:
            self.unsettled.add(operation_id)
        return {'job': job, 'operation': operation, 'reconciled': reconciled,
                'persistence': 'not_run', 'rendered': 'not_run'}

    def close(self):
        if self.unsettled:
            raise BridgeError('Unsettled native jobs require reconciliation before closing the client')
        self.transport.close()


def execute_operation(client, operation, receipt_path, timeout=120):
    # A saved stage artifact, not another connector journal. Refuse an
    # existing attempt even when its response was lost; reconcile its ID.
    with receipt_path.open('x') as stream:
        json.dump({'operation': operation, 'status': 'prepared_execution_not_yet_recorded'}, stream, indent=2)
    result = client.submit(operation)
    _write_stage_receipt(receipt_path, operation, result)
    if result['status'] != 'submitted':
        raise BridgeError(f'Uncertain submission; inspect {receipt_path}')
    deadline = time.monotonic() + timeout
    while True:
        state = client.reconcile(operation['operation_id'])
        _write_stage_receipt(receipt_path, operation, state)
        if state['reconciled']:
            native = state.get('operation') or {}
            if native.get('status') != 'committed_unverified' or native.get('result', {}).get('success') is not True:
                raise BridgeError(f'Native operation did not report success; inspect {receipt_path}')
            return native['result'].get('data', {})
        if (state.get('job') or {}).get('outcome') == 'unknown' or time.monotonic() >= deadline:
            raise BridgeError(f'Unresolved operation; keep its original ID and inspect {receipt_path}')
        time.sleep(0.2)

def _write_stage_receipt(path, operation, result):
    stage = path.with_suffix(path.suffix + '.staged')
    stage.write_text(json.dumps({'operation': operation, 'result': result}, indent=2))
    stage.replace(path)
