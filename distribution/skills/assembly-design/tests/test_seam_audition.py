import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('audition',Path(__file__).parents[1]/'scripts/seam_audition.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class CoverageTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.d=Path(self.tmp.name)
        asset=self.d/'audio';asset.write_bytes(b'current pcm');self.asset=m.pin(asset)
        response=self.d/'response';response.write_text('Actual test observation');self.response=m.pin(response)
        self.packet={'schema':'edit.seam-audition-packet/v1','manifest':self.asset,'clips':[{'id':'unit','audio':self.asset,'geometry':self.asset,'routing':self.asset,'regions':[{'id':'head','played':self.asset,'sources':[self.asset]},{'id':'tail','played':self.asset,'sources':[self.asset]},{'id':'full','played':self.asset,'sources':[]}]}]}
        manifest=self.d/'manifest.json';m.save(manifest,{'clips':[{'id':'unit','audio':self.asset,'geometry':self.asset,'routing':self.asset,'segments':[{}]}]});self.packet['manifest']=m.pin(manifest)
        self.p=self.d/'packet.json';m.save(self.p,self.packet)
        self.reviews={'schema':'edit.seam-audition-reviews/v1','packet_sha256':m.digest(self.p),'regions':[self.review('head',[self.asset['sha256']]),self.review('tail',[self.asset['sha256']]),self.review('full',[])]}
    def review(self,rid,sources):
        return dict(clip_id='unit',region_id=rid,status='LISTENED',reviewer='test fixture',method='human_listening',played_sha256=self.asset['sha256'],source_sha256s=sources,response=self.response,observation='Test observation',checks={k:'pass' for k in m.CHECKS},issues=[])
    def runcheck(self):
        p=self.d/'reviews.json';p.write_text(json.dumps(self.reviews));return m.check(self.p,p)
    def test_complete_evidence_is_not_named_perfect(self):
        self.assertEqual(self.runcheck()['status'],'REVIEW_EVIDENCE_COMPLETE')
    def test_missing_full_listening_blocks(self):
        self.reviews['regions'].pop();self.assertEqual(self.runcheck()['status'],'INCOMPLETE')
    def test_reported_clipping_overrides_blanket_pass(self):
        self.reviews['regions'][0]['issues']=['clipped final consonant'];self.assertEqual(self.runcheck()['status'],'REPAIR_REQUIRED')
    def test_uncertainty_is_not_pass(self):
        self.reviews['regions'][0]['checks']['retained_speech']='uncertain';self.assertEqual(self.runcheck()['status'],'REPAIR_REQUIRED')
    def test_wrong_source_comparison_blocks(self):
        self.reviews['regions'][0]['source_sha256s']=[];self.assertEqual(self.runcheck()['status'],'INCOMPLETE')
    def test_audio_change_invalidates_review(self):
        Path(self.asset['path']).write_bytes(b'different pcm')
        with self.assertRaises(ValueError):self.runcheck()
    def test_dropped_boundary_cannot_shrink_coverage(self):
        self.packet['clips'][0]['regions'].pop(1);self.p.write_text(json.dumps(self.packet));self.reviews['packet_sha256']=m.digest(self.p)
        with self.assertRaises(ValueError):self.runcheck()
    def test_unqualified_model_cannot_approve(self):
        self.reviews['regions'][0]['method']='audio_model';self.assertEqual(self.runcheck()['status'],'INCOMPLETE')
    def test_duplicate_observation_blocks(self):
        self.reviews['regions'].append(self.reviews['regions'][0]);self.assertEqual(self.runcheck()['status'],'INCOMPLETE')

if __name__=='__main__':unittest.main()
