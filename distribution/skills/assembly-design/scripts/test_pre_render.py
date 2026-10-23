import unittest,tempfile,pathlib,json,copy,sys,subprocess
sys.path.insert(0,str(pathlib.Path(__file__).parent))
from pre_render import inspect,digest
class ConstructionTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.d=pathlib.Path(self.tmp.name)
  def pin(name,data):
   p=self.d/name;p.write_text(json.dumps(data));return {'path':str(p),'sha256':digest(p)}
  self.pin=pin;source=pin('picture',{});audio=pin('audio',{});words=pin('words',{'words':[{'start':.1,'end':.7},{'start':1.2,'end':1.5}]});visual=pin('visual',{'source':source,'spans':[{'source_frames':[0,24],'status':'subject_visible'}]})
  self.x={'schema':'edit.pre-render/v1','native_project':pin('project',{}),'source_words':words,'picture_source':source,'audio_source':audio,'picture_evidence':visual,'fps':'24','sample_rate':48000,'duration_frames':24,'required_picture_lead_frames':0,'spans':[{'source_samples':[0,48000],'timeline_samples':[0,48000],'source_frames':[0,24],'timeline_frames':[0,24],'word_range':[0,0]}]}
 def tearDown(self):self.tmp.cleanup()
 def test_valid(self):self.assertEqual(inspect(self.x)['status'],'CONSTRUCTION_VALID')
 def test_stale(self):pathlib.Path(self.x['native_project']['path']).write_text('changed');self.assertRaises(ValueError,inspect,self.x)
 def test_missing_face(self):self.x['picture_evidence']=self.pin('v2',{'source':self.x['picture_source'],'spans':[{'source_frames':[0,24],'status':'fallback'}]});self.assertEqual(inspect(self.x)['status'],'BLOCKED')
 def test_wrong_range(self):self.x['picture_evidence']=self.pin('v2',{'source':self.x['picture_source'],'spans':[{'source_frames':[1,25],'status':'subject_visible'}]});self.assertRaises(ValueError,inspect,self.x)
 def test_fused(self):self.x['source_words']=self.pin('w2',{'words':[{'start':.1,'end':1.0},{'start':1.01,'end':1.5}]});self.assertEqual(inspect(self.x)['issues'][0]['reason'],'FUSED_RELEASE_CONTEXT')
 def test_lead(self):self.x['required_picture_lead_frames']=3;self.assertEqual(inspect(self.x)['status'],'BLOCKED')
 def test_retiming(self):self.x['spans'][0]['timeline_samples'][1]-=1;self.assertRaises(ValueError,inspect,self.x)
 def test_rational_rates(self):
  for fps in ['24','25','30','30000/1001']:
   x=copy.deepcopy(self.x);x['fps']=fps;x['duration_frames']=30;x['spans'][0].update(source_frames=[0,30],timeline_frames=[0,30],source_samples=[0,40000],timeline_samples=[0,40000]);x['picture_evidence']=self.pin('rate',{'source':x['picture_source'],'spans':[{'source_frames':[0,30],'status':'subject_visible'}]});self.assertEqual(inspect(x)['status'],'CONSTRUCTION_VALID')
 def test_blocked_does_not_launch(self):
  self.x['required_picture_lead_frames']=3;p=self.d/'packet';p.write_text(json.dumps(self.x));marker=self.d/'launched';r=subprocess.run([sys.executable,str(pathlib.Path(__file__).with_name('pre_render.py')),'--packet',str(p),'--out',str(self.d/'result'),'--',sys.executable,'-c',f'open({str(marker)!r},"w").write("bad")'],capture_output=True);self.assertEqual(r.returncode,2);self.assertFalse(marker.exists())
 def test_timer_failure_kept(self):
  script=str(pathlib.Path(__file__).resolve().parents[2]/'edit/scripts/run_clock.py');log=str(self.d/'clock');base=[sys.executable,script,'--log',log]
  subprocess.run(base+['init'],check=True);r=subprocess.run(base+['run','--stage','test','--',sys.executable,'-c','raise SystemExit(7)']);self.assertEqual(r.returncode,7);s=json.loads(subprocess.check_output(base+['finish']));self.assertEqual(s['operations'][0]['returncode'],7);self.assertAlmostEqual(sum(p['seconds']for p in s['phases']),s['wall_seconds'])
 def qa_plan(self,split=True):
  media=self.pin('qa-media',{});proof=self.pin('qa-proof',{});selection=self.pin('qa-selection',{});ticks=254016000000
  panels=[]
  for role,place,rect,head in [('host','top',[0,0,1080,960],[400,150,650,420]),('guest','bottom',[0,960,1080,1920],[400,1110,650,1380])][:2 if split else 1]:
   panels.append({'role':role,'placement':place if split else 'full','quality':'usable','face_visible':True,'visible_participant':role,'observed_picture':'Inspected fixture','participant_matches_intent':True,'media':media,'source_ticks':[0,ticks],'session_offset_ticks':0,'visual_evidence':[proof],'panel_framing':{'status':'INSPECTED','samples':[{'evidence':proof,'head_bounds':head}],'panel_rect':rect,'minimum_headroom_px':96,'maximum_head_height_fraction':.65}})
  plan={'schema':'edit.picture-plan/v2','content_format':'qa','spoken_selection':selection,'split_opportunities':'Required opening','shots':[{'id':'opening','timeline_frames':[0,24],'layout':'split' if split else 'single','panels':panels,'editorial_reason':'Establish participants'}]}
  self.x.update(content_format='qa',spoken_selection=selection,picture_plan=self.pin('qa-plan',plan));return plan
 def test_qa_no_plan(self):
  self.x['content_format']='qa'
  with self.assertRaisesRegex(ValueError,'opening split'):inspect(self.x)
 def test_qa_single_opening_rejected(self):
  self.qa_plan(False)
  with self.assertRaisesRegex(ValueError,'opening split'):inspect(self.x)
 def test_qa_split_opening_valid(self):
  self.qa_plan();self.assertEqual(inspect(self.x)['status'],'CONSTRUCTION_VALID')
 def test_qa_coverage_excuse_does_not_waive(self):
  p=self.qa_plan(False);p['opening_layout_override']={'authority':'builder','instruction':'Camera unavailable'};self.x['picture_plan']=self.pin('qa-plan',p)
  with self.assertRaisesRegex(ValueError,'opening split'):inspect(self.x)
 def test_qa_explicit_user_override(self):
  p=self.qa_plan(False);p['opening_layout_override']={'authority':'user','instruction':'Use a single for this opening'};self.x['picture_plan']=self.pin('qa-plan',p);self.assertEqual(inspect(self.x)['status'],'CONSTRUCTION_VALID')
 def test_format_omission_cannot_bypass_qa(self):
  p=self.qa_plan(False);p.pop('content_format');self.x.pop('content_format');self.x['picture_plan']=self.pin('qa-plan',p)
  with self.assertRaisesRegex(ValueError,'content_format'):inspect(self.x)
 def test_format_disagreement_rejected(self):
  self.qa_plan();self.x['content_format']='monologue'
  with self.assertRaisesRegex(ValueError,'content_format'):inspect(self.x)
if __name__=='__main__':unittest.main()
