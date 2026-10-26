import importlib.util,pathlib,unittest,tempfile,json
root=pathlib.Path(__file__).resolve().parents[1];spec=importlib.util.spec_from_file_location('prepare',root/'scripts/prepare_caption_handoff.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Handoff(unittest.TestCase):
 def test_exact_words_and_emphasis_and_rejections(self):
  p={'projectId':'p','clipId':'c','fps':{'numerator':25,'denominator':1},'sampleRate':48000,'cuts':[{'wordIds':['3','4'],'recordFrame':0,'frames':25,'audioRecordSample':0,'audioInSample':48000}]};words=[{}]*3+[{'word':'The','start':1.1,'end':1.3},{'word':'payoff','start':1.4,'end':1.8}];d={'profile':{},'styles':{'host':{}},'groups':[{'words':[3,4],'role':'host','emphasis':[{'text':'payoff','fontStyle':'Bold'}]}]}
  h,c=m.prepare(p,words,d);self.assertEqual(h['cards'][0]['text'],'The payoff');self.assertEqual(h['cards'][0]['style']['emphasis'][0]['start'],4);self.assertEqual(c[0]['word_ids'],[3,4])
  d['groups'][0]['words']=[4,4]
  with self.assertRaises(ValueError):m.prepare(p,words,d)
 def test_normalized_emphasis_uses_display_ranges(self):
  with tempfile.TemporaryDirectory() as folder:
   profile=pathlib.Path(folder)/'profile.json';profile.write_text(json.dumps({'normalization':'oliver_v2','proper_names':[]}))
   p={'projectId':'p','clipId':'c','fps':{'numerator':25,'denominator':1},'sampleRate':48000,'cuts':[{'wordIds':['0','1'],'recordFrame':0,'frames':25,'audioRecordSample':0,'audioInSample':0}]}
   d={'profile':{'path':str(profile)},'styles':{'host':{}},'groups':[{'words':[0,1],'role':'host','emphasis':[{'text':'Everybody.','fontStyle':'Bold'}]}]}
   h,_=m.prepare(p,[{'word':'To','start':.1,'end':.3},{'word':'Everybody.','start':.4,'end':.8}],d)
   run=h['cards'][0]['style']['emphasis'][0];display=m.normalize_display('To Everybody.',json.loads(profile.read_text()))
   self.assertEqual(display[run['start']:run['end']],run['text']);self.assertNotIn('.',run['text'])
 def test_adjacent_words_do_not_overlap_after_frame_quantization(self):
  p={'projectId':'p','clipId':'c','fps':{'numerator':24000,'denominator':1001},'sampleRate':48000,'cuts':[{'wordIds':['0','1'],'recordFrame':0,'frames':24,'audioRecordSample':0,'audioInSample':0}]}
  d={'profile':{},'styles':{'host':{}},'groups':[{'words':[0,0],'role':'host'},{'words':[1,1],'role':'host'}]}
  h,_=m.prepare(p,[{'word':'first','start':.1,'end':.51},{'word':'second','start':.51,'end':.8}],d)
  a,b=h['cards'];self.assertLessEqual(a['speech_end'],b['start_frame']/(24000/1001));self.assertEqual(a['speech_end'],.51)
if __name__=='__main__':unittest.main()
