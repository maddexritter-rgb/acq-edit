"""Complete the private compiled runtime and check MCP discovery without calling a host tool."""
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys

REQUIRED_TOOLS = {'lab_snapshot', 'lab_import_compiled_assembly', 'lab_apply_assembly_audio_edges',
                  'lab_export_exact_range', 'lab_import_prepared_caption_sequence'}


def copy_resources(root):
    root = Path(root)
    source = root / 'src/resources'
    resources = sorted(source.glob('*.json'))
    if not resources or not (source / 'adobe-uxp-coverage.json').is_file():
        raise RuntimeError('Premiere runtime resources are incomplete')
    # Parse every source before writing; preserve an existing conflicting build.
    for file in resources:
        json.loads(file.read_text())
        target = root / 'dist/resources' / file.name
        if file.is_symlink() or target.is_symlink() or (target.exists() and target.read_bytes() != file.read_bytes()):
            raise RuntimeError('Conflicting Premiere runtime resource preserved: ' + file.name)
    (root / 'dist/resources').mkdir(parents=True, exist_ok=True)
    hashes = {}
    for file in resources:
        target = root / 'dist/resources' / file.name
        if not target.exists():
            with target.open('xb') as stream:
                stream.write(file.read_bytes())
        hashes[file.name] = hashlib.sha256(target.read_bytes()).hexdigest()
    return hashes


def check_transport(root, profile, cli, resource_hashes):
    # tools/list initializes the actual packaged server but never dispatches an editor command.
    process = subprocess.Popen([sys.executable, str(cli), '--profile', str(profile), 'tools'],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                               start_new_session=True)
    try:
        stdout, stderr = process.communicate(timeout=60)
        if process.returncode:
            raise RuntimeError('Packaged Premiere MCP discovery failed; installation retained for diagnosis')
        result = json.loads(stdout)
        names = result.get('tools', [])
        if not isinstance(names, list) or not all(isinstance(name, str) for name in names):
            raise RuntimeError('Invalid Premiere tool catalog')
        missing = REQUIRED_TOOLS - set(names)
        if missing or result.get('count') != len(names):
            raise RuntimeError('Packaged Premiere tool catalog incomplete: ' + ', '.join(sorted(missing)))
    except subprocess.TimeoutExpired as error:
        raise RuntimeError('Packaged Premiere MCP discovery timed out; installation retained') from error
    finally:
        # Includes the Node transport if discovery failed or left a child running.
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.communicate()
    receipt = {'schema': 'acq-edit/premiere-runtime-v1', 'resourceHashes': resource_hashes,
               'transportInitialized': True, 'toolCount': len(names), 'requiredTools': sorted(REQUIRED_TOOLS),
               'hostToolsCalled': False, 'hostQualified': False}
    with (Path(root) / 'lab/runtime-preparation.json').open('x') as stream:
        json.dump(receipt, stream, indent=2)
    return receipt
