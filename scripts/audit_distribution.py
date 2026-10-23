#!/usr/bin/env python3
"""Scan tracked/untracked release source; emit file and line only, never secret values."""
import hashlib,json,re,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
patterns=[r'(?:sk-(?:proj-|ant-)?[A-Za-z0-9_-]{24,}|sb_secret_[A-Za-z0-9_-]{20,}|xox[baprs]-[A-Za-z0-9-]{15,}|AIza[A-Za-z0-9_-]{30,}|eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{10,})',r'(?i)(?:api_key|access_token|refresh_token|service_role_key)\s*[:=]\s*[\"\x27][a-zA-Z0-9_./+=-]{24,}[\"\x27]']
hits=[]
files=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=ROOT).decode().split('\0')
for name in filter(None,files):
 p=ROOT/name
 if p.name in {'credentials.json','read_token','.env'}:hits.append(name)
 if p.stat().st_size>5_000_000:hits.append(name+': large unreviewed asset')
 try:text=p.read_text()
 except UnicodeError:continue
 for pattern in patterns:
  for m in re.finditer(pattern,text):hits.append(f'{name}:{text[:m.start()].count(chr(10))+1}')
manifest=ROOT/'distribution/SOURCE_MANIFEST.json'
if manifest.exists():
 for entry in json.loads(manifest.read_text())['files']:
  p=ROOT/'distribution/skills'/entry['path']
  if hashlib.sha256(p.read_bytes()).hexdigest()!=entry['distribution_sha256']:hits.append(entry['path']+': manifest mismatch')
print(json.dumps({'files_scanned':len(files)-1,'findings':hits},indent=2));sys.exit(bool(hits))
