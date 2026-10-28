import contextlib,io,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import onboard

class PanelUpgrade(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.home=Path(self.temp.name);self.parent=self.home/'Library/Application Support/ACQ Edit/versions';self.old=self.parent/'old';self.new=self.parent/'new'
  self.target=self.home/'Library/Application Support/Adobe/CEP/extensions/ACQEditAgentCEP';self.target.mkdir(parents=True)
  self.old_source=self.old/'.local/premiere-agent/lab/packages/ACQEditAgentCEP';self.new_source=self.new/'.local/premiere-agent/lab/packages/ACQEditAgentCEP'
  for runtime,folder,text in [(self.old,self.old_source,'old'),(self.new,self.new_source,'new')]:
   (folder/'CSXS').mkdir(parents=True);(folder/'CSXS/manifest.xml').write_text(text);(runtime/'.package-sha256').write_text('fixture')
   (runtime/'.local/premiere-agent/lab/panel-preparation.json').write_text(json.dumps({'cepId':'com.acqedit.premiere.bridge','packageHashes':{'ACQEditAgentCEP/CSXS/manifest.xml':onboard.digest(folder/'CSXS/manifest.xml')}}))
  (self.target/'CSXS').mkdir();(self.target/'CSXS/manifest.xml').write_text('old');(self.new/'.local/onboarding.json').write_text(json.dumps({'previousRuntime':str(self.old)}))
  for context in [patch.object(onboard,'ROOT',self.new),patch.object(onboard,'HOME',self.home/'config'),patch.object(Path,'home',return_value=self.home),patch.dict('os.environ',{'ACQ_EDIT_CREDENTIALS_HOME':str(self.home/'config')}),contextlib.redirect_stdout(io.StringIO())]:context.__enter__();self.addCleanup(context.__exit__,None,None,None)
 def test_owned_upgrade_backs_up_old_bytes_and_is_idempotent(self):
  onboard.panel_install(True);self.assertEqual((self.target/'CSXS/manifest.xml').read_text(),'new')
  backups=list((self.home/'config/panel-backups').glob('*/CSXS/manifest.xml'));self.assertEqual(len(backups),1);self.assertEqual(backups[0].read_text(),'old')
  onboard.panel_install(True);self.assertEqual(len(list((self.home/'config/panel-backups').iterdir())),1)
 def test_no_flag_or_modified_panel_never_overwrites(self):
  with self.assertRaisesRegex(ValueError,'update-owned'):onboard.panel_install()
  (self.target/'CSXS/manifest.xml').write_text('user edit')
  with self.assertRaisesRegex(ValueError,'differs from its owned'):onboard.panel_install(True)
  self.assertEqual((self.target/'CSXS/manifest.xml').read_text(),'user edit')
 def test_active_writer_blocks_upgrade(self):
  work=self.old/'.local/premiere-agent/lab/runtime';work.mkdir();(work/'writer.lock').write_text('unsettled')
  with self.assertRaisesRegex(ValueError,'active native work'):onboard.panel_install(True)
  self.assertEqual((self.target/'CSXS/manifest.xml').read_text(),'old')
 def test_missing_owner_or_redirected_panel_preserved(self):
  (self.new/'.local/onboarding.json').write_text('{}')
  with self.assertRaisesRegex(ValueError,'Prior owned runtime'):onboard.panel_install(True)
  self.assertEqual((self.target/'CSXS/manifest.xml').read_text(),'old')

 def test_changed_new_panel_does_not_replace_existing_panel(self):
  (self.new_source/'CSXS/manifest.xml').write_text('unverified change')
  with self.assertRaisesRegex(ValueError,'New toolkit panel differs'):onboard.panel_install(True)
  self.assertEqual((self.target/'CSXS/manifest.xml').read_text(),'old')
