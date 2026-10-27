#!/usr/bin/env python3
"""Homebrew entrypoint. Mutable integrations belong to the signed-in user, not the keg."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

PACKAGE = Path(__file__).resolve().parents[1]

def user_runtime(package=PACKAGE, home=None, backend=None, fresh=False):
    home = Path(home or Path.home())
    release = json.loads((package / 'release.json').read_text())
    version = release['version']
    if not version or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-' for c in version):
        raise ValueError('Invalid release version')
    parent = home / 'Library/Application Support/ACQ Edit/versions'
    if backend not in (None,'filmcraft','premiere'): raise ValueError('Choose filmcraft or premiere')
    target = parent / (version+('-'+backend if backend else '')+('-repair-'+__import__('uuid').uuid4().hex[:12] if fresh else ''))
    marker = target / '.package-sha256'
    fingerprint = hashlib.sha256((package / 'release.json').read_bytes() + ((package / '.release-source.json').read_bytes() if (package / '.release-source.json').exists() else b'')).hexdigest()
    if target.is_symlink() or parent.is_symlink():
        raise ValueError('Symlink installation refused')
    if target.exists():
        if not marker.is_file() or marker.read_text().strip() != fingerprint:
            raise ValueError('Existing runtime belongs to different package bytes; preserved')
        return target
    parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=version+'.install-', dir=parent))
    # Interrupted staging is retained; no destructive cleanup or takeover.
    for item in package.iterdir():
        if item.name in {'.git', '.local', '.agents', '.claude', 'node_modules', '__pycache__'}:
            continue
        if item.is_symlink():
            raise ValueError('Release source symlink refused')
        if item.is_dir():
            shutil.copytree(item, staging / item.name)
        else:
            shutil.copy2(item, staging / item.name)
    (staging / '.package-sha256').write_text(fingerprint+'\n')
    staging.rename(target)
    return target

def engine_registry(base, home=None):
    base=Path(base);home=Path(home or Path.home());file=base/'engines.json'
    registry=json.loads(file.read_text()) if file.is_file() else {'schema':'acq-edit/engines-v1','engines':{}}
    if registry.get('schema')!='acq-edit/engines-v1':raise ValueError('Unknown engine registry; preserved')
    # Adopt the earlier single-engine configuration in place; never move its DB or projects.
    legacy=base/'config.json'
    if not file.exists() and legacy.is_file():
        config=json.loads(legacy.read_text());engine=config.get('backend');python=Path(config.get('python',''))
        if engine in ('filmcraft','premiere') and python.is_absolute():
            runtime=python.parents[3] if len(python.parents)>3 else Path('/not-a-runtime')
            if (runtime/'.package-sha256').is_file():
                registry['engines'][engine]={'runtime':str(runtime),'home':str(base)};registry['default']=engine
    for engine,entry in registry['engines'].items():
        root=Path(entry['runtime']);configured=Path(entry['home'])
        allowed=home/'Library/Application Support/ACQ Edit/versions'
        if engine not in ('filmcraft','premiere') or root.is_symlink() or not root.resolve().is_relative_to(allowed.resolve()) or configured not in (base,base/'engines'/engine):
            raise ValueError('Engine registry points outside its owned runtime/configuration; preserved')
    return registry

def main():
    args = sys.argv[1:]
    if args == ['version']:
        print(json.loads((PACKAGE / 'release.json').read_text())['version']); return
    base = Path(os.environ.get('ACQ_EDIT_HOME',str(Path.home()/'.config/acq-edit')))
    registry_path=base/'engines.json'
    registry=engine_registry(base)
    fresh='--fresh-runtime' in args
    if fresh:args.remove('--fresh-runtime')
    if fresh and not (len(args)>1 and args[0]=='onboard' and args[1] in ('filmcraft','premiere')):raise ValueError('--fresh-runtime is only for engine onboarding')
    selected=None
    if args[:1]==['--engine']:
        i=args.index('--engine')
        if i+1>=len(args):raise ValueError('--engine requires filmcraft or premiere')
        selected=args[i+1];del args[i:i+2]
    if len(args)>1 and args[0]=='onboard' and args[1] in ('filmcraft','premiere','premiere-panel'):selected='premiere' if args[1]=='premiere-panel' else args[1]
    if selected is not None and selected not in ('filmcraft','premiere'):raise ValueError('Choose filmcraft or premiere')
    selected=selected or registry.get('default')
    if selected:
        entry=registry.get('engines',{}).get(selected)
        installing=len(args)>1 and args[0]=='onboard' and args[1] in ('filmcraft','premiere')
        root=user_runtime(backend=selected,fresh=fresh) if installing or not entry or args[:2]==['onboard','guide'] else Path(entry['runtime'])
        if entry and installing:os.environ['ACQ_EDIT_PREVIOUS_RUNTIME']=entry['runtime']
        if not root.is_dir() or not (root/'.package-sha256').is_file():raise ValueError('Registered runtime is missing; resume onboarding for '+selected)
        engine_home=Path(entry['home']) if entry else base/'engines'/selected
        os.environ['ACQ_EDIT_HOME']=str(engine_home)
        os.environ['ACQ_EDIT_CREDENTIALS_HOME']=str(base)
    else:
        root = user_runtime()
        installing=False
    if args and args[0]=='helper':
        from runtime_environment import execution_environment
        os.environ.update(execution_environment())
        os.environ['PATH']=str(root/'.local/venv/bin')+os.pathsep+os.environ['PATH']
        if len(args)<2:raise ValueError('Use helper owner/script.py [arguments]')
        relative=Path(args[1]);helper_root=root if relative.parts and relative.parts[0]=='scripts' else root/'.local/skills';script=(helper_root/relative).resolve()
        if relative.is_absolute() or '..' in relative.parts or not script.is_relative_to(helper_root.resolve()) or not script.is_file() or script.suffix!='.py':raise ValueError('Use a packaged Python helper inside .local/skills or scripts')
        interpreter=root/'.local/venv/bin/python'
        subprocess.run([str(interpreter),str(root/'scripts/materialize.py'),'--verify'],check=True,stdout=subprocess.DEVNULL)
        os.execv(str(interpreter),[str(interpreter),str(script),*args[2:]])
    if args and args[0] == 'onboard':
        command = [sys.executable, str(root/'scripts/onboard.py'), *args[1:]]
    elif args and args[0] == 'skills':
        command = [sys.executable, str(root/'scripts/agent_skills.py'), *args[1:]]
    elif args and args[0] == 'delivery':
        mapping = {'credentials':'connect.py', 'check':'connect.py', 'status':'connect.py', 'login':'setup_frameio_oauth.py'}
        action = args[1] if len(args)>1 else 'help'
        if action not in mapping:
            raise ValueError('Use delivery credentials, login, check or status; see docs/ONBOARDING.md for routes')
        command = [str(root/'.local/venv/bin/python') if (root/'.local/venv/bin/python').exists() else sys.executable, str(root/'distribution/skills/monday/scripts'/mapping[action])]
        if action in {'credentials','check','status'}: command.extend([action, *args[2:]])
    else:
        if not (root/'dist/cli.js').is_file():
            raise ValueError('Run acq-edit onboard guide for guided setup, or acq-edit onboard filmcraft codex (or premiere / claude) first')
        command = ['node', str(root/'dist/cli.js'), *args]
    os.chdir(root)
    if not (args and args[:2]==['onboard','guide']) and not (args and args[0]=='skills'):
        from runtime_environment import execution_environment
        os.environ.update(execution_environment())
        os.environ['PATH']=str(root/'.local/venv/bin')+os.pathsep+os.environ['PATH']
    if installing:
        result=subprocess.run(command)
        state=root/'.local/onboarding.json'
        if state.is_file() and all(json.loads(state.read_text()).get('steps',{}).get(step)=='completed' for step in ('engine','configuration')) and (engine_home/'config.json').is_file():
            import fcntl
            base.mkdir(parents=True,exist_ok=True,mode=0o700)
            with (base/'engines.lock').open('a') as lock:
                fcntl.flock(lock,fcntl.LOCK_EX)
                registry=engine_registry(base)
                registry['engines'][selected]={'runtime':str(root),'home':str(engine_home)}
                registry.setdefault('default',selected)
                fd,tmp=tempfile.mkstemp(dir=base)
                with os.fdopen(fd,'w') as out:json.dump(registry,out,indent=2)
                os.replace(tmp,registry_path)
        sys.exit(result.returncode)
    os.execvp(command[0], command)

if __name__ == '__main__':
    try: main()
    except (ValueError, OSError, KeyError) as e:
        print('ACQ Edit: '+str(e), file=sys.stderr); sys.exit(1)
