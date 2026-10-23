import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from native_graphics.native_graph_clone import clone_graph, place_graph


class GraphCloneTests(unittest.TestCase):
    def root(self):
        return ET.fromstring('<Project><Item ObjectID="1"><Chain ObjectRef="2"/>'
            '<Source ObjectRef="3"/></Item><Chain ObjectID="2"><Owner ObjectRef="1"/>'
            '<Master ObjectURef="master"/></Chain><Source ObjectID="3"/></Project>')

    def test_cycles_remapped_and_shared_source_preserved(self):
        root=self.root();before=ET.tostring(root)
        result=clone_graph(root,'1',shared_ids={'3'},allowed_external_uids={'master'})
        self.assertEqual(result['mapping'],{'1':'4','2':'5'})
        self.assertEqual(result['nodes'][0].find('Source').get('ObjectRef'),'3')
        self.assertEqual(result['nodes'][1].find('Owner').get('ObjectRef'),'4')
        self.assertEqual(before,ET.tostring(root))

    def test_undeclared_uid_rejected(self):
        with self.assertRaisesRegex(ValueError,'UID reference'):
            clone_graph(self.root(),'1',shared_ids={'3'},allowed_external_uids=set())

    def test_dangling_reference_rejected(self):
        root=self.root();root[0].find('Chain').set('ObjectRef','99')
        with self.assertRaisesRegex(ValueError,'Dangling'):
            clone_graph(root,'1',shared_ids={'3'},allowed_external_uids={'master'})

    def test_repeated_cloning_after_append_uses_new_ids(self):
        root=self.root()
        a=clone_graph(root,'1',shared_ids={'3'},allowed_external_uids={'master'})
        root.extend(a['nodes'])
        b=clone_graph(root,'1',shared_ids={'3'},allowed_external_uids={'master'})
        self.assertFalse(set(a['mapping'].values()) & set(b['mapping'].values()))

    def timing_graph(self):
        root=ET.fromstring('<Project><VideoClipTrackItem ObjectID="1"><ClipTrackItem>'
            '<SubClip ObjectRef="2"/><TrackItem><Start>0</Start><End>50</End></TrackItem>'
            '</ClipTrackItem></VideoClipTrackItem><SubClip ObjectID="2"><Clip ObjectRef="3"/>'
            '</SubClip><VideoClip ObjectID="3"><Clip><InPoint>1000</InPoint>'
            '<OutPoint>1050</OutPoint><ClipID>old</ClipID></Clip></VideoClip>'
            '<Keys ObjectID="4"><Keyframes>1000,0;1010,1</Keyframes></Keys></Project>')
        return {'seed_id':'1','nodes':list(root)}

    def test_cut_continuation_advances_source_without_restarting_keys(self):
        graph=self.timing_graph()
        keys=ET.tostring(graph['nodes'][3])
        result=place_graph(graph,start_ticks=20,end_ticks=50,animation_elapsed_ticks=20)
        self.assertEqual(result['source_in_ticks'],'1020')
        self.assertEqual(result['source_out_ticks'],'1050')
        self.assertEqual(result['donor_duration_ticks'],'50')
        self.assertEqual(keys,ET.tostring(graph['nodes'][3]))
        self.assertEqual(graph['nodes'][2].findtext('Clip/InPoint'),'1020')

    def test_default_entrance_and_bad_elapsed(self):
        self.assertEqual(place_graph(self.timing_graph(),start_ticks=0,end_ticks=20)['source_in_ticks'],'1000')
        for bad in (-1,1.5,True):
            graph=self.timing_graph();before=[ET.tostring(n) for n in graph['nodes']]
            with self.assertRaises(ValueError):
                place_graph(graph,start_ticks=0,end_ticks=20,animation_elapsed_ticks=bad)
            self.assertEqual(before,[ET.tostring(n) for n in graph['nodes']])

    def test_saved_zero_start_can_be_implicit(self):
        graph=self.timing_graph();track=graph['nodes'][0].find('ClipTrackItem/TrackItem')
        track.remove(track.find('Start'))
        place_graph(graph,start_ticks=50,end_ticks=80)
        self.assertEqual(track.findtext('Start'),'50')


if __name__=='__main__':unittest.main()
