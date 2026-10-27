#!/usr/bin/env python3
"""Register verified toolkit skills in agent discovery folders without replacing user skills."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile

from materialize import materialize, verify, RECEIPT

ROOT = Path(__file__).resolve().parents[1]
AGENTS = {'codex': '.agents', 'claude': '.claude'}
PUBLIC_SKILLS = tuple(json.loads((ROOT/'scripts/public-skills.json').read_text()))


def catalog(root):
    manifest = json.loads((root / 'distribution/SOURCE_MANIFEST.json').read_text())
    result = {}
    for entry in manifest['files']:
        parts = Path(entry['path']).parts
        if len(parts) != 2 or parts[1] != 'SKILL.md':
            continue
        name = parts[0]
        if not re.fullmatch('[a-z][a-z0-9-]*', name):
            raise ValueError('Invalid skill name')
        data = (root / 'distribution/skills' / name / 'SKILL.md').read_bytes()
        if hashlib.sha256(data).hexdigest() != entry['distribution_sha256']:
            raise ValueError('Changed packaged skill: ' + name)
        text = data.decode()
        if not re.search(r'^name:\s*[\'"]?' + re.escape(name) + r'[\'"]?\s*$', text, re.M):
            raise ValueError('Skill metadata name differs: ' + name)
        result[name] = root / '.local/skills' / name
    if not result:
        raise ValueError('No packaged skills found')
    return result


def safe_directories(path):
    for item in (path, *path.parents):
        if item.is_symlink():
            raise ValueError('Symlink discovery parent preserved: ' + str(item))
        if item.exists() and not item.is_dir():
            raise ValueError('Non-directory discovery parent preserved: ' + str(item))


def locations(root, agent, scope, home):
    base = home if scope == 'user' else root
    parent = base / AGENTS[agent]
    return parent / 'skills', parent / 'acq-edit-skills.json'


def read_receipt(path):
    if path.is_symlink():
        raise ValueError('Symlink discovery receipt preserved')
    if not path.exists():
        return {'schema': 'acq-edit/skill-discovery-v1', 'links': {}}
    receipt = json.loads(path.read_text())
    if receipt.get('schema') != 'acq-edit/skill-discovery-v1' or not isinstance(receipt.get('links'), dict):
        raise ValueError('Unrecognized discovery receipt preserved')
    for name, entry in receipt['links'].items():
        if not re.fullmatch('[a-z][a-z0-9-]*', name) or not isinstance(entry, dict):
            raise ValueError('Invalid discovery ownership record; preserved')
    return receipt


def save_receipt(path, receipt):
    fd, temp = tempfile.mkstemp(prefix='.acq-discovery-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(receipt, stream, indent=2)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def selected(root, only):
    skills = catalog(root)
    names = sorted(set(only or PUBLIC_SKILLS))
    internal = set(names) - set(PUBLIC_SKILLS)
    if internal:
        raise ValueError('Not a public picker skill: ' + ', '.join(sorted(internal)))
    unknown = set(names) - skills.keys()
    if unknown:
        raise ValueError('Unknown skill(s): ' + ', '.join(sorted(unknown)))
    return {name: skills[name] for name in names}


def extra_links(folder, receipt):
    removable, preserved = [], []
    for name, entry in receipt['links'].items():
        if name in PUBLIC_SKILLS:
            continue
        link = folder/name
        expected = str(Path(entry.get('toolkit', ''))/'.local/skills'/name)
        if (link.is_symlink() and entry.get('target') == expected
                and Path(entry.get('toolkit', '')).is_absolute()
                and os.readlink(link) == expected):
            removable.append(name)
        elif link.exists() or link.is_symlink():
            preserved.append(name)
    return removable, preserved


def register(root, agent, scope='workspace', only=None, home=None, update_owned=False):
    root = Path(root).absolute()
    home = Path(home or Path.home()).absolute()
    skills = selected(root, only)
    verify(root)  # Never expose raw distribution placeholders or changed runtime helpers.
    folder, receipt_path = locations(root, agent, scope, home)
    safe_directories(folder)
    folder.mkdir(parents=True, exist_ok=True)
    lock = receipt_path.with_suffix('.lock')
    fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(str(os.getpid()))
        receipt = read_receipt(receipt_path)
        extras, preserved = extra_links(folder, receipt)
        operations = []
        conflicts = []
        for name, target in skills.items():
            link = folder / name
            if link.is_symlink() and os.readlink(link) == str(target):
                operations.append((name, link, target, False))
            elif link.is_symlink() or link.exists():
                old = receipt['links'].get(name, {})
                owned = link.is_symlink() and old.get('target') == os.readlink(link)
                if owned and update_owned:
                    operations.append((name, link, target, True))
                else:
                    conflicts.append(name + (' (owned older release; use --update-owned)' if owned else ' (existing user skill; preserved)'))
            else:
                operations.append((name, link, target, False))
        if conflicts:
            raise ValueError('Skill registration conflicts: ' + '; '.join(conflicts))
        for name, link, target, replace in operations:
            if replace:
                # Only replace a link still matching our receipt; never its target directory.
                if not link.is_symlink() or os.readlink(link) != receipt['links'][name]['target']:
                    raise ValueError('Discovery link changed during registration; preserved')
                temporary = folder / ('.acq-' + name + '-' + os.urandom(8).hex())
                temporary.symlink_to(target, target_is_directory=True)
                os.replace(temporary, link)
            elif not link.is_symlink():
                link.symlink_to(target, target_is_directory=True)
            receipt['links'][name] = {'target': str(target), 'toolkit': str(root)}
            save_receipt(receipt_path, receipt)
        # Remove only discovery aliases still owned by an older toolkit registration.
        # Supporting runtime folders and user-authored skills remain intact.
        for name in extras:
            link = folder/name
            if not link.is_symlink() or os.readlink(link) != receipt['links'][name]['target']:
                raise ValueError('Extra discovery link changed; preserved: ' + name)
            link.unlink()
            del receipt['links'][name]
            save_receipt(receipt_path, receipt)
        return {'ready': True, 'agent': agent, 'scope': scope, 'folder': str(folder), 'skills': list(skills),
                'removedInternalEntries': extras, 'preservedModifiedEntries': preserved,
                'qualification': 'Discovery links verified; reopen the agent session to refresh its skill picker. Native editing prerequisites are separate.'}
    finally:
        lock.unlink()


def status(root, agent, scope='workspace', only=None, home=None):
    root = Path(root).absolute()
    folder, receipt_path = locations(root, agent, scope, Path(home or Path.home()).absolute())
    safe_directories(folder)
    runtime_error = None
    try:
        verify(root)
    except (ValueError, RuntimeError, OSError, KeyError):
        runtime_error = 'Run skills install to prepare a verified runtime; preserve any changed installation.'
    states = []
    for name, target in selected(root, only).items():
        link = folder / name
        state = ('registered' if link.is_symlink() and os.readlink(link) == str(target) and (link / 'SKILL.md').is_file()
                 else 'conflict' if link.exists() or link.is_symlink() else 'missing')
        states.append({'name': name, 'state': state})
    extras, preserved = extra_links(folder, read_receipt(receipt_path))
    return {'ready': runtime_error is None and not extras and all(s['state'] == 'registered' for s in states),
            'extraRegisteredSkills': extras, 'preservedModifiedEntries': preserved,
            'agent': agent, 'scope': scope, 'folder': str(folder), 'runtimeRepair': runtime_error, 'skills': states}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['list', 'install', 'check'])
    parser.add_argument('--agent', choices=['codex', 'claude', 'both'], default='both')
    parser.add_argument('--scope', choices=['workspace', 'user'], default='workspace')
    parser.add_argument('--only', nargs='+')
    parser.add_argument('--assets', type=Path, help='Existing custom asset root; otherwise use this release bundle location')
    parser.add_argument('--update-owned', action='store_true', help='Retarget only links owned by a prior ACQ Edit registration')
    args = parser.parse_args()
    skills = selected(ROOT, args.only)
    if args.action == 'list':
        print(json.dumps({'skills': list(skills), 'guide': str(ROOT / 'docs/SKILLS.md')}, indent=2)); return
    if args.action == 'install':
        receipt = ROOT / '.local/skills' / RECEIPT
        if receipt.exists():
            verify(ROOT)
        else:
            release = json.loads((ROOT / 'release.json').read_text())
            assets = args.assets or Path.home() / 'Library/Application Support/ACQ Edit/assets' / release['assets']['version']
            materialize(ROOT, assets)
    agents = list(AGENTS) if args.agent == 'both' else [args.agent]
    results = [register(ROOT, agent, args.scope, args.only, update_owned=args.update_owned) if args.action == 'install'
               else status(ROOT, agent, args.scope, args.only) for agent in agents]
    print(json.dumps(results, indent=2))
    if not all(result['ready'] for result in results):
        sys.exit(1)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, RuntimeError, OSError, KeyError) as error:
        print('ACQ Edit skill discovery: ' + str(error), file=sys.stderr)
        sys.exit(1)
