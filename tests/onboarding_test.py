import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import subprocess
import shutil
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from onboard import extract, install_fonts, install_brain, verify_connections
from acq_edit import user_runtime

def manifest(root):
    files={p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
    (root/'asset-bundle.json').write_text(json.dumps({'schema':'acq-edit/assets-v1','version':'test','distribution':'test','files':files}))

class Onboarding(unittest.TestCase):
    def test_guide_works_before_dependencies_and_never_reads_or_changes_credentials(self):
        with tempfile.TemporaryDirectory() as d:
            config=Path(d)/'config';config.mkdir();secret=config/'credentials.json'
            secret.write_text('{"ASSEMBLYAI_API_KEY":"fixture-do-not-display"}')
            before={p.name:p.read_bytes() for p in config.iterdir()}
            env={**os.environ,'PATH':'','ACQ_EDIT_HOME':str(config),'PYTHONDONTWRITEBYTECODE':'1'}
            for args in ([],['guide']):
                result=subprocess.run([sys.executable,str(ROOT/'scripts/onboard.py'),*args],cwd=d,env=env,capture_output=True,text=True)
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertIn(str(ROOT),result.stdout)
                self.assertIn('docs/ONBOARDING.md',result.stdout)
                self.assertNotIn('fixture-do-not-display',result.stdout+result.stderr)
                self.assertEqual({p.name:p.read_bytes() for p in config.iterdir()},before)
    def test_packaged_launcher_hands_off_to_installed_agent_instructions(self):
        with tempfile.TemporaryDirectory() as d:
            package=Path(d)/'package';home=Path(d)/'user home';home.mkdir()
            for name in ['release.json','AGENTS.md','CLAUDE.md','docs/ONBOARDING.md','scripts/acq_edit.py','scripts/onboard.py','scripts/asset_bundle.py']:
                target=package/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,target)
            env={**os.environ,'HOME':str(home),'PATH':'','PYTHONDONTWRITEBYTECODE':'1'}
            result=subprocess.run([sys.executable,str(package/'scripts/acq_edit.py'),'onboard','guide'],env=env,cwd=d,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            version=json.loads((package/'release.json').read_text())['version']
            runtime=home/'Library/Application Support/ACQ Edit/versions'/version
            self.assertIn(str(runtime),result.stdout)
            for name in ['AGENTS.md','CLAUDE.md','docs/ONBOARDING.md']:
                self.assertEqual((runtime/name).read_bytes(),(package/name).read_bytes())
            self.assertFalse((home/'.config/acq-edit').exists())

    def test_runtime_keeps_existing_changes_and_rejects_different_package(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);package=root/'package';package.mkdir();(package/'release.json').write_text('{"version":"1.0"}')
            (package/'code.py').write_text('original'); home=root/'home'
            runtime=user_runtime(package,home);(runtime/'code.py').write_text('user change')
            self.assertEqual(user_runtime(package,home),runtime);self.assertEqual((runtime/'code.py').read_text(),'user change')
            (package/'release.json').write_text('{"version":"1.0","other":true}')
            with self.assertRaisesRegex(ValueError,'different package'):user_runtime(package,home)
    def test_archive_rejects_escape_and_links_before_extracting(self):
        for name,kind in [('../outside',tarfile.REGTYPE),('link',tarfile.SYMTYPE)]:
            with tempfile.TemporaryDirectory() as d:
                root=Path(d);archive=root/'a.tgz'
                with tarfile.open(archive,'w:gz') as tf:
                    item=tarfile.TarInfo(name);item.type=kind;item.linkname='/etc/passwd';tf.addfile(item)
                with self.assertRaises(ValueError):extract(archive,root/'output')
                self.assertFalse((root/'output').exists())
    def test_font_conflict_preserves_entire_batch(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);bundle=root/'bundle';(bundle/'fonts').mkdir(parents=True)
            (bundle/'fonts/a.otf').write_bytes(b'font a');(bundle/'fonts/b.otf').write_bytes(b'font b');manifest(bundle)
            target=root/'fonts';target.mkdir();(target/'b.otf').write_bytes(b'existing')
            with self.assertRaises(ValueError):install_fonts(bundle,target)
            self.assertFalse((target/'a.otf').exists());self.assertEqual((target/'b.otf').read_bytes(),b'existing')
    def test_font_install_repeat_is_verified(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);bundle=root/'bundle';(bundle/'fonts').mkdir(parents=True)
            (bundle/'fonts/a.otf').write_bytes(b'font');manifest(bundle)
            self.assertEqual(install_fonts(bundle,root/'installed'),1)
            self.assertEqual(install_fonts(bundle,root/'installed'),1)
    def test_brain_has_private_permissions_and_no_silent_rotation(self):
        with tempfile.TemporaryDirectory() as d,patch('onboard.HOME',Path(d)/'config'):
            root=Path(d);(root/'team').mkdir();source=root/'team/editorial-brain.json'
            source.write_text(json.dumps({'function_url':'https://example.test','project_ref':'test','token':'fixture-read-token'}))
            folder=install_brain(root);self.assertEqual((folder/'read_token').stat().st_mode&0o777,0o600)
            self.assertEqual(install_brain(root),folder)
            source.write_text(source.read_text().replace('fixture-read-token','rotated-read-token'))
            with self.assertRaisesRegex(ValueError,'rotation'):install_brain(root)
            self.assertEqual((folder/'read_token').read_text().strip(),'fixture-read-token')
    def test_read_checks_missing_credentials_do_not_make_requests(self):
        with tempfile.TemporaryDirectory() as d,patch('onboard.HOME',Path(d)),patch.dict(os.environ,{},clear=True),patch('urllib.request.urlopen') as request:
            self.assertFalse(verify_connections());request.assert_not_called()
            self.assertTrue((Path(d)/'connection-check.json').is_file())

if __name__=='__main__':unittest.main()
