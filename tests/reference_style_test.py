"""Reference ownership/provenance contracts, not evidence of viewing or fidelity."""
import copy,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'python'))
from common import sha,save,result_receipt
import reference_style as reference

class ReferenceStyleTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);(self.root/'00_SOURCE').mkdir();(self.root/'10_WORK').mkdir()
  self.project={'id':'p','backend':'resolve','root':str(self.root)};self.source=self.root/'00_SOURCE/ref.mp4';self.source.write_bytes(b'synthetic source stand-in; probe mocked')
  self.evidence=self.root/'10_WORK/watch.txt';self.evidence.write_text('Explicit synthetic contract fixture; not a viewed clip.')
  self.recipe={'sourceSha256':sha(self.source),'durationSeconds':2,'coverage':{'fullVideoViewed':True,'audioListened':True,'evidence':['report'],'denseIntervals':[{'start':0,'end':.2,'evidence':['report']}]},'segments':[{'start':0,'end':2,'category':c,'basis':'observed','observation':'Synthetic fixture '+c,'evidence':['report']} for c in sorted(reference.CATEGORIES)],'unsupportedEffects':[]}
  self.origin=self.root/'10_WORK/recipe.json';save(self.origin,self.recipe)
  self.snapshot={'schema':'acq-edit/reference-style-v1','owner':'watch','projectId':'p','backend':'resolve','source':{'path':str(self.source),'sha256':sha(self.source)},'hasAudio':True,'recipeOrigin':{'path':str(self.origin),'sha256':sha(self.origin)},'recipe':copy.deepcopy(self.recipe),'evidenceFiles':[{'id':'report','path':str(self.evidence),'sha256':sha(self.evidence)}],'coverageStatus':'reported-by-watch-owner','humanApproved':False}
 def test_working_recipe_changes_do_not_rewrite_frozen_reference(self):
  self.origin.write_text('{"new":"guidance"}')
  result=reference.validate_snapshot(self.project,self.snapshot)
  self.assertEqual(result['recipe'],self.recipe);self.assertFalse(result['humanApproved'])
 def test_all_backends_can_bind_the_same_owner_without_loading_an_editor(self):
  for backend in ['filmcraft','premiere','resolve']:
   p={**self.project,'backend':backend};snapshot={**self.snapshot,'backend':backend}
   self.assertEqual(reference.validate_snapshot(p,snapshot)['owner'],'watch')
 def test_changed_source_and_inspection_evidence_are_refused(self):
  for file in [self.source,self.evidence]:
   original=file.read_bytes();file.write_bytes(b'changed')
   with self.assertRaisesRegex(RuntimeError,'changed or missing'):reference.validate_snapshot(self.project,self.snapshot)
   file.write_bytes(original)
 def test_partial_coverage_missing_categories_and_unpinned_citations_are_refused(self):
  for change in [lambda s:s['recipe']['coverage'].update(fullVideoViewed=False),lambda s:s['recipe']['coverage'].update(audioListened=False),lambda s:s['recipe']['segments'].pop(),lambda s:s['recipe']['segments'][0].update(evidence=['missing']),lambda s:s['recipe']['segments'][0].update(end=3),lambda s:s['recipe']['segments'][0].update(basis='proven'),lambda s:s.update(humanApproved=True),lambda s:s.update(backend='premiere')]:
   s=copy.deepcopy(self.snapshot);change(s)
   with self.assertRaises(RuntimeError):reference.validate_snapshot(self.project,s)
 def test_absent_audio_is_explicit_and_cannot_claim_listening(self):
  self.snapshot['hasAudio']=False
  with self.assertRaisesRegex(RuntimeError,'absent'):reference.validate_snapshot(self.project,self.snapshot)
  self.snapshot['recipe']['coverage'].update(audioAbsent=True,audioListened=False)
  reference.validate_snapshot(self.project,self.snapshot)
 def test_prepare_writes_new_snapshot_and_plan_and_refuses_overwrite(self):
  snapshot=self.root/'10_WORK/frozen.json';output=self.root/'10_WORK/bound.json';spec={'projectId':'p','backend':'resolve','cuts':[{'id':'unchanged'}]}
  packet={'plan':'ignored by explicit test stub','recipe':str(self.origin),'recipeSha256':sha(self.origin),'source':self.snapshot['source'],'evidenceFiles':self.snapshot['evidenceFiles'],'snapshot':str(snapshot),'output':str(output)}
  probe=type('Probe',(),{'stdout':json.dumps({'streams':[{'codec_type':'video'},{'codec_type':'audio'}]})})()
  with patch.object(reference,'plan',return_value=spec),patch.object(reference.subprocess,'run',return_value=probe):
   result=reference.prepare_plan(self.project,packet)
   with self.assertRaisesRegex(RuntimeError,'distinct new'):reference.prepare_plan(self.project,packet)
  bound=json.loads(output.read_text());self.assertEqual(bound['cuts'],spec['cuts']);self.assertEqual(result['referenceStyle']['sha256'],sha(snapshot));reference.validate(self.project,bound)
  snapshot.write_text('{}')
  with self.assertRaisesRegex(RuntimeError,'changed or missing'):reference.validate(self.project,bound)

 def test_render_receipt_embeds_frozen_recipe_and_refuses_changed_evidence(self):
  work=self.root/'10_WORK';snapshot=work/'snapshot.json';save(snapshot,self.snapshot)
  selection=work/'selection.json';save(selection,{'testFixture':True})
  spec={'clipId':'c','cuts':[{'frames':25}],'width':160,'height':90,'fps':{'numerator':25,'denominator':1},'editorial':{'selectionPath':str(selection)},'referenceStyle':{'path':str(snapshot),'sha256':sha(snapshot)},'sources':[],'graphics':[]}
  planfile=work/'plan.json';save(planfile,spec);native=work/'native.fixture';native.write_text('Synthetic stand-in');media=work/'render.fixture';media.write_text('Synthetic render stand-in')
  packet={'plan':str(planfile),'receipt':str(work/'receipt.json')}
  receipt=result_receipt(self.project,packet,spec,native,media,work/'inspection.json',verification={'synthetic':True})
  self.assertEqual(receipt['referenceEvidence'],{'contract':spec['referenceStyle'],'snapshot':self.snapshot})
  self.evidence.write_text('changed after render');packet['receipt']=str(work/'rejected.json')
  with self.assertRaisesRegex(RuntimeError,'changed or missing'):result_receipt(self.project,packet,spec,native,media,work/'inspection.json',verification={'synthetic':True})
  self.assertFalse((work/'rejected.json').exists());self.assertTrue((work/'receipt.json').exists())

if __name__=='__main__':unittest.main()
