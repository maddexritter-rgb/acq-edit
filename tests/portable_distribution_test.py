import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from portable_patches import private_references, portable_distribution


class PortableDistributionTests(unittest.TestCase):
    def test_missing_explicit_fonts_fail_before_creating_artifacts(self):
        if importlib.util.find_spec('PIL') is None:
            self.skipTest('Shared Pillow dependency is required for graphic helper execution')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);out=root/'graphics'
            script=ROOT/'distribution/skills/ad-edit/scripts/make_graphics.py'
            for args in [[str(out)], [str(out),str(root/'missing.ttf')]]:
                run=subprocess.run([sys.executable,str(script),*args],text=True,capture_output=True)
                self.assertNotEqual(run.returncode,0);self.assertFalse(out.exists())
                self.assertIn('font',run.stderr.lower())
            config=root/'config.json';config.write_text(json.dumps({'source':'missing.mp4','out':str(root/'preview.mp4')}))
            run=subprocess.run([sys.executable,str(ROOT/'distribution/skills/ad-edit/scripts/render_ad.py'),str(config)],cwd=root,text=True,capture_output=True)
            self.assertNotEqual(run.returncode,0);self.assertIn('font',run.stderr.lower())
            self.assertEqual(list(root.iterdir()),[config])

    def test_drive_wrapper_preserves_arguments_and_uses_only_the_toolkit_owner(self):
        with tempfile.TemporaryDirectory(prefix='portable intake spaces ') as tmp:
            root = Path(tmp)
            node = root / 'node'
            node.write_text('#!' + sys.executable + '\nimport json,sys\nprint(json.dumps(sys.argv[1:]))\n')
            node.chmod(0o755)
            script = root / 'gdrive_pull.sh'
            script.write_text((ROOT / 'distribution/skills/footage-fetch/scripts/gdrive_pull.sh').read_text().replace('__ACQ_TOOLKIT__', str(root)))
            env = {**os.environ, 'PATH': str(root) + os.pathsep + os.environ['PATH']}
            for url, command in [('https://drive.google.com/file/d/test/view?x=a&b=c', 'drive'), ('https://drive.google.com/drive/folders/test', 'drive-folder')]:
                run = subprocess.run(['/bin/bash', str(script), 'project-id', url, 'team remote'], env=env, text=True, capture_output=True)
                self.assertEqual(run.returncode, 0, run.stderr)
                self.assertEqual(json.loads(run.stdout), [str(root/'dist/cli.js'), command, 'project-id', url, 'team remote'])
            invalid = subprocess.run(['/bin/bash', str(script), 'project-id', 'ambiguous-id'], env=env, text=True, capture_output=True)
            self.assertEqual(invalid.returncode, 2)
            self.assertFalse(invalid.stdout)

    def test_phrase_locator_keeps_zero_clock_and_reports_repeated_words_without_padding(self):
        spec = importlib.util.spec_from_file_location('portable_phrase', ROOT / 'distribution/skills/edit/scripts/cut_by_phrase.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        words = [{'word': w, 'start': i, 'end': i+.5} for i, w in enumerate(['Hook!', 'reason', 'Payoff.', 'Hook!', 'detail', 'Payoff.'])]
        pairs = module.candidates(words, 0, 'hook', 'payoff')
        self.assertEqual([(p['hook']['wordStart'], p['payoff']['wordEnd']) for p in pairs], [(0, 2), (0, 5), (3, 5)])
        self.assertEqual(pairs[0]['hook']['start'], 0)
        self.assertEqual(pairs[0]['payoff']['end'], 2.5)
        self.assertEqual(module.candidates(words, 0, 'absent', 'payoff'), [])
        with self.assertRaises(ValueError): module.candidates(words, float('nan'), 'hook', 'payoff')
        with self.assertRaises(ValueError): module.candidates(words, 0, '!!!', 'payoff')
        with self.assertRaises(ValueError): module.candidates(list(reversed(words)), 0, 'hook', 'payoff')

    def test_phrase_cli_is_read_only_and_pins_the_supplied_transcript(self):
        import hashlib
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); transcript=root/'words.json'
            raw=json.dumps({'words':[{'word':'Hook','start':0,'end':.2},{'word':'payoff','start':1,'end':1.5}]}).encode()
            transcript.write_bytes(raw)
            run=subprocess.run([sys.executable,str(ROOT/'distribution/skills/edit/scripts/cut_by_phrase.py'),'--transcript',str(transcript),'--near','0','--hook','Hook','--payoff','payoff'],cwd=root,text=True,capture_output=True)
            self.assertEqual(run.returncode,0,run.stderr);result=json.loads(run.stdout)
            self.assertTrue(result['locatorOnly']);self.assertTrue(result['requiresSourceWordDesign'])
            self.assertEqual(result['transcriptSha256'],hashlib.sha256(raw).hexdigest())
            self.assertEqual(transcript.read_bytes(),raw);self.assertEqual(list(root.iterdir()),[transcript])

    def test_private_shell_roots_are_detected_and_reviewed_overrides_are_pinned(self):
        for text in ['$HOME/Downloads/cluade/scripts/new_project.sh','${HOME}/.agents/skills/edit','$HOME/.claude/skills/edit','__ACQ_LEGACY_HOME__/source']:
            self.assertTrue(private_references(text))
        self.assertFalse(private_references('/System/Volumes/Data'))
        manifest=json.loads((ROOT/'distribution/SOURCE_MANIFEST.json').read_text())
        for name in ['footage-fetch/SKILL.md','footage-fetch/scripts/gdrive_pull.sh','edit/scripts/cut_by_phrase.py']:
            generated,transforms=portable_distribution('legacy source',name)
            self.assertEqual(generated,(ROOT/'distribution/skills'/name).read_text())
            entry=next(e for e in manifest['files'] if e['path']==name)
            self.assertIn(transforms[0],entry['transforms'])
            self.assertTrue(entry['source_sha256'])


if __name__ == '__main__':
    unittest.main()
