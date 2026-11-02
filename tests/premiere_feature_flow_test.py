"""Real frame decoding and tracking regression through a bounded reviewed ROI."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
import cv2
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('native_reframe_test',ROOT/'distribution/skills/horizontal-to-vertical/scripts/premiere_native_reframe.py')
owner=importlib.util.module_from_spec(spec);spec.loader.exec_module(owner)

class FeatureFlow(unittest.TestCase):
    def test_tracks_every_decoded_frame_and_preserves_missing_face_label(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);media=root/'source.avi';evidence=root/'inspection.png'
            rng=np.random.default_rng(42)
            frame=np.zeros((180,320,3),np.uint8)
            frame[50:110,80:150]=rng.integers(0,256,(60,70,3),dtype=np.uint8)
            cv2.imwrite(str(evidence),frame)
            writer=cv2.VideoWriter(str(media),cv2.VideoWriter_fourcc(*'MJPG'),24,(320,180))
            self.assertTrue(writer.isOpened())
            for i in range(16):writer.write(cv2.warpAffine(frame,np.float32([[1,0,i],[0,1,0]]),(320,180)))
            writer.release()
            pin={'path':str(evidence),'sha256':owner.__dict__['dense_subject_x'].__globals__['digest'](evidence)}
            result=owner.reviewed_feature_track(media,0,16,[80,50,150,110],.35,[pin])
            self.assertEqual(len(result['x']),16);self.assertFalse(result['faceDetections'])
            self.assertEqual([r['frame'] for r in result['observations']],list(range(16)))
            np.testing.assert_allclose(result['x'],.35+np.arange(16)/320,atol=.0015)
            with self.assertRaises(ValueError):owner.reviewed_feature_track(media,0,16,[0,0,30,30],.35,[pin])
            evidence.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'pinned'):owner.reviewed_feature_track(media,0,16,[80,50,150,110],.35,[pin])

if __name__=='__main__':unittest.main()
