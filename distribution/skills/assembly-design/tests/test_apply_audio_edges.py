import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import hashlib

spec=importlib.util.spec_from_file_location('audio_edges',Path(__file__).parents[1]/'scripts/apply_audio_edges.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


class AudioPlanTest(unittest.TestCase):
    def fixture(self):
        expected={'fps':'30','items':[{'media':'/source.mov','timeline_frames':[0,30],'source_frames':[30,60]}]}
        mapping=[{'assembly_item_index':0,'audio_node_id':'a','source_node_id':'s'}]
        links={'items':[{'kind':'audio','item':{'node_id':'a','source_id':'s','media_path':'/source.mov','start_ticks':'0','end_ticks':str(m.TPS),'source_in_ticks':str(m.TPS),'source_out_ticks':str(m.TPS*2)}}]}
        plan={'sample_rate':48000,'cuts':[{'assembly_item_index':0,'source_samples':[48001,95999]}]}
        return plan,expected,mapping,links

    def test_bind_keeps_sample_edges_and_sync(self):
        p,e,n,l=self.fixture();r=m.bind(p,e,n,l)['items'][0]
        self.assertEqual(r['after']['start'],'5292000')
        self.assertEqual(int(r['after']['end']),m.TPS-5292000)
        self.assertEqual(int(r['after']['inPoint'])-int(r['after']['start']),m.TPS)

    def test_changed_source_or_geometry_rejected(self):
        p,e,n,l=self.fixture();l['items'][0]['item']['source_in_ticks']=str(m.TPS+1)
        with self.assertRaisesRegex(m.BridgeError,'differs'):m.bind(p,e,n,l)

    def test_stale_expected_receipt_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);expected=d/'expected.json';expected.write_text('{}');p=d/'plan.json'
            p.write_text(json.dumps({'schema':'edit.assembly-audio-edges/v1','expected_sha256':'0'*64}))
            with self.assertRaisesRegex(m.BridgeError,'pin'):m.load_plan(p,expected,hashlib.sha256(expected.read_bytes()).hexdigest())

    def test_fractional_clock_cannot_silently_shift_sync(self):
        p,e,n,l=self.fixture();e['fps']='30000/1001';e['items'][0]['timeline_frames']=[1,31]
        ft=m.Fraction(m.TPS)*1001/30000
        a=l['items'][0]['item'];a.update(start_ticks=str(int(ft)),end_ticks=str(int(ft*31)),source_in_ticks=str(int(ft*30)),source_out_ticks=str(int(ft*60)))
        with self.assertRaisesRegex(m.BridgeError,'sample grid'):m.bind(p,e,n,l)


if __name__=='__main__':unittest.main()
