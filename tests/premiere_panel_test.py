"""Generated package isolation checks; no Adobe installation or host mutation."""
import hashlib,json,shutil,socket,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from prepare_premiere_panel import prepare,CEP_ID,UXP_ID

@unittest.skipUnless(shutil.which('node'),'Node is required for the packaged generator')
class PremierePanelTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(prefix='acq panel spaces ');self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  source=ROOT/'integrations/premiere-agent'
  for name in ['cep-plugin','uxp-plugin']:shutil.copytree(source/name,self.root/name)
  (self.root/'scripts').mkdir();shutil.copy2(source/'scripts/lab-prepare.mjs',self.root/'scripts/lab-prepare.mjs')
  (self.root/'lab').mkdir();(self.root/'lab/node-path.txt').write_text(shutil.which('node')+'\n')
  with socket.socket() as s:s.bind(('127.0.0.1',0));self.port=s.getsockname()[1]
 def test_generated_panels_have_distinct_ids_storage_and_local_endpoint(self):
  source=self.root/'cep-plugin/CSXS/manifest.xml';before=source.read_bytes();result=prepare(self.root,shutil.which('node'),self.port)
  self.assertEqual(source.read_bytes(),before);self.assertEqual(result['cepId'],CEP_ID);self.assertEqual(result['uxpId'],UXP_ID)
  self.assertFalse(result['installedIntoAdobe']);self.assertFalse(result['hostQualified'])
  self.assertIn('acq_edit_agent_', (Path(result['cep'])/'main.js').read_text())
  self.assertIn('acq-edit-agent.bridge-session', (Path(result['uxp'])/'index.cjs').read_text())
  config=self.root/'lab/runtime/config.json';data=json.loads(config.read_text());self.assertEqual(config.stat().st_mode&0o777,0o600)
  self.assertEqual(data['port'],self.port);self.assertNotIn(data['token'],json.dumps(result))
  for name,digest in result['packageHashes'].items():self.assertEqual(hashlib.sha256((self.root/'lab/packages'/name).read_bytes()).hexdigest(),digest)
  with self.assertRaisesRegex(RuntimeError,'Existing panel/runtime'):prepare(self.root,shutil.which('node'),self.port)
  self.assertEqual(json.loads(config.read_text())['token'],data['token'])
 def test_occupied_port_refuses_before_creating_runtime(self):
  with socket.socket() as s:
   s.bind(('127.0.0.1',0));port=s.getsockname()[1]
   with self.assertRaisesRegex(RuntimeError,'already in use'):prepare(self.root,shutil.which('node'),port)
  self.assertFalse((self.root/'lab/runtime').exists())
 def test_production_or_invalid_port_never_prepares_a_package(self):
  for port in [17877,0,65536,True]:
   with self.subTest(port=port),self.assertRaisesRegex(RuntimeError,'distinct local port'):prepare(self.root,shutil.which('node'),port)
  self.assertFalse((self.root/'lab/runtime').exists())

if __name__=='__main__':unittest.main()
