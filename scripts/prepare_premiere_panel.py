"""Prepare a distinct ACQ Edit panel in a new private runtime; never install into Adobe."""
import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import xml.etree.ElementTree as ET

CEP_ID = 'com.acqedit.premiere.bridge'
UXP_ID = 'com.acqedit.premiere.uxp'
NAME = 'ACQ Edit Agent'


def prepare(root, node, port=17878):
    root = Path(root).resolve()
    if type(port) is not int or not 1024 <= port <= 65535 or port == 17877:
        raise RuntimeError('Use a distinct local port in 1024..65535; 17877 is reserved for the existing Agent Lab')
    runtime, packages = root / 'lab/runtime', root / 'lab/packages'
    if runtime.exists() or runtime.is_symlink() or packages.exists() or packages.is_symlink():
        raise RuntimeError('Existing panel/runtime preserved; prepare in a fresh toolkit installation')
    # Availability at preparation time is advisory; the server still owns the bind when launched.
    with socket.socket() as probe:
        try: probe.bind(('127.0.0.1', port))
        except OSError as error: raise RuntimeError('Selected toolkit panel port is already in use') from error
    runtime.mkdir(parents=True, mode=0o700)
    config_path = runtime / 'config.json'
    with os.fdopen(os.open(config_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as stream:
        json.dump({'schema': 'premiere-agent-lab/config-v1', 'token': secrets.token_hex(32), 'port': port}, stream)
    subprocess.run([node, 'scripts/lab-prepare.mjs'], cwd=root, check=True)
    replacements = {'com.premiereagent.lab.bridge': CEP_ID, 'com.premiereagent.lab.uxp': UXP_ID,
                    'Premiere Agent Lab': NAME, 'MCP for Adobe Premiere Pro': NAME,
                    'premiere_agent_lab_': 'acq_edit_agent_', 'premiere-agent-lab.bridge-session': 'acq-edit-agent.bridge-session'}
    for folder in [packages / 'PremiereAgentLabCEP', packages / 'PremiereAgentLabUXP']:
        for file in folder.rglob('*'):
            if file.is_file() and file.suffix in ['.js', '.cjs', '.html', '.xml', '.json']:
                text = file.read_text()
                for old, new in replacements.items(): text = text.replace(old, new)
                file.write_text(text)
    cep, uxp = packages / 'ACQEditAgentCEP', packages / 'ACQEditAgentUXP'
    (packages / 'PremiereAgentLabCEP').rename(cep)
    (packages / 'PremiereAgentLabUXP').rename(uxp)
    manifest = ET.parse(cep / 'CSXS/manifest.xml').getroot()
    ids = [node.attrib['Id'] for node in manifest.findall('.//Extension')]
    if manifest.attrib['ExtensionBundleId'] != CEP_ID or not ids or any(value != CEP_ID + '.panel' for value in ids):
        raise RuntimeError('Generated CEP identity differs; retain package for inspection')
    ux = json.loads((uxp / 'manifest.json').read_text())
    if ux['id'] != UXP_ID: raise RuntimeError('Generated UXP identity differs')
    mailbox = str(runtime / 'mailbox')
    if json.dumps(mailbox) not in (cep / 'main.js').read_text(): raise RuntimeError('CEP mailbox is not pinned to this runtime')
    if f'ws://127.0.0.1:{port}/lab-uxp' not in (uxp / 'index.cjs').read_text(): raise RuntimeError('UXP address differs from this runtime')
    # No secret token or private config bytes in the public-facing preparation receipt.
    receipt = {'schema': 'acq-edit/premiere-panel-v1', 'name': NAME, 'cepId': CEP_ID, 'uxpId': UXP_ID,
               'port': port, 'cep': str(cep), 'uxp': str(uxp), 'runtime': str(runtime), 'mailbox': mailbox,
               'installedIntoAdobe': False, 'hostQualified': False,
               'packageHashes': {str(file.relative_to(packages)): hashlib.sha256(file.read_bytes()).hexdigest()
                                 for folder in [cep, uxp] for file in sorted(folder.rglob('*')) if file.is_file()}}
    with (root / 'lab/panel-preparation.json').open('x') as stream: json.dump(receipt, stream, indent=2)
    return receipt
