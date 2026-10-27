import importlib.util,json,subprocess,tempfile,unittest
from pathlib import Path
s=importlib.util.spec_from_file_location('owner',Path(__file__).resolve().parents[1]/'scripts/prepare_picture_dialogue.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class SourcePreparation(unittest.TestCase):
 def test_exact_picture_and_pcm_and_existing_output_refused(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);v=p/'v.mov';a=p/'a.wav';e=p/'clock.json';e.write_text('{"origin":0,"method":"synthetic common origin"}')
   subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=size=64x64:rate=24:duration=1','-c:v','libx264',str(v)],check=True)
   subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','sine=frequency=500:sample_rate=48000:duration=1','-c:a','pcm_s24le',str(a)],check=True)
   r=m.prepare(v,a,e,p/'result');self.assertTrue(r['picturePacketsAndClocksIdentical']);self.assertEqual(r['videoPackets'],24)
   with self.assertRaises(FileExistsError):m.prepare(v,a,e,p/'result')
 def test_missing_clock_evidence_refused(self):
  with self.assertRaises(ValueError):m.prepare('not-present','not-present','not-present','not-present')
if __name__=='__main__':unittest.main()
