#!/usr/bin/env python3
"""Issue an owner-authorized private installation bundle. Never publish from this helper."""
import argparse
import json
from pathlib import Path
import shutil
from asset_bundle import digest, verify, safe

def build(source, target, version, grant, profiles, fonts, brain):
    source,target=Path(source),Path(target)
    proof=verify(source); original=json.loads((source/'asset-bundle.json').read_text())
    permission=json.loads(Path(grant).read_text())
    if permission.get('scope')!='private-team-installation' or not all(permission.get(k) for k in ('authorizedBy','statement','date')):
        raise ValueError('Explicit installation bundle authorization required')
    if target.exists(): raise ValueError('Existing bundle preserved')
    shutil.copytree(source,target)
    for folder,inputs in [('profiles/captions',profiles),('fonts',fonts)]:
        (target/folder).mkdir(parents=True,exist_ok=True)
        for value in inputs:
            src=Path(value);out=target/folder/src.name
            if src.is_symlink() or not src.is_file(): raise ValueError('Invalid asset input')
            if out.exists() and digest(out)!=digest(src): raise ValueError('Asset collision: '+src.name)
            shutil.copyfile(src,out)
    team=json.loads(Path(brain).read_text())
    endpoint=team.get('function_url') or team.get('endpoint')
    if not endpoint or not team.get('project_ref') or not team.get('token'): raise ValueError('Dedicated team reader missing')
    (target/'team').mkdir()
    (target/'team/editorial-brain.json').write_text(json.dumps({'function_url':endpoint,'project_ref':team['project_ref'],'token':team['token']},indent=2)+'\n')
    (target/'team/editorial-brain.json').chmod(0o600)
    (target/'NOTICES.txt').write_text('Private ACQ team installation bundle. Music: owner-authorized internal use.\nFonts retain their original copyrights and licenses. This package does not grant font licenses or public redistribution rights. Install commercial fonts only on appropriately licensed machines; activate through the font provider where required.\nProfiles are ACQ configuration data. The team token is a dedicated document-reading gateway credential, not a database administration or personal service key.\n')
    files={p.relative_to(target).as_posix():digest(p) for p in sorted(target.rglob('*')) if p.is_file() and p.name not in {'asset-bundle.json','INSTALLATION_AUTHORIZATION.json'}}
    (target/'INSTALLATION_AUTHORIZATION.json').write_text(json.dumps({**permission,'sourceManifestSha256':proof['manifestSha256'],'assets':files},indent=2)+'\n')
    files['INSTALLATION_AUTHORIZATION.json']=digest(target/'INSTALLATION_AUTHORIZATION.json')
    manifest={**original,'version':version,'distribution':'owner-authorized-private-team-installation','files':files}
    (target/'asset-bundle.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return verify(target)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source');p.add_argument('target');p.add_argument('--version',required=True);p.add_argument('--grant',required=True);p.add_argument('--brain',required=True);p.add_argument('--font',action='append',default=[]);p.add_argument('--profile',action='append',default=[])
    a=p.parse_args();print(json.dumps(build(a.source,a.target,a.version,a.grant,a.profile,a.font,a.brain)))
