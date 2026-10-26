"""Fail closed when a saved native dialogue chain diverges from the owner plan."""
import copy,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
from common import sha
import dialogue_effects as effects
class DialogueEffectsTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  receipt=self.root/'mix.json';receipt.write_text('{}')
  self.chain=[{'effect':'amplify','params':{'gain':20}}]
  self.spec={'backend':'filmcraft','cuts':[{'id':'one'}],'audio':{'dialogueEffects':{'schema':'acq-edit/dialogue-effects-v1','receiptPath':str(receipt),'receiptSha256':sha(receipt),'cuts':{'one':self.chain}}}}
  self.project={'root':str(self.root)}
  self.native={'view':{'active_sequence':1},'project':{'items':{'1':{'kind':{'Sequence':{'audio_tracks':[{'items':[{'effects':[{'effect':x} for x in ['volume','channel_volume','panner']]+[{'effect':'amplify','enabled':True,'params':{'gain':{'value':{'Float':20.0}}}}]}]}]}}}}}}
 def check(self):
  p=self.root/'native.json';p.write_text(json.dumps(self.native));effects.verify(p,self.spec)
 def test_native_value_change_and_animation_refused(self):
  self.check();field=self.native['project']['items']['1']['kind']['Sequence']['audio_tracks'][0]['items'][0]['effects'][3]['params']['gain']
  field['value']['Float']=19
  with self.assertRaisesRegex(RuntimeError,'parameter changed'):self.check()
  field['value']['Float']=20;field['keyframes']=[{'time':1,'value':{'Float':19}}]
  with self.assertRaisesRegex(RuntimeError,'parameter changed'):self.check()
 def test_added_and_disabled_effects_refused(self):
  chain=self.native['project']['items']['1']['kind']['Sequence']['audio_tracks'][0]['items'][0]['effects']
  chain[3]['enabled']=False
  with self.assertRaisesRegex(RuntimeError,'Disabled'):self.check()
  chain[3]['enabled']=True;chain.append(copy.deepcopy(chain[3]))
  with self.assertRaisesRegex(RuntimeError,'membership'):self.check()
 def test_backend_cut_coverage_and_evidence_refused(self):
  effects.validate(self.project,self.spec);self.spec['backend']='premiere'
  with self.assertRaisesRegex(RuntimeError,'FilmCraft-only'):effects.validate(self.project,self.spec)
  self.spec['backend']='filmcraft';self.spec['cuts'].append({'id':'two'})
  with self.assertRaisesRegex(RuntimeError,'exact cuts'):effects.validate(self.project,self.spec)
  self.spec['cuts'].pop();(self.root/'mix.json').write_text('changed')
  with self.assertRaisesRegex(RuntimeError,'evidence changed'):effects.validate(self.project,self.spec)
 def test_unknown_missing_and_nonfinite_params_refused(self):
  for params in [{'gain':25},{'gain':float('nan')},{'gain':True},{},{'gain':20,'extra':0}]:
   self.chain[0]['params']=params
   with self.assertRaises(RuntimeError):effects.validate(self.project,self.spec)
if __name__=='__main__':unittest.main()
