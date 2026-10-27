"""Verify the selected checkout's isolated connector before starting any process."""
import json
import hashlib
from pathlib import Path
import sys


def verify_profile(config, toolkit):
    toolkit = Path(toolkit).absolute()
    local = toolkit / '.local'
    runtime = local / 'premiere-agent'
    profile_path = local / 'premiere-profile.json'
    # Do not read an arbitrary user-supplied profile, much less execute its command.
    if config.get('premiereProfile') != str(profile_path):
        raise RuntimeError('Configure this checkout\'s .local/premiere-profile.json; external and production profiles are refused')
    for target in (toolkit, local, runtime, profile_path, runtime / 'scripts', runtime / 'node_modules',
                   runtime / 'lab', runtime / 'lab/runtime', runtime / 'lab/packages', runtime / 'lab/node-path.txt',
                   runtime / 'lab/panel-preparation.json', runtime / 'lab/runtime/config.json'):
        if target.is_symlink():
            raise RuntimeError('Premiere installation path is redirected; preserved')
    profile = json.loads(profile_path.read_text())
    node = (runtime / 'lab/node-path.txt').read_text().strip()
    expected = {
        'schema': 'edit.premiere-bridge-profile/v1',
        'command': [node, str(local / 'skills/assembly-design/scripts/precision_bridge.mjs'), str(runtime)],
        'cwd': str(runtime), 'fixture_root': str(runtime / 'lab/runtime/fixtures'),
        'connector': 'premiere-agent-lab', 'host_version': '26.3.0', 'mode': 'scoped-edit',
        'project_authorization': str(runtime / 'lab/runtime/edit-project-authorization.json'),
    }
    if profile != expected or not Path(node).is_absolute() or not Path(node).is_file():
        raise RuntimeError('Premiere profile differs from the isolated installation; preserve it and use a fresh installation')
    panel = json.loads((runtime / 'lab/panel-preparation.json').read_text())
    settings = json.loads((runtime / 'lab/runtime/config.json').read_text())
    if (panel.get('runtime') != str(runtime / 'lab/runtime')
            or panel.get('mailbox') != str(runtime / 'lab/runtime/mailbox')
            or panel.get('cepId') != 'com.acqedit.premiere.bridge'
            or panel.get('uxpId') != 'com.acqedit.premiere.uxp'
            or type(settings.get('port')) is not int or not 1024 <= settings['port'] <= 65535
            or settings['port'] == 17877 or panel.get('port') != settings['port']):
        raise RuntimeError('Premiere panel isolation configuration differs; preserved')
    return profile


def verify(config, toolkit):
    toolkit = Path(toolkit).absolute()
    local = toolkit / '.local'
    runtime = local / 'premiere-agent'
    profile = verify_profile(config, toolkit)
    sys.path.insert(0, str(toolkit / 'scripts'))
    from materialize import verify as verify_skills
    from prepare_premiere_runtime import compiled_hashes, verify_helpers, REQUIRED_TOOLS
    skills = verify_skills(toolkit)
    helpers = verify_helpers(runtime, toolkit)
    receipt_path = runtime / 'lab/runtime-preparation.json'
    if receipt_path.is_symlink():
        raise RuntimeError('Premiere runtime receipt is redirected')
    receipt = json.loads(receipt_path.read_text())
    if receipt.get('schema') != 'acq-edit/premiere-runtime-v2':
        raise RuntimeError('Premiere runtime predates compiled-code verification; preserved. Use a fresh checkout installation')
    if (receipt.get('compiledHashes') != compiled_hashes(runtime) or receipt.get('helperHashes') != helpers
            or receipt.get('transportInitialized') is not True
            or not REQUIRED_TOOLS <= set(receipt.get('requiredTools', []))):
        raise RuntimeError('Premiere runtime differs from its installation receipt; preserved')
    # Never expose tokens or scope contents in doctor output.
    panel = json.loads((runtime / 'lab/panel-preparation.json').read_text())
    packages = runtime / 'lab/packages'
    hashes = {}
    for name in ('ACQEditAgentCEP', 'ACQEditAgentUXP'):
        folder = packages / name
        if folder.is_symlink() or not folder.is_dir():
            raise RuntimeError('Prepared Premiere panel is missing or redirected')
        for file in sorted(folder.rglob('*')):
            if file.is_symlink():
                raise RuntimeError('Prepared Premiere panel contains a redirected entry')
            if file.is_file():
                hashes[file.relative_to(packages).as_posix()] = hashlib.sha256(file.read_bytes()).hexdigest()
    if not hashes or hashes != panel.get('packageHashes'):
        raise RuntimeError('Prepared Premiere panel changed; preserved')
    return {'verified': True, 'skillFiles': skills['verifiedFiles'], 'helperFiles': len(helpers),
            'compiledFiles': len(receipt['compiledHashes']), 'panelFiles': len(hashes), 'port': panel['port'],
            'hostQualified': False}
