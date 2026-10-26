import copy,json,sys,unittest,tempfile
from unittest.mock import patch
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'python'),str(ROOT/'distribution/skills/horizontal-to-vertical/scripts')]
from composition_review import validate,digest
from composition_revision import compare,protected,require_build_review

class CompositionTests(unittest.TestCase):
 def fixture(self):
  crop={'mode':'fixed-crop','sourceWidth':3840,'sourceHeight':2160,'x':1160,'y':100,'width':720,'height':1280}
  cut={'id':'a','sourceId':'s','sourceInFrame':100,'frames':25,'recordFrame':0}
  spec={'fps':{'numerator':24,'denominator':1},'cuts':[cut],'sources':[{'id':'s','sha256':'source'}],'captions':[{'text':'keep me'}],'framing':{'schema':'acq-edit/framing-v1','receiptSha256':'old','shots':{'a':crop}}}
  ref={'sourceId':'s','sha256':'source','inFrame':100,'frames':25}
  review={'schema':'acq-edit/composition-review-v1','owner':'horizontal-to-vertical','shotsSha256':digest(spec['framing']['shots']),'entries':[{'cutId':'a','panelId':None,'sourceRange':ref,'headBoundsMethod':'manual-silhouette','visualInspection':'source-frames-reviewed','samples':[{'frame':n,'head':[1400,250,1780,600],'evidence':{'path':'frame.jpg','sha256':'x'}} for n in [0,12,24]]}]}
  return spec,review,json.loads((ROOT/'assets/profiles/framing/vertical-dialogue.json').read_text())
 def test_complete_composition_is_not_human_approval(self):
  s,r,p=self.fixture();result=validate(s,r,p);self.assertFalse(result['humanApproved']);self.assertEqual(len(result['samples']),3)
 def test_source_safe_but_too_wide_refuses(self):
  s,r,p=self.fixture();s['framing']['shots']['a'].update(x=700,y=0,width=1215,height=2160);r['shotsSha256']=digest(s['framing']['shots'])
  with self.assertRaisesRegex(ValueError,'subject size'):validate(s,r,p)
 def test_excess_headroom_refuses(self):
  s,r,p=self.fixture();r['entries'][0]['samples'][1]['head']=[1400,450,1780,800]
  with self.assertRaisesRegex(ValueError,'headroom'):validate(s,r,p)
 def test_hair_and_side_safety_refuse(self):
  s,r,p=self.fixture();r['entries'][0]['samples'][1]['head']=[1100,250,1480,600]
  with self.assertRaisesRegex(ValueError,'complete head'):validate(s,r,p)
 def test_sparse_and_stale_observations_refuse(self):
  s,r,p=self.fixture();r['entries'][0]['samples'].pop(1)
  with self.assertRaises(ValueError):validate(s,r,p)
  s,r,p=self.fixture();r['entries'][0]['sourceRange']['inFrame']=101
  with self.assertRaisesRegex(ValueError,'source-clock'):validate(s,r,p)
 def test_fixed_to_tracked_preserves_every_other_plan_field(self):
  s,r,p=self.fixture();new=copy.deepcopy(s);new['framing']['receiptSha256']='new';new['framing']['shots']['a'].update(mode='tracked-crop',xByFrame=[1160]*25,sourceRange=r['entries'][0]['sourceRange'])
  self.assertEqual(compare(s,new,[{'cutId':'a'}]),{('a',None)})
  new['captions'][0]['text']='changed'
  with self.assertRaisesRegex(RuntimeError,'preserves cuts'):compare(s,new,[{'cutId':'a'}])
 def test_new_production_build_requires_review_but_fixture_is_explicit(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);selection=root/'selection.json';receipt=root/'receipt.json'
   selection.write_text('{}');receipt.write_text('{}')
   project={'root':directory};spec={'editorial':{'selectionPath':str(selection)},'framing':{'receiptPath':str(receipt)}}
   with self.assertRaisesRegex(RuntimeError,'composition review'):require_build_review(project,spec)
   selection.write_text('{"testFixture":true}')
   self.assertIsNone(require_build_review(project,spec))
   selection.write_text('{}');receipt.write_text(json.dumps({'schema':'acq-edit/framing-composition-v1','owner':'horizontal-to-vertical','review':'review.json','reviewSha256':'pin'}))
   with patch('composition_revision.checked_review',return_value={'passed':True}) as check:
    self.assertEqual(require_build_review(project,spec),{'passed':True})
    check.assert_called_once_with(project,spec,'review.json','pin')
 def test_protected_graph_rejects_caption_and_audio_changes(self):
  data={'view':{'active_sequence':1},'project':{'name':'edit','root':{'name':'edit'},'items':{'1':{'kind':{'Sequence':{'video_tracks':[{'items':[{'id':3,'effects':[{'effect':'motion','params':{'anchor':{'value':1,'keyframes':[]},'scale':{'value':100},'position':{'value':2}}}]}]}],'audio_tracks':[{'gain':0}],'caption':'original'}}}}}}
  ops=[{'sequence':1,'clip':3}];before=protected(data,ops,'edit');changed=copy.deepcopy(data)
  changed['project']['items']['1']['kind']['Sequence']['video_tracks'][0]['items'][0]['effects'][0]['params']['anchor']['value']=2
  self.assertEqual(before,protected(changed,ops,'edit'))
  changed['project']['items']['1']['kind']['Sequence']['audio_tracks'][0]['gain']=1
  self.assertNotEqual(before,protected(changed,ops,'edit'))
if __name__=='__main__':unittest.main()
