import json,sys,unittest
from pathlib import Path
from unittest.mock import patch,Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
from common import verify_native_render
class RenderVerificationTests(unittest.TestCase):
 def spec(self):return {'width':640,'height':360,'fps':{'numerator':25,'denominator':1},'cuts':[{'frames':25},{'frames':25}]}
 def video(self):return {'codec_type':'video','width':640,'height':360,'avg_frame_rate':'25/1','nb_read_frames':'50'}
 def test_host_complete_audio_only_export_is_not_a_video_success(self):
  with patch('common.subprocess.check_output',return_value=json.dumps({'streams':[{'codec_type':'audio'},{'codec_type':'data'}]}).encode()),patch('common.subprocess.run') as decode:
   with self.assertRaisesRegex(RuntimeError,'picture stream'):verify_native_render('host-completed.mp4',self.spec())
   decode.assert_not_called()
 def test_wrong_geometry_clock_and_truncated_frames_are_rejected(self):
  for values in [{'width':320},{'avg_frame_rate':'30/1'}]:
   video={**self.video(),**values}
   with self.subTest(values=values),patch('common.subprocess.check_output',return_value=json.dumps({'streams':[video,{'codec_type':'audio'}]}).encode()),self.assertRaises(RuntimeError):verify_native_render('wrong.mp4',self.spec())
 def test_expected_streams_still_need_successful_full_decode(self):
  streams={'streams':[self.video(),{'codec_type':'audio'}]}
  with patch('common.subprocess.check_output',return_value=json.dumps(streams).encode()),patch('common.subprocess.run',return_value=Mock(stdout=b'frame=50\nprogress=end\n')) as decode:
   result=verify_native_render('expected.mp4',self.spec());self.assertTrue(result['fullDecode']);self.assertTrue(decode.call_args.kwargs['check']);self.assertIn('-xerror',decode.call_args.args[0])
   decode.side_effect=RuntimeError('decode failed')
   with self.assertRaisesRegex(RuntimeError,'decode failed'):verify_native_render('damaged.mp4',self.spec())
 def test_single_decode_counts_actual_frames_and_requires_completion(self):
  streams={'streams':[self.video(),{'codec_type':'audio'}]}
  for progress in [b'frame=49\nprogress=end\n',b'frame=50\nprogress=continue\n',b'progress=end\n']:
   with self.subTest(progress=progress),patch('common.subprocess.check_output',return_value=json.dumps(streams).encode()),patch('common.subprocess.run',return_value=Mock(stdout=progress)),self.assertRaisesRegex(RuntimeError,'frame count'):
    verify_native_render('incomplete.mp4',self.spec())
if __name__=='__main__':unittest.main()
