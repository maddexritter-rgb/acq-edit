import sys
import unittest
import xml.etree.ElementTree as E
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from native_graphics.native_caption_batch_graph import insert_batch


class InsertionTests(unittest.TestCase):
    def fixture(self):
        root=E.fromstring('''<Project><Sequence ObjectUID="seq"><TrackGroups><TrackGroup>
        <Second ObjectRef="1"/></TrackGroup></TrackGroups></Sequence>
        <VideoTrackGroup ObjectID="1"><TrackGroup><Tracks><Track Index="5" ObjectURef="track"/>
        </Tracks></TrackGroup></VideoTrackGroup><VideoClipTrack ObjectUID="track"><ClipTrack>
        <ClipItems><TrackItems><TrackItem Index="0" ObjectRef="old"/></TrackItems></ClipItems>
        </ClipTrack></VideoClipTrack><VideoClipTrackItem ObjectID="new"><ClipTrackItem><TrackItem>
        <Start>100</Start><End>200</End></TrackItem></ClipTrackItem></VideoClipTrackItem></Project>''')
        receipt=[dict(item_id='new',timing=dict(start_ticks='100',end_ticks='200'))]
        return root,receipt

    def run_insert(self,root,receipt,old=('old',)):
        return insert_batch(root,sequence_uid='seq',track_index=5,expected_old_item_ids=old,receipts=receipt)

    def test_uid_track_replacement_changes_only_track(self):
        root,r=self.fixture();before=[E.tostring(n) for n in root]
        self.assertEqual(self.run_insert(root,r)['inserted_count'],1)
        self.assertEqual([i for i,(n,b) in enumerate(zip(root,before)) if E.tostring(n)!=b],[2])

    def test_stale_target_fails_before_mutation(self):
        root,r=self.fixture();before=E.tostring(root)
        with self.assertRaises(ValueError):self.run_insert(root,r,old=('wrong',))
        self.assertEqual(E.tostring(root),before)

    def test_shared_group_rejected(self):
        root,r=self.fixture();E.SubElement(root,'Other',{'ObjectRef':'1'})
        with self.assertRaisesRegex(ValueError,'Shared track group'):self.run_insert(root,r)

    def test_receipt_mismatch_rejected(self):
        root,r=self.fixture();r[0]['timing']['end_ticks']='201'
        with self.assertRaisesRegex(ValueError,'differs from receipt'):self.run_insert(root,r)

    def test_existing_consumer_rejected(self):
        root,r=self.fixture();E.SubElement(root,'Other',{'ObjectRef':'new'})
        with self.assertRaisesRegex(ValueError,'consumer'):self.run_insert(root,r)


if __name__=='__main__':unittest.main()
