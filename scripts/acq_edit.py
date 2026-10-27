#!/usr/bin/env python3
"""Homebrew entrypoint. Mutable integrations belong to the signed-in user, not the keg."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

PACKAGE = Path(__file__).resolve().parents[1]

def user_runtime(package=PACKAGE, home=None):
    home = Path(home or Path.home())
    release = json.loads((package / 'release.json').read_text())
    version = release['version']
    if not version or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-' for c in version):
        raise ValueError('Invalid release version')
    parent = home / 'Library/Application Support/ACQ Edit/versions'
    target = parent / version
    marker = target / '.package-sha256'
    fingerprint = hashlib.sha256((package / 'release.json').read_bytes() + ((package / '.release-source.json').read_bytes() if (package / '.release-source.json').exists() else b'')).hexdigest()
    if target.is_symlink() or parent.is_symlink():
        raise ValueError('Symlink installation refused')
    if target.exists():
        if not marker.is_file() or marker.read_text().strip() != fingerprint:
            raise ValueError('Existing runtime belongs to different package bytes; preserved')
        return target
    parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=version+'.install-', dir=parent))
    # Interrupted staging is retained; no destructive cleanup or takeover.
    for item in package.iterdir():
        if item.name in {'.git', '.local', '.agents', '.claude', 'node_modules', '__pycache__'}:
            continue
        if item.is_symlink():
            raise ValueError('Release source symlink refused')
        if item.is_dir():
            shutil.copytree(item, staging / item.name)
        else:
            shutil.copy2(item, staging / item.name)
    (staging / '.package-sha256').write_text(fingerprint+'\n')
    staging.rename(target)
    return target

def main():
    args = sys.argv[1:]
    if args == ['version']:
        print(json.loads((PACKAGE / 'release.json').read_text())['version']); return
    root = user_runtime()
    if args and args[0] == 'onboard':
        command = [sys.executable, str(root/'scripts/onboard.py'), *args[1:]]
    elif args and args[0] == 'skills':
        command = [sys.executable, str(root/'scripts/agent_skills.py'), *args[1:]]
    elif args and args[0] == 'delivery':
        mapping = {'credentials':'connect.py', 'check':'connect.py', 'login':'setup_frameio_oauth.py'}
        action = args[1] if len(args)>1 else 'help'
        if action not in mapping:
            raise ValueError('Use delivery credentials, login or check; see docs/ONBOARDING.md for routes')
        command = [sys.executable, str(root/'distribution/skills/monday/scripts'/mapping[action])]
        if action in {'credentials','check'}: command.append(action)
    else:
        if not (root/'dist/cli.js').is_file():
            raise ValueError('Run acq-edit onboard guide for guided setup, or acq-edit onboard filmcraft codex (or premiere / claude) first')
        command = ['node', str(root/'dist/cli.js'), *args]
    os.chdir(root)
    os.execvp(command[0], command)

if __name__ == '__main__':
    try: main()
    except (ValueError, OSError, KeyError) as e:
        print('ACQ Edit: '+str(e), file=sys.stderr); sys.exit(1)
