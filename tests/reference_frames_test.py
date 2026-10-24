"""Actual FFmpeg extraction must report source clocks, not a fabricated fps grid."""
import importlib.util,json,subprocess,tempfile,unittest
from fractions import Fraction
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('reference_frames',ROOT/'scripts/reference_frames.py');reference=importlib.util.module_from_spec(spec);spec.loader.exec_module(reference)

class ReferenceFrameTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.source=self.root/'vfr.mkv'
  subprocess.run(['ffmpeg','-nostdin','-v','error','-f','lavfi','-i','testsrc2=size=160x90:rate=25:duration=0.28','-vf',"select='eq(n,0)+eq(n,2)+eq(n,5)+eq(n,6)'",'-fps_mode','vfr','-c:v','ffv1',str(self.source)],check=True)
 def test_all_native_frames_keep_variable_pts_and_source_hashes_without_audio(self):
  result=reference.extract(self.source,self.root/'all',.05,.25,all_frames=True,native_size=True)
  self.assertEqual([f['seconds'] for f in result['frames']],[.08,.2,.24]);self.assertEqual(result['status'],'extracted')
  self.assertEqual(result['imageMode'],'native-display-size-png')
  image=(self.root/'all'/result['frames'][0]['file']).read_bytes()
  self.assertEqual((int.from_bytes(image[16:20],'big'),int.from_bytes(image[20:24],'big')),(160,90))
  self.assertIsNone(result['audio']);self.assertIn('audioAbsence',result);self.assertEqual(result['sourceSha256'],reference.digest(self.source))
  for frame in result['frames']:
   self.assertEqual(float(frame['pts']*Fraction(frame['timeBase'])),frame['seconds'])
   self.assertEqual(reference.digest(self.root/'all'/frame['file']),frame['sha256'])
  self.assertEqual(result['evidence'],'extracted-not-yet-viewed-or-listened')
 def test_sampled_frames_use_actual_pts_instead_of_start_plus_index_over_fps(self):
  result=reference.extract(self.source,self.root/'sampled',.05,.25,fps=10)
  self.assertEqual([f['seconds'] for f in result['frames']],[.08,.2])
  self.assertNotEqual(result['frames'][1]['seconds'],.05+1/10)
 def test_invalid_bounds_and_existing_output_preserve_source_and_prior_artifacts(self):
  pin=reference.digest(self.source)
  for start,end in [(float('nan'),.2),(0,float('inf')),(-1,.2),(.2,.1),(0,1)]:
   with self.subTest(start=start,end=end),self.assertRaises(ValueError):reference.extract(self.source,self.root/'invalid',start,end)
   self.assertFalse((self.root/'invalid').exists())
  out=self.root/'existing';out.mkdir();sentinel=out/'index.json';sentinel.write_text('existing evidence')
  with self.assertRaises(FileExistsError):reference.extract(self.source,out,0,.2)
  self.assertEqual(sentinel.read_text(),'existing evidence');self.assertEqual(reference.digest(self.source),pin)
 def test_empty_interval_records_failure_without_claiming_extraction(self):
  out=self.root/'empty'
  with self.assertRaises(RuntimeError):reference.extract(self.source,out,.1,.12,all_frames=True)
  result=json.loads((out/'index.json').read_text());self.assertEqual(result['status'],'failed');self.assertEqual(result['frames'],[])
 def test_nonzero_container_start_is_explicit_and_frames_use_normalized_clock(self):
  source=self.root/'offset.mkv'
  subprocess.run(['ffmpeg','-nostdin','-v','error','-i',str(self.source),'-vf','setpts=PTS+5/TB','-fps_mode','vfr','-c:v','ffv1',str(source)],check=True)
  result=reference.extract(source,self.root/'offset',.05,.25,all_frames=True)
  self.assertEqual(float(result['inputFormatStartSeconds']),5)
  self.assertEqual([f['seconds'] for f in result['frames']],[.08,.2,.24])
 def test_audio_outside_requested_interval_cannot_be_reported_as_extracted(self):
  source=self.root/'delayed-audio.mkv'
  subprocess.run(['ffmpeg','-nostdin','-v','error','-i',str(self.source),'-itsoffset','0.2','-f','lavfi','-i','sine=frequency=440:sample_rate=48000:duration=0.05','-c:v','copy','-c:a','pcm_s16le',str(source)],check=True)
  out=self.root/'no-audio-in-window'
  with self.assertRaisesRegex(RuntimeError,'PCM audio samples'):reference.extract(source,out,0,.05,all_frames=True)
  result=json.loads((out/'index.json').read_text());self.assertEqual(result['status'],'failed');self.assertIsNone(result['audio'])
 def test_audio_mix_extraction_has_its_own_hash_and_listening_status(self):
  source=self.root/'av.mkv'
  subprocess.run(['ffmpeg','-nostdin','-v','error','-i',str(self.source),'-f','lavfi','-i','sine=frequency=440:sample_rate=48000:duration=0.28','-c:v','copy','-c:a','pcm_s16le',str(source)],check=True)
  out=self.root/'audio';result=reference.extract(source,out,.05,.25,all_frames=True)
  self.assertEqual(result['audio']['sha256'],reference.digest(out/'audio.wav'));self.assertEqual(result['audio']['evidence'],'extracted-not-yet-listened')
  self.assertEqual(result['audio']['requestedStartSeconds'],.05)
  self.assertEqual(result['audio']['sampleRate'],48000);self.assertEqual(result['audio']['sampleCount'],9600)

if __name__=='__main__':unittest.main()
