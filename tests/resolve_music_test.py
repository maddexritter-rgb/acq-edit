import copy,sys,unittest
from pathlib import Path
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
from resolve_music import items,fresh_media

class ResolveMusicTests(unittest.TestCase):
 def fixture(self):
  source={'id':'new','path':'/project/new.wav','sha256':'hash'}
  bed={'sourceId':'new','startFrame':5,'sourceInSample':48000,'samples':28800,'fadeInSamples':3840,'fadeOutSamples':3840}
  spec={'sources':[source],'audio':{'music':[bed]},'fps':{'numerator':25,'denominator':1},'sampleRate':48000}
  media=Mock();media.GetClipProperty.return_value=source['path'];media.GetUniqueId.return_value='new';media.GetFlagList.return_value=[]
  item=Mock();item.GetMediaPoolItem.return_value=media;item.GetStart.return_value=5;item.GetDuration.return_value=15;item.GetLeftOffset.return_value=25;item.GetLinkedItems.return_value=[];item.GetTakesCount.return_value=None;item.GetSelectedTakeIndex.return_value=None;item.GetFusionCompCount.return_value=0;item.GetSourceStartFrame.return_value=25;item.GetSourceEndFrame.return_value=40;item.GetFlagList.return_value=['Green'];item.GetName.return_value='Custom';item.GetClipColor.return_value='Pink'
  timeline=Mock();timeline.GetItemListInTrack.return_value=[item];timeline.GetIsTrackLocked.return_value=False
  return spec,media,item,timeline
 def test_native_music_preflight_preserves_nonzero_clock(self):
  spec,_,item,timeline=self.fixture();self.assertEqual(items(timeline,spec,[0]),[item])
  for method,value in [('GetTakesCount',2),('GetSelectedTakeIndex',1),('GetFusionCompCount',1),('GetLinkedItems',[object()]),('GetSourceStartFrame',0),('GetSourceEndFrame',39),('GetDuration',16)]:
   spec,_,item,timeline=self.fixture();getattr(item,method).return_value=value
   with self.subTest(method=method),self.assertRaises(RuntimeError):items(timeline,spec,[0])
  spec,_,_,timeline=self.fixture();timeline.GetIsTrackLocked.return_value=True
  with self.assertRaises(RuntimeError):items(timeline,spec,[0])
 def test_float_representation_noise_passes_but_sample_displacement_does_not(self):
  spec,_,item,timeline=self.fixture();item.GetDuration.return_value=15.000000000000002
  items(timeline,spec,[0])
  item.GetDuration.return_value=15+25/48000
  with self.assertRaisesRegex(RuntimeError,'timing changed'):items(timeline,spec,[0])
 def test_fractional_source_offset_refused_without_rounding(self):
  spec,media,item,timeline=self.fixture();spec['audio']['music'][0]['sourceInSample']+=1
  with self.assertRaisesRegex(RuntimeError,'whole timeline frames'):items(timeline,spec,[0])
  item.AddTake.assert_not_called()
 def test_existing_media_path_refused_before_import(self):
  spec,media,_,_=self.fixture();pool=Mock();root=Mock();pool.GetRootFolder.return_value=root;root.GetClipList.return_value=[media];root.GetSubFolderList.return_value=[]
  with self.assertRaisesRegex(RuntimeError,'already registered'):fresh_media(pool,spec,[0])
  pool.ImportMedia.assert_not_called()

if __name__=='__main__':unittest.main()
