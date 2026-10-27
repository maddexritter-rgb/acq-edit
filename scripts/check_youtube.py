#!/usr/bin/env python3
"""Probe the toolkit downloader and packaged challenge solver without a download."""
import importlib.metadata
import json
import subprocess
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from runtime_environment import select_node

def check():
    node=select_node()
    versions={name:importlib.metadata.version(name) for name in ('yt-dlp','yt-dlp-ejs')}
    subprocess.run([sys.executable,'-m','yt_dlp','--ignore-config','--js-runtimes','node:'+node,'--version'],check=True,capture_output=True)
    return {'ready':True,'python':sys.executable,'node':node,'versions':versions,'networkChallenge':'not-tested'}
if __name__=='__main__':
    try:print(json.dumps(check()))
    except Exception:print(json.dumps({'ready':False,'repair':'Run the shared installer to restore yt-dlp[default] and its EJS dependency, and select a working Node 24+ runtime.'}));sys.exit(1)
