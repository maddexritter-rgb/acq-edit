#!/usr/bin/env python3
"""Package a previously receipted clean FilmCraft build with its dependency notices."""
import argparse,hashlib,json,re,shutil,subprocess,tarfile,tempfile,tomllib,urllib.request
from pathlib import Path
from asset_bundle import digest
from filmcraft_runtime import PIN,BINARY

def package(source,receipt,dependencies,registry,output,minimum_macos):
    run=lambda args:subprocess.check_output(args,cwd=source,text=True).strip()
    if run(['git','rev-parse','HEAD'])!=PIN or run(['git','status','--porcelain','--untracked-files=all']):raise ValueError('Exact clean pinned FilmCraft sources required')
    proof=json.loads(receipt.read_text());binary=source/BINARY
    if proof['source']['commit']!=PIN or proof['binary']['sha256']!=digest(binary):raise ValueError('Binary differs from the original build receipt')
    if proof.get('buildEnvironment'):raise ValueError('Review non-default build environment before packaging')
    if run(['lipo','-archs',str(binary)])!='arm64':raise ValueError('Expected an Apple-silicon executable')
    links=run(['otool','-L',str(binary)]).splitlines()[1:]
    if any(not line.strip().startswith(('/System/Library/','/usr/lib/')) for line in links):raise ValueError('Runtime links non-system libraries')
    run([str(binary),'--help'])
    folder='filmcraft-macos-arm64-'+PIN[:7]
    with tempfile.TemporaryDirectory(prefix='acq-filmcraft-package-') as temp:
        target=Path(temp)/folder;(target/'target/release').mkdir(parents=True)
        shutil.copy2(binary,target/BINARY)
        for name in ['LICENSE-MIT','LICENSE-APACHE','NOTICE','ATTRIBUTION.md']:
            shutil.copy2(source/name,target/name)
        fonts=target/'licenses/fonts';fonts.mkdir(parents=True)
        for name in (source/'assets/fonts').glob('OFL-*.txt'):shutil.copy2(name,fonts/name.name)
        entries={};upstream_cache={}
        for line in dependencies.read_text().splitlines():
            match=re.match(r'([^ ]+) v([^ |]+)[ |].*',line+' ')
            if not match:raise ValueError('Unrecognized dependency line')
            name,version=match.groups();key=name+'-'+version
            if key in entries:continue
            license_id=line.split('|',1)[1].removesuffix(' (*)')
            entry={'name':name,'version':version,'license':license_id};entries[key]=entry
            if name.startswith('filmcraft-'):
                entry['notices']=['LICENSE-MIT','LICENSE-APACHE'];continue
            candidates=list(registry.glob('*/'+key))
            if len(candidates)!=1:raise ValueError('Dependency source unavailable: '+key)
            directory=candidates[0]
            notices=[p for p in directory.rglob('*') if p.is_file() and p.name.upper().startswith(('LICENSE','LICENCE','COPYING','COPYRIGHT','NOTICE'))]
            entry['notices']=[]
            if not notices:
                metadata=tomllib.loads((directory/'Cargo.toml').read_text())['package']
                repo=metadata['repository'].rstrip('/').removesuffix('.git').removeprefix('https://github.com/')
                if repo.count('/')!=1:raise ValueError('Review upstream license source: '+key)
                commit=json.loads((directory/'.cargo_vcs_info.json').read_text())['git']['sha1']
                cache_key=(repo,commit)
                if cache_key not in upstream_cache:
                    tree=json.loads(subprocess.check_output(['gh','api',f'repos/{repo}/git/trees/{commit}?recursive=1'],text=True))
                    if tree.get('truncated'):raise ValueError('Incomplete upstream license inventory')
                    names=[item['path'] for item in tree['tree'] if item['type']=='blob' and Path(item['path']).name.upper().startswith(('LICENSE','LICENCE','COPYING','COPYRIGHT','NOTICE'))]
                    if not names:raise ValueError('Missing upstream license text: '+key)
                    upstream_cache[cache_key]={}
                    for name_in_repo in names:
                        url=f'https://raw.githubusercontent.com/{repo}/{commit}/{name_in_repo}'
                        with urllib.request.urlopen(url,timeout=30) as response:upstream_cache[cache_key][name_in_repo]=response.read()
                for name_in_repo,content in upstream_cache[cache_key].items():
                    relative=Path('licenses')/key/'upstream'/name_in_repo;dest=target/relative;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(content);entry['notices'].append(relative.as_posix())
                entry['licenseSource']={'repository':repo,'commit':commit}
            if license_id=='MPL-2.0':
                # Corresponding unmodified covered source ships alongside the executable.
                shutil.copytree(directory,target/'sources'/key)
                entry['correspondingSource']='sources/'+key
            for notice in notices:
                relative=Path('licenses')/key/notice.relative_to(directory);dest=target/relative;dest.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(notice,dest);entry['notices'].append(relative.as_posix())
        (target/'dependencies.json').write_text(json.dumps(list(entries.values()),indent=2)+'\n')
        build={k:proof[k] for k in ['schema','createdAt','source','command','compiler','cargo','host']}
        build['binary']={k:v for k,v in proof['binary'].items() if k!='path'}
        (target/'build.json').write_text(json.dumps(build,indent=2)+'\n')
        files={p.relative_to(target).as_posix():digest(p) for p in sorted(target.rglob('*')) if p.is_file()}
        manifest={'schema':'acq-edit/filmcraft-runtime-v1','sourceCommit':PIN,'binarySha256':digest(binary),'system':'Darwin','architecture':'arm64','minimumMacOS':minimum_macos,'files':files}
        (target/'runtime.json').write_text(json.dumps(manifest,indent=2)+'\n')
        with tarfile.open(output,'x:gz') as archive:archive.add(target,arcname=folder)
        return {k:manifest[k] for k in ['sourceCommit','binarySha256','system','architecture','minimumMacOS']}|{'folder':folder,'archive':output.name,'sha256':digest(output),'manifestSha256':digest(target/'runtime.json'),'dependencyCount':len(entries)}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for arg in ['source','receipt','dependencies','registry','output']:p.add_argument('--'+arg,type=Path,required=True)
    p.add_argument('--minimum-macos',required=True)
    a=p.parse_args();print(json.dumps(package(a.source,a.receipt,a.dependencies,a.registry,a.output,a.minimum_macos),indent=2))
