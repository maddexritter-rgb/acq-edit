import copy,sys,unittest,math
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import music_agent_fixture as checker
import music_revision_test as fixtures

class MusicAgentFixtureTests(unittest.TestCase):
 def fixture(self):
  old,new,before,after=fixtures.MusicRevisionTests().fixture()
  for spec in [old,new]:
   bed=spec['audio']['music'][0];bed.update(samples=28800,fadeInSamples=3840,fadeOutSamples=3840);spec['audio']['music'].append({**old['audio']['music'][0],'id':'second','startFrame':30})
  for data in [before,after]:
   clips=data['project']['items']['1']['kind']['Sequence']['audio_tracks'][1]['items'];clips[0]['duration']=28800*254016000000//48000;clips.append({**copy.deepcopy(before['project']['items']['1']['kind']['Sequence']['audio_tracks'][1]['items'][0]),'id':7,'start':30*254016000000//25})
  return old,new,before,after
 def test_exact_requested_source_replacement_passes(self):
  old,new,a,b=self.fixture();checker.expected_revision(old,new,new['sources'][-1]);checker.native_state(a,b,old,new,'revision')
 def test_plan_checker_rejects_other_bed_timing_dialogue_or_cut_changes(self):
  old,new,_,_=self.fixture()
  for change in [lambda s:s['cuts'].append('extra'),lambda s:s['audio'].update(gainDb=-6),lambda s:s['audio']['music'][1].update(sourceId='b'),lambda s:s['audio']['music'][0].update(sourceInSample=0),lambda s:s['sources'][0].update(sha256='changed')]:
   value=copy.deepcopy(new);change(value)
   with self.assertRaises(RuntimeError):checker.expected_revision(old,value,new['sources'][-1])
 def test_native_checker_rejects_changed_automation_captions_dialogue_and_unselected_bed(self):
  old,new,a,b=self.fixture()
  for change in [lambda s:s['audio_tracks'][1]['items'][0]['effects'][1]['params']['level']['keyframes'].clear(),lambda s:s['video_tracks'][0]['items'].clear(),lambda s:s['audio_tracks'][0]['items'].clear(),lambda s:s['audio_tracks'][1]['items'][1].update(item=4)]:
   value=copy.deepcopy(b);change(value['project']['items']['1']['kind']['Sequence'])
   with self.assertRaises(RuntimeError):checker.native_state(a,value,old,new,'revision')

 def signals(self,selected=1320,unselected=220,dialogue_gain=-3):
  def signal(first,last,dialogue):
   return [.125*10**(dialogue/20)*math.sin(2*math.pi*440*i/48000)+(.125*10**(-12/20)*math.sin(2*math.pi*(first if i<48000 else last)*i/48000) if 9600<=i<38400 or 57600<=i<86400 else 0) for i in range(96000)]
  return signal(220,220,-3),signal(selected,unselected,dialogue_gain)
 def test_audio_checker_requires_replacement_tone_and_preserved_dialogue_and_second_bed(self):
  for selected,unselected,gain in [(1320,220,-3),(220,220,-3),(1320,1320,-3),(1320,220,-6)]:
   with patch.object(checker,'audio',side_effect=self.signals(selected,unselected,gain)),patch.object(checker.subprocess,'check_output',return_value=b'identical picture'):
    if (selected,unselected,gain)==(1320,220,-3):self.assertTrue(checker.rendered([{'media':'a'},{'media':'b'}])['picturesIdentical'])
    else:
     with self.assertRaises(RuntimeError):checker.rendered([{'media':'a'},{'media':'b'}])
 def test_picture_checker_refuses_changed_pixels(self):
  with patch.object(checker,'audio',side_effect=self.signals()),patch.object(checker.subprocess,'check_output',side_effect=[b'before',b'after']):
   with self.assertRaisesRegex(RuntimeError,'decoded pictures'):checker.rendered([{'media':'a'},{'media':'b'}])

if __name__=='__main__':unittest.main()
