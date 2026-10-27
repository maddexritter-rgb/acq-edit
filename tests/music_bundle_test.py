import importlib.util, json, tempfile, unittest
from pathlib import Path

spec=importlib.util.spec_from_file_location('assets',Path(__file__).resolve().parents[1]/'scripts/asset_bundle.py')
assets=importlib.util.module_from_spec(spec);spec.loader.exec_module(assets)

class MusicBundleTests(unittest.TestCase):
    def test_private_bundle_excludes_fonts_pins_permission_and_preserves_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'source';source.mkdir()
            track=source/assets.MUSIC/'track.wav';track.parent.mkdir(parents=True);track.write_bytes(b'audio fixture')
            font=source/'fonts/font.otf';font.parent.mkdir();font.write_bytes(b'font fixture')
            manifest={'schema':'acq-edit/assets-v1','version':'local','distribution':'local-only','musicTracks':1,
                      'files':{p.relative_to(source).as_posix():assets.digest(p) for p in (track,font)}}
            (source/'asset-bundle.json').write_text(json.dumps(manifest));before=assets.digest(source/'asset-bundle.json')
            grant=root/'grant.json';grant.write_text(json.dumps({'scope':'private-team-music','authorizedBy':'Owner','statement':'Authorized private team use','date':'2026-10-26'}))
            target=root/'release';result=assets.private_music(source,target,'v1',grant)
            self.assertTrue(result['ready']);self.assertFalse((target/'fonts').exists())
            rights=json.loads((target/'MUSIC_RIGHTS.json').read_text());self.assertEqual(len(rights['assets']),1)
            self.assertEqual(assets.digest(source/'asset-bundle.json'),before)
            with self.assertRaisesRegex(ValueError,'Existing bundle'):assets.private_music(source,target,'v1',grant)
            grant.write_text(json.dumps({'scope':'public'}))
            with self.assertRaisesRegex(ValueError,'authorization'):assets.private_music(source,root/'other','v2',grant)

if __name__=='__main__':unittest.main()
