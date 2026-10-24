"""Framing transport protects source clocks and every native key, not subject choice."""
import copy,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
from common import sha
from framing_plan import validate_framing,verify_filmcraft_framing
from resolve_framing import verify_linear_keys,track_positions

class TrackingTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  receipt=self.root/'decision.json';receipt.write_text('{}');self.project={'root':str(self.root)}
  self.cut={'id':'cut','sourceId':'source','recordFrame':25,'sourceInFrame':50,'frames':3}
  self.shot={'mode':'tracked-crop','sourceWidth':640,'sourceHeight':360,'x':100.25,'y':20,'width':180,'height':320,'xByFrame':[100.25,100.5,101.0],'sourceRange':{'sourceId':'source','sha256':'hash','inFrame':50,'frames':3}}
  self.spec={'backend':'resolve','fps':{'numerator':25,'denominator':1},'width':360,'height':640,'cuts':[self.cut],'sources':[{'id':'source','sha256':'hash','path':'source.mp4'}],'framing':{'schema':'acq-edit/framing-v1','receiptPath':str(receipt),'receiptSha256':sha(receipt),'shots':{'cut':self.shot}}}
  self.probe=patch('framing_plan.subprocess.check_output',return_value=json.dumps({'streams':[{'width':640,'height':360,'sample_aspect_ratio':'1:1','r_frame_rate':'25/1','avg_frame_rate':'25/1'}]}).encode());self.probe.start();self.addCleanup(self.probe.stop)
 def test_fractional_tracking_is_preserved_and_bound_to_source_range(self):
  self.assertEqual(validate_framing(self.project,self.spec)['cut']['xByFrame'],[100.25,100.5,101.0])
  for key,value in [('sourceInFrame',51),('frames',4),('sourceId','other')]:
   spec=copy.deepcopy(self.spec);spec['cuts'][0][key]=value
   if key=='sourceId':spec['sources'].append({'id':'other','sha256':'otherhash','path':'other.mp4'})
   with self.assertRaisesRegex(RuntimeError,'Tracking source range changed'):validate_framing(self.project,spec)
  spec=copy.deepcopy(self.spec);spec['sources'][0]['sha256']='changed'
  with self.assertRaisesRegex(RuntimeError,'Tracking source range changed'):validate_framing(self.project,spec)
 def test_incomplete_out_of_bounds_or_unsupported_curves_are_refused(self):
  for xs in [[100.25,100.5],[100.25,float('nan'),101],[100.25,461,101],[100.25,True,101],[101,102,103]]:
   spec=copy.deepcopy(self.spec);spec['framing']['shots']['cut']['xByFrame']=xs
   with self.assertRaises(RuntimeError):validate_framing(self.project,spec)
  spec=copy.deepcopy(self.spec);spec['fps']['numerator']=30
  with self.assertRaisesRegex(RuntimeError,'matching constant source/timeline'):validate_framing(self.project,spec)
  spec=copy.deepcopy(self.spec);spec['backend']='premiere'
  with self.assertRaisesRegex(RuntimeError,'selected FilmCraft or Resolve'):validate_framing(self.project,spec)
 def test_typed_native_key_verifier_catches_retiming_easing_and_y_motion(self):
  ft=10
  m={'anchor':{'value':{'Vec2':{'x':190.25,'y':180}},'keyframes':[{'time':(50+i)*ft,'interp':'Linear','value':{'Vec2':{'x':x+90,'y':180}}} for i,x in enumerate(self.shot['xByFrame'])]},'position':{'value':{'Vec2':{'x':180,'y':320}},'keyframes':[]},'scale':{'value':{'Float':200},'keyframes':[]}}
  item={'start':250,'source_in':500,'duration':30,'effects':[{'effect':'motion','params':m}]}
  data={'view':{'active_sequence':1},'project':{'items':{'1':{'kind':{'Sequence':{'video_tracks':[{'items':[item]}]}}}}}}
  def verify(value):
   file=self.root/'native.json';file.write_text(json.dumps(value));verify_filmcraft_framing(file,self.spec,ft)
  verify(data)
  for field,value in [('time',251),('interp','Bezier'),('value',{'Vec2':{'x':190.5,'y':181}})]:
   changed=copy.deepcopy(data);changed['project']['items']['1']['kind']['Sequence']['video_tracks'][0]['items'][0]['effects'][0]['params']['anchor']['keyframes'][1][field]=value
   with self.assertRaisesRegex(RuntimeError,'clock/curve differs'):verify(changed)

 def test_resolve_subpixel_translation_and_native_relative_handles(self):
  xs=track_positions(self.shot);self.assertAlmostEqual(xs[0],.5-.25/640)
  start=50;keys={}
  for i,x in enumerate(xs):
   key={1:x}
   for handle,neighbor in [('LH',i-1),('RH',i+1)]:
    if 0<=neighbor<len(xs):key[handle]={1:(neighbor-i)/3,2:(xs[neighbor]-x)/3}
   keys[start+i]=key
  verify_linear_keys(keys,start,xs)
  for alteration in ['time','ease','step','value']:
   changed=copy.deepcopy(keys)
   if alteration=='time':changed[51.5]=changed.pop(51)
   elif alteration=='ease':changed[51]['RH'][2]+=.01
   elif alteration=='step':changed[51]['Flags']={'StepIn':True}
   else:changed[51][1]+=.01
   with self.assertRaises(RuntimeError):verify_linear_keys(changed,start,xs)

if __name__=='__main__':unittest.main()
