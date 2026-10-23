import copy, json, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path
import xml.etree.ElementTree as E
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'_shared'),str(ROOT/'edit/scripts'),str(ROOT/'caption-clips/scripts')]
from premiere_graph_integrity import materialize_aliases,validate_aliases,connect_owned_track
from pp_export_clips import export_script,TICKS,verify_export
from apply_native_captions import structure_request,BridgeError

class GraphTests(unittest.TestCase):
 def test_metadata_alias_is_materialized_without_source_mutation(self):
  source=E.fromstring('<Root><ModificationState BinaryHash="h" Encoding="base64">YWJj</ModificationState></Root>')
  transferred=E.fromstring('<Node><ModificationState BinaryHash="h"/></Node>');before=E.tostring(transferred)
  out=materialize_aliases([transferred],[source])[0]
  self.assertEqual(out[0].text,'YWJj');self.assertEqual(E.tostring(transferred),before);self.assertEqual(validate_aliases(out),1)
 def test_missing_and_conflicting_payloads_rejected(self):
  with self.assertRaises(ValueError):materialize_aliases([E.fromstring('<Node BinaryHash="missing"/>')],[])
  with self.assertRaises(ValueError):materialize_aliases([E.fromstring('<N BinaryHash="h">a</N>')],[E.fromstring('<N BinaryHash="h">b</N>')])
 def test_master_routing_changes_only_owned_inlet(self):
  r=E.fromstring('<R><Sequence ObjectUID="s"><TrackGroups><TrackGroup><Second ObjectRef="1"/></TrackGroup></TrackGroups></Sequence><AudioTrackGroup ObjectID="1"><TrackGroup><Tracks><Track ObjectURef="music"/></Tracks></TrackGroup><MasterTrack ObjectRef="2"/></AudioTrackGroup><AudioClipTrack ObjectUID="music"/><Master ObjectID="2"><Inlet ObjectRef="3"/></Master><AudioTrackInlet ObjectID="3"><Sources><Source Index="0" ObjectURef="speech"/></Sources></AudioTrackInlet></R>')
  before=[E.tostring(x)for x in list(r)[:-1]]
  receipt=connect_owned_track(r,sequence_uid='s',track_uid='music',expected_sources=['speech'])
  self.assertEqual(receipt['after'],['speech','music']);self.assertEqual(before,[E.tostring(x)for x in list(r)[:-1]])
  with self.assertRaises(ValueError):connect_owned_track(r,sequence_uid='s',track_uid='music',expected_sources=['speech'])
 def test_muted_caption_lane_rejected_before_native_dispatch(self):
  with self.assertRaisesRegex(BridgeError,'visible'):
   structure_request({'artifacts':[{'sha256':'x'}],'track_index':2},{'schema':'edit.caption-transfer-structure/v1','prepared_sha256':'x','expectation':{'tracks':[{'kind':'video','index':2,'muted':True}]}},{})

class ExportTests(unittest.TestCase):
 def setUp(self):
  self.base={'project':'/project.prproj','sequence':'s','state':{'tracks':[],'settings':{}},'in_ticks':'0','out_ticks':str(TICKS*2)}
  self.clip={'start_ticks':str(TICKS*540),'end_ticks':str(TICKS*5418//10)}
 def script(self):return export_script(self.base,self.clip,'/preset.epr','/output.mp4',48000,TICKS//25)
 def run_js(self,fail=False,drift=False):
  node=shutil.which('node')
  if not node:self.skipTest('Node unavailable')
  # Simulate the observed sample-floor defect; an export failure must still restore both marks.
  mock='''var marks={in:0,out:2},calls=0;
var s={sequenceID:'s',videoTracks:{numTracks:0},audioTracks:{numTracks:0},getSettings:function(){return {};},
getInPointAsTime:function(){return {ticks:String(Math.round(marks.in*254016000000))};},
getOutPointAsTime:function(){return {ticks:String(Math.round(marks.out*254016000000))};},
setInPoint:function(v){marks.in=Math.max(0,Math.floor(v*48000-0.0000001)/48000);},
setOutPoint:function(v){marks.out=Math.floor(v*48000-0.0000001)/48000;},
exportAsMediaDirect:function(){calls++;FAIL;return 0;}};
var app={project:{path:'/project.prproj',activeSequence:s},encoder:{ENCODE_IN_TO_OUT:1}};
function File(p){this.exists=p==='/preset.epr';}
'''.replace('FAIL',"throw Error('native failure')" if fail else '')
  if drift:mock+="app.project.path='/other.prproj';"
  mock+='try{var result=(new Function('+json.dumps(self.script())+'))();}catch(e){var error=String(e);}\nconsole.log(JSON.stringify({marks:marks,calls:calls,result:result,error:error}));'
  # Function() runs in the global scope; expose only the mock host bindings.
  mock=mock.replace('try{var result=', 'global.app=app;global.File=File;try{var result=')
  return json.loads(subprocess.check_output([node,'-e',mock],text=True))
 def test_sample_floor_compensation_and_exact_restoration(self):
  z=self.run_js();self.assertNotIn('error',z);self.assertEqual(z['calls'],1);self.assertEqual(z['marks'],{'in':0,'out':2});self.assertEqual(z['result']['expected_frames'],45)
 def test_native_failure_restores_marks(self):
  z=self.run_js(fail=True);self.assertIn('native failure',z['error']);self.assertEqual(z['marks'],{'in':0,'out':2})
 def test_wrong_project_never_exports(self):
  z=self.run_js(drift=True);self.assertIn('TARGET_CHANGED',z['error']);self.assertEqual(z['calls'],0)
 def test_non_frame_range_rejected(self):
  self.clip['start_ticks']='1'
  with self.assertRaises(ValueError):self.script()
 def test_unrestorable_marks_rejected(self):
  self.base['out_ticks']='1'
  with self.assertRaises(ValueError):self.script()

if __name__=='__main__':unittest.main()
