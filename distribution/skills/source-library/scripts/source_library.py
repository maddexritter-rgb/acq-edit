#!/usr/bin/env python3
"""Discover and query an independent transcript collection; emit structured JSON."""
import argparse,json,pathlib,subprocess,sys
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--collection');a,remaining=p.parse_known_args()
registry=pathlib.Path.home()/'Documents'/'ACQ_Source_Library'/'catalog.json'
catalog=json.loads(registry.read_text());collections=catalog['collections']
if not a.collection:
 print(json.dumps({'collections':collections},indent=2));raise SystemExit(0)
if a.collection not in collections:p.error('Unknown collection; run without --collection to list available collections')
client=pathlib.Path(collections[a.collection]['client'])
raise SystemExit(subprocess.call([sys.executable,str(client),*(remaining or ['status'])]))
