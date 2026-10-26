"""Append-only framing polish must not alter any pre-existing native work."""
import copy,importlib.util,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'distribution/skills/edit/scripts'))
spec=importlib.util.spec_from_file_location('split_shadow',ROOT/'scripts/portable_snippets/filmcraft_split_shadow.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
class ShadowProtectionTests(unittest.TestCase):
 def setUp(self):
  self.old={'view':{'active_sequence':1},'project':{'name':'edit','next_id':10,'settings':{'fps':24},'root':{'name':'edit','children':[{'Item':1},{'Item':2}]},'items':{'1':{'kind':{'Sequence':{'video_tracks':[{'items':[{'source_in':12,'caption':'Keep these words'}]}],'audio_tracks':[{'items':[{'duration':96}]}]}}},'2':{'kind':{'Sequence':{'video_tracks':[{'items':[{'camera':'upper'}]},{'items':[{'camera':'lower'}]}]}}}}}}
  self.new=copy.deepcopy(self.old);p=self.new['project'];p['next_id']=20;p['root']['children'].append({'Item':10});p['items']['10']={'kind':{'Sequence':{}}};p['items']['2']['kind']['Sequence']['video_tracks'] += [{'items':[]},{'items':[]}]
 def test_only_append_only_changes_are_allowed(self):module.protected(self.old,self.new,[2])
 def test_original_caption_camera_or_audio_changes_fail(self):
  for target in ['caption','audio','camera']:
   d=copy.deepcopy(self.new)
   if target=='caption':d['project']['items']['1']['kind']['Sequence']['video_tracks'][0]['items'][0]['caption']='Changed'
   if target=='audio':d['project']['items']['1']['kind']['Sequence']['audio_tracks'][0]['items'][0]['duration']=95
   if target=='camera':d['project']['items']['2']['kind']['Sequence']['video_tracks'][0]['items'][0]['camera']='Different'
   with self.subTest(target=target),self.assertRaisesRegex(RuntimeError,'Protected'):module.protected(self.old,d,[2])
 def test_extra_items_or_master_switch_fail(self):
  for change in ['item','master']:
   d=copy.deepcopy(self.new)
   if change=='item':d['project']['items']['11']={}
   else:d['view']['active_sequence']=2
   with self.subTest(change=change),self.assertRaises(RuntimeError):module.protected(self.old,d,[2])
 def test_source_and_exporter_must_be_packaged_identically(self):
  self.assertEqual((ROOT/'scripts/portable_snippets/filmcraft_split_shadow.py').read_bytes(),(ROOT/'distribution/skills/horizontal-to-vertical/scripts/filmcraft_split_shadow.py').read_bytes())
