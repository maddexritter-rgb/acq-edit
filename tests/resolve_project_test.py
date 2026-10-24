import sys,unittest
from pathlib import Path
from unittest.mock import MagicMock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
from resolve_project import inspect_without_timeline
from resolve import Adapter


class ResolveProjectTests(unittest.TestCase):
 def setUp(self):
  self.project=MagicMock();self.project.GetTimelineCount.return_value=0;self.project.GetCurrentTimeline.return_value=None
  self.project.GetName.return_value='ACQ_fixture';self.project.GetUniqueId.return_value='native-project';self.project.GetSettings.return_value={'timelineFrameRate':'25'};self.project.IsRenderingInProgress.return_value=False;self.project.GetRenderJobList.return_value=[]
  self.folder=self.project.GetMediaPool.return_value.GetRootFolder.return_value
  self.folder.GetUniqueId.return_value='root';self.folder.GetName.return_value='Master';self.folder.GetIsFolderStale.return_value=False;self.folder.GetClipList.return_value=[];self.folder.GetSubFolderList.return_value=[]
 def test_first_inspection_reports_empty_project_without_native_mutation(self):
  adapter=Adapter({});r=MagicMock();r.GetVersionString.return_value='21.1.1';adapter.selected=MagicMock(return_value=(r,self.project))
  result=adapter.inspect({},{});self.assertEqual(result['state']['kind'],'resolve-project-without-timelines');self.assertIsNone(result['state']['timeline']);self.assertEqual(result['state']['mediaPool']['clips'],[]);self.assertEqual(len(result['fingerprint']),64)
  self.project.SetCurrentTimeline.assert_not_called();self.project.SetSettings.assert_not_called()
 def test_imported_media_is_reported_instead_of_claiming_empty_project(self):
  clip=MagicMock();clip.GetUniqueId.return_value='source';clip.GetName.return_value='Source';clip.GetClipProperty.return_value={'File Path':'/fixture/source.mov','Frames':'150'};self.folder.GetClipList.return_value=[clip]
  self.assertEqual(inspect_without_timeline(self.project)['mediaPool']['clips'][0]['properties']['Frames'],'150')
 def test_unselected_existing_or_changed_timeline_is_not_treated_as_empty(self):
  self.project.GetTimelineCount.return_value=1
  with self.assertRaisesRegex(RuntimeError,'none is selected'):inspect_without_timeline(self.project)
  self.project.GetTimelineCount.side_effect=[0,1]
  with self.assertRaisesRegex(RuntimeError,'changed during'):inspect_without_timeline(self.project)


if __name__=='__main__':unittest.main()
