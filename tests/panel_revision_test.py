import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
from panel_revision import compare_plans, resolve_changes, protected_fusion, duplicate_snapshot


class PanelRevisionTests(unittest.TestCase):
    def plans(self):
        panels=[]
        for i in range(2):
            span={'sourceId':str(i),'sha256':str(i),'inFrame':25*i,'frames':2}
            crop={'mode':'fixed-crop','sourceWidth':640,'sourceHeight':360,'x':80,'y':20,'width':360,'height':320}
            if not i:crop.update(mode='tracked-crop',sourceRange=copy.deepcopy(span),xByFrame=[80,81])
            panels.append({'id':str(i),'sourceRange':span,'rect':{'x':0,'y':i*320,'width':360,'height':320},'crop':crop})
        layout={'mode':'panel-layout','cameraReceiptPath':'camera','cameraReceiptSha256':'camera-hash','panels':panels}
        old={'width':360,'height':640,'cuts':[{'id':'a'},{'id':'b'}],'captions':[{'text':'keep'}],'audio':{'gain':0},'framing':{'schema':'acq-edit/framing-v1','receiptPath':'old','receiptSha256':'oldhash','shots':{'a':layout,'b':copy.deepcopy(layout)}}}
        new=copy.deepcopy(old);new['framing'].update(receiptPath='new',receiptSha256='newhash');new['framing']['shots']['a']['panels'][0]['crop'].update(x=90,xByFrame=[90,92])
        return old,new,[{'cutId':'a','panelIds':['0']}]

    def test_crop_revision_retains_camera_decision_and_other_panels(self):
        old,new,targets=self.plans();self.assertEqual(compare_plans(old,new,targets),{'a':['0']})
        fields,curves=resolve_changes(new,old['framing']['shots']['a'],new['framing']['shots']['a'],['0'])
        self.assertEqual(fields,{'ACQ_Panel0_Crop':{'XOffset':90}})
        self.assertEqual(len(curves['ACQ_Panel0_PathX']),2)

    def test_layout_movement_requires_new_camera_receipt(self):
        old,new,targets=self.plans();a=new['framing']['shots']['a'];a['panels'][0]['rect']['y']=320;a['panels'][1]['rect']['y']=0;targets[0]['panelIds'].append('1')
        with self.assertRaisesRegex(RuntimeError,'fresh Assembly Design'):compare_plans(old,new,targets)
        a.update(cameraReceiptPath='new-camera',cameraReceiptSha256='new-camera-hash');compare_plans(old,new,targets)
        fields,_=resolve_changes(new,old['framing']['shots']['a'],a,['0','1'])
        self.assertEqual(fields['ACQ_Panel0_Merge']['Center'],{1:.5,2:.25})
        self.assertEqual(fields['ACQ_PanelComposite']['Center'],{1:.5,2:.75})

    def test_scope_cannot_expand_to_sources_cuts_captions_or_unselected_panels(self):
        old,new,targets=self.plans()
        for damage in ['source','sync','cut','caption','audio','unselected-cut','unselected-panel','mode','identity','receipt','camera-receipt','source-size']:
            changed=copy.deepcopy(new);shot=changed['framing']['shots']['a'];panel=shot['panels'][0]
            if damage=='source':panel['sourceRange']['sourceId']='other'
            elif damage=='sync':panel['sourceRange']['inFrame']+=1
            elif damage=='cut':changed['cuts'][0]['frames']=3
            elif damage=='caption':changed['captions'][0]['text']='changed'
            elif damage=='audio':changed['audio']['gain']=-1
            elif damage=='unselected-cut':changed['framing']['shots']['b']['panels'][0]['crop']['x']=90
            elif damage=='unselected-panel':shot['panels'][1]['crop']['x']=90
            elif damage=='mode':panel['crop']['mode']='fixed-crop'
            elif damage=='identity':panel['id']='changed'
            elif damage=='receipt':changed['framing']['receiptSha256']='oldhash'
            elif damage=='camera-receipt':shot['cameraReceiptSha256']='changed'
            else:panel['crop']['sourceWidth']=800
            with self.subTest(damage=damage),self.assertRaises(RuntimeError):compare_plans(old,changed,targets)
        for chosen in [[],[{'cutId':'a','panelIds':[]}],[{'cutId':'a','panelIds':['0','0']}],[{'cutId':'a','panelIds':['missing']}],targets+targets,[{'cutId':'b','panelIds':['0']}]]:
            with self.assertRaises(RuntimeError):compare_plans(old,new,chosen)

    def test_panel_resize_changes_only_crop_resize_and_placement_values(self):
        old,new,targets=self.plans();a=new['framing']['shots']['a'];targets[0]['panelIds'].append('1')
        a['panels'][0]['crop']=copy.deepcopy(old['framing']['shots']['a']['panels'][0]['crop'])
        a['panels'][0]['crop']['width']=480;a['panels'][1]['crop']['width']=288
        a['panels'][0]['rect']['height']=240;a['panels'][1]['rect'].update(y=240,height=400)
        a.update(cameraReceiptPath='new-camera',cameraReceiptSha256='new-camera-hash');compare_plans(old,new,targets)
        fields,curves=resolve_changes(new,old['framing']['shots']['a'],a,['0','1'])
        self.assertEqual(curves,{})
        self.assertEqual(fields,{'ACQ_Panel0_Crop':{'XSize':480},'ACQ_Panel0_Resize':{'Height':240},'ACQ_Panel0_Merge':{'Center':{1:.5,2:.8125}},'ACQ_Panel1_Crop':{'XSize':288},'ACQ_Panel1_Resize':{'Height':400},'ACQ_PanelComposite':{'Center':{1:.5,2:.3125}}})

    def test_protected_graph_retains_every_nonapproved_field(self):
        graph='Composition {Tools={ACQ_Panel0_Crop=Crop {Inputs={XOffset=Input {Value=80},YOffset=Input {Value=20},Input=Input {SourceOp="ACQ_Panel0_Track",Source="Output"}}},ACQ_Panel0_PathX=BezierSpline {KeyFrames={[0]={0.5},[1]={0.6}},SplineColor={Red=1}},ACQ_Panel1_Source=Loader {Inputs={ClipTimeStart=Input {Value=50}}},Caption=TextPlus {Inputs={StyledText=Input {Value="Keep"}}}}}'
        fields={'ACQ_Panel0_Crop':{'XOffset':90}};curves={'ACQ_Panel0_PathX':[.4,.5]}
        baseline=protected_fusion(graph,fields,curves)
        self.assertEqual(baseline,protected_fusion(graph.replace('Value=80','Value=90').replace('[1]={0.6}','[1]={0.4}'),fields,curves))
        for a,b in [('Value=20','Value=21'),('Value=50','Value=51'),('Keep','Changed'),('Source="Output"','Source="Other"'),('Red=1','Red=0')]:
            self.assertNotEqual(baseline,protected_fusion(graph.replace(a,b),fields,curves))
        with self.assertRaisesRegex(RuntimeError,'absent or driven'):protected_fusion(graph.replace('Value=80','Expression="time"'),fields,curves)

    def test_duplicate_comparison_allows_only_new_ids_and_cache_paths(self):
        item={'id':'old','linkedIds':['old'],'fusion':['hash'],'properties':{'Volume':0},'sourcePath':'camera.mp4'}
        state={'timeline':'old-timeline','name':'old-name','tracks':{'video':[[item]]},'settings':{'fps':25}}
        graph='Composition {Prefs={Comp={Paths={Map={["ResolveCaches:"]="/cache/old/Fusion"}}}},Tools={Caption=TextPlus {Inputs={StyledText=Input {Value="Keep"}}}}}'
        key=('video',0,0,0);baseline=duplicate_snapshot(state,{key:graph});changed=copy.deepcopy(state);changed.update(timeline='new-timeline',name='new-name');changed['tracks']['video'][0][0].update(id='new',linkedIds=['new'])
        self.assertEqual(baseline,duplicate_snapshot(changed,{key:graph.replace('/old/','/new/')}))
        self.assertNotEqual(baseline,duplicate_snapshot(changed,{key:graph.replace('Keep','Changed')}))
        changed['tracks']['video'][0][0]['properties']['Volume']=-1
        self.assertNotEqual(baseline,duplicate_snapshot(changed,{key:graph}))
        with self.assertRaisesRegex(RuntimeError,'coverage required'):duplicate_snapshot(state,{})


if __name__=='__main__':unittest.main()
