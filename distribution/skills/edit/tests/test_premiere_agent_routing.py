"""Regression checks for canonical discovery and scoped execution, without a host."""
from pathlib import Path
import importlib.util,json,sys,tempfile,unittest,os
from unittest.mock import patch
S=Path(__file__).resolve().parents[2];sys.path.insert(0,str(S/'_shared'));sys.path.insert(0,str(S/'edit/scripts'))
from premiere_bridge import Profile,PremiereBridge,BridgeError
from native_export_body import generate
from premiere_agent import STAGES

class Routing(unittest.TestCase):
 def test_default_profile_resolves_new_entrypoint(self):
  p=Profile.load();self.assertEqual(p.mode,'scoped-edit');self.assertIn('precision_bridge.mjs',p.command[1]);self.assertTrue(Path(p.command[0]).exists())
 def test_no_legacy_transport(self):
  for f in [S/'edit/scripts/pp_export_clips.py',S/'horizontal-to-vertical/scripts/premiere_native_reframe.py']:
   self.assertNotIn('.premiere-mcp-bridge',f.read_text());self.assertNotIn('cmd_{',f.read_text())
 def test_raw_script_helper_refuses_before_dispatch(self):
  from pp_export_clips import es
  with self.assertRaisesRegex(RuntimeError,'retired'):es('return true;')
 def test_input_generator_does_not_accept_raw_code(self):
  with self.assertRaises(ValueError):generate({'kind':'raw','arguments':{'script':'anything'}})
 def test_export_wrong_grid_refused(self):
  with self.assertRaises(ValueError):generate({'kind':'export','arguments':{'baseline':{},'start_ticks':'1','end_ticks':'100','preset_path':'/preset.epr','output_path':'/out.mp4','sample_rate':48000,'frame_ticks':100}})
 def test_inspection_escapes_identity(self):
  body=generate({'kind':'inspect','arguments':{'project_path':'/a";throw.prproj','sequence_id':'seq"'}})
  self.assertIn('a\\";throw.prproj',body);self.assertIn('TARGET_CHANGED',body)
 def test_scoped_edit_requires_scope_inside_fixtures_too(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);project=root/'p.prproj';project.touch()
   p=Profile(command=(sys.executable,),cwd=d,fixture_root=d,mode='scoped-edit',project_authorization=str(root/'auth.json'))
   class NoTransport:
    def call(*a):raise AssertionError('must refuse before any host call')
   c=PremiereBridge(p,NoTransport())
   plan={'schema':'edit.native-operation/v1','stage':'captions','operation_id':'one','tool':'lab_import_prepared_caption_sequence','arguments':{},'target':{'project_path':str(project),'sequence_id':'s','expected_revision':'a'*64},'intended_changes':['captions'],'protected_state':['dialogue']}
   with self.assertRaises(FileNotFoundError):c.submit(plan)
 def test_scope_excludes_raw_and_lifecycle(self):
  tools={t for v in STAGES.values() for t in v}
  self.assertTrue({'lab_apply_assembly_audio_edges','lab_export_exact_range','lab_import_prepared_caption_sequence'}<=tools)
  self.assertTrue(tools.isdisjoint({'execute_extendscript','open_project','close_project','move_clip','undo'}))
 def test_every_premiere_skill_has_startup_link(self):
  for p in S.rglob('SKILL.md'):
   if any(x in p.parts for x in ['_archive','.venv','node_modules']):continue
   content=p.read_text(errors='replace')
   if 'Premiere' in content:self.assertIn('premiere_start_here.md',content,str(p))
if __name__=='__main__':unittest.main()
