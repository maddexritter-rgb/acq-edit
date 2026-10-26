import hashlib
import importlib.util
import math
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
import wave

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('native_music', ROOT/'distribution/skills/music/scripts/apply_native_music.py')
music = importlib.util.module_from_spec(spec)
spec.loader.exec_module(music)


class ProjectSourceTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root/'00_SOURCE').mkdir()
        (self.root/'10_WORK').mkdir()
        self.catalog = self.root/'catalog.wav'
        self.media = self.root/'00_SOURCE/normalized.wav'
        with wave.open(str(self.catalog), 'wb') as stream:
            stream.setparams((2, 2, 48000, 0, 'NONE', 'not compressed'))
            stream.writeframes(b''.join(struct.pack('<hh', value, value)
                                       for value in (int(5000*math.sin(i*0.05)) for i in range(48000))))
        subprocess.run(['ffmpeg','-v','error','-i',str(self.catalog),'-c:a','pcm_s24le',str(self.media)],check=True)
        decoded = subprocess.check_output(['ffmpeg','-v','error','-i',str(self.catalog),'-map','0:a:0','-vn','-ar','48000','-ac','2','-c:a','pcm_s24le','-f','hash','-hash','sha256','-'],text=True).strip().split('=')[1]
        self.selection = {'target':{'project_path':str(self.root/'10_WORK/edit.prproj')},
                          'project_source':{'schema':'edit.music-project-source/v1','path':str(self.media),
                                            'catalog_sha256':music.sha(self.catalog),'sha256':music.sha(self.media),
                                            'decoded_pcm_sha256':decoded}}
        self.candidate = {'path':str(self.catalog),'id':'approved-track','start':'796/15'}

    def test_lossless_normalization_preserves_identity(self):
        result,evidence=music.project_source_candidate(self.selection,self.candidate,[])
        self.assertEqual(result,{**self.candidate,'path':str(self.media)})
        self.assertEqual(self.candidate['path'],str(self.catalog))
        self.assertEqual(len(evidence),2)

    def test_changed_audio_rejected_even_with_updated_file_hash(self):
        subprocess.run(['ffmpeg','-v','error','-y','-i',str(self.catalog),'-af','volume=0.5','-c:a','pcm_s24le',str(self.media)],check=True)
        self.selection['project_source']['sha256']=music.sha(self.media)
        with self.assertRaisesRegex(music.BridgeError,'differs from the complete'):
            music.project_source_candidate(self.selection,self.candidate,[])

    def test_external_and_missing_pins_rejected(self):
        self.selection['project_source']['path']=str(self.catalog)
        with self.assertRaisesRegex(music.BridgeError,'project-owned'):
            music.project_source_candidate(self.selection,self.candidate,[])
        self.selection['project_source']['path']=str(self.media)
        del self.selection['project_source']['catalog_sha256']
        with self.assertRaisesRegex(music.BridgeError,'SHA256 pins'):
            music.project_source_candidate(self.selection,self.candidate,[])

    def test_unbound_behavior_and_exact_rational_clock(self):
        self.assertEqual(music.project_source_candidate({},self.candidate,[]),(self.candidate,[]))
        self.assertEqual(music.seconds_ticks('796/15'),'13479782400000')


if __name__ == '__main__':
    unittest.main()
