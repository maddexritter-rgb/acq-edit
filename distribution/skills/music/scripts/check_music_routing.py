#!/usr/bin/env python3
"""Check or repair one owned prepared-copy track's direct master connection.

Only for offline prepared projects. Does not prove audibility or support submixes.
"""
import argparse, gzip, hashlib, json, sys, xml.etree.ElementTree as ET
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / '_shared'))
from premiere_graph_integrity import master_sources, connect_owned_track, validate_aliases

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project',type=Path,required=True);p.add_argument('--sequence-uid',required=True)
    p.add_argument('--track-uid',required=True);p.add_argument('--output',type=Path)
    p.add_argument('--expected-sources',help='JSON ordered master source UIDs; required for repair')
    a=p.parse_args();raw=a.project.read_bytes();root=ET.fromstring(gzip.decompress(raw) if raw[:2]==b'\x1f\x8b' else raw)
    validate_aliases(root);inlet,sources=master_sources(root,a.sequence_uid,a.track_uid)
    before=[n.get('ObjectURef') for n in sources]
    result={'connected':a.track_uid in before,'master_sources':before,'source_sha256':hashlib.sha256(raw).hexdigest(),'native_mix_verified':False}
    if a.output:
        if a.output.resolve()==a.project.resolve() or a.output.exists() or a.output.with_suffix('.routing.json').exists():raise ValueError('New offline output and receipt required')
        if a.expected_sources is None:raise ValueError('Exact preparation routing precondition required')
        protected=[ET.tostring(n) for n in root if n is not inlet]
        result.update(connect_owned_track(root,sequence_uid=a.sequence_uid,track_uid=a.track_uid,expected_sources=json.loads(a.expected_sources)))
        if protected!=[ET.tostring(n) for n in root if n is not inlet]:raise ValueError('Protected graph changed')
        if a.project.read_bytes()!=raw:raise ValueError('Source changed during preparation')
        with a.output.open('xb') as f:f.write(gzip.compress(ET.tostring(root,encoding='utf-8',xml_declaration=True),mtime=0))
        result['connected']=True
        with a.output.with_suffix('.routing.json').open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps(result))
    if not result['connected']:raise SystemExit(2)
if __name__=='__main__':main()
