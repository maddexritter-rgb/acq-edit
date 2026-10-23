#!/usr/bin/env python3
"""Search the pinned Premiere inventory without connecting to or mutating Premiere."""
import argparse
import json
from pathlib import Path


def search(catalog, query='', backend=None, host_tested=False):
    words = query.casefold().split()
    return [row for row in catalog['operations']
            if all(word in (row['name'] + ' ' + row.get('description', '')).casefold() for word in words)
            and (backend is None or backend in row.get('backends', []))
            and (not host_tested or row.get('hostTest') == 'postcondition_passed')]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog', type=Path, default=Path(__file__).resolve().parents[1] / 'references/premiere_capabilities.json')
    parser.add_argument('--query', default='')
    parser.add_argument('--operation', help='Return one exact operation including its full schema and evidence')
    parser.add_argument('--backend', choices=['cep', 'extendscript', 'uxp', 'qe', 'local'])
    parser.add_argument('--host-tested', action='store_true', help='Filter to fixture-scoped passed postconditions, not blanket production acceptance')
    parser.add_argument('--limit', type=int, default=20)
    args = parser.parse_args()
    if args.limit < 1 or args.limit > 500:
        parser.error('--limit must be between 1 and 500')
    data = json.loads(args.catalog.read_text())
    if data.get('schema') != 'premiere-agent-lab/catalog-v1':
        parser.error('Unsupported catalog schema')
    result = {'catalog_path': str(args.catalog.resolve()), 'generated_at': data['generatedAt'],
              'target_host': data['targetHost'], 'upstream_commit': data['upstreamCommit'],
              'boundary': 'Pinned inventory snapshot. No live host check or execution. Evidence applies only to its recorded fixture scope.',
              'counts': data['counts']}
    if args.operation:
        rows = [row for row in data['operations'] if row['name'] == args.operation]
        if not rows:
            parser.error('Operation absent from this inventory: ' + args.operation)
        result['operation'] = rows[0]
    else:
        rows = search(data, args.query, args.backend, args.host_tested)
        result['matched'] = len(rows)
        keys = ['name', 'description', 'backends', 'status', 'minimumPremiereVersion',
                'targetVersionEligible', 'authorityPermitted', 'labMutationPolicy',
                'hostTest', 'persistenceTest', 'visualTest', 'limitation']
        result['operations'] = [{key: row.get(key) for key in keys} for row in rows[:args.limit]]
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
