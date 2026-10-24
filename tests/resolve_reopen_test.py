"""Reopening selects verified native state without replacing manual edits."""
import sys,unittest
from pathlib import Path
from unittest.mock import MagicMock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
from common import fingerprint
from resolve_project import reopen,inspection_result,empty_workspace


class ResolveReopenTests(unittest.TestCase):
 def setUp(self):
  self.r=MagicMock();self.pm=self.r.GetProjectManager.return_value
  self.p=self.pm.GetCurrentProject.return_value;self.p.GetName.return_value='ACQ_test'
  self.p.GetUniqueId.return_value='project-unique';self.p.IsRenderingInProgress.return_value=False
  self.r.GetVersionString.return_value='21.1.1';self.pm.GetCurrentDatabase.return_value={'DbType':'Disk','DbName':'Test'}
  self.t=MagicMock();self.t.GetUniqueId.return_value='timeline-unique'
  self.other=MagicMock();self.other.GetUniqueId.return_value='other-timeline'
  self.p.GetTimelineCount.return_value=2;self.p.GetTimelineByIndex.side_effect=[self.other,self.t]
  self.p.GetCurrentTimeline.return_value=self.other
  def select(t):self.p.GetCurrentTimeline.return_value=t;return True
  self.p.SetCurrentTimeline.side_effect=select
  self.state={'timeline':'timeline-unique','caption':'Original','cuts':[0,50]}
  self.other_state={'timeline':'other-timeline','caption':'Keep this edit'}
  self.snapshot=MagicMock(side_effect=lambda p:self.state if p.GetCurrentTimeline() is self.t else self.other_state)
  self.packet=inspection_result(self.r,self.p,self.state)['reopen']
 def call(self):return reopen(self.r,{'id':'test'},self.packet,self.snapshot)
 def test_selects_verified_version_and_returns_reusable_packet_without_save_or_rebuild(self):
  result=self.call();self.assertEqual(result['reopen'],self.packet)
  self.snapshot.assert_any_call(self.p);self.p.SetCurrentTimeline.assert_called_once_with(self.t)
  for name in ['LoadProject','SaveProject','CreateProject','ImportProject','CloseProject']:getattr(self.pm,name).assert_not_called()
 def test_loads_exact_saved_project_only_when_no_project_is_open(self):
  self.pm.GetCurrentProject.return_value=None
  def load(name):self.assertEqual(name,'ACQ_test');self.pm.GetCurrentProject.return_value=self.p;return self.p
  self.pm.LoadProject.side_effect=load
  self.assertEqual(self.call()['fingerprint'],fingerprint(self.state));self.pm.CreateProject.assert_not_called()
 def test_other_project_or_database_refused_before_load_or_selection(self):
  self.p.GetName.return_value='Production'
  with self.assertRaisesRegex(RuntimeError,'Another Resolve project'):self.call()
  self.p.GetName.return_value='ACQ_test';self.pm.GetCurrentDatabase.return_value={'DbName':'Other'}
  with self.assertRaisesRegex(RuntimeError,'database changed'):self.call()
  self.pm.LoadProject.assert_not_called();self.p.SetCurrentTimeline.assert_not_called()
 def test_wrong_identity_active_render_or_missing_timeline_refused(self):
  self.p.GetUniqueId.return_value='wrong'
  with self.assertRaisesRegex(RuntimeError,'identity differs'):self.call()
  self.p.GetUniqueId.return_value='project-unique';self.p.IsRenderingInProgress.return_value=True
  with self.assertRaisesRegex(RuntimeError,'render is active'):self.call()
  self.p.IsRenderingInProgress.return_value=False;self.p.GetTimelineByIndex.side_effect=None;self.p.GetTimelineByIndex.return_value=self.other
  with self.assertRaisesRegex(RuntimeError,'timeline unavailable'):self.call()
  self.p.SetCurrentTimeline.assert_not_called();self.pm.CreateProject.assert_not_called()
 def test_manual_change_is_preserved_and_previous_selection_restored(self):
  self.snapshot.side_effect=lambda p:{**self.state,'caption':'Manual edit'} if p.GetCurrentTimeline() is self.t else self.other_state
  with self.assertRaisesRegex(RuntimeError,'preserve user edits'):self.call()
  self.assertEqual(self.p.SetCurrentTimeline.call_count,2);self.assertIs(self.p.GetCurrentTimeline(),self.other)
 def test_changed_previous_timeline_is_not_hidden_by_restoration(self):
  self.snapshot.side_effect=[self.other_state,{**self.state,'cuts':[0,51]},{**self.other_state,'caption':'Concurrent edit'}]
  with self.assertRaisesRegex(RuntimeError,'Previous timeline differs'):self.call()
  self.pm.SaveProject.assert_not_called()
 def test_missing_project_is_not_recreated_and_malformed_packet_cannot_load(self):
  self.pm.GetCurrentProject.return_value=None;self.pm.LoadProject.return_value=None
  with self.assertRaisesRegex(RuntimeError,'Saved native project unavailable'):self.call()
  self.pm.CreateProject.assert_not_called();self.pm.LoadProject.reset_mock()
  self.packet['expectedFingerprint']=''
  with self.assertRaisesRegex(RuntimeError,'prior inspected fingerprint'):self.call()
  self.pm.LoadProject.assert_not_called()
 def placeholder(self):
  p=MagicMock();p.GetName.return_value='Untitled Project';p.GetUniqueId.return_value='empty-placeholder'
  p.GetCurrentTimeline.return_value=None;p.GetTimelineCount.return_value=0;p.IsRenderingInProgress.return_value=False;p.GetRenderJobList.return_value=[];p.GetSettings.return_value={'frameRate':'25'}
  root=p.GetMediaPool.return_value.GetRootFolder.return_value;root.GetUniqueId.return_value='empty-root';root.GetName.return_value='Master';root.GetIsFolderStale.return_value=False;root.GetClipList.return_value=[];root.GetSubFolderList.return_value=[]
  self.pm.GetCurrentProject.return_value=p
  return p
 def test_empty_startup_placeholder_requires_exact_explicit_pin(self):
  self.placeholder();self.packet['emptyWorkspace']=empty_workspace(self.r)
  def load(name):self.pm.GetCurrentProject.return_value=self.p;return self.p
  self.pm.LoadProject.side_effect=load
  self.assertEqual(self.call()['fingerprint'],fingerprint(self.state));self.pm.CloseProject.assert_not_called();self.pm.SaveProject.assert_not_called()
 def test_changed_or_unpinned_placeholder_is_never_discarded(self):
  p=self.placeholder()
  with self.assertRaisesRegex(RuntimeError,'Another Resolve project'):self.call()
  self.packet['emptyWorkspace']=empty_workspace(self.r);p.GetSettings.return_value={'frameRate':'30'}
  with self.assertRaisesRegex(RuntimeError,'Another Resolve project'):self.call()
  p.GetSettings.return_value={'frameRate':'25'};p.GetMediaPool.return_value.GetRootFolder.return_value.GetSubFolderList.return_value=[MagicMock()]
  # Nonempty hierarchy cannot qualify as the empty startup placeholder.
  self.assertIsNone(empty_workspace(self.r))
  self.pm.LoadProject.assert_not_called()


if __name__=='__main__':unittest.main()
