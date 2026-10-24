#!/usr/bin/env python3
"""Release maintainer: snapshot Lab source, preserving reviewed distribution patches."""
import argparse
import hashlib
import json
from pathlib import Path
from prepare_premiere_runtime import REQUIRED_HELPERS


def package(source, root):
    dest = root / 'integrations/premiere-agent'
    override_path = root / 'integrations/premiere-distribution-overrides.json'
    overrides = json.loads(override_path.read_text())
    old = {row['path']: row for row in overrides['files']}
    entries, changes, prepared = [], [], []
    names = ['src', 'cep-plugin', 'uxp-plugin', 'registry', 'package.json',
             'package-lock.json', 'tsconfig.json', 'LICENSE', 'scripts/lab-prepare.mjs']
    names += ['scripts/' + name for name in REQUIRED_HELPERS]
    for name in names:
        base = source / name
        if not base.exists():
            raise RuntimeError('Missing required Premiere source: ' + name)
        for file in sorted([base] if base.is_file() else base.rglob('*')):
            rel = file.relative_to(source)
            if not file.is_file() or any(part in ['node_modules', '.git', 'runtime', 'artifacts'] for part in rel.parts):
                continue
            if file.suffix not in ['.ts', '.js', '.mjs', '.cjs', '.json', '.html', '.css', '.xml', '.jsx', '.md', '.txt', '.svg', '.map', '.py'] and file.name != 'LICENSE':
                continue
            raw = file.read_bytes()
            sha = hashlib.sha256(raw).hexdigest()
            data = raw
            key = rel.as_posix()
            if key in old:
                prior = old[key]
                existing = dest / rel
                if sha != prior['originalSourceSha256'] or hashlib.sha256(existing.read_bytes()).hexdigest() != prior['distributionSha256']:
                    raise RuntimeError('Premiere distribution patch needs review: ' + key)
                data = existing.read_bytes()
            elif file.name in REQUIRED_HELPERS:
                text = raw.decode().replace("Path.home()/'.agents/skills/edit/scripts'", 'skill_scripts()')
                if text != raw.decode():
                    data = ('from acq_edit_runtime import skill_scripts\n' + text).encode()
            entries.append({'path': key, 'sha256': sha})
            if data != raw:
                changes.append({'path': key, 'originalSourceSha256': sha,
                                'distributionSha256': hashlib.sha256(data).hexdigest()})
            prepared.append((dest / rel, data))
    if set(old) - {row['path'] for row in entries}:
        raise RuntimeError('Previously patched source disappeared; review required')
    # Validate the entire source set before changing the distribution.
    for target, data in prepared:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    manifest = {'upstream': 'https://github.com/leancoderkavy/premiere-pro-mcp', 'version': '1.18.6',
                'source': 'installed-premiere-agent-lab-snapshot', 'files': entries}
    (root / 'integrations/premiere-source-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    overrides['files'] = changes
    override_path.write_text(json.dumps(overrides, indent=2) + '\n')
    return {'files': len(entries)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(package(args.source, Path(__file__).resolve().parents[1])))
