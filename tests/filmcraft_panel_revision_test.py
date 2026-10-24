import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
from filmcraft_panels import revision_operations, protected_revision


class FilmcraftPanelRevisionTests(unittest.TestCase):
    def fixture(self):
        from panel_layout_test import PanelLayoutTests
        fixture=PanelLayoutTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        old=fixture.spec;data=fixture.native();data['project'].update(name='parent',root={'name':'parent'})
        for identity in ['1','2','3','4']:
            for index,track in enumerate(data['project']['items'][identity]['kind']['Sequence']['video_tracks']):track['items'][0]['id']=int(identity)*10+index
        new=copy.deepcopy(old);panels=new['framing']['shots']['cut']['panels'];panels[0]['rect']['y']=320;panels[1]['rect']['y']=0;panels[0]['crop']['x']=100
        return data,old,new

    def test_swap_targets_existing_nests_and_camera_anchor(self):
        data,old,new=self.fixture();ops=revision_operations(data,old,new,{'cut':['a','b']})
        self.assertEqual([(o['container'],o['child'],o['nestClip'],o['cameraClip']) for o in ops],[(2,3,20,30),(2,4,21,40)])
        self.assertEqual(ops[0]['nestMotion'],{'position':[180,480]})
        self.assertEqual(ops[0]['cameraMotion'],{'anchor':[280,180]})
        self.assertEqual(ops[1]['cameraMotion'],{})
        self.assertTrue(all(not o['trackingChanged'] and not o['settings'] for o in ops))

    def test_resize_scopes_native_settings_and_motion_without_touching_master(self):
        data,old,new=self.fixture();new=copy.deepcopy(old);a,b=new['framing']['shots']['cut']['panels']
        a['rect']['height']=240;b['rect'].update(y=240,height=400);a['crop']['width']=480;b['crop']['width']=288
        ops=revision_operations(data,old,new,{'cut':['a','b']})
        self.assertEqual(ops[0]['settings'],{'height':240});self.assertEqual(ops[1]['settings'],{'height':400})
        self.assertEqual(ops[0]['cameraMotion'],{'anchor':[320,180],'position':[180,120],'scale':75})
        self.assertEqual(ops[1]['cameraMotion'],{'anchor':[224,180],'position':[180,200],'scale':125})

    def test_full_project_comparison_keeps_unselected_motion_sources_audio_and_effects(self):
        data,old,new=self.fixture();ops=revision_operations(data,old,new,{'cut':['a','b']});baseline=protected_revision(data,ops,'revised')
        changed=copy.deepcopy(data);changed['project']['name']=changed['project']['root']['name']='revised';items=changed['project']['items']
        items['2']['kind']['Sequence']['video_tracks'][0]['items'][0]['effects'][0]['params']['position']['value']={'Vec2':{'x':180,'y':480}}
        items['2']['kind']['Sequence']['video_tracks'][1]['items'][0]['effects'][0]['params']['position']['value']={'Vec2':{'x':180,'y':160}}
        items['3']['kind']['Sequence']['video_tracks'][0]['items'][0]['effects'][0]['params']['anchor']['value']={'Vec2':{'x':280,'y':180}}
        self.assertEqual(baseline,protected_revision(changed,ops))
        for mutation in ['source','audio','scale','other-anchor','effect','settings','active','name']:
            value=copy.deepcopy(changed);items=value['project']['items'];camera=items['3']['kind']['Sequence']['video_tracks'][0]['items'][0]
            if mutation=='source':camera['source_in']+=1
            elif mutation=='audio':items['1']['kind']['Sequence']['audio_tracks'].append({'items':[]})
            elif mutation=='scale':camera['effects'][0]['params']['scale']['value']={'Float':101}
            elif mutation=='other-anchor':items['4']['kind']['Sequence']['video_tracks'][0]['items'][0]['effects'][0]['params']['anchor']['value']={'Vec2':{'x':280,'y':180}}
            elif mutation=='effect':camera['effects'][1]['enabled']=False
            elif mutation=='settings':items['3']['kind']['Sequence']['settings']['height']=321
            elif mutation=='active':value['view']['active_sequence']=2
            else:value['project']['root']['name']='unexpected'
            with self.subTest(mutation=mutation):self.assertNotEqual(baseline,protected_revision(value,ops))

    def test_tracking_curve_changes_even_when_first_anchor_stays_fixed(self):
        data,old,new=self.fixture();a=old['framing']['shots']['cut']['panels'][0]
        a['crop'].update(mode='tracked-crop',xByFrame=[80,81],sourceRange=copy.deepcopy(a['sourceRange']));new=copy.deepcopy(old);new['framing']['shots']['cut']['panels'][0]['crop']['xByFrame']=[80,82]
        ops=revision_operations(data,old,new,{'cut':['a']});self.assertTrue(ops[0]['trackingChanged']);self.assertEqual(ops[0]['cameraMotion'],{})
        camera=data['project']['items']['3']['kind']['Sequence']['video_tracks'][0]['items'][0];camera['effects'][0]['params']['anchor']['keyframes']=[{'time':1,'value':80}]
        baseline=protected_revision(data,ops);changed=copy.deepcopy(data);changed['project']['items']['3']['kind']['Sequence']['video_tracks'][0]['items'][0]['effects'][0]['params']['anchor']['keyframes']=[{'time':2,'value':82}]
        self.assertEqual(baseline,protected_revision(changed,ops))
        changed['project']['items']['3']['kind']['Sequence']['video_tracks'][0]['items'][0]['effects'][0]['params']['anchor']['value']={'Vec2':{'x':99,'y':99}}
        self.assertNotEqual(baseline,protected_revision(changed,ops))


if __name__=='__main__':unittest.main()
