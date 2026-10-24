#!/usr/bin/env python3
"""Inventory explicit packaged skill routes; refuse unknown missing dependencies."""
import argparse
import hashlib
import json
import re
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = 'distribution/SKILL_DEPENDENCIES.json'
POLICY = 'scripts/skill-dependency-policy.json'
PATTERNS = [
    r'__ACQ_SKILLS__/([a-z_][a-z0-9_-]*)/',
    r'\.\./([a-z][a-z0-9-]*)/SKILL\.md',
    r'Use skill:\s*[`\[]?([a-z][a-z0-9-]*)',
]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def inventory(root):
    root = Path(root)
    raw = (root/'distribution/SOURCE_MANIFEST.json').read_bytes()
    manifest = json.loads(raw)
    owners = manifest['owners']
    if len(set(owners)) != len(owners):
        raise ValueError('Duplicate skill owner')
    files = {entry['path']: entry for entry in manifest['files']}
    if len(files) != len(manifest['files']):
        raise ValueError('Duplicate source manifest path')
    entrypoints = {str(PurePosixPath(name).parent) for name in files if len(PurePosixPath(name).parts)==2 and name.endswith('/SKILL.md')}
    if set(owners) != entrypoints or any(not re.fullmatch(r'[a-z][a-z0-9-]*',owner) for owner in owners):
        raise ValueError('Skill owners and packaged entrypoints differ')
    for owner in owners:
        if owner+'/SKILL.md' not in files:
            raise ValueError('Packaged skill entrypoint is missing: '+owner)
    policy_raw = (root/POLICY).read_bytes()
    policy = json.loads(policy_raw)
    exceptions = {}
    for item in policy['externalRoutes']:
        key = (item['source'], item['target'])
        if key in exceptions or item['status'] not in {'external-opt-in','unavailable-optional','historical-only'} or not item['reason'].strip():
            raise ValueError('Invalid or duplicate external route classification')
        exceptions[key] = item
    used, edges = set(), []
    for name, entry in sorted(files.items()):
        relative = PurePosixPath(name)
        if relative.is_absolute() or '..' in relative.parts or str(relative) != name:
            raise ValueError('Invalid manifest path: '+name)
        path = root/'distribution/skills'/name
        if not path.resolve().is_relative_to((root/'distribution/skills').resolve()):
            raise ValueError('Skill path escapes distribution: '+name)
        data = path.read_bytes()
        if digest(data) != entry['distribution_sha256']:
            raise ValueError('Skill hash differs: '+name)
        matches = {}
        for number, line in enumerate(data.decode().splitlines(), 1):
            targets = {target for pattern in PATTERNS for target in re.findall(pattern,line)}
            for target in targets:
                if target == relative.parts[0] or target == '_shared':
                    continue
                matches.setdefault(target, []).append(number)
        for target, lines in sorted(matches.items()):
            edge = {'source':name, 'target':target, 'lines':lines, 'sourceSha256':digest(data)}
            if target in owners:
                edge['status'] = 'packaged'
            else:
                key = (name,target)
                if key not in exceptions:
                    raise ValueError(f'Unclassified missing skill dependency: {name} -> {target}')
                used.add(key);edge.update({k:exceptions[key][k] for k in ('status','reason')})
            edges.append(edge)
    if used != set(exceptions):
        raise ValueError('Stale external route classification: '+str(sorted(set(exceptions)-used)))
    return {'schema':'acq-edit/skill-dependencies-v1','manifestSha256':digest(raw),
            'policySha256':digest(policy_raw),'owners':owners,'edges':edges}


def verify(root):
    expected = inventory(root)
    path = Path(root)/INVENTORY
    raw = path.read_bytes()
    if json.loads(raw) != expected:
        raise ValueError('Skill dependency inventory is stale; regenerate from reviewed sources and policy')
    external = [edge for edge in expected['edges'] if edge['status']!='packaged']
    return {'sha256':digest(raw),'packagedOwners':len(expected['owners']),
            'explicitRoutes':len(expected['edges']),'externalRoutes':external}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--write',action='store_true',help='Generate the inventory after reviewing missing routes')
    args=parser.parse_args()
    if args.write:
        result=inventory(args.root)
        (args.root/INVENTORY).write_text(json.dumps(result,indent=2)+'\n')
    result=verify(args.root)
    print(json.dumps({'packagedOwners':result['packagedOwners'],'explicitRoutes':result['explicitRoutes'],
                      'externalRoutes':len(result['externalRoutes']),'sha256':result['sha256']},indent=2))


if __name__=='__main__':
    main()
