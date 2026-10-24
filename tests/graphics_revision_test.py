import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
from graphics_revision import compare_plans,filmcraft_targets,verify_filmcraft_replacement


class GraphicsRevisionTests(unittest.TestCase):
    def fixture(self):
        old={'fps':{'numerator':25,'denominator':1},'cuts':['unchanged'],'graphics':[{'path':'/project/old.mov','sha256':'old','startFrame':5,'frames':25},{'path':'/project/old.mov','sha256':'old','startFrame':15,'frames':25}]}
        new=copy.deepcopy(old);new['graphics'][0].update(path='/project/new.mov',sha256='new')
        def media(i,path):return {'id':i,'label':'Rose','kind':{'Media':{'media':{'File':{'path':path}}}}}
        def clip(i,item,start):return {'id':i,'item':item,'name':'Custom label','label':'Rose','start':start*10160640000,'duration':254016000000,'source_in':0,'speed':1,'reverse':False,'frame_hold':None,'link':None,'group':None,'effects':[{'effect':'time_remap','params':{'speed':{'value':{'Float':100.0}}}},{'effect':'opacity','params':{'opacity':{'value':{'Float':75.0}}}}]}
        seq={'video_tracks':[{'items':[]},{'items':[]},{'items':[clip(3,2,5)]},{'items':[clip(4,2,15)]}],'audio_tracks':[{'items':['dialogue unchanged']} ]}
        before={'view':{'active_sequence':1},'project':{'name':'parent','root':{'name':'parent','children':[{'Item':1},{'Item':2}]},'next_id':5,'items':{'1':{'kind':{'Sequence':seq}},'2':media(2,'/project/old.mov')}}}
        after=copy.deepcopy(before);p=after['project'];p['name']=p['root']['name']='revision';p['next_id']=6;p['items']['5']=media(5,'/project/new.mov');p['root']['children'].append({'Item':5});p['items']['1']['kind']['Sequence']['video_tracks'][2]['items'][0]['item']=5
        return old,new,before,after

    def test_only_selected_content_can_change(self):
        old,new,_,_=self.fixture();self.assertEqual(compare_plans(old,new,[0]),[0])
        for targets in [[],[True],[0,0],[-1],[2]]:
            with self.subTest(targets=targets),self.assertRaises(RuntimeError):compare_plans(old,new,targets)
        for field in ['cuts','time','other','same']:
            changed=copy.deepcopy(new)
            if field=='cuts':changed['cuts']=[]
            elif field=='time':changed['graphics'][0]['startFrame']=6
            elif field=='other':changed['graphics'][1]['sha256']='other'
            else:changed['graphics'][0]=copy.deepcopy(old['graphics'][0])
            with self.subTest(field=field),self.assertRaises(RuntimeError):compare_plans(old,changed,[0])

    def test_native_replacement_preserves_manual_effects_and_other_occurrence(self):
        old,new,before,after=self.fixture();verify_filmcraft_replacement(before,after,old,new,[0],'revision')
        for field in ['effect','other-source','label','dialogue','bin','id']:
            changed=copy.deepcopy(after);p=changed['project'];seq=p['items']['1']['kind']['Sequence']
            if field=='effect':seq['video_tracks'][2]['items'][0]['effects'][1]['params']['opacity']['value']['Float']=100
            elif field=='other-source':seq['video_tracks'][3]['items'][0]['item']=5
            elif field=='label':seq['video_tracks'][2]['items'][0]['label']='Violet'
            elif field=='dialogue':seq['audio_tracks']=[]
            elif field=='bin':p['root']['children'].reverse()
            else:p['next_id']+=1
            with self.subTest(field=field),self.assertRaises(RuntimeError):verify_filmcraft_replacement(before,changed,old,new,[0],'revision')

    def test_unsafe_native_targets_are_rejected_before_replacement(self):
        old,_,before,_=self.fixture()
        for field,value in [('link',9),('group',9),('speed',2),('reverse',True),('frame_hold',{}),('multicam',{})]:
            changed=copy.deepcopy(before);changed['project']['items']['1']['kind']['Sequence']['video_tracks'][2]['items'][0][field]=value
            with self.subTest(field=field),self.assertRaises(RuntimeError):filmcraft_targets(changed,old,[0])


if __name__=='__main__':unittest.main()
