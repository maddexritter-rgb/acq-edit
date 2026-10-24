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
REQUIRED_HELPERS = ('validate-assembly-import.py', 'validate-master-import.py',
                    'assembly-master-compiler.py', 'prepare-assembly-coverage.py')


def compiled_hashes(root):
    dist = Path(root) / 'dist'
    if dist.is_symlink() or not (dist / 'lab/index.js').is_file():
        raise RuntimeError('Compiled Premiere entrypoint missing or redirected')
    hashes = {}
    for target in sorted(dist.rglob('*')):
        if target.is_symlink():
            raise RuntimeError('Symlink in compiled Premiere runtime')
        if target.is_file() and target.suffix in ('.js', '.json'):
            hashes[target.relative_to(dist).as_posix()] = hashlib.sha256(target.read_bytes()).hexdigest()
    return hashes


def verify_helpers(root, toolkit):
    root, toolkit = Path(root), Path(toolkit)
    manifest = json.loads((toolkit / 'integrations/premiere-source-manifest.json').read_text())
    overrides = json.loads((toolkit / 'integrations/premiere-distribution-overrides.json').read_text())
    entries = {row['path']: row['sha256'] for row in manifest['files']}
    changes = {row['path']: row for row in overrides['files']}
    hashes = {}
    for name in REQUIRED_HELPERS:
        rel = 'scripts/' + name
        expected = entries[rel]
        if rel in changes:
            if changes[rel]['originalSourceSha256'] != expected:
                raise RuntimeError('Premiere helper original source mismatch: ' + name)
            expected = changes[rel]['distributionSha256']
        target = root / rel
        if target.is_symlink() or hashlib.sha256(target.read_bytes()).hexdigest() != expected:
            raise RuntimeError('Premiere helper hash mismatch: ' + name)
        hashes[name] = expected
    bootstrap = root / 'scripts/acq_edit_runtime.py'
    if bootstrap.is_symlink() or bootstrap.read_bytes() != (toolkit / 'scripts/premiere_skill_runtime.py').read_bytes():
        raise RuntimeError('Premiere skill runtime bootstrap mismatch')
    hashes[bootstrap.name] = hashlib.sha256(bootstrap.read_bytes()).hexdigest()
    return hashes


def prepare_helpers(root, toolkit):
    root, toolkit = Path(root), Path(toolkit)
    with (root / 'scripts/acq_edit_runtime.py').open('xb') as stream:
        stream.write((toolkit / 'scripts/premiere_skill_runtime.py').read_bytes())
    hashes = verify_helpers(root, toolkit)
    # Exercise real imports and verified compiler resolution before MCP discovery.
    probe = """import importlib.util, sys
from pathlib import Path
root=Path(sys.argv[1]);sys.path.insert(0,str(root/'scripts'))
from acq_edit_runtime import skill_scripts
assert skill_scripts().is_dir()
for name in ('validate-assembly-import.py','validate-master-import.py','assembly-master-compiler.py','prepare-assembly-coverage.py'):
    spec=importlib.util.spec_from_file_location('probe_'+name,root/'scripts'/name)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    if name=='assembly-master-compiler.py':module.canonical()
"""
    subprocess.run([sys.executable, '-B', '-c', probe, str(root)], check=True, timeout=60,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return hashes


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


def check_transport(root, profile, cli, resource_hashes, helper_hashes=None):
    code_hashes = compiled_hashes(root)
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
    if compiled_hashes(root) != code_hashes:
        raise RuntimeError('Compiled Premiere runtime changed during discovery')
    receipt = {'schema': 'acq-edit/premiere-runtime-v2', 'resourceHashes': resource_hashes,
               'compiledHashes': code_hashes,
               'helperHashes': helper_hashes or {},
               'transportInitialized': True, 'toolCount': len(names), 'requiredTools': sorted(REQUIRED_TOOLS),
               'hostToolsCalled': False, 'hostQualified': False}
    with (Path(root) / 'lab/runtime-preparation.json').open('x') as stream:
        json.dump(receipt, stream, indent=2)
    return receipt
