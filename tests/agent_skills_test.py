import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import agent_skills
import materialize


class Discovery(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='acq discovery ')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.home = self.base / 'isolated home'; self.home.mkdir()
        self.root = self.fixture('version one')

    def fixture(self, name):
        root = self.base / name
        (root / 'docs').mkdir(parents=True)
        (root / 'docs/AGENT_WORKFLOW.md').write_text('Fixed backend; standalone stages preserve unrelated layers.')
        entries = []
        for owner in ('edit', 'caption-clips', 'monday'):
            for name, data in [('SKILL.md', f'---\nname: {owner}\ndescription: Example workflow\n---\nUse __ACQ_SKILLS__/{owner}/scripts/helper.py'), ('scripts/helper.py', 'print("fixture")')]:
                relative = owner + '/' + name
                target = root / 'distribution/skills' / relative
                target.parent.mkdir(parents=True, exist_ok=True); target.write_text(data)
                entries.append({'path': relative, 'distribution_sha256': hashlib.sha256(target.read_bytes()).hexdigest()})
        (root / 'distribution/SOURCE_MANIFEST.json').write_text(json.dumps({'schema': 'acq-edit/source-manifest-v1', 'files': entries}))
        materialize.materialize(root, self.base / 'shared assets')
        return root

    def install(self, **kwargs):
        return agent_skills.register(self.root, 'codex', home=self.home, **kwargs)

    def test_workspace_discovery_is_routed_and_leaves_personal_skills_untouched(self):
        for agent, directory in agent_skills.AGENTS.items():
            result = agent_skills.register(self.root, agent, home=self.home)
            self.assertTrue(result['ready'])
            for owner in result['skills']:
                link = self.root / directory / 'skills' / owner
                self.assertTrue(link.is_symlink())
                self.assertEqual(link.resolve(), self.root / '.local/skills' / owner)
                self.assertIn('ACQ Edit execution route', (link / 'SKILL.md').read_text())
                self.assertNotIn('__ACQ_SKILLS__', (link / 'SKILL.md').read_text())
                self.assertTrue((link / 'scripts/helper.py').is_file())
            self.assertTrue(agent_skills.status(self.root, agent, home=self.home)['ready'])
        self.assertEqual(list(self.home.iterdir()), [])

    def test_personal_subset_and_repeat_keep_same_links(self):
        self.install(scope='user', only=['monday'])
        folder = self.home / '.agents/skills'
        before = (folder / 'monday').lstat().st_ino
        self.install(scope='user', only=['monday'])
        self.assertEqual((folder / 'monday').lstat().st_ino, before)
        self.assertEqual([p.name for p in folder.iterdir()], ['monday'])
        self.assertTrue(agent_skills.status(self.root, 'codex', 'user', ['monday'], self.home)['ready'])

    def test_existing_user_directory_blocks_entire_registration(self):
        folder = self.home / '.agents/skills'; (folder / 'monday').mkdir(parents=True)
        (folder / 'monday/SKILL.md').write_text('user-owned')
        with self.assertRaisesRegex(ValueError, 'existing user skill'):
            self.install(scope='user', update_owned=True)
        self.assertFalse((folder / 'edit').exists())
        self.assertEqual((folder / 'monday/SKILL.md').read_text(), 'user-owned')

    def test_foreign_symlink_and_symlink_parent_are_preserved(self):
        folder = self.home / '.agents/skills'; folder.mkdir(parents=True)
        (folder / 'edit').symlink_to(self.base / 'unrelated')
        with self.assertRaisesRegex(ValueError, 'existing user skill'):
            self.install(scope='user', only=['edit'], update_owned=True)
        self.assertEqual(os.readlink(folder / 'edit'), str(self.base / 'unrelated'))
        (self.home / '.claude').mkdir()
        (self.home / '.claude/skills').symlink_to(folder)
        with self.assertRaisesRegex(ValueError, 'Symlink discovery parent'):
            agent_skills.register(self.root, 'claude', 'user', home=self.home)

    def test_upgrade_changes_only_owned_links_and_preserves_old_runtime(self):
        self.install(scope='user')
        old = (self.root / '.local/skills/edit/SKILL.md').read_bytes()
        next_root = self.fixture('version two')
        with self.assertRaisesRegex(ValueError, 'update-owned'):
            agent_skills.register(next_root, 'codex', 'user', home=self.home)
        agent_skills.register(next_root, 'codex', 'user', only=['edit'], home=self.home, update_owned=True)
        self.assertEqual((self.home / '.agents/skills/edit').resolve(), next_root / '.local/skills/edit')
        self.assertEqual((self.home / '.agents/skills/monday').resolve(), self.root / '.local/skills/monday')
        self.assertEqual((self.root / '.local/skills/edit/SKILL.md').read_bytes(), old)

    def test_manually_retargeted_owned_link_is_not_overwritten(self):
        self.install(scope='user')
        link = self.home / '.agents/skills/edit'; link.unlink(); link.symlink_to(self.base / 'user-edited')
        with self.assertRaisesRegex(ValueError, 'existing user skill'):
            self.install(scope='user', only=['edit'], update_owned=True)
        self.assertEqual(os.readlink(link), str(self.base / 'user-edited'))

    def test_changed_runtime_refuses_exposure(self):
        (self.root / '.local/skills/edit/scripts/helper.py').write_text('changed')
        with self.assertRaises(RuntimeError): self.install()
        self.assertFalse((self.root / '.agents').exists())

    def test_unknown_names_and_tampered_source_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Unknown skill'): self.install(only=['../../outside'])
        (self.root / 'distribution/skills/edit/SKILL.md').write_text('changed')
        with self.assertRaisesRegex(ValueError, 'Changed packaged skill'): self.install()
        self.assertFalse((self.root / '.agents').exists())

    def test_check_is_read_only_and_reports_missing_and_broken(self):
        result = agent_skills.status(self.root, 'codex', home=self.home)
        self.assertFalse(result['ready'])
        self.assertFalse((self.root / '.agents').exists())
        self.install()
        link = self.root / '.agents/skills/edit'; link.unlink(); link.symlink_to(self.base / 'gone')
        result = agent_skills.status(self.root, 'codex', home=self.home)
        self.assertFalse(result['ready'])
        self.assertEqual(next(s for s in result['skills'] if s['name'] == 'edit')['state'], 'conflict')

    def test_packaged_launcher_routes_skills_without_node_build_or_editor(self):
        import acq_edit
        with patch.object(acq_edit, 'user_runtime', return_value=self.root), patch.object(acq_edit.os, 'chdir') as chdir, patch.object(acq_edit.os, 'execvp') as execute, patch.object(sys, 'argv', ['acq-edit', 'skills', 'install', '--agent', 'codex', '--only', 'monday']):
            acq_edit.main()
        command = execute.call_args.args[1]
        self.assertEqual(command, [sys.executable, str(self.root / 'scripts/agent_skills.py'), 'install', '--agent', 'codex', '--only', 'monday'])
        chdir.assert_called_once_with(self.root)
        self.assertFalse((self.root / 'dist').exists())

    def test_lock_prevents_parallel_writers(self):
        parent = self.root / '.agents'; parent.mkdir()
        (parent / 'acq-edit-skills.lock').write_text('123')
        with self.assertRaises(FileExistsError): self.install()
        self.assertEqual((parent / 'acq-edit-skills.lock').read_text(), '123')
        self.assertFalse((parent / 'skills/edit').exists())


if __name__ == '__main__': unittest.main()
