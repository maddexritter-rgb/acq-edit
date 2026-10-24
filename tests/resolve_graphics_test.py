import copy,sys,unittest
from pathlib import Path
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
from resolve_graphics import items,protected,replace,fresh_media


class ResolveGraphicsTests(unittest.TestCase):
    def fixture(self):
        asset={'path':'/project/title.mov','sha256':'hash','startFrame':5,'frames':25}
        media=Mock();media.GetClipProperty.return_value=asset['path'];media.GetUniqueId.return_value='new';media.GetFlagList.return_value=[]
        item=Mock();item.GetMediaPoolItem.return_value=media;item.GetStart.return_value=5;item.GetDuration.return_value=25;item.GetLeftOffset.return_value=0;item.GetLinkedItems.return_value=[];item.GetTakesCount.return_value=0;item.GetSelectedTakeIndex.return_value=0;item.GetFusionCompCount.return_value=0;item.GetSourceStartFrame.return_value=0;item.GetSourceEndFrame.return_value=24
        item.GetFlagList.return_value=['Green'];timeline=Mock();timeline.GetItemListInTrack.return_value=[item];timeline.GetIsTrackLocked.return_value=False
        return asset,media,item,timeline

    def test_native_target_preflight_refuses_unsupported_state(self):
        asset,_,item,timeline=self.fixture();self.assertEqual(items(timeline,{'graphics':[asset]},[0]),[item])
        for method,value in [('GetTakesCount',2),('GetSelectedTakeIndex',1),('GetFusionCompCount',1),('GetLinkedItems',[object()]),('GetSourceEndFrame',49),('GetDuration',26)]:
            asset,_,item,timeline=self.fixture();getattr(item,method).return_value=value
            with self.subTest(method=method),self.assertRaises(RuntimeError):items(timeline,{'graphics':[asset]},[0])
        asset,_,_,timeline=self.fixture();timeline.GetIsTrackLocked.return_value=True
        with self.assertRaises(RuntimeError):items(timeline,{'graphics':[asset]},[0])

    def test_protection_allows_only_selected_source_binding(self):
        item={'id':'same','name':'custom','source':'old','sourcePath':'/old.mov','properties':{'Opacity':72},'fusion':[]}
        before={'state':{'tracks':{'video':[[{'id':'picture'}],[item],[copy.deepcopy(item)]]}},'extra':{'video:1:0':{'color':'Pink','markers':{'0':'keep'}}}}
        changed=copy.deepcopy(before);changed['state']['tracks']['video'][1][0].update(source='new',sourcePath='/new.mov')
        self.assertEqual(protected(before,[0]),protected(changed,[0]))
        for field in ['name','effect','other-source','marker']:
            bad=copy.deepcopy(changed);clip=bad['state']['tracks']['video'][1][0]
            if field=='name':clip['name']='new'
            elif field=='effect':clip['properties']['Opacity']=100
            elif field=='other-source':bad['state']['tracks']['video'][2][0]['source']='new'
            else:bad['extra']['video:1:0']['markers']={}
            with self.subTest(field=field):self.assertNotEqual(protected(before,[0]),protected(bad,[0]))

    def test_native_take_uses_inclusive_end_restores_name_and_color(self):
        asset,media,item,_=self.fixture();item.GetName.return_value='Custom';item.GetClipColor.return_value='Pink';item.GetTakesCount.side_effect=[2,0];item.GetSelectedTakeIndex.side_effect=[2,0];item.GetTakeByIndex.return_value={'mediaPoolItem':media,'startFrame':0,'endFrame':24}
        with patch('resolve_graphics.sha',return_value='hash'):replace(item,media,asset)
        item.AddTake.assert_called_once_with(media,0,24);item.SelectTakeByIndex.assert_called_once_with(2);item.SetName.assert_called_once_with('Custom');item.SetClipColor.assert_called_once_with('Pink')
        item.AddFlag.assert_called_once_with('Green')

    def test_wrong_take_binding_fails_before_selection_and_finalization(self):
        asset,media,item,_=self.fixture();item.GetTakesCount.return_value=2;item.GetTakeByIndex.return_value={'mediaPoolItem':media,'startFrame':1,'endFrame':25}
        with patch('resolve_graphics.sha',return_value='hash'),self.assertRaises(RuntimeError):replace(item,media,asset)
        item.SelectTakeByIndex.assert_not_called();item.FinalizeTake.assert_not_called()

    def test_reused_media_in_nested_bin_is_rejected_without_mutation(self):
        asset,media,_,_=self.fixture();pool=Mock();root=Mock();child=Mock();pool.GetRootFolder.return_value=root;root.GetClipList.return_value=[];root.GetSubFolderList.return_value=[child];child.GetClipList.return_value=[media];child.GetSubFolderList.return_value=[]
        with self.assertRaisesRegex(RuntimeError,'already registered'):fresh_media(pool,{'graphics':[asset]},[0])
        pool.ImportMedia.assert_not_called()
        fresh_media(pool,{'graphics':[{**asset,'path':'/project/new.mov'}]},[0])


if __name__=='__main__':unittest.main()
