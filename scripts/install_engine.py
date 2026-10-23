#!/usr/bin/env python3
"""Preflight and install only the chosen integration in this checkout's .local tree."""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from materialize import materialize

ROOT = Path(__file__).resolve().parents[1]
PIN = '71438c627b5cbcfb550526c3971f4d0037733c5c'
RESOLVE = Path('/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Applications/ResolvePython')


def run(args, cwd=None):
    subprocess.run(args, cwd=cwd, check=True)


def output(args, cwd=None):
    return subprocess.check_output(args, cwd=cwd, text=True, stderr=subprocess.STDOUT).strip()


def preflight(backend):
    required = ['node', 'ffmpeg', 'ffprobe']
    if backend == 'filmcraft':
        required += ['git', 'cargo', 'rustc', 'pkg-config']
    elif backend == 'premiere':
        required += ['npm']
    tools = {name: shutil.which(name) for name in required}
    errors = ['Missing executable: ' + name for name, executable in tools.items() if not executable]
    if tools['node']:
        try:
            major = int(output([tools['node'], '--version']).lstrip('v').split('.')[0])
            if major < 24:
                errors.append('Node.js 24 or later is required')
        except (ValueError, subprocess.SubprocessError):
            errors.append('Cannot determine Node.js version')
    if backend == 'filmcraft' and tools.get('rustc'):
        try:
            match = re.search(r'rustc (\d+)\.(\d+)', output([tools['rustc'], '--version']))
            if not match or tuple(map(int, match.groups())) < (1, 95):
                errors.append('FilmCraft requires Rust 1.95 or later')
        except subprocess.SubprocessError:
            errors.append('Cannot determine Rust version')
    if backend == 'resolve' and not RESOLVE.is_file():
        errors.append('Install DaVinci Resolve Studio 21.1; bundled ResolvePython was not found')
    return {'backend': backend, 'prerequisitesPresent': not errors, 'executables': tools,
            'errors': errors, 'nativeWorkflowQualified': False}


def install(backend, assets):
    check = preflight(backend)
    if check['errors']:
        raise RuntimeError('\n'.join(check['errors']))
    local = ROOT / '.local'
    if local.is_symlink():
        raise RuntimeError('Symlink .local root refused')
    local.mkdir(exist_ok=True)
    fd = os.open(local / 'engine-install.lock', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump({'pid': os.getpid(), 'backend': backend}, stream)
        dest = local / ('filmcraft' if backend == 'filmcraft' else 'premiere-agent')
        if backend != 'resolve' and dest.is_symlink():
            raise RuntimeError('Symlink engine destination refused; preserved.')
        if backend == 'premiere' and dest.exists():
            raise RuntimeError('Existing toolkit Lab installation preserved. Use a fresh checkout for upgrade.')
        if backend == 'premiere' and ((local / 'premiere-profile.json').exists() or (local / 'premiere-profile.json').is_symlink()):
            raise RuntimeError('Existing toolkit Premiere profile preserved. Use a fresh checkout for upgrade.')
        if backend == 'filmcraft' and dest.exists():
            if dest.is_symlink() or not (dest / '.git').is_dir():
                raise RuntimeError('Existing FilmCraft path is not an isolated checkout; preserved.')
            if output(['git', 'status', '--porcelain', '--untracked-files=all'], dest):
                raise RuntimeError('Existing FilmCraft checkout has local changes; preserved.')
            if output(['git', 'rev-parse', 'HEAD'], dest) != PIN:
                raise RuntimeError('Existing FilmCraft checkout is not at the required pin; preserved. Use a fresh checkout.')
            if output(['git', 'remote', 'get-url', 'origin'], dest) != 'https://github.com/storytold/filmcraft.git':
                raise RuntimeError('Unexpected FilmCraft origin; preserved.')
        assets.mkdir(parents=True, exist_ok=True)
        materialize(ROOT, assets)
        if backend == 'filmcraft':
            if not dest.exists():
                run(['git', 'clone', '--filter=blob:none', '--no-checkout', 'https://github.com/storytold/filmcraft.git', str(dest)])
                run(['git', 'fetch', 'origin', PIN], dest)
                run(['git', 'checkout', '--detach', PIN], dest)
            run(['cargo', 'build', '--release', '--locked', '-p', 'filmcraft-cli'], dest)
            print('FilmCraft CLI: ' + str(dest / 'target/release/filmcraft-cli'))
        elif backend == 'premiere':
            shutil.copytree(ROOT / 'integrations/premiere-agent', dest)
            run(['npm', 'ci', '--ignore-scripts'], dest)
            # Invoke the installed compiler directly; npx must not fetch another version.
            run([str(dest / 'node_modules/.bin/tsc')], dest)
            (dest / 'lab').mkdir(exist_ok=True)
            (dest / 'lab/node-path.txt').write_text(check['executables']['node'] + '\n')
            run(['node', 'scripts/lab-prepare.mjs'], dest)
            profile = {'schema': 'edit.premiere-bridge-profile/v1',
                       'command': [check['executables']['node'], str(local / 'skills/assembly-design/scripts/precision_bridge.mjs'), str(dest)],
                       'cwd': str(dest), 'fixture_root': str(dest / 'lab/runtime/fixtures'),
                       'connector': 'premiere-agent-lab', 'host_version': '26.3.0', 'mode': 'scoped-edit',
                       'project_authorization': str(dest / 'lab/runtime/edit-authorization.json')}
            target = local / 'premiere-profile.json'
            with target.open('x') as stream:
                json.dump(profile, stream, indent=2)
            target.chmod(0o600)
            print('Prepared isolated panel: ' + str(dest / 'lab/packages/PremiereAgentLabCEP'))
            print('Profile: ' + str(target))
            print('Panel not installed into Adobe automatically. Follow docs/ENGINES.md.')
        else:
            print('Resolve integration prepared. Start Studio and enable External scripting: Local, then run doctor.')
        print('Installation is not native workflow acceptance. See docs/ACCEPTANCE.md.')
    finally:
        (local / 'engine-install.lock').unlink()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('backend', choices=['filmcraft', 'premiere', 'resolve'])
    parser.add_argument('--assets', type=Path, default=Path.home() / 'Movies/ACQ Edit Assets')
    parser.add_argument('--check', action='store_true', help='Read-only selected-engine prerequisite check')
    args = parser.parse_args()
    if args.check:
        result = preflight(args.backend)
        print(json.dumps(result, indent=2))
        return 0 if result['prerequisitesPresent'] else 1
    install(args.backend, args.assets)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (RuntimeError, OSError, subprocess.SubprocessError) as error:
        print('Installation stopped: ' + str(error), file=sys.stderr)
        sys.exit(1)
