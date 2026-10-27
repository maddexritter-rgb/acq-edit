#!/usr/bin/env python3
"""Archive tracked source at a clean commit; never include local runtimes or secrets."""
import argparse
import io
import json
from pathlib import Path
import subprocess
import tarfile

ROOT=Path(__file__).resolve().parents[1]
def package(output):
    changes=subprocess.check_output(['git','status','--porcelain','--untracked-files=normal'],cwd=ROOT,text=True)
    if changes.strip(): raise ValueError('Commit and inspect the source before packaging')
    release=json.loads((ROOT/'release.json').read_text());version=release['version']
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    names=subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0')
    prefix='acq-edit-'+version
    with tarfile.open(output,'x:gz') as archive:
        for name in filter(None,names):
            source=ROOT/name
            if source.is_symlink(): raise ValueError('Tracked symlink refused')
            archive.add(source,arcname=prefix+'/'+name,recursive=False)
        data=(json.dumps({'commit':commit,'version':version})+'\n').encode()
        info=tarfile.TarInfo(prefix+'/.release-source.json');info.size=len(data);info.mode=0o644
        archive.addfile(info,io.BytesIO(data))
    print(json.dumps({'commit':commit,'version':version,'archive':str(output)}))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);package(p.parse_args().output)
