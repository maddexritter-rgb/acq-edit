import json,plistlib,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
from premiere_compatibility import installed,select_host,bind_host,profile_host,report

class HostBinding(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.apps=self.root/'Applications';self.apps.mkdir()
 def app(self,name,version,nested=True):
  app=self.apps/name/(name+'.app') if nested else self.apps/(name+'.app');plist=app/'Contents/Info.plist';plist.parent.mkdir(parents=True);plist.write_bytes(plistlib.dumps({'CFBundleShortVersionString':version}));return app
 def test_installed_bundle_paths_and_running_host_win(self):
  old=self.app('Adobe Premiere Pro 2026','26.3.0');new=self.app('Adobe Premiere Pro New','26.5.2',False)
  self.assertEqual({x['application'] for x in installed(self.apps)},{str(old),str(new)})
  self.assertEqual(select_host(self.apps,'')['observedVersion'],'26.5.2')
  self.assertEqual(select_host(self.apps,str(old)+'/Contents/MacOS/Adobe Premiere Pro')['observedVersion'],'26.3.0')
 def test_unknown_running_host_is_not_silently_replaced(self):
  self.app('Adobe Premiere Pro 2026','26.3.0');beta=self.app('Adobe Premiere Pro Beta','27.0.0')
  with self.assertRaisesRegex(RuntimeError,'running Premiere'):select_host(self.apps,str(beta)+'/Contents/MacOS/Adobe Premiere Pro')
 def test_exact_binding_and_changed_host_refusal(self):
  app=self.app('Adobe Premiere Pro 2026','26.5.2');toolkit=self.root/'toolkit'
  self.assertEqual(bind_host(toolkit,select_host(self.apps,'')),'26.5.2');self.assertEqual(profile_host(toolkit),'26.5.2')
  with self.assertRaises(FileExistsError):bind_host(toolkit,select_host(self.apps,''))
  (app/'Contents/Info.plist').write_bytes(plistlib.dumps({'CFBundleShortVersionString':'26.5.3'}))
  with self.assertRaisesRegex(RuntimeError,'changed since installation'):profile_host(toolkit)
 def test_legacy_and_version_suffixes_do_not_expand_authority(self):
  self.assertEqual(profile_host(self.root),'26.3.0')
  self.assertTrue(report('26.5.2 (build 12)')['executionAllowed'])
  for value in ['26.5.20','26.5.2-malicious','26.5.3','27.0.0',None]:self.assertFalse(report(value)['executionAllowed'])
 def test_two_running_versions_need_a_specific_host(self):
  a=self.app('Adobe Premiere Pro 2026','26.3.0');b=self.app('Adobe Premiere Pro New','26.5.2')
  with self.assertRaisesRegex(RuntimeError,'More than one'):select_host(self.apps,str(a)+'/Contents/MacOS/Adobe Premiere Pro\n'+str(b)+'/Contents/MacOS/Adobe Premiere Pro')
