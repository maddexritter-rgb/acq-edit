#!/usr/bin/env python3
"""Rebuild a developer runtime from exact checkout sources, retaining prior bytes.

This does not upgrade sources or touch an installed Adobe panel. Teammate
upgrades still use a fresh installation. The caller must settle native work.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys


def run(a):
    root=a.toolkit.resolve();runtime=root/'.local/premiere-agent'
    if any((runtime/'lab/runtime'/n).exists() for n in ('writer.lock','mutation.lock')):raise ValueError('Unsettled native writer')
    sources=root/'integrations/premiere-agent/src';installed=runtime/'src'
    def hashes(folder):
        result={}
        for f in folder.rglob('*'):
            if f.is_symlink():raise ValueError('Redirected runtime source')
            if f.is_file():result[str(f.relative_to(folder))]=hashlib.sha256(f.read_bytes()).hexdigest()
        return result
    expected=hashes(sources)
    if expected!=hashes(installed):raise ValueError('Installed source differs from exact checkout')
    for name in ('tsconfig.json','package.json','package-lock.json'):
        if (runtime/name).read_bytes()!=(root/'integrations/premiere-agent'/name).read_bytes():raise ValueError('Runtime build inputs differ')
    a.backup.mkdir()
    receipt=runtime/'lab/runtime-preparation.json'
    shutil.copy2(receipt,a.backup/'runtime-preparation.json')
    shutil.copytree(runtime/'dist',a.backup/'dist')
    node=(runtime/'lab/node-path.txt').read_text().strip()
    subprocess.run([node,str(runtime/'node_modules/typescript/bin/tsc'),'-p',str(runtime/'tsconfig.json')],cwd=runtime,check=True)
    if expected!=hashes(installed):raise ValueError('Source changed during build')
    sys.path.insert(0,str(root/'scripts'))
    from prepare_premiere_runtime import check_transport,copy_resources,verify_helpers
    resources=copy_resources(runtime);helpers=verify_helpers(runtime,root)
    receipt.rename(a.backup/'retired-runtime-preparation.json')
    result=check_transport(runtime,root/'.local/premiere-profile.json',root/'.local/skills/edit/scripts/premiere_agent.py',resources,helpers)
    provenance={'sourceCommit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),'sourceHashes':expected,'priorReceiptSha256':hashlib.sha256((a.backup/'retired-runtime-preparation.json').read_bytes()).hexdigest(),'newReceiptSha256':hashlib.sha256(receipt.read_bytes()).hexdigest(),'nativeHostToolsCalled':False}
    (a.backup/'rebuild.json').write_text(json.dumps(provenance,indent=2))
    return {'compiledFiles':len(result['compiledHashes']),'toolCount':result['toolCount'],'backup':str(a.backup),'sourceCommit':provenance['sourceCommit']}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--toolkit',type=Path,required=True);p.add_argument('--backup',type=Path,required=True)
    print(json.dumps(run(p.parse_args()),indent=2))
