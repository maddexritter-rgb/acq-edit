"""First construction must not replace saved or intervening native work."""
import sys,unittest
from pathlib import Path
from unittest.mock import MagicMock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
from resolve_project import construction_project


class ResolveConstructionTests(unittest.TestCase):
 def setUp(self):
  self.r=MagicMock();self.pm=self.r.GetProjectManager.return_value
  self.pm.GetCurrentDatabase.return_value={'DbType':'Disk','DbName':'Test'};self.pm.GetProjectListInCurrentFolder.return_value=[]
  self.placeholder=MagicMock();self.placeholder.GetName.return_value='Untitled Project';self.pm.GetCurrentProject.return_value=self.placeholder
  self.project=MagicMock();self.project.GetName.return_value='ACQ_test';self.project.GetUniqueId.return_value='created-id';self.project.IsRenderingInProgress.return_value=False
  self.pin={'nativeProjectId':'empty-id','database':{'DbType':'Disk','DbName':'Test'},'fingerprint':'a'*64}
  def create(name):self.assertEqual(name,'ACQ_test');self.pm.GetCurrentProject.return_value=self.project;return self.project
  self.pm.CreateProject.side_effect=create
  self.empty=patch('resolve_project.empty_workspace',return_value=self.pin).start();self.addCleanup(patch.stopall)
 def call(self,packet=None):return construction_project(self.r,{'id':'test'},packet or {'emptyWorkspace':self.pin})
 def test_pinned_empty_workspace_creates_only_named_project(self):
  self.assertIs(self.call(),self.project);self.pm.CreateProject.assert_called_once_with('ACQ_test')
  for method in ['LoadProject','CloseProject','SaveProject','ImportProject']:getattr(self.pm,method).assert_not_called()
 def test_existing_closed_project_is_never_recreated(self):
  self.pm.GetProjectListInCurrentFolder.return_value=['ACQ_test']
  with self.assertRaisesRegex(RuntimeError,'already exists'):self.call()
  self.pm.CreateProject.assert_not_called();self.pm.LoadProject.assert_not_called()
 def test_missing_or_changed_pin_and_populated_workspace_are_refused(self):
  for observed,packet in [(self.pin,{'emptyWorkspace':None}),({**self.pin,'fingerprint':'b'*64},{'emptyWorkspace':self.pin}),(None,{'emptyWorkspace':self.pin})]:
   self.empty.return_value=observed
   with self.assertRaisesRegex(RuntimeError,'Another Resolve project'):self.call(packet)
  self.pm.CreateProject.assert_not_called()
 def test_changed_host_before_creation_is_not_overwritten(self):
  self.empty.side_effect=[self.pin,None]
  with self.assertRaisesRegex(RuntimeError,'Another Resolve project'):self.call()
  self.pm.CreateProject.assert_not_called()
 def test_selected_existing_project_is_reused_but_active_render_refused(self):
  self.pm.GetCurrentProject.return_value=self.project
  self.assertIs(self.call(),self.project);self.pm.CreateProject.assert_not_called()
  self.project.IsRenderingInProgress.return_value=True
  with self.assertRaisesRegex(RuntimeError,'render is active'):self.call()
 def test_failed_creation_or_wrong_readback_never_returns_success(self):
  self.pm.CreateProject.side_effect=None;self.pm.CreateProject.return_value=None
  with self.assertRaisesRegex(RuntimeError,'Could not create'):self.call()
  self.pm.CreateProject.return_value=self.project
  with self.assertRaisesRegex(RuntimeError,'selection readback differs'):self.call()


if __name__=='__main__':unittest.main()
