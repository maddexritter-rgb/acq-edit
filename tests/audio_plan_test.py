import copy,json,math,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
from audio_plan import validate_audio,resolve_music_frames,linear_fade_points
from common import sha
class AudioPlanTests(unittest.TestCase):
 def fixture(self,root):
  receipt=Path(root)/'selection.json';receipt.write_text('{}')
  bed={'id':'bed','sourceId':'music','startFrame':5,'sourceInSample':48000,'samples':76800,'gainDb':-12,'fadeInSamples':9600,'fadeOutSamples':9600,'receiptPath':str(receipt),'receiptSha256':sha(receipt)}
  return {'root':root},{'fps':{'numerator':25,'denominator':1},'sampleRate':48000,'sources':[{'id':'music'}],'audio':{'music':[bed]}}
 def test_rejects_missing_changed_or_external_selection_evidence(self):
  with tempfile.TemporaryDirectory() as root:
   project,spec=self.fixture(root);self.assertEqual(len(validate_audio(project,spec,50)),1)
   Path(spec['audio']['music'][0]['receiptPath']).write_text('changed')
   with self.assertRaisesRegex(RuntimeError,'receipt changed'):validate_audio(project,spec,50)
   spec['audio']['music'][0]['receiptPath']='/outside/selection.json'
   with self.assertRaisesRegex(RuntimeError,'outside'):validate_audio(project,spec,50)
 def test_refuses_overlaps_rounding_and_ignored_effects(self):
  with tempfile.TemporaryDirectory() as root:
   project,spec=self.fixture(root);bed=spec['audio']['music'][0]
   self.assertEqual(resolve_music_frames(spec,bed)['sourceInSample'],25)
   for patch in [{'samples':1},{'gainDb':float('nan')},{'ducking':'automatic'},{'fadeInSamples':80000},{'sourceId':'missing'}]:
    changed=copy.deepcopy(spec);changed['audio']['music'][0].update(patch)
    with self.assertRaises(RuntimeError):
     validate_audio(project,changed,50);resolve_music_frames(changed,changed['audio']['music'][0])
   second=copy.deepcopy(bed);second['id']='other';spec['audio']['music'].append(second)
   with self.assertRaisesRegex(RuntimeError,'overlap'):validate_audio(project,spec,50)
 def test_dB_lane_fade_tracks_linear_amplitude_and_preserves_sample_endpoints(self):
  bed={'gainDb':-12,'samples':76800,'fadeInSamples':9600,'fadeOutSamples':9600}
  points=dict(linear_fade_points(bed,48000));self.assertEqual(points[0],-96);self.assertEqual(points[76800],-96)
  self.assertAlmostEqual(points[4800],-12+20*math.log10(.5),places=6)
  self.assertAlmostEqual(points[72000],points[4800]);self.assertEqual(points[9600],-12)
  self.assertEqual(points[67200],-12)
if __name__=='__main__':unittest.main()
