from acq_edit_runtime import skill_scripts
"""Validate the optional mixed-source master mode of the assembly importer."""
from pathlib import Path
import sys,json,hashlib,importlib.util,tempfile
sys.dont_write_bytecode=True
p=Path(__file__).parent
spec=importlib.util.spec_from_file_location('original_guard',p/'validate-assembly-import.py');guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard)
spec=importlib.util.spec_from_file_location('master_compiler',p/'assembly-master-compiler.py');compiler=importlib.util.module_from_spec(spec);spec.loader.exec_module(compiler)
def validate(xml_path,xml_sha,expected_path,expected_sha,fixture_root,queue_path,queue_sha,gap_frames):
 root=Path(fixture_root).resolve(strict=True);m=json.loads(guard.checked(expected_path,expected_sha,root));raw=guard.checked(xml_path,xml_sha,root);queue=json.loads(guard.checked(queue_path,queue_sha,root))
 if m.get('schema')!='edit.assembly-review-master-proof/v1' or m['queue_path']!=str(Path(queue_path).resolve()) or m['queue_sha256']!=queue_sha or m['xml_path']!=str(Path(xml_path).resolve()) or m['xml_sha256']!=xml_sha or int(gap_frames)!=30:raise ValueError('Master proof/queue/identity mismatch')
 if not 1<=len(queue['clips'])<=1000 or not 1<=len(m['items'])*2<=10000 or len(m['markers'])>2000:raise ValueError('Master aggregate resource bound')
 prov=m['provenance']
 allowed_code={str(skill_scripts()/n) for n in ('review_xml.py','compile_assembly.py','assembly_job.py')}|{str((p/'assembly-master-compiler.py').resolve())}
 if {a['path'] for a in prov['canonical_code']}!=allowed_code:raise ValueError('Unrecognized compiler code reference')
 if not Path(queue_path).resolve().is_relative_to(root) and not queue.get('frozen_manifest'):raise ValueError('Production master requires its exact frozen batch ledger')
 for a in prov['artifacts']:guard.checked(a['path'],a['sha256'],root)
 for a in prov['canonical_code']:
  if compiler.sha(a['path'])!=a['sha256']:raise ValueError('Compiler code changed')
 for a in prov['media']:
  info=guard.bounded(a['path'],root).stat()
  if str(info.st_size)!=a['size'] or str(info.st_mtime_ns)!=a['mtime_ns']:raise ValueError('Original media identity changed')
 allowed={a['path'] for a in prov['artifacts']};media={a['path'] for a in prov['media']}
 for c in queue['clips']:
  if any(str(Path(c[k]['path']).resolve()) not in allowed for k in ('design','compiled','source_words','original_expected')):raise ValueError('Unbound original artifact')
  d=json.loads(Path(c['design']['path']).read_text())
  if any(str(Path(r['media']).resolve()) not in media or str(Path(r['source_words']).resolve()) not in allowed for r in d['clips']):raise ValueError('Unbound source reference')
 with tempfile.TemporaryDirectory(prefix='master-exact-reproduction-',dir=root) as directory:
  x=Path(directory)/'reproduced.xml';e=Path(directory)/'reproduced.proof.json';rebuilt=compiler.build(queue_path,x,e);rebuilt['xml_path']=m['xml_path']
  if x.read_bytes()!=raw or rebuilt!=m:raise ValueError('Master is not exact original v2 reproduction plus approved picture-grid conform')
 for a in prov['artifacts']:guard.checked(a['path'],a['sha256'],root)
 return {'manifest_path':str(Path(expected_path).resolve()),'manifest_sha256':expected_sha,'verification':'exact_mixed_source_master_reproduced','clips':len(m['clip_index']),'items':len(m['items'])}
if __name__=='__main__':
 try:print(json.dumps(validate(*sys.argv[1:])))
 except Exception as e:print(str(e),file=sys.stderr);sys.exit(1)
