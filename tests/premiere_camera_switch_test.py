import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from verify_premiere_camera_test import verify

def fixture():
    r={'track_index':3,'start_ticks':'0','end_ticks':'20','source_in_ticks':'100','source_out_ticks':'120','frame_ticks':'10','scale':100,'anchor_keys':[[.4,.5],[.41,.5]],'media_path':'/original.mov'}
    old={'id':'old','start':'0','end':'20'}
    before={'projectPath':'/p.prproj','sequenceId':'s','tracks':[{'kind':0,'index':3,'clips':[old]},{'kind':0,'index':4,'clips':[{'id':'caption','text':'Keep this'}]},{'kind':1,'index':0,'clips':[{'id':'dialogue'}]}]}
    c={'id':'new','start':'0','end':'20','inPoint':'100','outPoint':'120','speed':1,'disabled':False,'components':[{'matchName':'AE.ADBE Motion','properties':[{'name':'Position','value':[.5,.5]},{'name':'Scale','value':100},{'name':'Anchor Point','keys':[{'ticks':'100','value':[.4,.5]},{'ticks':'110','value':[.41,.5]}]}]}]}
    after=copy.deepcopy(before);after['tracks'][0]['clips']=[c]
    links={'project_path':'/p.prproj','sequence_id':'s','items':[{'kind':'video','item':{'node_id':'new','media_path':'/original.mov','offline':False,'is_sequence':False,'speed_reversed':False}}]}
    return {'shots':[{'request':r}]},before,after,[{'item':{'id':'new'}}],links

class CameraTest(unittest.TestCase):
    def test_exact_original_camera_dense_keys_and_protected_tracks(self):
        self.assertEqual(verify(*fixture())['denseKeys'],2)
    def test_caption_or_dialogue_changes_fail(self):
        for track in [1,2]:
            args=list(fixture());args[2]['tracks'][track]['clips'][0]['id']='changed'
            with self.assertRaisesRegex(ValueError,'protected'):verify(*args)
    def test_missing_or_changed_key_fails(self):
        for missing in [True,False]:
            args=list(fixture());keys=args[2]['tracks'][0]['clips'][0]['components'][0]['properties'][2]['keys']
            if missing:keys.pop()
            else:keys[1]['value'][0]=.5
            with self.assertRaises(ValueError):verify(*args)
    def test_flattened_or_changed_original_source_fails(self):
        for field,value in [('media_path','/finished.mp4'),('offline',True),('is_sequence',True),('speed_reversed',True)]:
            args=list(fixture());args[4]['items'][0]['item'][field]=value
            with self.assertRaisesRegex(ValueError,'offline, reversed, flattened'):verify(*args)

if __name__=='__main__':unittest.main()
