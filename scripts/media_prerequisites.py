#!/usr/bin/env python3
"""Preserve existing FFmpeg providers; install core only when none is installed."""
import argparse,json,shutil,subprocess,sys
from pathlib import Path

def check(install_missing=False):
    paths={name:shutil.which(name) for name in ('ffmpeg','ffprobe')};issues=[]
    for name,executable in paths.items():
        if not executable:issues.append(name+' missing');continue
        try:
            r=subprocess.run([executable,'-version'],capture_output=True,text=True,timeout=15)
            if r.returncode or not r.stdout.startswith(name+' version '):issues.append(name+' cannot execute')
        except (OSError,subprocess.SubprocessError):issues.append(name+' cannot execute')
    if not issues:return {'ready':True,'executables':paths,'changed':False}
    if not install_missing:return {'ready':False,'executables':paths,'issues':issues,'repair':'Repair the existing provider if present. If neither executable is installed, run acq-edit media-check --install-missing.'}
    if any(paths.values()):raise ValueError('Existing or incomplete FFmpeg provider preserved. Repair its binaries/shared libraries with its package manager; no automatic replacement.')
    brew=shutil.which('brew')
    if not brew:raise ValueError('Use your existing Homebrew/Workbrew setup to provide FFmpeg; no second package manager will be installed.')
    listed=subprocess.run([brew,'list','--formula','--full-name'],capture_output=True,text=True,timeout=30)
    if listed.returncode:raise ValueError('Cannot inspect installed formulas; resolve the reported Homebrew/Workbrew policy or tap issue before installing FFmpeg.')
    if any(line.strip().split('/')[-1]=='ffmpeg' for line in listed.stdout.splitlines()):
        raise ValueError('An FFmpeg formula is already installed but not on PATH. Repair that provider; no core replacement was attempted.')
    result=subprocess.run([brew,'install','ffmpeg'])
    if result.returncode:raise ValueError('FFmpeg installation failed. Review the package-manager error; tap trust and company policy require their normal user/admin action.')
    report=check();report['changed']=True;return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--install-missing',action='store_true');a=p.parse_args()
    try:
        report=check(a.install_missing);print(json.dumps(report,indent=2));sys.exit(0 if report['ready'] else 1)
    except (ValueError,OSError,subprocess.SubprocessError) as e:print(str(e),file=sys.stderr);sys.exit(1)
