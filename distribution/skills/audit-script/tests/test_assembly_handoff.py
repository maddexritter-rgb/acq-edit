import importlib.util, json, tempfile, unittest, subprocess, sys
from pathlib import Path
from unittest.mock import patch
p=Path(__file__).resolve().parents[1]/'scripts/assembly_handoff.py'
s=importlib.util.spec_from_file_location('gate',p); gate=importlib.util.module_from_spec(s);s.loader.exec_module(gate)
class GateTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  self.state={'project':'Test.prproj','sequence':'Cuts','sequence_id':'1','project_path':'/project/Test.prproj','video':[{'muted':False,'items':[{'start':0,'end':110,'in_point':10,'out_point':120,'source':'source.mov','disabled':False},{'start':130,'end':160,'in_point':200,'out_point':230,'source':'source.mov','disabled':False}]}],'audio':[]}
  for i in range(1,3):(self.root/f'clip_{i:03}.txt').write_text('1 [00:00] Specific problem.\n2 [00:05] Concrete mechanism and complete useful answer.')
  self.packet=gate.make_packet(self.state,self.root,'builder')
  self.reports=self.root/'reports';self.reports.mkdir()
  for clip in self.packet['clips']:
   r={'schema':'assembly-review/v1','clip_id':clip['clip_id'],'evidence_sha256':clip['evidence_sha256'],'agent_id':'reviewer_'+clip['clip_id'],'verdict':'PASS','viewer':'Business owner','promise':'Solve the problem','reward':'Concrete mechanism','handoff_note':'Editorial review only','checks':{k:{'verdict':'PASS','evidence':'Lines 1-2, 0:00-0:05','reason':'Complete answer to stated problem'} for k in gate.CRITERIA},'fixes':[]}
   (self.reports/(clip['clip_id']+'.json')).write_text(json.dumps(r))
 def mutate_report(self,fn):
  p=self.reports/'clip_001.json';r=json.loads(p.read_text());fn(r);p.write_text(json.dumps(r))
 def blocked(self):
  with self.assertRaises((ValueError,FileNotFoundError,json.JSONDecodeError)):gate.check_packet(self.packet,self.state,self.reports)
 def test_complete_110_second_clip_passes(self):self.assertEqual(gate.check_packet(self.packet,self.state,self.reports),2)
 def test_missing_report(self):(self.reports/'clip_002.json').unlink();self.blocked()
 def test_malformed_report(self):(self.reports/'clip_001.json').write_text('{');self.blocked()
 def test_unknown(self):self.mutate_report(lambda r:r.update(verdict='UNKNOWN'));self.blocked()
 def test_missing_payoff(self):self.mutate_report(lambda r:r['checks']['reward'].update(verdict='REVISE'));self.blocked()
 def test_missing_criterion(self):self.mutate_report(lambda r:r['checks'].pop('goodwill'));self.blocked()
 def test_missing_evidence(self):self.mutate_report(lambda r:r['checks']['hook'].update(evidence=''));self.blocked()
 def test_outstanding_fix(self):self.mutate_report(lambda r:r.update(fixes=[{'required':True,'evidence':'L2','edit':'Restore payoff'}]));self.blocked()
 def test_builder_self_review(self):self.mutate_report(lambda r:r.update(agent_id='builder'));self.blocked()
 def test_reused_agent(self):self.mutate_report(lambda r:r.update(agent_id='reviewer_clip_002'));self.blocked()
 def test_stale_hash(self):self.mutate_report(lambda r:r.update(evidence_sha256='old'));self.blocked()
 def test_changed_transcript(self):(self.root/'clip_001.txt').write_text('changed');self.blocked()
 def test_changed_timeline(self):self.state['video'][0]['items'][0]['in_point']=11;self.blocked()
 def test_added_clip(self):self.state['video'][0]['items'].append(dict(start=180,end=190));self.blocked()
 def test_omitted_clip(self):self.packet['clips'].pop();self.blocked()
 def test_duplicate_clip(self):self.packet['clips'][1]=self.packet['clips'][0];self.blocked()
 def test_empty_assembly(self):
  self.state['video'][0]['items']=[]
  with self.assertRaises(ValueError):gate.make_packet(self.state,self.root,'builder')
 def test_stray_audio(self):
  self.state['audio']=[{'muted':False,'items':[{'start':115,'end':125}]}]
  with self.assertRaises(ValueError):gate.make_packet(self.state,self.root,'builder')
 def test_nested_sequence_blocks(self):
  self.state['video'][0]['items'][0]['is_sequence']=True
  with self.assertRaises(ValueError):gate.make_packet(self.state,self.root,'builder')
 def test_unresolved_source_blocks(self):
  self.state['video'][0]['items'][0]['source']=''
  with self.assertRaises(ValueError):gate.make_packet(self.state,self.root,'builder')
 def test_dispatch_requires_evidence(self):
  dispatcher=Path(gate.__file__).resolve().parents[2]/'edit/scripts/assembled_gate.py'
  result=subprocess.run([sys.executable,str(dispatcher),'--assembly-handoff'],capture_output=True,text=True)
  self.assertNotEqual(result.returncode,0)
  self.assertIn('--packet',result.stderr)
 def test_unavailable_bridge_cli_blocks(self):
  with patch.object(gate,'read_native',side_effect=TimeoutError('bridge unavailable')):
   self.assertEqual(gate.main(['--check','--packet',str(self.root/'none'),'--reviews',str(self.reports),'--require-project','Test.prproj','--require-sequence','Cuts']),1)
 def test_check_cli_pass_and_fail(self):
  pp=self.root/'packet.json';pp.write_text(json.dumps(self.packet))
  args=['--check','--packet',str(pp),'--reviews',str(self.reports),'--require-project','Test.prproj','--require-sequence','Cuts']
  with patch.object(gate,'read_native',return_value=self.state):
   self.assertEqual(gate.main(args),0)
   (self.reports/'clip_002.json').unlink()
   self.assertEqual(gate.main(args),1)
if __name__=='__main__':unittest.main()
