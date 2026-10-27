import hashlib,io,json,os,sys,tarfile,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import filmcraft_runtime as runtime
import install_engine
import onboard

def fixture(root):
    folder=root/'prepared/runtime';binary=folder/runtime.BINARY;binary.parent.mkdir(parents=True)
    binary.write_text('#!/bin/sh\nprintf "fixture runtime help\\n"\n');binary.chmod(0o755)
    (folder/'LICENSE').write_text('fixture notice')
    files={p.relative_to(folder).as_posix():runtime.digest(p) for p in folder.rglob('*') if p.is_file()}
    manifest={'sourceCommit':runtime.PIN,'binarySha256':runtime.digest(binary),'files':files}
    (folder/'runtime.json').write_text(json.dumps(manifest))
    stream=io.BytesIO()
    with tarfile.open(fileobj=stream,mode='w:gz') as tar:tar.add(folder,arcname='runtime')
    payload=stream.getvalue()
    spec={'sourceCommit':runtime.PIN,'binarySha256':runtime.digest(binary),'manifestSha256':runtime.digest(folder/'runtime.json'),'system':'Darwin','architecture':'arm64','minimumMacOS':'15.7','folder':'runtime','archive':'runtime.tar.gz','tag':'fixture','sha256':hashlib.sha256(payload).hexdigest()}
    (root/'release.json').write_text(json.dumps({'repository':'example/edit','filmcraftRuntime':spec}));(root/'.local').mkdir()
    return folder,spec,payload

class Runtime(unittest.TestCase):
    def test_prebuilt_installs_and_reopens_without_compiler_or_download_replay(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);folder,spec,payload=fixture(root)
            def download(release,staging):
                p=staging/spec['archive'];p.write_bytes(payload);return p
            with patch.object(runtime,'compatibility',return_value=None),patch.object(runtime,'download_assets',side_effect=download) as request,patch.dict(os.environ,{'PATH':''}):
                binary=runtime.install(root);self.assertEqual(binary,root/'.local/filmcraft'/runtime.BINARY)
                self.assertEqual(runtime.install(root),binary);request.assert_called_once()
                self.assertEqual((binary.parents[2]/'LICENSE').read_text(),'fixture notice')
                binary.write_text('modified')
                with self.assertRaisesRegex(ValueError,'changed'):runtime.install(root)
                self.assertEqual(binary.read_text(),'modified')

    def test_incompatible_install_never_downloads_or_builds(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);fixture(root)
            with patch.object(runtime,'compatibility',return_value='Unsupported host'),patch.object(runtime,'download_assets') as download,patch.object(runtime.subprocess,'run') as execute:
                with self.assertRaisesRegex(ValueError,'Unsupported host'):runtime.install(root)
                download.assert_not_called();execute.assert_not_called()
            self.assertFalse((root/'.local/filmcraft').exists())

    def test_corrupt_download_never_installs_and_is_retained(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);_,spec,_=fixture(root)
            def download(release,staging):
                p=staging/spec['archive'];p.write_bytes(b'corrupt');return p
            with patch.object(runtime,'compatibility',return_value=None),patch.object(runtime,'download_assets',side_effect=download):
                with self.assertRaisesRegex(ValueError,'archive checksum'):runtime.install(root)
            self.assertFalse((root/'.local/filmcraft').exists());self.assertTrue(list((root/'.local').glob('filmcraft-runtime-*/runtime.tar.gz')))

    def test_changed_manifest_and_symlinked_binary_are_refused(self):
        with tempfile.TemporaryDirectory() as d:
            folder,spec,_=fixture(Path(d));binary=folder/runtime.BINARY
            original=(folder/'runtime.json').read_bytes();(folder/'runtime.json').write_text('{}')
            with self.assertRaisesRegex(ValueError,'manifest'):runtime.verify(folder,spec)
            (folder/'runtime.json').write_bytes(original);binary.unlink();binary.symlink_to('/bin/sh')
            with self.assertRaisesRegex(ValueError,'Symlink'):runtime.verify(folder,spec)

    def test_incompatible_host_is_explicit_and_never_invokes_source_build(self):
        spec={'system':'Darwin','architecture':'arm64','minimumMacOS':'15.7'}
        with patch.object(runtime.platform,'system',return_value='Darwin'),patch.object(runtime.platform,'machine',return_value='x86_64'):
            self.assertIn('Keep FilmCraft selected',runtime.compatibility(spec))
        with patch.object(runtime.platform,'system',return_value='Darwin'),patch.object(runtime.platform,'machine',return_value='arm64'),patch.object(runtime.platform,'mac_ver',return_value=('14.7',(),'')):
            self.assertIn('15.7',runtime.compatibility(spec))

    @patch.object(install_engine, 'media_tool_ready', lambda *_: True)
    def test_prebuilt_preflight_does_not_require_rust_or_xcode(self):
        with patch.object(runtime,'specification',return_value=({},{})),patch.object(runtime,'compatibility',return_value=None),patch.object(install_engine.shutil,'which',side_effect=lambda name: '/bin/'+name if name in ['node','ffmpeg','ffprobe'] else None),patch.object(install_engine,'output',return_value='v24.0.0'):
            check=install_engine.preflight('filmcraft')
        self.assertTrue(check['prerequisitesPresent']);self.assertEqual(check['installMode'],'prebuilt');self.assertNotIn('cargo',check['executables']);self.assertNotIn('xcrun',check['executables'])

    def test_missing_selected_prerequisite_stops_before_assets_and_keeps_backend(self):
        with tempfile.TemporaryDirectory() as d,patch.object(onboard,'ROOT',Path(d)),patch.object(onboard.sys,'argv',['onboard','filmcraft','codex']),patch.object(onboard.sys,'platform','darwin'),patch.object(onboard.shutil,'which',return_value='/bin/tool'),patch.object(install_engine,'preflight',return_value={'errors':['unsupported fixture host']}),patch.object(onboard,'assets') as assets:
            with self.assertRaisesRegex(ValueError,'unsupported fixture host'):onboard.main()
            assets.assert_not_called();state=json.loads((Path(d)/'.local/onboarding.json').read_text());self.assertEqual(state['backend'],'filmcraft');self.assertEqual(state['steps']['prerequisites'],'failed');self.assertFalse((Path(d)/'.local/onboarding.lock').exists())

if __name__=='__main__':unittest.main()
