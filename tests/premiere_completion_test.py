"""Readback verifier fixtures; these do not qualify a native Premiere host."""
import copy
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
from premiere_completion import close,verify_motion,verify_audio_item
from premiere_compatibility import report

class Completion(unittest.TestCase):
 def test_unknown_and_unqualified_hosts_never_gain_permission(self):
  for version in ('28.0.0','26.3.1',None):
   value=report(version);self.assertFalse(value['executionAllowed']);self.assertTrue(all(x=='unverified' for x in value['operations'].values()))
  self.assertTrue(report('26.3.0')['executionAllowed'])
  enabled=report('26.5.2');self.assertTrue(enabled['executionAllowed']);self.assertFalse(enabled['nativeQualified']);self.assertEqual(enabled['status'],'enabled-native-verification-pending')
 def test_nonfinite_and_wrong_curve_lengths_fail(self):
  self.assertFalse(close([float('nan')],[0]));self.assertFalse(close([1,2],[1]));self.assertFalse(close(True,1))
 def test_framing_verifies_every_key_against_design_and_native_readback(self):
  item={'node_id':'v','source_id':'s','media_path':'source','start_ticks':'0','end_ticks':'2','source_in_ticks':'0','source_out_ticks':'2','position':[.5,.5],'scale':100,'keys':[{'ticks':'0','value':[.5,.5]},{'ticks':'1','value':[.6,.5]}]}
  spec={'width':1080,'height':1920,'fps':{'numerator':1,'denominator':1},'cuts':[{'id':'cut','frames':2}],'framing':{'shots':{'cut':{'mode':'tracked-crop','xByFrame':[0,100],'width':1000,'height':1920,'sourceWidth':1000,'sourceHeight':1920,'y':0}}}}
  motion={'project_path':'p','sequence_id':'s','records':[{'anchor_keys':[[0,.5,.5],[1,.6,.5]],'position':[.5,.5],'scale_percent':100}]}
  observed={'project_path':'p','sequence_id':'s','width':1080,'height':1920,'video_tracks':[{'clips':[{**item,'speed':1,'speed_reversed':False,'motion':{'anchor_time_varying':True,'position_time_varying':False,'scale_time_varying':False,'anchor_keys':copy.deepcopy(item['keys']),'position':[.5,.5],'scale':100}}]}]}
  owner=SimpleNamespace(fresh_operation=lambda *a:{'arguments':{'items':[item]}})
  self.assertEqual(verify_motion(spec,motion,observed,owner)['keys'],2)
  observed['video_tracks'][0]['clips'][0]['motion']['anchor_keys'][1]['value'][0]=.7
  with self.assertRaisesRegex(RuntimeError,'keys differ'):verify_motion(spec,motion,observed,owner)
  motion['records'][0]['anchor_keys'].pop()
  with self.assertRaisesRegex(RuntimeError,'curve differs'):verify_motion(spec,motion,observed,owner)
 def test_audio_requires_exact_independent_item_keys(self):
  args={'node_id':'a','media_path':'source','parameter':{'name':'Level'},'keys':[{'ticks':'0','value':.5}]}
  plan={'operation':{'arguments':args,'target':{'project_path':'p','sequence_id':'s'}}}
  state={'project_path':'p','sequence_id':'s','audio_tracks':[{'clips':[{'node_id':'a','media_path':'source','speed':1,'speed_reversed':False,'level':{'name':'Level','time_varying':True,'keys':[{'ticks':'0','value':.5}]}}]}]}
  owner=SimpleNamespace(ITEM_FIELDS=['node_id','media_path'],PARAMETER_FIELDS=['name'])
  self.assertEqual(verify_audio_item(plan,state,owner)['nodeId'],'a')
  state['audio_tracks'][0]['clips'][0]['level']['keys'][0]['value']=.6
  with self.assertRaisesRegex(RuntimeError,'envelope differs'):verify_audio_item(plan,state,owner)
if __name__=='__main__':unittest.main()
