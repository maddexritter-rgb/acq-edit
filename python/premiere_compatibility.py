"""Exact host routing; execution eligibility and native qualification are distinct."""
import hashlib
import json
import plistlib
import re
import subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def registry():return json.loads((ROOT/'compatibility/premiere.json').read_text())
def default_version():return registry()['defaultQualifiedVersion']
def normalized_version(value):
    if not isinstance(value,str):return None
    match=re.fullmatch(r'(\d+\.\d+\.\d+)(?:\s+\([^\r\n]*\))?',value.strip())
    return match.group(1) if match else None

def report(version):
    data=registry();key=normalized_version(version)
    entry=data['versions'].get(key,{'executionAllowed':False,'status':'unknown-version','evidence':None})
    operation_status='existing-support' if entry['status']=='retained-existing-support' else 'enabled-native-verification-pending' if entry['executionAllowed'] else 'unverified'
    return {'observedVersion':version,**entry,'operations':{op:operation_status for op in data['operations']},'repair':None if entry['executionAllowed'] else 'This exact Premiere version is not enabled in the compatibility registry. Preserve the installed editor and report the version; do not edit profiles or switch connectors.'}

def installed(applications=Path('/Applications')):
    result=[]
    files=set(applications.glob('Adobe Premiere Pro*/*.app/Contents/Info.plist'))|set(applications.glob('Adobe Premiere Pro*.app/Contents/Info.plist'))
    for file in sorted(files):
        try:
            data=plistlib.loads(file.read_bytes());version=data.get('CFBundleShortVersionString')
            if version:result.append({'application':str(file.parents[1]),**report(version)})
        except (OSError,ValueError,plistlib.InvalidFileException):continue
    return result

def select_host(applications=Path('/Applications'),processes=None):
    hosts=installed(applications)
    if processes is None:
        try:processes=subprocess.check_output(['ps','-axo','comm='],text=True,stderr=subprocess.PIPE,timeout=10)
        except (OSError,subprocess.SubprocessError):raise RuntimeError('Cannot inspect running Premiere. Preserve the editor and retry host detection.')
    running=[host for host in hosts if any(line.strip().startswith(host['application']+'/Contents/MacOS/') for line in processes.splitlines())]
    if len(running)>1:raise RuntimeError('More than one Premiere version is running. Keep the intended editor open and close the other version before setup.')
    if running:
        selected=running[0]
        if not selected['executionAllowed']:raise RuntimeError('The running Premiere '+str(selected['observedVersion'])+' is not enabled. Preserve it; do not silently target a different installed editor.')
        return selected
    enabled=[host for host in hosts if host['executionAllowed']]
    if not enabled:raise RuntimeError('No enabled installed Premiere was found. Supported execution versions: '+', '.join(k for k,v in registry()['versions'].items() if v['executionAllowed']))
    return max(enabled,key=lambda host:tuple(map(int,normalized_version(host['observedVersion']).split('.'))))

def bind_host(toolkit,host):
    version=normalized_version(host['observedVersion'])
    if not report(version)['executionAllowed']:raise RuntimeError('Cannot bind a disabled Premiere host')
    app=Path(host['application']);plist=app/'Contents/Info.plist'
    if not app.is_absolute() or not app.is_dir() or app.is_symlink() or plist.is_symlink():raise RuntimeError('Premiere application must be an existing, unredirected absolute bundle path')
    raw=plist.read_bytes()
    if normalized_version(plistlib.loads(raw).get('CFBundleShortVersionString'))!=version:raise RuntimeError('Premiere changed during host detection; retry setup')
    receipt={'schema':'acq-edit/premiere-host-v1','application':str(app),'version':version,'plistSha256':hashlib.sha256(raw).hexdigest(),'nativeQualified':False}
    target=Path(toolkit)/'.local/premiere-host.json';target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('x') as stream:json.dump(receipt,stream,indent=2)
    target.chmod(0o600)
    return version

def profile_host(toolkit):
    file=Path(toolkit)/'.local/premiere-host.json'
    if file.is_symlink():raise RuntimeError('Redirected Premiere host receipt refused')
    if not file.exists():return default_version() # Preserve legacy 26.3 installations.
    receipt=json.loads(file.read_text());version=receipt.get('version');app=Path(receipt.get('application',''));plist=app/'Contents/Info.plist'
    if receipt.get('schema')!='acq-edit/premiere-host-v1' or not report(version)['executionAllowed'] or not app.is_absolute() or app.is_symlink() or plist.is_symlink():raise RuntimeError('Invalid Premiere host binding; preserve it and reinstall in a fresh toolkit runtime')
    try:raw=plist.read_bytes()
    except OSError as error:raise RuntimeError('Bound Premiere application is unavailable; preserve the project and rerun setup in a fresh runtime') from error
    if hashlib.sha256(raw).hexdigest()!=receipt.get('plistSha256') or normalized_version(plistlib.loads(raw).get('CFBundleShortVersionString'))!=version:raise RuntimeError('Premiere changed since installation. Preserve projects and rerun onboarding in a fresh toolkit runtime; do not hand-edit the profile.')
    return version

if __name__=='__main__':print(json.dumps({'installed':installed()},indent=2))
