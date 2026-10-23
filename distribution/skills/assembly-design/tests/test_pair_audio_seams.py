import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('pairs',Path(__file__).parents[1]/'scripts/pair_audio_seams.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class PairedSeamTests(unittest.TestCase):
    def decision(self):
        return {'schema':'edit.paired-seam-decisions/v1','sample_rate':48000,'fps':'24000/1001','span_count':2,'first_source_frame':0,'last_source_frame':42,'joins':[{'out_window':[19500,20500],'in_window':[59500,60500],'preferred_out':20000,'preferred_in':60000,'reason':'Inspected source releases and onsets','evidence':'fixture','status':'LOCALLY_INSPECTED'}]}
    def test_continuity_and_sync(self):
        r=m.compile_pairs(self.decision());self.assertEqual(r['timeline_samples'][0][1],r['timeline_samples'][1][0]);self.assertEqual(r['joins'][0]['in_source_sample']-r['joins'][0]['out_source_sample'],r['joins'][0]['removed_frames']*2002)
        cursor=0
        for f,s,t in zip(r['source_frames'],r['source_samples'],r['timeline_samples']):
            self.assertEqual(s[0]-t[0],f[0]*2002-cursor);cursor+=(f[1]-f[0])*2002
    def test_does_not_widen_infeasible_windows(self):
        d=self.decision();d['joins'][0].update(out_window=[20000,20000],in_window=[60000,60000])
        with self.assertRaisesRegex(ValueError,'PROVISIONAL'):m.compile_pairs(d)
    def test_rejects_fractional_sample_grid(self):
        d=self.decision();d['fps']='30000/1001'
        with self.assertRaisesRegex(ValueError,'Non-integer'):m.compile_pairs(d)
    def test_rejects_missing_evidence(self):
        d=self.decision();d['joins'][0]['evidence']=''
        with self.assertRaisesRegex(ValueError,'evidence'):m.compile_pairs(d)
    def test_explicit_outer_edges_preserve_internal_continuity(self):
        d=self.decision();d.update(first_source_sample=100,last_source_sample=42*2002-150,outer_edge_evidence='inspected outer source')
        r=m.compile_pairs(d)
        self.assertEqual(r['outer_picture_only_samples'],[100,150])
        self.assertEqual(r['timeline_samples'][0][1],r['timeline_samples'][1][0])
        self.assertEqual(r['timeline_samples'][0][0],100)
    def test_outer_trim_cannot_hide_a_long_gap(self):
        d=self.decision();d.update(first_source_sample=2003,outer_edge_evidence='fixture')
        with self.assertRaisesRegex(ValueError,'enclosing'):m.compile_pairs(d)
    def test_outer_trim_requires_evidence(self):
        d=self.decision();d['first_source_sample']=100
        with self.assertRaisesRegex(ValueError,'evidence'):m.compile_pairs(d)

if __name__=='__main__':unittest.main()
