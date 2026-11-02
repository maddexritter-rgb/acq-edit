import copy, importlib.util, hashlib, tempfile, unittest
from pathlib import Path
import numpy as np
from scipy.signal import savgol_filter
from scipy.ndimage import gaussian_filter1d

path=Path(__file__).resolve().parents[1]/'distribution/skills/horizontal-to-vertical/scripts/filmcraft_smooth_x.py'
spec=importlib.util.spec_from_file_location('dense_x_owner',path)
owner=importlib.util.module_from_spec(spec);spec.loader.exec_module(owner)

class DenseCurveTests(unittest.TestCase):
    def view(self,n=20):
        return {'denseFrameIndices':list(range(n)), 'denseFaces':[[100+i,100,30,40,.9] for i in range(n)]}

    def test_dense_evidence_required_not_sparse_interpolation(self):
        view=self.view();view['denseFrameIndices']=[0,10,19]
        with self.assertRaisesRegex(ValueError,'Every displayed'):owner.dense_subject_x(view,20)
        view=self.view();view['denseFaces'][5][-1]=0
        with self.assertRaisesRegex(ValueError,'manual positions'):owner.dense_subject_x(view,20)

    def test_short_gap_preserves_raw_evidence_and_labels_interpolation(self):
        view=self.view();view['denseFaces'][5:8]=[None]*3;before=copy.deepcopy(view)
        xs,origins=owner.dense_subject_x(view,20)
        np.testing.assert_allclose(xs,np.arange(100,120))
        self.assertEqual(origins[5:8],['interpolated']*3);self.assertEqual(view,before)

    def test_long_or_edge_gap_stops_until_explicit_pinned_fallback(self):
        for start,end in [(0,1),(3,10),(19,20)]:
            view=self.view();view['denseFaces'][start:end]=[None]*(end-start)
            with self.assertRaisesRegex(ValueError,'Unresolved detector gap'):owner.dense_subject_x(view,20)
        with tempfile.TemporaryDirectory() as tmp:
            evidence=Path(tmp)/'source.png';evidence.write_bytes(b'inspected source fixture')
            pin={'path':str(evidence),'sha256':hashlib.sha256(evidence.read_bytes()).hexdigest()}
            fallback={'startFrame':19,'endFrame':20,'x':118,'reason':'Profile turn inspected','evidence':[pin]}
            xs,origins=owner.dense_subject_x(view,20,fallbacks=[fallback])
            self.assertEqual(origins[-1],'manual-fallback');self.assertEqual(xs[-1],118)
            self.assertIsNone(view['denseFaces'][-1])
            evidence.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'pinned inspected'):owner.dense_subject_x(view,20,fallbacks=[fallback])

    def test_smoothing_is_two_stage_and_preserves_static_x(self):
        raw=np.array([0,1,0,2,9,2,3,2,4,5,4,6],float)
        np.testing.assert_allclose(owner.smooth_x(raw,2),gaussian_filter1d(savgol_filter(raw,7,2,mode='interp'),sigma=2,mode='nearest'))
        for count in (1,2,3,6,20):
            np.testing.assert_allclose(owner.smooth_x([300]*count),[300]*count)
        with self.assertRaises(ValueError):owner.smooth_x([1,float('nan')])

    def test_feature_flow_preserves_face_observations_and_reconnects_subject(self):
        with tempfile.TemporaryDirectory() as tmp:
            evidence=Path(tmp)/'inspection.png';evidence.write_bytes(b'inspected head occlusion')
            view={'denseFrameIndices':list(range(30)), 'denseFaces':[[.3+i*.001,.2,.1,.1,.9] for i in range(30)]}
            view['denseFaces'][6:24]=[None]*18;before=copy.deepcopy(view)
            track={'startFrame':5,'endFrame':25,'x':[.3+i*.001 for i in range(5,25)],'reason':'Visible head texture through arm occlusion','evidence':[{'path':str(evidence),'sha256':owner.digest(evidence)}]}
            xs,origins=owner.dense_subject_x(view,30,feature_tracks=[track])
            self.assertEqual(view,before);self.assertEqual(origins[5:25],['reviewed-head-feature-flow']*20)
            np.testing.assert_allclose(xs,[.3+i*.001 for i in range(30)])
            for change in ('endpoint','jump','sparse','hash','unbounded'):
                t=copy.deepcopy(track)
                if change=='endpoint':t['x'][-1]=.7
                elif change=='jump':t['x'][5]=.7
                elif change=='sparse':t['x'].pop()
                elif change=='hash':t['evidence'][0]['sha256']='0'*64
                else:t['startFrame']=-1
                with self.subTest(change=change),self.assertRaises(ValueError):owner.dense_subject_x(view,30,feature_tracks=[t])

    def test_reviewed_occlusion_preserves_missing_evidence_and_checks_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            evidence=Path(tmp)/'frames.png';evidence.write_bytes(b'inspected consecutive frames')
            view={'denseFrameIndices':list(range(24)), 'denseFaces':[[.3+i*.0001,.2,.05,.1,.95] for i in range(24)]}
            view['denseFaces'][5:18]=[None]*13;before=copy.deepcopy(view)
            decision={'startFrame':5,'endFrame':18,'reason':'Brief arm occlusion inspected', 'evidence':[{'path':str(evidence),'sha256':owner.digest(evidence)}]}
            xs,origins=owner.dense_subject_x(view,24,reviewed_occlusions=[decision])
            self.assertEqual(view,before);self.assertEqual(origins[5:18],['reviewed-occlusion-interpolation']*13)
            np.testing.assert_allclose(xs,np.arange(24)*.0001+.3)
            for change in ('subject','observation','edge','duration','hash'):
                v=copy.deepcopy(view);d=copy.deepcopy(decision)
                if change=='subject':v['denseFaces'][18][0]=.7
                elif change=='observation':v['denseFaces'][10]=[.3,.2,.05,.1,.95]
                elif change=='edge':d['startFrame']=0
                elif change=='duration':d.update(startFrame=1,endFrame=21)
                else:d['evidence'][0]['sha256']='0'*64
                with self.subTest(change=change),self.assertRaises(ValueError):owner.dense_subject_x(v,24,reviewed_occlusions=[d])

if __name__=='__main__':unittest.main()
