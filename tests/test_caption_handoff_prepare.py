import importlib.util,pathlib,unittest
root=pathlib.Path(__file__).resolve().parents[1];spec=importlib.util.spec_from_file_location('prepare',root/'scripts/prepare_caption_handoff.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Handoff(unittest.TestCase):
 def test_exact_words_and_emphasis_and_rejections(self):
  p={'projectId':'p','clipId':'c','fps':{'numerator':25,'denominator':1},'sampleRate':48000,'cuts':[{'wordIds':['3','4'],'recordFrame':0,'frames':25,'audioRecordSample':0,'audioInSample':48000}]};words=[{}]*3+[{'word':'The','start':1.1,'end':1.3},{'word':'payoff','start':1.4,'end':1.8}];d={'profile':{},'styles':{'host':{}},'groups':[{'words':[3,4],'role':'host','emphasis':[{'text':'payoff','fontStyle':'Bold'}]}]}
  h,c=m.prepare(p,words,d);self.assertEqual(h['cards'][0]['text'],'The payoff');self.assertEqual(h['cards'][0]['style']['emphasis'][0]['start'],4);self.assertEqual(c[0]['word_ids'],[3,4])
  d['groups'][0]['words']=[4,4]
  with self.assertRaises(ValueError):m.prepare(p,words,d)
if __name__=='__main__':unittest.main()
