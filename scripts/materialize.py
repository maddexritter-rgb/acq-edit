#!/usr/bin/env python3
"""Materialize portable path tokens into an isolated toolkit runtime, never global skills."""
import argparse,hashlib,json,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--assets',type=Path,required=True);a=ap.parse_args();dest=ROOT/'.local/skills';dest.mkdir(parents=True,exist_ok=True)
 m=json.loads((ROOT/'distribution/SOURCE_MANIFEST.json').read_text());blocked=[]
 for entry in m['files']:
  source=ROOT/'distribution/skills'/entry['path'];data=source.read_bytes()
  if hashlib.sha256(data).hexdigest()!=entry['distribution_sha256']:raise RuntimeError('Distribution hash mismatch: '+entry['path'])
  text=data.decode().replace('__ACQ_SKILLS__',str(dest)).replace('__ACQ_ASSETS__',str(a.assets.resolve()))
  if '__ACQ_LEGACY_HOME__' in text or '__ACQ_EXTERNAL_VOLUME__' in text:blocked.append(entry['path'])
  target=dest/entry['path'];target.parent.mkdir(parents=True,exist_ok=True);target.write_text(text)
 (ROOT/'.local/portability.json').write_text(json.dumps({'blockedReferences':blocked},indent=2))
 # Toolkit-owned instructions take precedence over installation-specific legacy routing.
 header='''\n## ACQ Edit distribution execution contract\nRead the toolkit docs/AGENT_WORKFLOW.md before executing. The project backend is immutable.\nUse the local toolkit project paths and credentials; never use personal workstation paths.\nResolve routes to python/resolve.py; Premiere to scoped Agent Lab; FilmCraft to its headless adapter.\nUnresolved __ACQ_ markers indicate unavailable optional dependencies; report them explicitly.\nNo delivery to external accounts is implied. The review room publishes only local immutable versions.\n'''
 target=dest/'edit/SKILL.md';target.write_text(target.read_text()+header)
 print(json.dumps({'materializedFiles':len(m['files']),'runtime':str(dest),'unresolvedOptionalReferences':blocked}))
if __name__=='__main__':main()
