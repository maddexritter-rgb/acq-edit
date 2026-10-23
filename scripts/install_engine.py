#!/usr/bin/env python3
"""Install only the chosen integration into this checkout's ignored .local tree."""
import argparse,json,os,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];LOCAL=ROOT/'.local';LOCAL.mkdir(exist_ok=True)
PIN='71438c627b5cbcfb550526c3971f4d0037733c5c'
def run(args,cwd=None):subprocess.run(args,cwd=cwd,check=True)
ap=argparse.ArgumentParser();ap.add_argument('backend',choices=['filmcraft','premiere','resolve']);ap.add_argument('--assets',type=Path,default=Path.home()/'Movies/ACQ Edit Assets');a=ap.parse_args();a.assets.mkdir(parents=True,exist_ok=True)
run([sys.executable,str(ROOT/'scripts/materialize.py'),'--assets',str(a.assets)])
if a.backend=='filmcraft':
 dest=LOCAL/'filmcraft';
 if not dest.exists():run(['git','clone','--filter=blob:none','--no-checkout','https://github.com/storytold/filmcraft.git',str(dest)])
 run(['git','fetch','origin',PIN],dest);run(['git','checkout','--detach',PIN],dest);run(['cargo','build','--release','--locked','-p','filmcraft-cli'],dest)
 print('FilmCraft CLI: '+str(dest/'target/release/filmcraft-cli'))
elif a.backend=='premiere':
 dest=LOCAL/'premiere-agent';
 if dest.exists():raise SystemExit('Existing toolkit Lab installation found; inspect before upgrading. No overwrite performed.')
 shutil.copytree(ROOT/'integrations/premiere-agent',dest)
 run(['npm','ci','--ignore-scripts'],dest);run(['npx','tsc'],dest)
 (dest/'lab').mkdir(exist_ok=True);(dest/'lab/node-path.txt').write_text(shutil.which('node')+'\n');run(['node','scripts/lab-prepare.mjs'],dest)
 profile={'schema':'edit.premiere-bridge-profile/v1','command':[shutil.which('node'),str(LOCAL/'skills/assembly-design/scripts/precision_bridge.mjs'),str(dest)],'cwd':str(dest),'fixture_root':str(dest/'lab/runtime/fixtures'),'connector':'premiere-agent-lab','host_version':'26.3.0','mode':'scoped-edit','project_authorization':str(dest/'lab/runtime/edit-authorization.json')}
 target=LOCAL/'premiere-profile.json';target.write_text(json.dumps(profile,indent=2));target.chmod(0o600)
 print('Prepared isolated panel: '+str(dest/'lab/packages/PremiereAgentLabCEP'))
 print('Profile: '+str(target));print('Panel is not installed into Adobe automatically. Follow docs/ENGINES.md to avoid replacing an existing Lab panel.')
else:
 python=Path('/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Applications/ResolvePython')
 if not python.is_file():raise SystemExit('Install licensed DaVinci Resolve Studio 21.1. Then enable External scripting: Local.')
 print('Resolve integration ready to inspect. No Premiere/FilmCraft installation required. Start Studio and enable External scripting: Local.')
