#!/usr/bin/env python3
"""Export canonical procedures without touching their live source. Never copy account configuration."""
import argparse,ast,hashlib,json,re
from pathlib import Path
from portable_patches import portable_text,portable_distribution,private_references
OWNERS='edit assembly-design long-form-ingest find-precedents source-intel footage-fetch horizontal-to-vertical caption-clips text-hook music render watch clip-review-room revision-planner transcript-edit clip-review-tracker audit-script audit-audio audit-captions audit-visual mozi-sf-audit scorecard-audit book-doodle b-roll-injector broll-cutaway cinematic vertical-livestream-card promo saas-animation-video ad-edit listicle-short live-clip testimonial-edit source-library alex premiere-to-resolve editorial-brain-ingest'.split()
EXT={'.md','.py','.js','.mjs','.cjs','.ts','.tsx','.jsx','.json','.sh','.css','.html','.toml','.yaml','.yml','.txt','.svg'}
SKIP={'node_modules','.git','__pycache__','.venv','venv','training','corpus','dataset','deliveries','outputs','results','runtime','.cache','artifacts','evidence','fixtures','logs'}
SECRET=re.compile(r'(?:sk-(?:proj-|ant-)?[A-Za-z0-9_-]{24,}|sb_secret_[A-Za-z0-9_-]{20,}|xox[baprs]-[A-Za-z0-9-]{15,}|AIza[A-Za-z0-9_-]{30,}|eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{10,})')
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();root=a.source.resolve();out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
 manifest=[];omitted=[];external=[]
 for owner in ['_shared']+OWNERS:
  base=root/owner
  if not base.exists():raise SystemExit(f'Missing canonical owner {owner}')
  for f in sorted(base.rglob('*')):
   if not f.is_file():continue
   rel=f.relative_to(root);reason=None
   if f.is_symlink() and not f.resolve().is_relative_to(root):reason='external symlink'
   elif any(p in SKIP or 'venv' in p or p.startswith('.') for p in rel.parts) or any(t in f.name.lower() for t in ['.env','.bak','pre-2026','backup','read_token','credential','secret']):reason='private/runtime/backup material'
   elif f.suffix not in EXT or f.stat().st_size>2_000_000:reason='binary, large asset or unreviewed extension'
   if reason:omitted.append({'path':str(rel),'reason':reason});continue
   try:text=f.read_text()
   except UnicodeError:omitted.append({'path':str(rel),'reason':'binary'});continue
   if SECRET.search(text):raise SystemExit(f'Secret-shaped content: {rel}; inspect privately before packaging')
   source_hash=hashlib.sha256(f.read_bytes()).hexdigest();transform=[]
   for old,new in [(str(root),'__ACQ_SKILLS__'),('~/.agents/skills','__ACQ_SKILLS__'),('~/.claude/skills','__ACQ_SKILLS__'),(str(Path.home()/ 'Downloads/cluade'),'__ACQ_ASSETS__'),('~/Downloads/cluade','__ACQ_ASSETS__')]:
    if old in text:text=text.replace(old,new);transform.append({'from':'canonical-root' if 'skills' in old else 'asset-library-root','to':new})
   text,patches=portable_text(text,str(rel));transform.extend(patches)
   # Personal project paths are never working defaults in the portable distribution.
   text=re.sub(r'/Users/[^/\s]+/', '__ACQ_LEGACY_HOME__/',text)
   text=re.sub(r'/Volumes/[^\n\"\'`]+',lambda m:'__ACQ_EXTERNAL_VOLUME__/'+m.group(0).split('/',3)[-1],text) if f.suffix=='.md' else text
   text,patches=portable_distribution(text,str(rel));transform.extend(patches)
   refs=private_references(text)
   if refs:external.append({'path':str(rel),'references':len(refs),'status':'requires-profile-or-portable-replacement'})
   target=out/rel;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(text)
   manifest.append({'path':str(rel),'source':'canonical-skills/'+str(rel),'source_sha256':source_hash,'distribution_sha256':hashlib.sha256(text.encode()).hexdigest(),'bytes':len(text.encode()),'transforms':transform})
 (out.parent/'SOURCE_MANIFEST.json').write_text(json.dumps({'schema':'acq-edit/source-manifest-v1','owners':OWNERS,'files':manifest},indent=2)+'\n')
 (out.parent/'PORTABILITY_REPORT.json').write_text(json.dumps({'excluded':[x for x in omitted if not any('venv' in part or part in {'node_modules','__pycache__'} for part in Path(x['path']).parts)],'excluded_total':len(omitted),'unresolved_external_references':external,'note':'External reference markers are blocked dependencies, never permission to access a private workstation.'},indent=2)+'\n')
 print(json.dumps({'owners':len(OWNERS),'files':len(manifest),'excluded':len(omitted),'files_requiring_portability_work':len(external)}))
if __name__=='__main__':main()
