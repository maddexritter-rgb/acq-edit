"""Read-only owner transport and immutable guidance receipt contracts."""
import hashlib,io,json,os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'python'))
import brain_receipts as brain
from common import sha

class Response(io.BytesIO):
 def __enter__(self):return self
 def __exit__(self,*args):self.close()

def response(version,query):
 body=f'Synthetic editorial guidance revision {version}';digest=hashlib.sha256(body.encode()).hexdigest()
 return {'schema':'editorial-brain.context/v1','project_ref':'fixtureproject','query':query,
  'playbooks':[{'format':fmt,'version':version,'body':body,'body_sha256':digest} for fmt in ['universal','monologue']],
  'cards':[], 'required_reading':{'policies':[{'policy_id':'required-'+fmt,'format':fmt,'version':version,'priority_note':'Synthetic required reading','documents':[{'ordinal':1,'source_id':'source-'+fmt,'source_title':fmt,'source_body':body,'source_sha256':digest}]} for fmt in ['universal','monologue']]}}

class BrainReceiptTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
  self.project={'id':'project','root':str(self.root)};(self.root/'10_WORK').mkdir()
  cfg=self.root/'private-config';cfg.mkdir();(cfg/'context.json').write_text(json.dumps({'function_url':'https://fixtureproject.supabase.co/functions/v1/editorial-search','project_ref':'fixtureproject'}));token=cfg/'read_token';token.write_text('fixture-restricted-token');token.chmod(0o600)
  self.config={'brainConfig':str(cfg)};self.readerPatch=patch.object(brain,'SKILLS',ROOT/'distribution/skills');self.readerPatch.start();self.addCleanup(self.readerPatch.stop)
  self.env=patch.dict(os.environ,{'EDITORIAL_BRAIN_READ_KEY':''});self.env.start();self.addCleanup(self.env.stop)
  self.calls=[];self.revision=1
 def transport(self,request,**kwargs):
  payload=json.loads(request.data);self.calls.append((request,payload))
  query={'problem':payload['problem'],'format':payload['format'],'limit':5,'includeDevelopment':False,'currentProjectPrefix':payload['current_project_prefix'],'heldOutSourcePrefixes':payload['held_out_source_prefixes'],'includeRequiredReading':True,'readingOverlays':payload['reading_overlays']}
  return Response(json.dumps(response(self.revision,query)).encode())
 def request(self,name):return {'format':'monologue','problem':'Preserve the complete source payoff','output':str(self.root/'10_WORK'/name)}
 def fetch(self,name):
  with patch('urllib.request.urlopen',side_effect=self.transport):return brain.fetch(self.project,self.config,self.request(name))
 def test_local_readiness_reuses_owner_without_network_or_secret_output(self):
  cfg=Path(self.config['brainConfig']);before={str(p):p.read_bytes() for p in cfg.iterdir()}
  with patch('urllib.request.urlopen',side_effect=AssertionError('Doctor must not fetch guidance')):
   result=brain.check_configuration(self.config)
  self.assertTrue(result['ready']);self.assertEqual(result['remoteAccess'],'not-checked')
  self.assertNotIn('fixture-restricted-token',json.dumps(result));self.assertEqual(before,{str(p):p.read_bytes() for p in cfg.iterdir()})
  self.assertEqual(list((self.root/'10_WORK').iterdir()),[])
 def test_local_readiness_refuses_missing_mismatched_or_broad_token_configuration(self):
  cfg=Path(self.config['brainConfig']);token=cfg/'read_token';context=cfg/'context.json';original=context.read_text()
  self.assertFalse(brain.check_configuration({})['ready'])
  for data in [{'function_url':'https://other.supabase.co/functions/v1/editorial-search','project_ref':'fixtureproject'}, {'function_url':'http://fixtureproject.supabase.co/functions/v1/editorial-search','project_ref':'fixtureproject'}, {'function_url':'https://fixtureproject.supabase.co/functions/v1/editorial-search?key=private','project_ref':'fixtureproject'}]:
   context.write_text(json.dumps(data));self.assertFalse(brain.check_configuration(self.config)['ready'])
  context.write_text(original);token.chmod(0o644);self.assertFalse(brain.check_configuration(self.config)['ready'])
  token.chmod(0o600);token.write_text('  ');self.assertFalse(brain.check_configuration(self.config)['ready'])
 def test_local_readiness_hides_malformed_configuration_and_restores_environment(self):
  context=Path(self.config['brainConfig'])/'context.json';context.write_text('{"secret":"do-not-print-this"')
  result=brain.check_configuration(self.config);self.assertFalse(result['ready']);self.assertNotIn('do-not-print-this',json.dumps(result))
  context.write_text(json.dumps({'function_url':'https://fixtureproject.supabase.co/functions/v1/editorial-search','project_ref':'fixtureproject'}))
  with patch.dict(os.environ,{'EDITORIAL_BRAIN_CONFIG_DIR':'unrelated','EDITORIAL_BRAIN_FUNCTION_URL':'unrelated','EDITORIAL_BRAIN_PROJECT_REF':'unrelated'}):
   self.assertTrue(brain.check_configuration(self.config)['ready'])
   self.assertEqual(os.environ['EDITORIAL_BRAIN_CONFIG_DIR'],'unrelated');self.assertEqual(os.environ['EDITORIAL_BRAIN_FUNCTION_URL'],'unrelated');self.assertEqual(os.environ['EDITORIAL_BRAIN_PROJECT_REF'],'unrelated')
 def test_new_revision_records_new_guidance_without_rewriting_existing_design(self):
  first=self.fetch('first');pinned=Path(first['receiptPath']).read_bytes();plan=self.root/'10_WORK/approved-plan.json';plan.write_text(json.dumps({'brain':first,'approved':True}));plan_before=sha(plan)
  self.revision=2;second=self.fetch('second')
  self.assertEqual(first['versions']['playbooks'][0]['version'],1);self.assertEqual(second['versions']['playbooks'][0]['version'],2)
  self.assertNotEqual(first['sha256'],second['sha256']);self.assertEqual(Path(first['receiptPath']).read_bytes(),pinned);self.assertEqual(sha(plan),plan_before)
  self.assertEqual(brain.verify_saved(first['receiptPath'])['versions'],first['versions'])
  for request,payload in self.calls:
   self.assertTrue(request.full_url.endswith('/functions/v1/editorial-search'));self.assertEqual(request.method,'POST');self.assertTrue(payload['include_required_reading']);self.assertNotIn('update',payload)
  for p in (self.root/'10_WORK').rglob('*.json'):self.assertNotIn('fixture-restricted-token',p.read_text())
 def test_repeat_destination_does_not_fetch_or_overwrite(self):
  self.fetch('one');count=len(self.calls)
  with self.assertRaisesRegex(RuntimeError,'destination exists'):self.fetch('one')
  self.assertEqual(len(self.calls),count)
 def test_response_or_playbook_tampering_is_rejected(self):
  saved=self.fetch('one');p=Path(saved['receiptPath']);p.chmod(0o600);data=json.loads(p.read_text());data['playbooks'][0]['version']=99;p.write_text(json.dumps(data))
  with self.assertRaisesRegex(RuntimeError,'response hash'):brain.verify_saved(p)
  data['client_receipt']['response_sha256']=brain.response_hash({k:v for k,v in data.items() if k!='client_receipt'});data['playbooks'][0]['body']='tampered';data['client_receipt']['response_sha256']=brain.response_hash({k:v for k,v in data.items() if k!='client_receipt'});p.write_text(json.dumps(data))
  with self.assertRaisesRegex(RuntimeError,'content hash'):brain.verify_saved(p)
 def test_offline_verification_never_refreshes_guidance(self):
  saved=self.fetch('one')
  with patch('urllib.request.urlopen',side_effect=AssertionError('No network during saved-plan validation')):brain.verify_saved(saved['receiptPath'])
 def test_missing_explicit_config_does_not_fall_back_to_global(self):
  with patch('urllib.request.urlopen') as network,self.assertRaisesRegex(RuntimeError,'explicitly'):brain.fetch(self.project,{},self.request('missing'))
  network.assert_not_called();self.assertFalse((self.root/'10_WORK/missing').exists())
 def test_failed_retrieval_preserves_attempt_and_never_returns_cached_context(self):
  self.fetch('prior')
  import urllib.error
  with patch('urllib.request.urlopen',side_effect=urllib.error.URLError('offline')),self.assertRaises(Exception):brain.fetch(self.project,self.config,self.request('failure'))
  self.assertTrue((self.root/'10_WORK/failure/failure.json').is_file());self.assertFalse((self.root/'10_WORK/failure/versions.json').exists())
  self.assertEqual(brain.verify_saved(self.root/'10_WORK/prior/context.json')['versions']['playbooks'][0]['version'],1)
 def test_output_escape_and_unknown_mutation_field_are_refused(self):
  request=self.request('test');request['output']=str(self.root.parent/'escape')
  with self.assertRaisesRegex(RuntimeError,'outside'):brain.fetch(self.project,self.config,request)
  request=self.request('test');request['publish']=True
  with self.assertRaisesRegex(brain.InvalidBrainRequest,'only retrieves'):brain.fetch(self.project,self.config,request)
 def test_render_receipt_keeps_original_guidance_after_a_new_retrieval(self):
  import common
  first=self.fetch('first');self.revision=2;self.fetch('second');work=self.root/'10_WORK'
  selection=work/'selection.json';selection.write_text('{}')
  native=work/'native.fixture';native.write_text('mock checkpoint');media=work/'media.fixture';media.write_text('mock media')
  project={**self.project,'backend':'filmcraft'}
  spec={'clipId':'clip','cuts':[{'frames':25}],'width':640,'height':360,'fps':{'numerator':25,'denominator':1},'brain':first,'editorial':{'selectionPath':str(selection)}}
  packet={'plan':str(work/'plan.json'),'receipt':str(work/'render-receipt.json')}
  Path(packet['plan']).write_text(json.dumps(spec))
  # Explicit mocked native verification: this test proves guidance provenance only.
  with patch('urllib.request.urlopen',side_effect=AssertionError('No refresh at render time')):
   receipt=common.result_receipt(project,packet,spec,native,media,work/'inspection.json',verification={'fixture':True})
  self.assertEqual(receipt['brainEvidence']['versions']['playbooks'][0]['version'],1)
  self.assertEqual(receipt['brainEvidence']['sha256'],first['sha256'])

if __name__=='__main__':unittest.main()
