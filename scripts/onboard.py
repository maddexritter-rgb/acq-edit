#!/usr/bin/env python3
"""Resumable per-user setup. No editor mutation or external delivery during setup."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
import urllib.error
from urllib.parse import quote
from asset_bundle import verify, digest

ROOT = Path(__file__).resolve().parents[1]
HOME = Path(os.environ.get('ACQ_EDIT_HOME', str(Path.home()/'.config/acq-edit')))

def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(dir=path.parent)
    with os.fdopen(fd, 'w') as stream:
        json.dump(data, stream, indent=2); stream.write('\n')
    os.replace(temporary, path)

def execute(args, **kwargs):
    print('Step: '+str(args[0])+' '+str(args[1] if len(args)>1 else ''), flush=True)
    subprocess.run([str(x) for x in args], check=True, cwd=ROOT, **kwargs)

def extract(archive, target):
    target = Path(target)
    if target.exists(): raise ValueError('Extraction destination already exists; preserved')
    with tarfile.open(archive, 'r:gz') as tf:
        for entry in tf.getmembers():
            name = Path(entry.name)
            if name.is_absolute() or '..' in name.parts or not (entry.isfile() or entry.isdir()):
                raise ValueError('Unsafe release archive member')
        target.mkdir(parents=True)
        tf.extractall(target, filter='data')

def download_assets(release, staging):
    """Public releases need no GitHub account. Preserve authenticated access if made private later."""
    spec=release['assets'];archive=staging/spec['archive']
    url=f"https://github.com/{release['repository']}/releases/download/{quote(spec['tag'],safe='')}/{quote(spec['archive'],safe='')}"
    request=urllib.request.Request(url,headers={'User-Agent':'ACQ-Edit-onboarding'})
    try:
        response=urllib.request.urlopen(request,timeout=60)
    except urllib.error.HTTPError as e:
        if e.code not in (401,403,404) or not shutil.which('gh'):
            raise ValueError('Release download unavailable. Check repository access and connection; no GitHub login is needed for public releases.') from e
        execute(['gh','release','download',spec['tag'],'--repo',release['repository'],'--pattern',spec['archive'],'--dir',staging])
    else:
        with response,archive.open('xb') as stream:
            shutil.copyfileobj(response,stream)
    return archive

def assets(release):
    spec = release['assets']
    parent = Path.home()/'Library/Application Support/ACQ Edit/assets'
    dest = parent/spec['version']
    if dest.is_symlink(): raise ValueError('Symlink asset destination refused')
    if dest.exists():
        verify(dest)
        if digest(dest/'asset-bundle.json') != spec['manifestSha256']:
            raise ValueError('Installed asset version differs; preserved')
        return dest
    parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=spec['version']+'.download-', dir=parent))
    archive = download_assets(release, staging)
    if digest(archive) != spec['sha256']: raise ValueError('Asset archive checksum mismatch')
    expanded = staging/'expanded'
    extract(archive, expanded)
    source = expanded/spec['version']; verify(source)
    if digest(source/'asset-bundle.json') != spec['manifestSha256']:
        raise ValueError('Asset manifest checksum mismatch')
    source.rename(dest)
    return dest

def install_fonts(bundle, target=None):
    manifest = json.loads((bundle/'asset-bundle.json').read_text())
    target = Path(target or Path.home()/'Library/Fonts/ACQEdit')
    if target.is_symlink(): raise ValueError('Font destination is a symlink; preserved')
    wanted = [(bundle/name, target/Path(name).name, sha) for name,sha in manifest['files'].items()
              if name.startswith('fonts/') and Path(name).suffix.lower() in {'.otf','.ttf'}]
    if not wanted: raise ValueError('Release has no fonts')
    # Validate the whole batch before writing; preserve different installed fonts.
    for source,dest,sha in wanted:
        if digest(source)!=sha or dest.is_symlink() or (dest.exists() and digest(dest)!=sha):
            raise ValueError('Font conflict or checksum mismatch: '+dest.name)
    target.mkdir(parents=True, exist_ok=True)
    for source,dest,sha in wanted:
        if not dest.exists():
            with dest.open('xb') as out, source.open('rb') as src: shutil.copyfileobj(src,out)
        if digest(dest)!=sha: raise ValueError('Font copy failed verification')
    return len(wanted)

def install_brain(bundle):
    source = bundle/'team/editorial-brain.json'
    value = json.loads(source.read_text())
    # This is the dedicated team gateway reader, never a personal/admin token.
    context = {'function_url':value['function_url'], 'project_ref':value['project_ref']}
    folder = HOME/'team-brain'; folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    token = folder/'read_token'; config = folder/'context.json'
    for path in (token,config):
        if path.is_symlink(): raise ValueError('Brain configuration symlink refused')
    if token.exists() or config.exists():
        if not token.is_file() or not config.is_file(): raise ValueError('Incomplete existing brain config; preserved')
        if json.loads(config.read_text())!=context or token.read_text().strip()!=value['token']:
            raise ValueError('Existing brain config differs; explicit credential rotation required')
        if token.stat().st_mode & 0o077: raise ValueError('Brain token needs mode 0600')
    else:
        save(config,context)
        with os.fdopen(os.open(token,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as out: out.write(value['token']+'\n')
    return folder

def panel_install(update_owned=False):
    source = ROOT/'.local/premiere-agent/lab/packages/ACQEditAgentCEP'
    if not (source/'CSXS/manifest.xml').is_file(): raise ValueError('Run Premiere onboarding first')
    target = Path.home()/'Library/Application Support/Adobe/CEP/extensions/ACQEditAgentCEP'
    if target.exists() or target.is_symlink():
        old = {p.relative_to(target).as_posix():digest(p) for p in target.rglob('*') if p.is_file()}
        new = {p.relative_to(source).as_posix():digest(p) for p in source.rglob('*') if p.is_file()}
        if target.is_symlink():raise ValueError('Existing Adobe panel is redirected; preserved.')
        if old != new:
            if not update_owned:raise ValueError('Existing Adobe panel differs; preserved. Use onboard premiere-panel --update-owned to upgrade a verified ACQ Edit panel with backup.')
            current=json.loads((ROOT/'.local/premiere-agent/lab/panel-preparation.json').read_text())
            current_hashes={key.removeprefix('ACQEditAgentCEP/'):value for key,value in current.get('packageHashes',{}).items() if key.startswith('ACQEditAgentCEP/')}
            if current.get('cepId')!='com.acqedit.premiere.bridge' or new!=current_hashes or any(p.is_symlink() for p in source.rglob('*')):raise ValueError('New toolkit panel differs from its preparation receipt; preserved')
            state=ROOT/'.local/onboarding.json'
            previous=json.loads(state.read_text()).get('previousRuntime') if state.is_file() else None
            parent=Path.home()/'Library/Application Support/ACQ Edit/versions'
            prior=Path(previous) if previous else None
            if not prior or not prior.is_absolute() or prior.is_symlink() or not prior.resolve().is_relative_to(parent.resolve()) or not (prior/'.package-sha256').is_file():
                raise ValueError('Prior owned runtime is unavailable; existing panel preserved. Inspect its original installation before replacement.')
            prior_source=prior/'.local/premiere-agent/lab/packages/ACQEditAgentCEP'
            preparation=json.loads((prior/'.local/premiere-agent/lab/panel-preparation.json').read_text())
            if preparation.get('cepId')!='com.acqedit.premiere.bridge':raise ValueError('Prior panel identity differs; preserved')
            expected={key.removeprefix('ACQEditAgentCEP/'):value for key,value in preparation.get('packageHashes',{}).items() if key.startswith('ACQEditAgentCEP/')}
            if any(p.is_symlink() for p in target.rglob('*')) or any(p.is_symlink() for p in prior_source.rglob('*')) or old!=expected or old!={p.relative_to(prior_source).as_posix():digest(p) for p in prior_source.rglob('*') if p.is_file()}:
                raise ValueError('Existing panel differs from its owned installation receipt; preserved. Do not overwrite manual changes.')
            if any((prior/'.local/premiere-agent/lab/runtime'/name).exists() for name in ('writer.lock','reconcile.lock')):raise ValueError('Prior Premiere integration has active native work; finish it before upgrading the panel')
            backup=Path(os.environ.get('ACQ_EDIT_CREDENTIALS_HOME',str(HOME)))/'panel-backups'/__import__('uuid').uuid4().hex
            backup.parent.mkdir(parents=True,exist_ok=True)
            staging=target.parent/('ACQEditAgentCEP-staging-'+__import__('uuid').uuid4().hex)
            shutil.copytree(source,staging)
            target.rename(backup)
            try:staging.rename(target)
            except OSError:
                backup.rename(target)
                raise
            print('Previous owned ACQ Edit panel backed up at '+str(backup))
    else:
        target.parent.mkdir(parents=True, exist_ok=True); shutil.copytree(source,target)
    print('Panel installed. Open Window > Extensions > ACQ Edit Agent in Premiere, then run acq-edit doctor.')
    print('If unsigned CEP is disabled, follow docs/ENGINES.md for the host debug setting.')

def verify_connections():
    credential_home=Path(os.environ.get('ACQ_EDIT_CREDENTIALS_HOME',str(HOME)))
    saved = json.loads((credential_home/'credentials.json').read_text()) if (credential_home/'credentials.json').exists() else {}
    endpoints = {'ASSEMBLYAI_API_KEY':('https://api.assemblyai.com/v2/transcript?limit=1','authorization'),
                 'GEMINI_API_KEY':('https://generativelanguage.googleapis.com/v1beta/models','x-goog-api-key')}
    results=[]
    for name,(url,header) in endpoints.items():
        token = os.environ.get(name) or saved.get(name)
        if not token: results.append({'service':name,'status':'missing'}); continue
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers={header:token}),timeout=30) as response:
                response.read(1024)  # Never display account/transcript data.
            results.append({'service':name,'status':'read-verified'})
        except urllib.error.HTTPError as e: results.append({'service':name,'status':'billing-required' if e.code==402 else 'failed','http':e.code})
        except (OSError,urllib.error.URLError): results.append({'service':name,'status':'unreachable'})
    save(HOME/'connection-check.json',{'results':results,'qualification':'Read access only; not billing balance, model generation or an editing test'})
    print(json.dumps(results,indent=2))
    return all(x['status']=='read-verified' for x in results)

def ensure_credentials(reenter=False):
    """Reuse private shared keys; presence is not provider authentication."""
    from credentials import KEYS
    root = Path(os.environ.get('ACQ_EDIT_CREDENTIALS_HOME', str(HOME)))
    file = root/'credentials.json'
    saved = {}
    if file.exists() or file.is_symlink():
        if file.is_symlink() or file.stat().st_uid != os.getuid() or file.stat().st_mode & 0o077:
            raise ValueError('Credential file needs private ownership/mode 0600; existing file preserved')
        try:
            saved = json.loads(file.read_text())
            if not isinstance(saved, dict): raise ValueError()
        except (ValueError, OSError):
            raise ValueError('Existing credentials are unreadable; use private key setup to repair') from None
    complete = all(isinstance(os.environ.get(key) or saved.get(key), str) and
                   (os.environ.get(key) or saved.get(key)).strip() for key in KEYS)
    if complete and not reenter:
        print('Reusing saved editing keys. Run onboard verify for a provider read check.')
        return 'reused'
    execute(['node', 'dist/cli.js', 'credentials'])
    return 'entered'


def configure_delivery(state, state_file, stage, defer=False):
    # A cancelled form is not consent to defer. Only this explicit choice skips it.
    if defer:
        state['steps']['delivery'] = 'deferred-by-user'
        state['status'] = 'editing-configured-delivery-deferred'
        state['currentStep'] = 'delivery'
        save(state_file, state)
        return {'ready': False, 'deferred': True, 'status': state['status']}
    state['status'] = 'delivery-pending'; state['steps']['delivery'] = 'pending'
    save(state_file, state)
    stage('delivery-connections', delivery_connections)
    check = delivery_check()
    state['steps']['delivery'] = 'read-verified' if check['ready'] else 'pending'
    state['status'] = 'delivery-read-verified' if check['ready'] else 'delivery-pending'
    state['currentStep'] = 'delivery'; save(state_file, state)
    return check


def delivery_connections():
    """Resume the actual credential/login steps; the agent handles account-page guidance."""
    owner = ROOT/'distribution/skills/monday/scripts'
    delivery = Path(os.environ.get('ACQ_EDIT_CREDENTIALS_HOME',str(HOME)))/'delivery'
    if not all((delivery/name).is_file() for name in ('monday.json', 'frameio/credentials.json')):
        execute([sys.executable, owner/'connect.py', 'credentials'])
    if not (delivery/'frameio/token.json').is_file():
        execute([sys.executable, owner/'setup_frameio_oauth.py'])


def delivery_check():
    command = [sys.executable, str(ROOT/'distribution/skills/monday/scripts/connect.py'), 'check']
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    try:
        check = json.loads(result.stdout)
        if not isinstance(check, dict): raise ValueError('Invalid response')
    except (ValueError, TypeError):
        check = {'ready': False, 'status': 'delivery-pending', 'repair': 'Follow the monday onboarding guide and retry.'}
    check['ready'] = result.returncode == 0 and check.get('ready') is True
    return check


def finish_delivery():
    """Complete the standard delivery checkpoint without an upload or editor operation."""
    local = ROOT/'.local'; local.mkdir(exist_ok=True)
    lock = local/'onboarding.lock'
    fd = os.open(lock, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'w') as stream: json.dump({'pid': os.getpid()}, stream)
        check = delivery_check()
        state_file = local/'onboarding.json'
        state = json.loads(state_file.read_text()) if state_file.exists() else {'steps': {}}
        state['steps']['delivery'] = 'read-verified' if check['ready'] else 'pending'
        state['status'] = 'delivery-read-verified' if check['ready'] else 'delivery-pending'
        state['currentStep'] = 'delivery'
        save(state_file, state)
        print(json.dumps(check, indent=2))
        return check['ready']
    finally: lock.unlink()


def register_picker_skills(agent, bundle):
    from agent_skills import default_scope
    scope = default_scope(agent)
    execute(['python3.11', 'scripts/agent_skills.py', 'install', '--agent', agent,
             '--scope', scope, '--update-owned', '--assets', bundle])
    execute(['python3.11', 'scripts/agent_skills.py', 'check', '--agent', agent, '--scope', scope])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',nargs='?',default='guide',choices=['guide','filmcraft','premiere','status','verify','premiere-panel','delivery'])
    parser.add_argument('agent',nargs='?',choices=['codex','claude'],default='codex')
    parser.add_argument('--non-interactive', action='store_true', help='Use saved/default settings and explicit --storage-root; key entry remains in the browser')
    parser.add_argument('--storage-root', type=Path)
    parser.add_argument('--defer-delivery', action='store_true', help='Explicitly configure local editing with delivery deferred; never inferred from cancellation')
    parser.add_argument('--reenter-keys', action='store_true', help='Open private entry even when both shared keys exist')
    parser.add_argument('--update-owned',action='store_true',help='Upgrade only a receipt-verified older ACQ Edit panel, preserving a backup')
    parser.add_argument('--source-build',action='store_true',help='Explicit FilmCraft source build; requires Rust and build tools')
    a=parser.parse_args()
    if a.action=='guide':
        print('Your personal setup guide runs in Codex or Claude Code.')
        print('Open this installed folder in your agent:')
        print(ROOT)
        print('Then say: Help me get set up. Read AGENTS.md and docs/ONBOARDING.md, '
              'walk me through one step at a time, and resume any existing progress.')
        print('Your agent will explain the account links and help with questions. '
              'Your agent opens a local setup page: paste your keys into the boxes and click Save keys.')
        return
    if a.action=='status':
        state=ROOT/'.local/onboarding.json'
        print(state.read_text() if state.exists() else '{"status":"not-started"}')
        print('Full onboarding includes Frame/Monday sign-in and destination verification. Run onboard delivery after the guided connection steps.'); return
    if a.action=='delivery': sys.exit(0 if finish_delivery() else 2)
    from runtime_environment import execution_environment
    os.environ.update(execution_environment())
    if a.action=='verify': sys.exit(0 if verify_connections() else 1)
    if a.action=='premiere-panel': panel_install(a.update_owned); return
    if sys.platform!='darwin': raise ValueError('This release requires macOS')
    for command in ['node','npm','python3.11','ffmpeg','ffprobe','fc-scan']:
        if not shutil.which(command): raise ValueError('Missing '+command+'; see docs/ONBOARDING.md')
    ROOT.joinpath('.local').mkdir(exist_ok=True)
    lock=ROOT/'.local/onboarding.lock'
    fd=os.open(lock,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as f: json.dump({'pid':os.getpid()},f)
    try:
        state_file=ROOT/'.local/onboarding.json'
        state=json.loads(state_file.read_text()) if state_file.exists() else {'backend':a.action,'agent':a.agent,'steps':{}}
        if state['backend']!=a.action: raise ValueError('This runtime is already configured for another backend; preserve it and use a separate installation')
        state['agent']=a.agent
        if os.environ.get('ACQ_EDIT_PREVIOUS_RUNTIME') and os.environ['ACQ_EDIT_PREVIOUS_RUNTIME']!=str(ROOT):state['previousRuntime']=os.environ['ACQ_EDIT_PREVIOUS_RUNTIME']
        def stage(name,work):
            state['currentStep']=name; state['status']='running';save(state_file,state)
            started=time.monotonic()
            try:
                result=work();state['steps'][name]='completed'
            except Exception:
                state['steps'][name]='failed';state['status']='failed';raise
            finally:
                state.setdefault('timings',{}).setdefault(name,[]).append(round(time.monotonic()-started,3));save(state_file,state)
            return result
        def prerequisites():
            from install_engine import preflight
            result=preflight(a.action,a.source_build)
            if result['errors']:raise ValueError('Selected engine prerequisites: '+ '; '.join(result['errors']))
        stage('prerequisites',prerequisites)
        release=json.loads((ROOT/'release.json').read_text())
        bundle=stage('assets',lambda:assets(release))
        stage('fonts',lambda:install_fonts(bundle))
        brain=stage('brain',lambda:install_brain(bundle))
        stage('skill-discovery',lambda:register_picker_skills(a.agent,bundle))
        if not (ROOT/'dist/cli.js').exists():
            stage('service',lambda:(execute(['npm','ci','--ignore-scripts']),execute(['npm','run','build'])))
        if not (ROOT/'.local/venv/bin/python').exists() or state['steps'].get('shared')!='completed':
            stage('shared',lambda:execute(['bash','scripts/install_shared.sh']))
        else: stage('shared-check',lambda:execute([ROOT/'.local/venv/bin/python','python/check_framing_dependencies.py']))
        if state['steps'].get('engine')!='completed':
            stage('engine',lambda:execute(['python3.11','scripts/install_engine.py',a.action,'--assets',bundle]+(['--source-build'] if a.source_build else [])))
        else: stage('skills-check',lambda:execute(['python3.11','scripts/materialize.py','--verify']))
        env={**os.environ,'ACQ_EDIT_TEAM_BRAIN_DIR':str(brain)}
        stage('configuration',lambda:execute(['node','dist/cli.js','setup',a.action,a.agent]+(['--non-interactive'] if a.non_interactive else [])+(['--storage-root',str(a.storage_root)] if a.storage_root else []),env=env))
        stage('credentials',lambda:ensure_credentials(a.reenter_keys))
        delivery = configure_delivery(state,state_file,stage,a.defer_delivery)
        print(json.dumps(delivery,indent=2))
        if a.action=='premiere':
            print('Next: acq-edit --engine premiere onboard premiere-panel; open the ACQ Edit Agent panel in Premiere.')
        if delivery.get('deferred'):
            print('Local editing configured; delivery deferred by your choice. Full delivery setup remains pending.')
        elif not delivery['ready']:
            print('Full onboarding is DELIVERY PENDING. Your agent must finish the failed account/destination step using docs/ONBOARDING.md, then run acq-edit onboard delivery. Setup does not upload clips.')
        print('Also run acq-edit onboard verify and acq-edit doctor before an editing test.')
        execute(['node','dist/cli.js','doctor'])
        if not delivery['ready'] and not delivery.get('deferred'): sys.exit(2)
    finally: lock.unlink()

if __name__=='__main__':
    try: main()
    except (ValueError,OSError,KeyError,subprocess.CalledProcessError) as e:
        print('Onboarding stopped: '+str(e),file=sys.stderr);sys.exit(1)
