"""Regression evidence for the shipped Premiere framing owner, no host approval."""
import copy, importlib.util, sys, unittest
from pathlib import Path
from fractions import Fraction
from unittest.mock import patch
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
OWNER=ROOT/'distribution/skills/horizontal-to-vertical/scripts'
sys.path.insert(0,str(OWNER))
import premiere_native_reframe as native
import premiere_reframe_bridge as bridge
from filmcraft_smooth_x import smooth_x


def item(start=0,end=1,sin=0,sout=1,index=0):
    return dict(name='fixture',start=start,end=end,source_in=sin,source_out=sout,
                media_path=__file__,track_index=0,item_index=index,speed=1,speed_reversed=False,
                camera_id='a',layout_id='portrait',motion=dict(anchor=[.5,.5],position=[.5,.5],scale=100,
                anchor_time_varying=False,position_time_varying=False,scale_time_varying=False))

def data(xs):
    n=len(xs);raw=[[float(x),.4,.1,.1,.9] for x in xs]
    return dict(width=1920,height=1080,fps=30,frame_ticks=8467200000,relative_times=[i/30 for i in range(n)],
                face_x=smooth_x(xs).tolist(),face_y=[.4]*n,face_y_median=.4,detections=n,samples=n,
                fallback=False,miss_rate=0,edge_face_seen=[True,True],origins=['detected']*n,
                evidence=dict(denseFaces=raw,denseFrameIndices=list(range(n))))

class DensePremiereTests(unittest.TestCase):
    def test_contiguous_splits_are_identical_to_one_filmcraft_curve(self):
        xs=np.linspace(.3,.7,60)+np.sin(np.arange(60))*.01
        items=[item(),item(1,2,1,2,1)]
        with patch.object(native,'track_item',return_value=data(xs)) as detector:
            result=native.dense_tracking_runs(items,[native.PRESETS['podcast']]*2)
        self.assertEqual(detector.call_count,1)
        self.assertEqual(detector.call_args.args[0]['source_out'],2)
        np.testing.assert_allclose(result[0]['face_x']+result[1]['face_x'],smooth_x(xs))
        self.assertEqual(result[1]['relative_times'][0],0)

    def test_source_camera_layout_calibration_and_timeline_boundaries_reset(self):
        for changes in [dict(source_in=4,source_out=5),dict(camera_id='b'),dict(layout_id='split'),dict(start=2,end=3),dict(media_path='/other.mov')]:
            second={**item(1,2,1,2,1),**changes}
            with patch.object(native,'track_item',side_effect=[data([.35]*30),data([.65]*30)]) as detector:
                rows=native.dense_tracking_runs([item(),second],[native.PRESETS['podcast']]*2)
            self.assertEqual(detector.call_count,2)
            self.assertAlmostEqual(rows[1]['face_x'][0],.65)
        with patch.object(native,'track_item',side_effect=[data([.4]*30)]*2) as detector:
            native.dense_tracking_runs([item(),item(1,2,1,2,1)],[native.PRESETS['podcast'],{**native.PRESETS['podcast'],'zoom':1.2}])
            self.assertEqual(detector.call_count,2)

    def test_long_plan_keeps_all_frames_y_locked_even_with_legacy_sparse_flags(self):
        inspection=dict(project_path='/fixture.prproj',sequence_name='fixture',sequence_id='seq',width=1080,height=1920,
                        video_tracks=[dict(clips=[item(0,120,0,120)])])
        with patch.object(native,'track_item',return_value=data(np.linspace(.3,.7,3600))):
            plan=native.build_plan(inspection,'podcast',.5,100)
        row=plan['records'][0]
        self.assertEqual(len(row['anchor_keys']),3600)
        self.assertEqual(len(set(p[2] for p in row['anchor_keys'])),1)
        self.assertEqual(row['frame_ticks'],8467200000)
        self.assertAlmostEqual(row['anchor_keys'][-1][0],3599/30)
        self.assertTrue(all(.158<=p[1]<=.842 for p in row['anchor_keys']))

    def test_native_ticks_remain_exact_at_ntsc_and_bad_coverage_fails(self):
        row={**item(0,1001/1000,1001/1000,1001/500),'node_id':'node','source_id':'src',
             'start_ticks':'0','end_ticks':str(30*8475667200),
             'source_in_ticks':str(30*8475667200),'source_out_ticks':str(60*8475667200)}
        record={**row,'baseline_motion':row['motion'],'position':[.5,.5],'scale_percent':200,
                'frame_ticks':8475667200,'anchor_keys':[[i*1001/30000,.4+i/1000,.5] for i in range(30)]}
        plan=dict(schema='premiere-native-reframe/v1',sequence_dimensions=[1080,1920],project_path='/fixture.prproj',sequence_id='s',
                  bridge_baseline=dict(items=[row],snapshot={'fixture':True},revision='rev'),records=[record])
        op=bridge.fresh_operation(plan,'test')
        self.assertEqual([k['ticks'] for k in op['arguments']['items'][0]['keys']],[str((30+i)*8475667200) for i in range(30)])
        bad=copy.deepcopy(plan);bad['records'][0]['anchor_keys'].pop()
        with self.assertRaisesRegex(bridge.BridgeError,'every displayed frame'):bridge.fresh_operation(bad,'test')
        bad=copy.deepcopy(plan);bad['records'][0]['anchor_keys'][1][0]+=.001
        with self.assertRaisesRegex(bridge.BridgeError,'frame grid'):bridge.fresh_operation(bad,'test')
        bad=copy.deepcopy(plan);bad['tracking_mode']='dense-yunet-shared-smoothing/v1';del bad['records'][0]['frame_ticks']
        with self.assertRaisesRegex(bridge.BridgeError,'exact frame tick grid'):bridge.fresh_operation(bad,'test')

    def test_dense_plan_cannot_use_legacy_simplifier(self):
        from simplify_native_keyframes import simplify_plan
        with self.assertRaisesRegex(ValueError,'every displayed frame'):
            simplify_plan({'records':[{'frame_ticks':8467200000,'anchor_keys':[[0,.5,.5],[1,.5,.5]]}]},.1)

    def test_opted_in_posture_transition_keeps_its_duration_at_dense_rate(self):
        fixture={**data([.5]*120),'face_y':[.3]*45+np.linspace(.3,.5,30).tolist()+[.5]*45}
        values,_=native.discrete_y_values(fixture,0,1)
        self.assertEqual(sum(.3<y<.5 for y in values),29)
        self.assertEqual(values[:30],[.3]*30)
        self.assertEqual(values[-30:],[.5]*30)

    def test_nonconstant_source_rate_fails_before_detection(self):
        import json
        payload={'streams':[{'r_frame_rate':'30/1','avg_frame_rate':'299/10','sample_aspect_ratio':'1:1'}]}
        with patch.object(native.subprocess,'check_output',return_value=json.dumps(payload)):
            with self.assertRaisesRegex(ValueError,'constant-frame-rate'):native.source_clock('source.mp4')

    def test_retimed_items_fail_even_before_a_cache_hit(self):
        for changes in [dict(speed=2),dict(speed_reversed=True),dict(end=2)]:
            with patch.object(native,'track_item') as detector:
                with self.assertRaisesRegex(ValueError,'unit-speed'):native.dense_tracking_runs([{**item(),**changes}],[native.PRESETS['podcast']])
                detector.assert_not_called()

    def test_decoder_visits_every_frame_and_missing_edges_stop(self):
        class Capture:
            def __init__(self,*args):self.pos=0;self.reads=0;self.seeks=[]
            def isOpened(self):return True
            def get(self,p):return {native.cv2.CAP_PROP_FPS:30,native.cv2.CAP_PROP_FRAME_WIDTH:1920,native.cv2.CAP_PROP_FRAME_HEIGHT:1080,native.cv2.CAP_PROP_POS_FRAMES:self.pos}.get(p,0)
            def set(self,p,value):self.seeks.append((p,value));self.pos=value
            def read(self):self.pos+=1;self.reads+=1;return True,np.zeros((10,10,3),np.uint8)
            def release(self):pass
        class Detector:
            def detect(self,frame):return None,None
        for missing in (False,True):
            cap=Capture();choices=[(500+i,400,100,100,.9) for i in range(30)]
            if missing:choices[0]=None
            with patch.object(native,'source_clock',return_value=Fraction(30)),patch.object(native.cv2,'VideoCapture',return_value=cap),patch.object(native,'detector_for',return_value=(Detector(),1920,1080)),patch.object(native,'select_face',side_effect=choices):
                if missing:
                    with self.assertRaisesRegex(ValueError,'Unresolved detector gap'):native._track_item_uncached(item(),native.PRESETS['podcast'],.5)
                else:
                    result=native._track_item_uncached(item(),native.PRESETS['podcast'],.5)
                    self.assertEqual(result['samples'],30)
                    self.assertEqual(result['evidence']['denseFrameIndices'],list(range(30)))
            self.assertEqual(cap.reads,30);self.assertEqual(len(cap.seeks),1)

if __name__=='__main__':unittest.main()
