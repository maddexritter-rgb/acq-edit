import ast,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'python'))
from common import inside
class NativeContracts(unittest.TestCase):
 def test_backend_modules_are_independent(self):
  for backend in ['resolve','filmcraft','premiere']:
   tree=ast.parse((ROOT/'python'/f'{backend}.py').read_text())
   imports={n.module for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)}|{a.name for n in ast.walk(tree) if isinstance(n,ast.Import) for a in n.names}
   self.assertFalse(set(['resolve','filmcraft','premiere'])-{backend}&imports)
 def test_project_containment(self):
  self.assertEqual(inside(ROOT,ROOT/'python/native.py'),ROOT/'python/native.py')
  with self.assertRaises(RuntimeError):inside(ROOT,ROOT/'../outside')
 def test_packaged_python_syntax(self):
  for p in (ROOT/'distribution/skills').rglob('*.py'):
   with self.subTest(file=str(p.relative_to(ROOT))):ast.parse(p.read_text())
 def test_every_owner_has_entrypoint(self):
  m=json.loads((ROOT/'distribution/SOURCE_MANIFEST.json').read_text())
  for owner in m['owners']:self.assertTrue((ROOT/'distribution/skills'/owner/'SKILL.md').is_file(),owner)
if __name__=='__main__':unittest.main()
