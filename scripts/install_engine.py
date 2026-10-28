#!/usr/bin/env python3
"""Preflight and install only the chosen integration in this checkout's .local tree."""
import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
from materialize import materialize
import filmcraft_runtime
from prepare_premiere_panel import prepare as prepare_premiere_panel
from prepare_premiere_runtime import copy_resources, check_transport, prepare_helpers
from premiere_compatibility import select_host, bind_host

ROOT = Path(__file__).resolve().parents[1]
PIN = '71438c627b5cbcfb550526c3971f4d0037733c5c'
RESOLVE = Path('/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Applications/ResolvePython')


def digest(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()


def run(args, cwd=None):
    subprocess.run(args, cwd=cwd, check=True)


def output(args, cwd=None):
    return subprocess.check_output(args, cwd=cwd, text=True, stderr=subprocess.STDOUT).strip()


def media_tool_ready(executable, name):
    try:
        probe = subprocess.run([executable, '-version'], capture_output=True, text=True, timeout=15)
        return probe.returncode == 0 and probe.stdout.startswith(name + ' version ')
    except (OSError, subprocess.SubprocessError):
        return False


def preflight(backend, source_build=False):
    required = ['node', 'ffmpeg', 'ffprobe']
    if backend == 'filmcraft' and source_build:
        required += ['git', 'cargo', 'rustc']
        required += ['xcrun'] if sys.platform == 'darwin' else ['pkg-config']
    elif backend == 'premiere':
        required += ['npm']
    tools = {name: shutil.which(name) for name in required}
    errors = ['Missing executable: ' + name for name, executable in tools.items() if not executable]
    for name in ('ffmpeg', 'ffprobe'):
        if tools[name]:
            if not media_tool_ready(tools[name],name):
                errors.append(name + ' exists but cannot run. Repair its current installation and shared libraries, then retry; ACQ Edit will not replace another tap automatically.')
    if backend == 'filmcraft' and not source_build:
        try:
            _,spec=filmcraft_runtime.specification(ROOT)
            problem=filmcraft_runtime.compatibility(spec)
            if problem:errors.append(problem)
        except (ValueError,OSError,KeyError) as e:errors.append(str(e))
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
    premiere_host=None
    if backend=='premiere':
        try:premiere_host=select_host()
        except RuntimeError as error:errors.append(str(error))
    native_build = {}
    if backend == 'filmcraft' and sys.platform == 'darwin' and tools.get('xcrun'):
        try:
            native_build = {'clang': output([tools['xcrun'], '--find', 'clang']),
                            'sdk': output([tools['xcrun'], '--show-sdk-path'])}
            if not Path(native_build['clang']).is_file() or not Path(native_build['sdk']).is_dir():
                errors.append('Xcode Command Line Tools compiler or macOS SDK is unavailable')
        except subprocess.SubprocessError:
            errors.append('Install or select Xcode Command Line Tools; xcrun could not locate the compiler and macOS SDK')
    return {'backend': backend, 'prerequisitesPresent': not errors, 'executables': tools, 'nativeBuildTools': native_build,
            'premiereHost': premiere_host, 'errors': errors, 'nativeWorkflowQualified': False, 'installMode': 'source' if source_build else 'prebuilt' if backend=='filmcraft' else 'native-integration'}


def record_filmcraft_build(dest, check):
    """Record actual inputs/output after a clean, pinned, locked source build."""
    if output(['git', 'rev-parse', 'HEAD'], dest) != PIN or output(['git', 'status', '--porcelain', '--untracked-files=all'], dest):
        raise RuntimeError('FilmCraft sources changed during build; no successful build receipt written')
    binary = dest / 'target/release/filmcraft-cli'
    if not binary.is_file():
        raise RuntimeError('FilmCraft build did not produce the expected native executable')
    help_output = output([str(binary), '--help'], dest)
    receipt = {
        'schema': 'acq-edit/filmcraft-build-v1',
        'createdAt': datetime.now(timezone.utc).isoformat(),
        'source': {'origin': output(['git', 'remote', 'get-url', 'origin'], dest), 'commit': PIN,
                   'cargoLockSha256': digest(dest / 'Cargo.lock'), 'cargoManifestSha256': digest(dest / 'Cargo.toml')},
        'command': ['cargo', 'build', '--release', '--locked', '-p', 'filmcraft-cli'],
        'compiler': output([check['executables']['rustc'], '-vV']),
        'cargo': output([check['executables']['cargo'], '--version']),
        'nativeBuildTools': check.get('nativeBuildTools', {}),
        'host': {'system': platform.system(), 'machine': platform.machine(), 'release': platform.release()},
        'buildEnvironment': {key: os.environ[key] for key in ['RUSTFLAGS', 'CARGO_ENCODED_RUSTFLAGS', 'CARGO_BUILD_TARGET',
                              'CARGO_BUILD_RUSTFLAGS', 'MACOSX_DEPLOYMENT_TARGET', 'SDKROOT', 'CRAFT_FONTS_DIR', 'CRAFT_FONTS_REQUIRED'] if key in os.environ},
        'binary': {'path': str(binary.resolve()), 'sha256': digest(binary), 'bytes': binary.stat().st_size,
                   'helpSha256': hashlib.sha256(help_output.encode()).hexdigest()},
        'installerSha256': digest(Path(__file__)), 'nativeWorkflowQualified': False,
    }
    directory = ROOT / '.local/filmcraft-builds'
    directory.mkdir(exist_ok=True)
    target = directory / (str(uuid.uuid4()) + '.json')
    with target.open('x') as stream:
        json.dump(receipt, stream, indent=2)
    print('FilmCraft build receipt: ' + str(target))
    return target


def install(backend, assets, premiere_port=17878, source_build=False):
    from runtime_environment import execution_environment
    os.environ.update(execution_environment())
    check = preflight(backend, source_build)
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
        if backend == 'filmcraft' and source_build and dest.exists():
            if dest.is_symlink() or not (dest / '.git').is_dir():
                raise RuntimeError('Existing FilmCraft path is not an isolated checkout; preserved.')
            if output(['git', 'status', '--porcelain', '--untracked-files=all'], dest):
                raise RuntimeError('Existing FilmCraft checkout has local changes; preserved.')
            if output(['git', 'rev-parse', 'HEAD'], dest) != PIN:
                raise RuntimeError('Existing FilmCraft checkout is not at the required pin; preserved. Use a fresh checkout.')
            if output(['git', 'remote', 'get-url', 'origin'], dest) != 'https://github.com/storytold/filmcraft.git':
                raise RuntimeError('Unexpected FilmCraft origin; preserved.')
        if backend == 'filmcraft' and not source_build and dest.exists():
            if (dest/'.git').exists():raise RuntimeError('Existing source checkout preserved; explicitly use --source-build to continue it')
            _,spec=filmcraft_runtime.specification(ROOT)
            filmcraft_runtime.verify(dest,spec)
        assets.mkdir(parents=True, exist_ok=True)
        materialize(ROOT, assets)
        if backend == 'filmcraft' and not source_build:
            print('FilmCraft CLI: ' + str(filmcraft_runtime.install(ROOT)))
        elif backend == 'filmcraft':
            if not dest.exists():
                run(['git', 'clone', '--filter=blob:none', '--no-checkout', 'https://github.com/storytold/filmcraft.git', str(dest)])
                run(['git', 'fetch', 'origin', PIN], dest)
                run(['git', 'checkout', '--detach', PIN], dest)
            run(['cargo', 'build', '--release', '--locked', '-p', 'filmcraft-cli'], dest)
            record_filmcraft_build(dest, check)
            print('FilmCraft CLI: ' + str(dest / 'target/release/filmcraft-cli'))
        elif backend == 'premiere':
            host_version=bind_host(ROOT,check['premiereHost'])
            shutil.copytree(ROOT / 'integrations/premiere-agent', dest,
                            ignore=shutil.ignore_patterns('node_modules', 'dist', '__pycache__'))
            helper_hashes = prepare_helpers(dest, ROOT)
            run(['npm', 'ci', '--ignore-scripts'], dest)
            # Invoke the installed compiler directly; npx must not fetch another version.
            run([str(dest / 'node_modules/.bin/tsc')], dest)
            resource_hashes = copy_resources(dest)
            (dest / 'lab').mkdir(exist_ok=True)
            (dest / 'lab/node-path.txt').write_text(check['executables']['node'] + '\n')
            panel=prepare_premiere_panel(dest, check['executables']['node'], premiere_port)
            profile = {'schema': 'edit.premiere-bridge-profile/v1',
                       'command': [check['executables']['node'], str(local / 'skills/assembly-design/scripts/precision_bridge.mjs'), str(dest)],
                       'cwd': str(dest), 'fixture_root': str(dest / 'lab/runtime/fixtures'),
                       'connector': 'premiere-agent-lab', 'host_version': host_version, 'mode': 'scoped-edit',
                       'project_authorization': str(dest / 'lab/runtime/edit-project-authorization.json')}
            target = local / 'premiere-profile.json'
            with target.open('x') as stream:
                json.dump(profile, stream, indent=2)
            target.chmod(0o600)
            check_transport(dest, target, local / 'skills/edit/scripts/premiere_agent.py', resource_hashes, helper_hashes)
            print('Prepared isolated panel: ' + panel['cep'])
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
    parser.add_argument('--source-build', action='store_true', help='Explicit developer fallback requiring Rust and build tools; never selected automatically')
    parser.add_argument('--check', action='store_true', help='Read-only selected-engine prerequisite check')
    parser.add_argument('--premiere-port', type=int, default=17878, help='Dedicated ACQ Edit UXP port; never the production Lab port')
    args = parser.parse_args()
    if args.check:
        result = preflight(args.backend,args.source_build)
        print(json.dumps(result, indent=2))
        return 0 if result['prerequisitesPresent'] else 1
    install(args.backend, args.assets, args.premiere_port,args.source_build)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (RuntimeError, ValueError, OSError, subprocess.SubprocessError) as error:
        print('Installation stopped: ' + str(error), file=sys.stderr)
        sys.exit(1)
