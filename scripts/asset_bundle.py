#!/usr/bin/env python3
"""Build/install a hash-verified, relocatable asset directory. Never infer licenses."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path, PurePosixPath

MUSIC = Path('content-skill-system/(1) Tik Tok')

def digest(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def safe(root, name):
    rel = PurePosixPath(name)
    if rel.is_absolute() or '..' in rel.parts or not rel.parts or str(rel) != name or '\\' in name:
        raise ValueError('Invalid asset path')
    p = root
    for part in rel.parts:
        p = p / part
        if p.is_symlink():
            raise ValueError('Symlink asset refused')
    return p

def verify(root):
    root = Path(root)
    if root.is_symlink():
        raise ValueError('Symlink bundle refused')
    manifest = json.loads((root / 'asset-bundle.json').read_text())
    if manifest.get('schema') != 'acq-edit/assets-v1' or not manifest.get('files'):
        raise ValueError('Invalid bundle manifest')
    for name, expected in manifest['files'].items():
        if digest(safe(root, name)) != expected:
            raise ValueError('Asset hash mismatch: ' + name)
    found = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and p != root / 'asset-bundle.json'}
    if found != set(manifest['files']):
        raise ValueError('Unmanifested or missing assets')
    return {'ready': True, 'version': manifest['version'], 'manifestSha256': digest(root / 'asset-bundle.json'),
            'files': len(found), 'distribution': manifest['distribution']}

def build(music, decisions, target, version, fonts=(), profiles=()):
    music, target = Path(music), Path(target)
    if target.exists():
        raise ValueError('Use a new bundle directory; existing assets are preserved')
    review = json.loads(Path(decisions).read_text())
    index = json.loads((music / '_music_index.json').read_text())
    semantic = json.loads((music / '_music_semantic_index.json').read_text())
    keep = [key for key, row in review.items() if row.get('decision') == 'keep' and key in index]
    if not keep:
        raise ValueError('No reviewed music available')
    # Missing catalog items stay explicitly unavailable, never eligible candidates.
    missing = [key for key in keep if not safe(music, key).is_file()]
    keep = [key for key in keep if key not in missing]
    if not keep:
        raise ValueError('No approved music files are present')
    target.mkdir(parents=True)
    dest = target / MUSIC
    dest.mkdir(parents=True)
    for key in keep:
        out = safe(dest, key)
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(safe(music, key), out)
    selected = {key: {**index[key], 'path': key} for key in keep}
    semantic['embeddings'] = {key: semantic['embeddings'][key] for key in keep if key in semantic['embeddings']}
    for name, data in [('_music_index.json', selected), ('_music_semantic_index.json', semantic),
                       ('music_review_decisions.json', {key: review[key] for key in keep})]:
        (dest / name).write_text(json.dumps(data, indent=2) + '\n')
    for name in ['_APPROVED.txt', 'MUSIC_BLACKLIST.txt', '_BLACKLIST.txt', 'MUSIC_RULES.md', '(3) ViralREELS/_vibe_tags.json']:
        if (music / name).is_file():
            (dest / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(music / name, dest / name)
    for folder, inputs in [('fonts', fonts), ('profiles', profiles)]:
        (target / folder).mkdir()
        for value in inputs:
            source = Path(value)
            output = target / folder / source.name
            if output.exists() or source.is_symlink() or not source.is_file():
                raise ValueError('Duplicate or invalid asset input')
            shutil.copyfile(source, output)
    manifest = {'schema': 'acq-edit/assets-v1', 'version': version,
                'distribution': 'local-evaluation-only; redistribution rights not established',
                'musicTracks': len(keep), 'unavailableMusic': missing, 'files': {p.relative_to(target).as_posix(): digest(p)
                for p in sorted(target.rglob('*')) if p.is_file()}}
    (target / 'asset-bundle.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return verify(target)

def install(source, target):
    proof = verify(source)
    target = Path(target)
    if target.exists():
        raise ValueError('Existing bundle preserved; choose a new version directory')
    shutil.copytree(source, target, symlinks=True)
    return verify(target)

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    s = p.add_subparsers(dest='command', required=True)
    b = s.add_parser('build-local'); b.add_argument('--music', required=True); b.add_argument('--decisions', required=True)
    b.add_argument('--target', required=True); b.add_argument('--version', required=True)
    b.add_argument('--font', action='append', default=[]); b.add_argument('--profile', action='append', default=[])
    v = s.add_parser('verify'); v.add_argument('root')
    v = s.add_parser('runtime-check'); v.add_argument('root')
    i = s.add_parser('install'); i.add_argument('source'); i.add_argument('target')
    a = p.parse_args()
    if a.command == 'runtime-check':
        a.root = json.loads((Path(a.root) / '.local/skills/.acq-materialization.json').read_text())['assets']
    print(json.dumps(build(a.music, a.decisions, a.target, a.version, a.font, a.profile) if a.command == 'build-local'
                     else install(a.source, a.target) if a.command == 'install' else verify(a.root)))
