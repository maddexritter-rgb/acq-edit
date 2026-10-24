"""Exact project bootstrap/reopen through the dedicated scoped Lab lifecycle endpoint."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import os
import re
import uuid
from common import inside, require, sha, save, read


def call(client, name, args):
    require(name in ('lab_inspect_toolkit_workspace', 'lab_toolkit_project', 'lab_reconcile_toolkit_project'), 'Unknown lifecycle endpoint')
    value, error = client._call(name, args)
    require(not error, 'Premiere lifecycle request failed: ' + str(value))
    require(isinstance(value, dict), 'Malformed Premiere lifecycle response')
    return value


def inspect_result(project, native, state):
    from common import fingerprint
    require(state['projectPath'] == str(native), 'Wrong native Premiere project')
    native_hash = sha(native)
    current = fingerprint(state)
    return {'state': state, 'fingerprint': current, 'nativeSha256': native_hash,
            'reopen': {'schema': 'acq-edit/premiere-reopen-v1', 'nativeProject': str(native),
                       'nativeSha256': native_hash, 'expectedFingerprint': current,
                       'sequenceId': state['sequenceId']}}


def open_project(adapter, project, packet, client_type):
    mode = packet.get('mode', 'open')
    require(mode in ('create', 'open'), 'Premiere lifecycle mode must be create or open')
    root = Path(project['root']).resolve()
    require(project['backend'] == 'premiere' and read(root / 'project.json') == project,
            'Lifecycle requires the exact persisted Premiere toolkit project')
    native = inside(root / '10_WORK', packet['nativeProject'])
    require(native.suffix == '.prproj', 'Native Premiere project extension required')
    receipt = inside(root / '10_WORK', packet['receipt'])
    require(receipt != native and not receipt.exists() and not receipt.is_symlink(), 'Fresh lifecycle receipt required')
    reopen = packet.get('reopen')
    if mode == 'open':
        require(isinstance(reopen, dict) and reopen.get('schema') == 'acq-edit/premiere-reopen-v1'
                and reopen.get('nativeProject') == str(native), 'Exact prior Premiere reopening identity required')
        required = {'schema', 'nativeProject', 'nativeSha256', 'expectedFingerprint', 'sequenceId'}
        require(required <= set(reopen) <= required | {'inspectionSha256'}
                and isinstance(reopen['expectedFingerprint'], str)
                and re.fullmatch(r'[a-f0-9]{64}', reopen['expectedFingerprint'])
                and (reopen['sequenceId'] is None or isinstance(reopen['sequenceId'], str)),
                'Valid complete Premiere reopening fingerprint and sequence identity required')
        require(native.is_file() and sha(native) == reopen.get('nativeSha256'), 'Saved Premiere project changed; preserve it and inspect before reopening')
    else:
        require(not native.exists() and not native.is_symlink(), 'New Premiere project already exists; preserved')
    runtime = Path(adapter.profile.cwd) / 'lab/runtime'
    operation_id = os.environ.get('ACQ_EDIT_NATIVE_OPERATION_ID') or str(uuid.uuid4())
    require(str(uuid.UUID(operation_id)) == operation_id, 'Invalid toolkit native operation identity')
    client = client_type(adapter.profile)
    try:
        before = call(client, 'lab_inspect_toolkit_workspace', {})
        state = before['state']
        if mode == 'open' and state.get('activePath') == str(native):
            current = inspect_result(project, native, client.inspect('lab_snapshot', {}))
            require(current['fingerprint'] == reopen.get('expectedFingerprint')
                    and current['nativeSha256'] == reopen['nativeSha256'], 'Open Premiere project has intervening edits; preserved')
            result = {'status': 'verified_existing_session', 'inspection': current, 'nativeMutations': 0}
            save(receipt, result)
            return result
        require(state.get('openProjects') == [] and state.get('activePath') is None,
                'Premiere has another open or unsaved project. Preserve it; this route never closes or switches unrelated projects')
        require(packet.get('ownershipConfirmed') is True,
                'Confirm exclusive Premiere ownership before lifecycle dispatch; the agent must coordinate other writers')
        native.parent.mkdir(parents=True, exist_ok=True)
        scope_root = runtime / 'toolkit-scopes'
        require(not scope_root.is_symlink(), 'Redirected lifecycle scope directory refused')
        scope_root.mkdir(exist_ok=True)
        scope = {'schema': 'acq-edit/premiere-project-scope-v1', 'operationId': operation_id,
                 'mode': mode, 'projectId': project['id'], 'projectRoot': str(root),
                 'projectManifestSha256': sha(root / 'project.json'), 'projectPath': str(native),
                 'expectedWorkspaceRevision': before['revision'],
                 'expectedNativeSha256': reopen['nativeSha256'] if mode == 'open' else None,
                 'ownershipConfirmed': True, 'ownerPid': os.getpid(),
                 'expiresAt': (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()}
        scope_path = scope_root / (operation_id + '.json')
        with scope_path.open('x') as stream:
            import json
            json.dump(scope, stream, indent=2)
        scope_path.chmod(0o600)
        args = {'operationId': operation_id, 'mode': mode, 'projectPath': str(native),
                'expectedWorkspaceRevision': before['revision']}
        if mode == 'open': args['expectedNativeSha256'] = reopen['nativeSha256']
        result = call(client, 'lab_toolkit_project', args)
        # Preserve host evidence even when postconditions or later inspection fail.
        save(receipt, result)
        require(result.get('status') == 'committed_unverified', 'Premiere lifecycle outcome requires reconciliation; do not replay')
        require(result.get('request') == args and result.get('projectId') == project['id'],
                'Premiere lifecycle receipt identity differs')
    finally:
        client.close()
    current = adapter.inspect(project, {'nativeProject': str(native)})
    require(current['nativeSha256'] == result.get('nativeSha256'), 'Saved Premiere project changed after lifecycle operation')
    if mode == 'open':
        require(current['fingerprint'] == reopen['expectedFingerprint'] and current['state']['sequenceId'] == reopen['sequenceId'],
                'Reopened Premiere state differs from the prior inspection; preserve the open project and reconcile')
    return {'status': 'inspected_native_session', 'mode': mode, 'receipt': str(receipt),
            'operationId': operation_id, 'inspection': current, 'requiresStageScope': True,
            'nativeWorkflowQualified': False}


def reconcile_project(adapter, project, evidence, client_type):
    """Inspect the uncertain operation and request lock reconciliation, never replay."""
    root = Path(project['root']).resolve()
    operation_id = evidence['operationId']
    require(str(uuid.UUID(operation_id)) == operation_id and evidence.get('backend') == 'premiere',
            'Exact Premiere lifecycle operation required')
    intent = evidence.get('premiereLifecycle')
    require(isinstance(intent, dict) and set(intent) <= {'schema', 'outcome'}
            and intent.get('schema', 'acq-edit/premiere-lifecycle-reconciliation-v1') == 'acq-edit/premiere-lifecycle-reconciliation-v1'
            and intent.get('outcome') in ('unchanged', 'target-open', 'artifacts-retained'),
            'Specify the observed Premiere lifecycle outcome')
    require(evidence.get('noActiveWriter') is True and evidence.get('processInspection')
            and evidence.get('nativeInspection'), 'Terminal process and native inspection evidence required')
    # native.py pins the original evidence file; its path is supplied separately by the adapter.
    source = inside(root, evidence['_evidencePath'])
    original = read(source)
    require({key: value for key, value in evidence.items() if key != '_evidencePath'} == original,
            'Recovery evidence differs from its source file')
    source_hash = sha(source)
    directory = inside(root / '10_WORK', root / '10_WORK/premiere-reconciliation' / operation_id / source_hash)
    request_file, result_file = directory / 'request.json', directory / 'result.json'
    client = client_type(adapter.profile)
    try:
        operation = client.inspect('lab_get_operation', {'operation_id': operation_id})
        require(operation and operation.get('schema') == 'acq-edit/premiere-project-operation-v2'
                and operation.get('projectId') == project['id'] and operation.get('status') in ('unknown', 'running'),
                'Original uncertain Premiere lifecycle journal required; legacy journals need explicit repair')
        native = inside(root / '10_WORK', operation['request']['projectPath'])
        if request_file.exists():
            request = read(request_file)
            require(request.get('originalEvidencePath') == str(source)
                    and request.get('originalEvidenceSha256') == source_hash, 'Existing reconciliation request differs; preserved')
        else:
            observed = call(client, 'lab_inspect_toolkit_workspace', {'operationId': operation_id})
            observed_intent = {'schema': 'acq-edit/premiere-lifecycle-reconciliation-v1',
                               'outcome': intent['outcome'], 'expectedWorkspaceRevision': observed['revision']}
            if intent['outcome'] != 'unchanged':
                observed_intent['expectedNativeSha256'] = sha(native)
            if intent['outcome'] == 'target-open':
                require(observed['state']['activePath'] == str(native), 'Expected lifecycle target is not active; unrelated project preserved')
                state = client.inspect('lab_snapshot', {})
                require(state['projectPath'] == str(native) and re.fullmatch(r'[a-f0-9]{64}', state['revision']),
                        'Exact native snapshot revision required')
                observed_intent['expectedNativeRevision'] = state['revision']
            request = {**original, 'originalEvidencePath': str(source), 'originalEvidenceSha256': source_hash,
                       'premiereLifecycle': observed_intent}
            require(sha(source) == source_hash, 'Recovery evidence changed during inspection')
            save(request_file, request)
            request_file.chmod(0o600)
        result = call(client, 'lab_reconcile_toolkit_project', {'operationId': operation_id,
                      'evidencePath': str(request_file), 'evidenceSha256': sha(request_file)})
        require(result.get('operationId') == operation_id and result.get('projectId') == project['id']
                and result.get('releaseAuthorized') is True and result.get('originalWriterLockReleased') is True
                and result.get('nativeRequestReplayed') is False, 'Lifecycle reconciliation did not release its original lock')
        if result_file.exists(): require(read(result_file) == result, 'Existing recovery result differs; preserved')
        else:
            save(result_file, result)
            result_file.chmod(0o600)
        require(sha(source) == source_hash, 'Original recovery evidence changed')
        return {'schema': 'acq-edit/premiere-lifecycle-recovery-result-v1', 'operationId': operation_id,
                'resultPath': str(result_file), 'resultSha256': sha(result_file),
                'originalWriterLockReleased': True, 'nativeRequestReplayed': False}
    finally:
        client.close()
