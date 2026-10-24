import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
from tracking_revision import compare_plans,protected_filmcraft,protected_fusion

class TrackingRevisionTests(unittest.TestCase):
 def plans(self):
  shot={'mode':'tracked-crop','x':10,'xByFrame':[10,11],'y':20,'width':180,'height':320,'sourceWidth':640,'sourceHeight':360,'sourceRange':{'sourceId':'s','sha256':'hash','inFrame':50,'frames':2}}
  old={'cuts':[{'id':'a'},{'id':'b'}],'captions':[{'text':'keep'}],'audio':{'gainDb':0},'framing':{'schema':'acq-edit/framing-v1','receiptPath':'old','receiptSha256':'oldhash','shots':{'a':shot,'b':copy.deepcopy(shot)}}}
  new=copy.deepcopy(old);new['framing'].update(receiptPath='new',receiptSha256='newhash');new['framing']['shots']['a'].update(x=15,xByFrame=[15,16]);return old,new
 def test_only_selected_x_curves_change(self):
  old,new=self.plans();compare_plans(old,new,['a'])
  for mutation in ['y','cuts','caption','unselected','mode','source','receipt']:
   changed=copy.deepcopy(new)
   if mutation=='y':changed['framing']['shots']['a']['y']=21
   elif mutation=='cuts':changed['cuts'][0]['frames']=3
   elif mutation=='caption':changed['captions'][0]['text']='changed'
   elif mutation=='unselected':changed['framing']['shots']['b']['xByFrame']=[14,15]
   elif mutation=='mode':changed['framing']['shots']['a']['mode']='fixed-crop'
   elif mutation=='source':changed['framing']['shots']['a']['sourceRange']['inFrame']=51
   else:changed['framing']['receiptSha256']='oldhash'
   with self.subTest(mutation=mutation),self.assertRaises(RuntimeError):compare_plans(old,changed,['a'])
  for ids in [[],['a','a'],['missing'],['b']]:
   with self.assertRaises(RuntimeError):compare_plans(old,new,ids)
 def test_filmcraft_protection_keeps_other_curves_and_every_non_anchor_field(self):
  old,_=self.plans();item={'effects':[{'effect':'motion','params':{'anchor':{'value':1,'keyframes':[1]},'scale':{'value':100}}}],'source_in':20}
  data={'view':{'active_sequence':1},'project':{'name':'parent','root':{'name':'parent'},'items':{'1':{'kind':{'Sequence':{'video_tracks':[{'items':[item,copy.deepcopy(item)]}],'audio_tracks':[{'gain':0}]}}}}}}
  baseline=protected_filmcraft(data,['a'],old)
  renamed=copy.deepcopy(data);renamed['project']['name']=renamed['project']['root']['name']='revision'
  self.assertEqual(protected_filmcraft(data,['a'],old,'revision'),protected_filmcraft(renamed,['a'],old))
  renamed['project']['root']['name']='unexpected'
  self.assertNotEqual(protected_filmcraft(data,['a'],old,'revision'),protected_filmcraft(renamed,['a'],old))
  changed=copy.deepcopy(data)
  seq=changed['project']['items']['1']['kind']['Sequence'];seq['video_tracks'][0]['items'][0]['effects'][0]['params']['anchor']['keyframes']=[2]
  self.assertEqual(baseline,protected_filmcraft(changed,['a'],old))
  for change in ['audio','scale','other-curve','source']:
   sample=copy.deepcopy(changed);seq=sample['project']['items']['1']['kind']['Sequence'];items=seq['video_tracks'][0]['items']
   if change=='audio':seq['audio_tracks'][0]['gain']=1
   elif change=='scale':items[0]['effects'][0]['params']['scale']['value']=101
   elif change=='other-curve':items[1]['effects'][0]['params']['anchor']['keyframes']=[3]
   else:items[0]['source_in']=21
   self.assertNotEqual(baseline,protected_filmcraft(sample,['a'],old))
 def test_fusion_protection_ignores_only_selected_curve_values(self):
  graph='Composition {Tools={ACQ_FramingCrop=Crop {Inputs={XOffset=Input {Value=100},YOffset=Input {Value=20},Input=Input {SourceOp="ACQ_FramingTrack",Source="Output"}}},ACQ_FramingPathX=BezierSpline {KeyFrames={[0]={0.5},[1]={0.6}},SplineColor={Red=1}},Other=TextPlus {Inputs={StyledText=Input {Value="Keep"}}}}}'
  baseline=protected_fusion(graph)
  self.assertEqual(baseline,protected_fusion(graph.replace('Value=100','Value=110').replace('[1]={0.6}','[1]={0.7}')))
  for a,b in [('Value=20','Value=21'),('Keep','Changed'),('Source="Output"','Source="Other"'),('Red=1','Red=0')]:
   self.assertNotEqual(baseline,protected_fusion(graph.replace(a,b)))
  with self.assertRaises(RuntimeError):protected_fusion(graph.replace('ACQ_FramingPathX','ForeignDriver'))

if __name__=='__main__':unittest.main()
