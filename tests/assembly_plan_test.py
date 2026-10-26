"""Contract tests with synthetic words and mocked media probes, not editorial proof."""
import copy,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'python'))
import assembly_plan
from common import sha
SKILLS=ROOT/'distribution/skills'
sys.path.insert(0,str(SKILLS/'edit/scripts'))
from compile_assembly import compile_design

def write(path,value):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value));return str(path)
def fixture(root):
 root=Path(root);source=root/'00_SOURCE';source.mkdir();video=source/'picture.mp4';audio=source/'played.wav';video.write_bytes(b'fixture-picture');audio.write_bytes(b'fixture-pcm');work=root/'10_WORK';work.mkdir()
 words=write(work/'words.json',{'words':[{'word':word,'start':start,'end':end,'speaker':'A'} for word,start,end in [('First',.1,.3),('claim',.5,.8),('discard',1.3,1.5),('Complete',2.1,2.4),('payoff',2.5,2.8)]]})
 brain=write(work/'brain.json',{'testFixture':'not live guidance'})
 selection=write(work/'selection.json',{'schema':'edit.assembly-selection/v2','clips':[{'id':'clip','media':str(audio),'source_words':words,'brain_preflight':brain,'interaction_word_range':[0,4],'paper_cut':[{'word_range':[0,1],'action':'KEEP'},{'word_range':[2,2],'action':'CUT','reason':'Synthetic omitted word'},{'word_range':[3,4],'action':'KEEP'}],'kept_word_ranges':[[0,1],[3,4]],'speaker_roles':{'A':'expert'},'payoff_speaker':'A','retained_fillers':[],'hook_word_range':[0,0],'reasoning_word_range':[1,1],'payoff_word_range':[3,4]}]})
 # Replay mode constructs a synthetic compiler fixture; it is NOT an authoring preflight.
 compiled=write(work/'compiled.json',compile_design(Path(selection),check_templates=False))
 decisions=write(work/'decisions.json',{'schema':'edit.paired-seam-decisions/v1','selection':selection,'sample_rate':48000,'fps':'25','span_count':2,'first_source_frame':0,'last_source_frame':75,'first_source_sample':11,'last_source_sample':143989,'outer_edge_evidence':{'status':'LOCALLY_INSPECTED','reason':'Synthetic contract fixture only'},'joins':[{'out_window':[48017,48017],'in_window':[96017,96017],'preferred_out':48017,'preferred_in':96017,'status':'LOCALLY_INSPECTED','reason':'Synthetic contract fixture','evidence':'No acoustic claim'}]})
 evidence=write(work/'routing-evidence.json',{'testFixture':True});routing=write(work/'routing.json',{'media':str(audio),'picture':str(video),'stream':0,'channel':0,'source_clock_offset_samples':0,'evidence':{'path':evidence,'sha256':sha(evidence)}})
 project={'id':'project','root':str(root),'backend':'filmcraft'}
 spec={'schema':'acq-edit/plan-v1','projectId':'project','backend':'filmcraft','clipId':'clip','title':'Synthetic','fps':{'numerator':25,'denominator':1},'width':640,'height':360,'sampleRate':48000,'brain':{'receiptPath':brain,'sha256':sha(brain)},'editorial':{'selectionPath':selection,'sha256':sha(selection),'compiledPath':compiled,'compiledSha256':sha(compiled),'reviewed':True,'execution':{'decisionsPath':decisions,'decisionsSha256':sha(decisions),'routingPath':routing,'routingSha256':sha(routing)}},'sources':[{'id':name,'projectId':'project','path':str(p),'sha256':sha(p)} for name,p in [('picture',video),('audio',audio)]],'cuts':[],'captions':[],'graphics':[],'framing':{},'audio':{}}
 return project,spec

def probe(args,**kwargs):
 return json.dumps({'streams':[{'codec_type':'audio','codec_name':'pcm_s16le','sample_rate':'48000','channels':1}] if args[-1].endswith('.wav') else [{'codec_type':'video','r_frame_rate':'25/1','avg_frame_rate':'25/1'}]}).encode()
class AssemblyBindingTests(unittest.TestCase):
 def bind(self,p,s):
  with patch.object(assembly_plan,'SKILLS',SKILLS),patch('assembly_plan.subprocess.check_output',side_effect=probe):return assembly_plan.bound_assembly(p,s)
 def test_real_canonical_compilers_preserve_independent_sample_ranges(self):
  with tempfile.TemporaryDirectory() as root:
   p,s=fixture(root);result=self.bind(p,s);a,b=result['cuts']
   self.assertEqual((a['sourceInFrame'],a['frames'],a['audioInSample'],a['audioSamples'],a['audioRecordSample']),(0,25,11,48006,11))
   self.assertEqual((b['sourceInFrame'],b['frames'],b['audioInSample'],b['audioSamples'],b['audioRecordSample']),(50,25,96017,47972,48017))
   self.assertEqual(b['wordIds'],['3','4']);self.assertEqual(result['coverage']['wholly_outside_word_count'],0)
 def test_stale_decisions_and_changed_played_sources_are_rejected(self):
  with tempfile.TemporaryDirectory() as root:
   p,s=fixture(root);changed=copy.deepcopy(s);changed['editorial']['execution']['decisionsSha256']='stale'
   with self.assertRaisesRegex(RuntimeError,'Pinned assembly input'):self.bind(p,changed)
   Path(s['sources'][1]['path']).write_bytes(b'changed')
   with self.assertRaisesRegex(RuntimeError,'Played source changed'):self.bind(p,s)
 def test_verified_media_reuses_only_the_current_complete_byte_check(self):
  from common import verify_plan_media
  with tempfile.TemporaryDirectory() as root:
   p,s=fixture(root);verified=verify_plan_media(p,s);baseline=self.bind(p,s)
   with patch.object(assembly_plan,'SKILLS',SKILLS),patch('assembly_plan.subprocess.check_output',side_effect=probe),patch.object(assembly_plan,'sha',wraps=sha) as digest:
    self.assertEqual(assembly_plan.bound_assembly(p,s,verified),baseline)
    paths=[str(call.args[0]) for call in digest.call_args_list]
    self.assertFalse(any(x['path'] in paths for x in s['sources']))
    with self.assertRaisesRegex(RuntimeError,'does not cover'):
     assembly_plan.bound_assembly(p,s,verified[:1])
 def test_unreviewed_joins_and_wrong_clocks_are_refused(self):
  with tempfile.TemporaryDirectory() as root:
   p,s=fixture(root);changed=copy.deepcopy(s);changed['sampleRate']=44100
   with self.assertRaisesRegex(RuntimeError,'clocks differ'):self.bind(p,changed)
   e=s['editorial']['execution'];d=json.loads(Path(e['decisionsPath']).read_text());d['joins'][0]['status']='PROPOSED';write(Path(e['decisionsPath']),d);e['decisionsSha256']=sha(e['decisionsPath'])
   with self.assertRaisesRegex(RuntimeError,'Inspect both sides'):self.bind(p,s)
 def test_wrong_brain_and_stereo_channel_guess_are_refused(self):
  with tempfile.TemporaryDirectory() as root:
   p,s=fixture(root);changed=copy.deepcopy(s);changed['brain']['receiptPath']=write(Path(root)/'other.json',{})
   with self.assertRaisesRegex(RuntimeError,'Brain receipt differs'):self.bind(p,changed)
   e=s['editorial']['execution'];routing=json.loads(Path(e['routingPath']).read_text());routing['channel']=1;write(Path(e['routingPath']),routing);e['routingSha256']=sha(e['routingPath'])
   with self.assertRaisesRegex(RuntimeError,'mono channel'):self.bind(p,s)
 def test_runtime_rejects_changed_native_ranges_even_with_correct_word_ids(self):
  with tempfile.TemporaryDirectory() as root:
   p,s=fixture(root);binding=self.bind(p,s);s['cuts']=copy.deepcopy(binding['cuts']);s['cuts'][1]['sourceInFrame']+=1
   completed=type('Result',(),{'returncode':0,'stdout':json.dumps(binding),'stderr':''})()
   with patch('assembly_plan.subprocess.run',return_value=completed),self.assertRaisesRegex(RuntimeError,'Native cuts differ'):assembly_plan.verify_bound_plan(p,s)
if __name__=='__main__':unittest.main()
