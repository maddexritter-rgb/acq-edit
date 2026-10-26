"""Removed headline requests cannot install an owner or reach a native editor."""
import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'python'));sys.path.insert(0,str(ROOT/'scripts'))
import native,common,materialize,package_skills
class RemovedHeadlinesTests(unittest.TestCase):
 def test_fresh_package_and_routing_have_no_headline_owner(self):
  files,receipt=materialize.prepare(ROOT,ROOT/'assets')
  self.assertNotIn('text-hook',package_skills.OWNERS)
  self.assertFalse(any(name.startswith('text-hook/') for name in files))
  self.assertNotIn('text-hook/SKILL.md',receipt['executionContract']['entrypoints'])
  self.assertNotIn('Use skill: [text-hook]',files['edit/SKILL.md'].decode())
 def test_prepare_refuses_before_configuration_or_editor_import(self):
  with patch.object(native.importlib,'import_module') as load:
   with self.assertRaisesRegex(RuntimeError,'removed'):native.execute('hooks','filmcraft','missing-config.json')
   load.assert_not_called()
 def test_revision_refuses_before_editor_import(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);(root/'config.json').write_text('{}');(root/'project.json').write_text(json.dumps({'backend':'filmcraft','root':str(root)}));packet=root/'packet.json'
   for kind in ['text-hook','text-hook-remove']:
    packet.write_text(json.dumps({'kind':kind}))
    with patch.object(native.importlib,'import_module') as load:
     with self.assertRaisesRegex(RuntimeError,'removed'):native.execute('revise','filmcraft',root/'config.json',root/'project.json',packet)
     load.assert_not_called()
 def test_legacy_plan_is_not_silently_rendered_without_its_hook(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);file=root/'plan.json';file.write_text(json.dumps({'hookContract':{'legacy':True}}))
   with self.assertRaisesRegex(RuntimeError,'pinned toolkit'):common.plan({'root':str(root)},{'plan':str(file)})
