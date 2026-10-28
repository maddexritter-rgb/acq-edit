"""Sanitized teammate failures; no accounts or global skills needed."""
import contextlib,io,json,os,sys,subprocess,tempfile,unittest,importlib.util
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'));sys.path.insert(0,str(ROOT/'python'))
import onboard,install_engine,brain_receipts

def module(name,file):
 spec=importlib.util.spec_from_file_location(name,file);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
asr=module('team_asr',ROOT/'distribution/skills/_shared/asr.py')
transcribe=module('team_transcribe',ROOT/'distribution/skills/caption-clips/scripts/transcribe.py')

class TeamOnboarding(unittest.TestCase):
 def test_engine_onboarding_reaches_setup_without_a_second_agent_cli(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/'release.json').write_text('{}');calls=[]
   def execute(args,**kwargs):calls.append([str(x) for x in args])
   with patch.object(onboard,'ROOT',root),patch.object(onboard.sys,'platform','darwin'),patch.object(onboard.sys,'argv',['onboard','filmcraft','claude','--non-interactive','--defer-delivery']),patch('runtime_environment.execution_environment',return_value={}),patch.object(onboard.shutil,'which',side_effect=lambda name:None if name in ('claude','codex') else '/fixture/'+name) as which,patch.object(install_engine,'preflight',return_value={'errors':[]}),patch.object(onboard,'assets',return_value=root/'bundle'),patch.object(onboard,'install_fonts'),patch.object(onboard,'install_brain',return_value=root/'brain'),patch.object(onboard,'execute',side_effect=execute),patch.object(onboard,'ensure_credentials'),patch.object(onboard,'configure_delivery',return_value={'ready':False,'deferred':True}),contextlib.redirect_stdout(io.StringIO()):
    onboard.main()
   self.assertTrue(any('setup' in c and '--non-interactive' in c for c in calls))
   self.assertFalse(any(x.args[0] in ('claude','codex') for x in which.call_args_list))
   self.assertFalse(any('agent-check' in c or '--background' in c for c in calls))

 def test_broken_existing_media_binary_is_not_ready(self):
  with patch.object(install_engine.shutil,'which',side_effect=lambda n:'/fixture/'+n),patch.object(install_engine,'output',return_value='v24.1.0'),patch.object(install_engine.subprocess,'run',return_value=subprocess.CompletedProcess([],127,'','dyld missing secret-path')):
   result=install_engine.preflight('premiere')
  self.assertFalse(result['prerequisitesPresent']);self.assertEqual(len(result['errors']),2)
  self.assertNotIn('secret-path',str(result));self.assertTrue(all('cannot run' in x for x in result['errors']))
 def test_media_timeout_and_wrong_binary_fail(self):
  for outcome in [OSError(),subprocess.TimeoutExpired('ffmpeg',15),subprocess.CompletedProcess([],0,'unrelated executable','')]:
   with patch.object(install_engine.subprocess,'run',side_effect=outcome if isinstance(outcome,Exception) else None,return_value=outcome):
    self.assertFalse(install_engine.media_tool_ready('/fixture/ffmpeg','ffmpeg'))
  with patch.object(install_engine.subprocess,'run',return_value=subprocess.CompletedProcess([],0,'ffmpeg version 9.0','')):
   self.assertTrue(install_engine.media_tool_ready('/fixture/ffmpeg','ffmpeg'))
 def test_shared_credentials_reuse_and_explicit_reentry(self):
  with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'ACQ_EDIT_CREDENTIALS_HOME':d},clear=True),patch.object(onboard,'execute') as execute:
   f=Path(d)/'credentials.json';f.write_text(json.dumps({'ASSEMBLYAI_API_KEY':'private-aai','GEMINI_API_KEY':'private-gemini'}));f.chmod(0o600);before=f.read_bytes()
   with contextlib.redirect_stdout(io.StringIO()) as output:self.assertEqual(onboard.ensure_credentials(),'reused')
   execute.assert_not_called();self.assertNotIn('private-',output.getvalue());self.assertEqual(f.read_bytes(),before)
   onboard.ensure_credentials(True);execute.assert_called_once()
 def test_missing_key_opens_form_and_cancel_does_not_defer(self):
  with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'ACQ_EDIT_CREDENTIALS_HOME':d},clear=True),patch.object(onboard,'execute',side_effect=subprocess.CalledProcessError(1,['credentials'])):
   with self.assertRaises(subprocess.CalledProcessError):onboard.ensure_credentials()
 def test_private_credential_validation_preserves_bad_file(self):
  with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'ACQ_EDIT_CREDENTIALS_HOME':d},clear=True),patch.object(onboard,'execute') as execute:
   f=Path(d)/'credentials.json';f.write_text('not json');f.chmod(0o600)
   with self.assertRaisesRegex(ValueError,'unreadable'):onboard.ensure_credentials()
   self.assertEqual(f.read_text(),'not json');execute.assert_not_called()
 def test_delivery_deferral_then_resume(self):
  with tempfile.TemporaryDirectory() as d,patch.object(onboard,'delivery_connections') as connect,patch.object(onboard,'delivery_check',return_value={'ready':True}):
   f=Path(d)/'state.json';state={'steps':{'engine':'completed'}}
   stage=lambda name,work:work()
   value=onboard.configure_delivery(state,f,stage,True);self.assertTrue(value['deferred']);connect.assert_not_called()
   self.assertEqual(json.loads(f.read_text())['steps']['delivery'],'deferred-by-user')
   self.assertTrue(onboard.configure_delivery(state,f,stage)['ready']);connect.assert_called_once()
   self.assertEqual(state['steps']['engine'],'completed');self.assertEqual(state['steps']['delivery'],'read-verified')
 def test_delivery_cancel_remains_pending(self):
  with tempfile.TemporaryDirectory() as d,patch.object(onboard,'delivery_connections',side_effect=subprocess.CalledProcessError(1,['form'])):
   state={'steps':{}};f=Path(d)/'state.json'
   with self.assertRaises(subprocess.CalledProcessError):onboard.configure_delivery(state,f,lambda name,work:work())
   self.assertEqual(state['steps']['delivery'],'pending')
 def test_bad_brain_input_never_reserves_directory_or_fetches(self):
  with tempfile.TemporaryDirectory() as d,patch.object(brain_receipts,'owner') as owner:
   owner.return_value.FORMATS=['monologue'];project={'root':d,'id':'p'}
   for problem in ['x','x'*241]:
    with self.assertRaises(brain_receipts.InvalidBrainRequest):brain_receipts.fetch(project,{},dict(format='monologue',problem=problem,output=d+'/10_WORK/guidance'))
   owner.return_value.fetch_context.assert_not_called();self.assertFalse((Path(d)/'10_WORK').exists())
 def test_asr_uses_shared_toolkit_credentials_not_personal_fallback(self):
  with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'ACQ_EDIT_CREDENTIALS_HOME':d,'ASSEMBLYAI_API_KEY':'env-key'},clear=True),patch.object(asr.Path,'home',side_effect=AssertionError('personal fallback')):
   f=Path(d)/'credentials.json';f.write_text('{"ASSEMBLYAI_API_KEY":"saved-key"}');f.chmod(0o600)
   self.assertEqual(asr.assemblyai_keys(),['saved-key'])
 def test_asr_failure_never_silently_switches_provider(self):
  with patch.object(asr,'_wav16',return_value='/nonexistent'),patch.object(asr,'assemblyai_keys',return_value=['key']),patch.object(asr,'_assemblyai',return_value=None),patch.object(asr,'_groq') as groq,patch.object(asr,'_mlx') as mlx:
   with self.assertRaisesRegex(asr.AsrUnavailable,'No alternate provider'):asr.transcribe('/fixture',use_cache=False,profile='editorial_ingest')
   groq.assert_not_called();mlx.assert_not_called()
 def test_caption_help_does_not_require_optional_whisper(self):
  r=subprocess.run([sys.executable,str(ROOT/'distribution/skills/caption-clips/scripts/transcribe.py'),'--help'],capture_output=True,text=True)
  self.assertEqual(r.returncode,0,r.stderr);self.assertIn('--provider',r.stdout)

if __name__=='__main__':unittest.main()

class MediaPrerequisites(unittest.TestCase):
 def test_existing_broken_provider_is_never_replaced(self):
  import media_prerequisites as media
  with patch.object(media.shutil,'which',return_value='/existing/ffmpeg'),patch.object(media.subprocess,'run',return_value=subprocess.CompletedProcess([],127,'','')) as run:
   with self.assertRaisesRegex(ValueError,'preserved'):media.check(True)
   self.assertTrue(all(x.args[0][-1]=='-version' for x in run.call_args_list))
 def test_unlinked_tap_provider_is_preserved(self):
  import media_prerequisites as media
  with patch.object(media.shutil,'which',side_effect=lambda name:'/managed/brew' if name=='brew' else None),patch.object(media.subprocess,'run',return_value=subprocess.CompletedProcess([],0,'homebrew-ffmpeg/ffmpeg/ffmpeg\n','')) as run:
   with self.assertRaisesRegex(ValueError,'already installed'):media.check(True)
   self.assertEqual(run.call_count,1)
 def test_only_missing_provider_uses_existing_managed_brew(self):
  import media_prerequisites as media
  installed=False;calls=[]
  def which(name):return '/managed/brew' if name=='brew' else '/media/'+name if installed else None
  def run(args,**kwargs):
   nonlocal installed
   calls.append(args)
   if args[1]=='install':installed=True
   return subprocess.CompletedProcess(args,0,Path(args[0]).name+' version 9' if args[-1]=='-version' else '', '')
  with patch.object(media.shutil,'which',side_effect=which),patch.object(media.subprocess,'run',side_effect=run):self.assertTrue(media.check(True)['ready'])
  self.assertIn(['/managed/brew','install','ffmpeg'],calls)
