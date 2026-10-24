"""Recut dependency/immutability tests, not editorial or host acceptance."""
import copy,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch,Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
import recut_execution as recut
from common import sha,fingerprint

class RecutTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  work=self.root/'10_WORK';work.mkdir();archive=self.root/'20_DELIVER/clip/v1-parent';archive.mkdir(parents=True)
  self.project={'id':'project','root':str(self.root),'backend':'filmcraft'}
  prior={'projectId':'project','backend':'filmcraft','clipId':'clip','fps':{'numerator':25,'denominator':1},'sampleRate':48000,'width':640,'height':360,'editorial':{'sha256':'old-selection'},'cuts':[{'id':'old'}]}
  self.spec={**prior,'editorial':{'sha256':'new-selection'},'cuts':[{'id':'new'}],'captions':[],'framing':{},'audio':{},'graphics':[]}
  def write(p,obj):p.write_text(json.dumps(obj));return str(p)
  self.write=write
  native=archive/'native.fcproj';native.write_text('native fixture');media=archive/'clip.mp4';media.write_text('media fixture')
  inspection=write(archive/'inspection.json',{'testFixture':True})
  plan=write(archive/'plan.json',prior);receipt=write(archive/'receipt.json',{'projectId':'project','clipId':'clip','backend':'filmcraft','nativeFingerprint':sha(native)})
  self.version={'id':'parent','clipId':'clip','number':1,'nativeProject':str(native),'nativeCheckpoint':str(native),'nativeFingerprint':sha(native),'media':str(media),'sha256':sha(media),'planPath':plan,'planSha256':sha(plan),'inspectionPath':inspection,'inspectionSha256':sha(inspection),'receiptPath':receipt,'receiptSha256':sha(receipt)}
  v=write(archive/'version.json',self.version);new=write(work/'new-plan.json',self.spec)
  self.proof={'schema':'acq-edit/recut-finishing-v1','parentVersionId':'parent','parentPlanSha256':self.version['planSha256'],'planSha256':sha(new),'cutsFingerprint':fingerprint(self.spec['cuts']),'components':{key:{'owner':owner,'action':'not-used','reason':'Synthetic omitted layer','valueFingerprint':fingerprint(recut.component(self.spec,key))} for key,owner in recut.OWNERS.items()}}
  proof=write(work/'finishing.json',self.proof)
  self.packet={'kind':'spoken-recut','parentVersion':v,'parentId':'parent','plan':new,'finishingReceipt':proof,'finishingSha256':sha(proof),'construction':{'plan':new,'output':str(work/'new-native')},'verification':str(work/'verification.json')}
  self.mock=patch.object(recut,'plan',side_effect=lambda *args: self.spec);self.mock.start();self.addCleanup(self.mock.stop)
 def refresh_proof(self):
  self.write(Path(self.packet['finishingReceipt']),self.proof);self.packet['finishingSha256']=sha(self.packet['finishingReceipt'])
 def test_complete_dependencies_bind_exact_parent_and_new_plan(self):
  p=recut.prepare(self.project,self.packet)
  self.assertEqual(p['expected'],fingerprint({'state':{'testFixture':True},'fileHash':self.version['nativeFingerprint']}))
  result=recut.record(self.project,self.packet,p,{'nativeProject':self.version['nativeCheckpoint'],'fingerprint':'new'})
  self.assertEqual(result['parentId'],'parent');self.assertTrue(Path(result['recutVerification']).exists())
 def test_missing_owner_stale_layer_or_other_parent_refused(self):
  original=copy.deepcopy(self.proof)
  for kind in ['missing','stale','parent']:
   self.proof=copy.deepcopy(original)
   if kind=='missing':del self.proof['components']['captions']
   if kind=='stale':self.proof['components']['captions']['valueFingerprint']='old'
   if kind=='parent':self.proof['parentVersionId']='other'
   self.refresh_proof()
   with self.assertRaises(RuntimeError):recut.prepare(self.project,self.packet)
 def test_visibility_requires_new_caption_and_hook_context_decisions(self):
  self.spec['captionVisibility']={'hiddenRanges':[{'startFrame':0,'endFrame':10}]}
  self.write(Path(self.packet['plan']),self.spec);self.proof['planSha256']=sha(self.packet['plan']);self.refresh_proof()
  with self.assertRaisesRegex(RuntimeError,'Dependent layer differs.*captions'):recut.prepare(self.project,self.packet)
  caption=self.proof['components']['captions'];caption['valueFingerprint']=fingerprint(recut.component(self.spec,'captions'));self.refresh_proof()
  with self.assertRaisesRegex(RuntimeError,'Nonempty layer'):recut.prepare(self.project,self.packet)
  caption['action']='recomputed';self.refresh_proof()
  with self.assertRaisesRegex(RuntimeError,'Dependent layer differs.*textHook'):recut.prepare(self.project,self.packet)
  hook=self.proof['components']['textHook'];hook['valueFingerprint']=fingerprint(recut.component(self.spec,'textHook'));hook['action']='recomputed';self.refresh_proof()
  recut.prepare(self.project,self.packet)
  # Removing the mask changes both owner fingerprints too.
  del self.spec['captionVisibility'];self.write(Path(self.packet['plan']),self.spec);self.proof['planSha256']=sha(self.packet['plan']);self.refresh_proof()
  with self.assertRaisesRegex(RuntimeError,'Dependent layer differs.*captions'):recut.prepare(self.project,self.packet)
 def test_old_publications_need_explicit_reconciliation(self):
  del self.version['inspectionSha256'];self.write(Path(self.packet['parentVersion']),self.version)
  with self.assertRaisesRegex(RuntimeError,'lacks pinned'):recut.prepare(self.project,self.packet)
 def test_changed_archived_plan_or_native_refused(self):
  for key in ['planPath','nativeCheckpoint','inspectionPath','receiptPath','media']:
   p=Path(self.version[key]);original=p.read_bytes();p.write_text('changed')
   with self.assertRaisesRegex(RuntimeError,'evidence changed'):recut.prepare(self.project,self.packet)
   p.write_bytes(original)
 def test_construction_cannot_use_other_plan_or_existing_destination(self):
  self.packet['construction']['plan']=str(self.root/'10_WORK/other-plan.json')
  with self.assertRaisesRegex(RuntimeError,'another plan'):recut.prepare(self.project,self.packet)
  self.packet['construction']['plan']=self.packet['plan'];Path(self.packet['construction']['output']).mkdir()
  with self.assertRaisesRegex(RuntimeError,'output exists'):recut.prepare(self.project,self.packet)
 def test_selection_or_canvas_cannot_silently_stay_stale(self):
  self.spec['editorial']['sha256']='old-selection'
  with self.assertRaisesRegex(RuntimeError,'fresh source-word'):recut.prepare(self.project,self.packet)
  self.spec['editorial']['sha256']='new-selection';self.spec['width']=360
  with self.assertRaisesRegex(RuntimeError,'clocks and canvas'):recut.prepare(self.project,self.packet)
 def test_parent_or_planner_mutation_during_build_prevents_success_receipt(self):
  prepared=recut.prepare(self.project,self.packet);Path(self.version['media']).write_text('changed')
  with self.assertRaisesRegex(RuntimeError,'parent changed'):recut.record(self.project,self.packet,prepared,{})
  self.assertFalse(Path(self.packet['verification']).exists())
 def test_resolve_uses_published_snapshot_not_file_hash(self):
  self.project['backend']='resolve';self.spec['backend']='resolve'
  for key in ['planPath','receiptPath']:
   data=json.loads(Path(self.version[key]).read_text());data['backend']='resolve';self.write(Path(self.version[key]),data)
  self.version['planSha256']=sha(self.version['planPath']);self.version['receiptSha256']=sha(self.version['receiptPath']);self.write(Path(self.packet['parentVersion']),self.version)
  self.proof['parentPlanSha256']=self.version['planSha256'];self.refresh_proof()
  self.packet['construction']={'plan':self.packet['plan'],'nativeProject':str(self.root/'10_WORK/new.drp'),'inspection':str(self.root/'10_WORK/inspection.json'),'versionId':'new'}
  self.assertEqual(recut.prepare(self.project,self.packet)['expected'],fingerprint({'testFixture':True}))
 def test_resolve_duplicate_name_refuses_before_project_settings_or_import(self):
  import resolve
  p=Mock();p.GetName.return_value='ACQ_project';p.GetTimelineCount.return_value=1;p.GetTimelineByIndex.return_value.GetName.return_value='Test_existing';p.IsRenderingInProgress.return_value=False
  r=Mock();r.GetProjectManager.return_value.GetCurrentProject.return_value=p
  spec={'title':'Test','cuts':[],'fps':{'numerator':25,'denominator':1},'sampleRate':48000,'width':640,'height':360}
  adapter=resolve.Adapter({});packet={'nativeProject':str(self.root/'10_WORK/new.drp'),'inspection':str(self.root/'10_WORK/new.json'),'versionId':'existing'}
  with patch.object(resolve,'plan',return_value=spec),patch.object(adapter,'connect',return_value=r):
   with self.assertRaisesRegex(RuntimeError,'timeline name exists'):adapter.build(self.project,packet)
  p.SetSettings.assert_not_called();p.GetMediaPool.assert_not_called()
 def test_caption_intervals_cannot_outlive_recut(self):
  import common
  work=self.root/'10_WORK';selection=self.write(work/'synthetic-selection.json',{'testFixture':True});brain=self.write(work/'brain.json',{'testFixture':True})
  spec={**self.spec,'schema':'acq-edit/plan-v1','brain':{'receiptPath':brain,'sha256':sha(brain)},'editorial':{'selectionPath':selection,'sha256':sha(selection),'reviewed':True},'sources':[], 'cuts':[{'recordFrame':0,'frames':25,'wordIds':['fixture'],'boundaryEvidence':'synthetic'}],'captions':[{'startFrame':0,'endFrame':50,'text':'Stale','style':{}}]}
  path=self.write(work/'bad-captions.json',spec)
  with patch.dict('os.environ',{'ACQ_EDIT_TEST_FIXTURE':'1'}),self.assertRaisesRegex(RuntimeError,'Caption timing'):common.plan(self.project,{'plan':path})

if __name__=='__main__':unittest.main()
