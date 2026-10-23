#!/usr/bin/env python3
"""Release maintainer: snapshot current Lab code, never its runtime or user projects."""
import argparse,hashlib,json,shutil
from pathlib import Path
ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,required=True);a=ap.parse_args();root=Path(__file__).resolve().parents[1];dest=root/'integrations/premiere-agent';dest.mkdir(parents=True,exist_ok=True)
entries=[]
for name in ['src','cep-plugin','uxp-plugin','registry','package.json','package-lock.json','tsconfig.json','LICENSE','scripts/lab-prepare.mjs']:
 base=a.source/name
 for f in ([base] if base.is_file() else base.rglob('*')):
  if not f.is_file() or any(x in ['node_modules','.git','runtime','artifacts'] for x in f.relative_to(a.source).parts):continue
  if f.suffix not in ['.ts','.js','.mjs','.cjs','.json','.html','.css','.xml','.jsx','.md','.txt','.svg','.map'] and f.name!='LICENSE':continue
  rel=f.relative_to(a.source);target=dest/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,target);entries.append({'path':str(rel),'sha256':hashlib.sha256(f.read_bytes()).hexdigest()})
(root/'integrations/premiere-source-manifest.json').write_text(json.dumps({'upstream':'https://github.com/leancoderkavy/premiere-pro-mcp','version':'1.18.6','source':'installed-premiere-agent-lab-snapshot','files':entries},indent=2)+'\n')
print(json.dumps({'files':len(entries)}))
