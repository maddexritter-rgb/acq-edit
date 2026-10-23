#!/usr/bin/env python3
"""Validate current independent reviews and reconciliation; not a semantic scorer."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'edit/scripts'))
from assembly_job import validate_job, native_packet


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--job', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    results = []
    try:
        job = validate_job(args.job)
        for cid in job['candidates']:
            try:
                packet = native_packet(args.job, cid)
                results.append({'clip_id': cid, 'status': 'EVIDENCE_VALID',
                                'statuses': packet['statuses'], 'errors': []})
            except (ValueError, KeyError, TypeError, OSError) as e:
                results.append({'clip_id': cid, 'status': 'BLOCK', 'errors': [str(e)]})
    except (ValueError, KeyError, TypeError, OSError) as e:
        results.append({'clip_id': None, 'status': 'BLOCK', 'errors': [str(e)]})
    blocked = any(r['status'] == 'BLOCK' for r in results)
    receipt = {'schema': 'assembly-design.final-editorial-gate/v2',
               'status': 'BLOCK' if blocked else 'EVIDENCE_VALID', 'clips': results,
               'scope': 'Validates recorded reviews and exact revisions; native and human acceptance pending.'}
    try:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open('x') as f:
            json.dump(receipt, f, indent=2); f.write('\n')
    except OSError as e:
        print(str(e), file=sys.stderr)
        return 2
    print(json.dumps(receipt, indent=2))
    return 2 if blocked else 0


if __name__ == '__main__':
    raise SystemExit(main())
