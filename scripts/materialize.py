#!/usr/bin/env python3
"""Verify and materialize a checkout-local skill runtime without overwriting work."""
import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
HEADER = '''\n## ACQ Edit distribution execution contract\nRead the toolkit docs/AGENT_WORKFLOW.md before executing. The project backend is immutable.\nUse the local toolkit project paths and credentials; never use personal workstation paths.\nResolve routes to python/resolve.py; Premiere to scoped Agent Lab; FilmCraft to its headless adapter.\nUnresolved __ACQ_ markers indicate unavailable optional dependencies; report them explicitly.\nNo delivery to external accounts is implied. The review room publishes only local immutable versions.\n'''
RECEIPT = '.acq-materialization.json'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def no_symlinks(base, relative):
    current = base
    if current.is_symlink():
        raise RuntimeError('Symlink runtime/distribution root refused')
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise RuntimeError('Symlink runtime/distribution entry refused: ' + str(relative))
    return current


def prepare(root, assets):
    source_root = root / 'distribution/skills'
    dest = root / '.local/skills'
    raw_manifest = (root / 'distribution/SOURCE_MANIFEST.json').read_bytes()
    manifest = json.loads(raw_manifest)
    if manifest.get('schema') != 'acq-edit/source-manifest-v1':
        raise RuntimeError('Unsupported source manifest schema')
    files, blocked = {}, []
    for entry in manifest['files']:
        name = entry['path']
        relative = PurePosixPath(name)
        if (relative.is_absolute() or '..' in relative.parts or str(relative) != name
                or not relative.parts or '\\' in name or name == RECEIPT or name in files):
            raise RuntimeError('Invalid or duplicate manifest path: ' + name)
        data = no_symlinks(source_root, relative).read_bytes()
        if sha(data) != entry['distribution_sha256']:
            raise RuntimeError('Distribution hash mismatch: ' + name)
        content = data.decode().replace('__ACQ_SKILLS__', str(dest)).replace('__ACQ_ASSETS__', str(assets))
        if '__ACQ_LEGACY_HOME__' in content or '__ACQ_EXTERNAL_VOLUME__' in content:
            blocked.append(name)
        files[name] = content.encode()
    if 'edit/SKILL.md' not in files:
        raise RuntimeError('Manifest does not include the edit owner')
    files['edit/SKILL.md'] += HEADER.encode()
    receipt = {'schema': 'acq-edit/materialization-v1', 'manifestSha256': sha(raw_manifest),
               'runtime': str(dest), 'assets': str(assets), 'blockedReferences': blocked,
               'files': {name: sha(data) for name, data in files.items()}}
    return files, receipt


def verify_existing(dest, expected):
    receipt_path = no_symlinks(dest, PurePosixPath(RECEIPT))
    if not receipt_path.is_file():
        raise RuntimeError('Existing runtime has no installation receipt. Preserved; use a fresh checkout for installation.')
    actual = json.loads(receipt_path.read_text())
    if actual != expected:
        raise RuntimeError('Existing runtime uses a different distribution, location or asset root. Preserved; use a fresh checkout for upgrade.')
    found = set()
    for current, dirs, names in os.walk(dest, followlinks=False):
        for name in dirs + names:
            p = Path(current) / name
            if p.is_symlink():
                raise RuntimeError('Existing runtime contains a symlink; preserved.')
        for name in names:
            p = Path(current) / name
            rel = p.relative_to(dest).as_posix()
            # Python creates bytecode while executing helpers; it is not source.
            if '__pycache__' in p.relative_to(dest).parts and p.suffix == '.pyc':
                continue
            if rel == RECEIPT:
                continue
            found.add(rel)
            if rel not in expected['files'] or sha(p.read_bytes()) != expected['files'][rel]:
                raise RuntimeError('Existing runtime has a changed or extra file; preserved: ' + rel)
    if found != set(expected['files']):
        raise RuntimeError('Existing runtime is incomplete; preserved.')


def materialize(root, assets):
    root, assets = root.absolute(), assets.resolve()
    local, dest = root / '.local', root / '.local/skills'
    if local.is_symlink() or dest.is_symlink():
        raise RuntimeError('Symlink runtime root refused')
    # Validate every input before creating any runtime file.
    files, receipt = prepare(root, assets)
    local.mkdir(exist_ok=True)
    lock = local / 'materialize.lock'
    try:
        fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise RuntimeError('Materialization reservation exists. Inspect its PID and retained staging directories before manual reconciliation.') from None
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump({'pid': os.getpid(), 'runtime': str(dest)}, stream)
        if dest.exists():
            verify_existing(dest, receipt)
        else:
            # Staging is retained on failure for inspection; the live directory is atomic.
            stage = Path(tempfile.mkdtemp(prefix='skills-stage-', dir=local))
            for name, data in files.items():
                target = stage / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
            (stage / RECEIPT).write_text(json.dumps(receipt, indent=2) + '\n')
            if dest.exists() or dest.is_symlink():
                raise RuntimeError('Runtime appeared during installation; staged files retained.')
            stage.rename(dest)
        report = local / 'portability.json'
        if report.is_symlink():
            raise RuntimeError('Symlink portability report refused')
        fd, temporary = tempfile.mkstemp(prefix='portability-', suffix='.pending', dir=local)
        temp = Path(temporary)
        with os.fdopen(fd, 'w') as stream:
            json.dump({'blockedReferences': receipt['blockedReferences']}, stream, indent=2)
        temp.replace(report)
    finally:
        lock.unlink()
    return {'materializedFiles': len(files), 'runtime': str(dest),
            'receipt': str(dest / RECEIPT), 'unresolvedOptionalReferences': receipt['blockedReferences']}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--assets', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(materialize(ROOT, args.assets)))


if __name__ == '__main__':
    main()
