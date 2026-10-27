"""Install an immutable, hash-pinned native runtime without a compiler toolchain."""
import json
import platform
import subprocess
import tempfile
from pathlib import Path
from asset_bundle import digest, safe
from onboard import download_assets, extract

ROOT=Path(__file__).resolve().parents[1]
PIN='71438c627b5cbcfb550526c3971f4d0037733c5c'
BINARY='target/release/filmcraft-cli'

def specification(root=ROOT):
    release=json.loads((root/'release.json').read_text())
    spec=release.get('filmcraftRuntime')
    if not spec or spec.get('sourceCommit')!=PIN:
        raise ValueError('No pinned prebuilt FilmCraft runtime in this release')
    return release,spec

def compatibility(spec):
    if platform.system()!=spec['system'] or platform.machine()!=spec['architecture']:
        return f"This runtime requires {spec['system']} {spec['architecture']}. Keep FilmCraft selected; use an explicitly requested source build on other platforms."
    version=tuple(int(x) for x in platform.mac_ver()[0].split('.'))
    minimum=tuple(int(x) for x in spec['minimumMacOS'].split('.'))
    if version<minimum:return 'This runtime requires macOS '+spec['minimumMacOS']+' or later; older macOS is not qualified.'
    return None

def verify(folder,spec):
    if folder.is_symlink():raise ValueError('Symlink runtime refused')
    manifest=safe(folder,'runtime.json')
    if digest(manifest)!=spec['manifestSha256']:raise ValueError('Runtime manifest differs; existing files preserved')
    value=json.loads(manifest.read_text())
    if value['sourceCommit']!=PIN or value['binarySha256']!=spec['binarySha256']:
        raise ValueError('Runtime source or binary pin differs')
    for name,expected in value['files'].items():
        if digest(safe(folder,name))!=expected:raise ValueError('Runtime file changed: '+name)
    found={p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file() and p!=manifest}
    if found!=set(value['files']):raise ValueError('Runtime has missing or extra files; preserved')
    binary=safe(folder,BINARY)
    if digest(binary)!=spec['binarySha256']:raise ValueError('Native executable checksum differs')
    subprocess.run([str(binary),'--help'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=20)
    return binary

def install(root=ROOT):
    release,spec=specification(root)
    problem=compatibility(spec)
    if problem:raise ValueError(problem)
    local=root/'.local';dest=local/'filmcraft'
    if dest.exists() or dest.is_symlink():return verify(dest,spec)
    staging=Path(tempfile.mkdtemp(prefix='filmcraft-runtime-',dir=local))
    archive=download_assets({'repository':release['repository'],'assets':spec},staging)
    if digest(archive)!=spec['sha256']:raise ValueError('Runtime archive checksum differs; download retained')
    expanded=staging/'expanded';extract(archive,expanded)
    candidate=expanded/spec['folder']
    binary=verify(candidate,spec)
    if dest.exists() or dest.is_symlink():raise ValueError('Runtime appeared during install; both copies preserved')
    candidate.rename(dest)
    return dest/BINARY
