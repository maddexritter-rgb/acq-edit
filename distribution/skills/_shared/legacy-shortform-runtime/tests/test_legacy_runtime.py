"""Contract tests for the legacy-shortform-runtime shared library.

Covers: silence_map output contract, transcribe_groq import/--help without
credentials, and the caption-clips training callers resolving to this library.
"""
import ast, json, os, subprocess, sys, unittest
from pathlib import Path

LIB = Path(__file__).resolve().parents[1] / "scripts"
SKILLS = Path(__file__).resolve().parents[3]


class LibraryShape(unittest.TestCase):
    def test_no_skill_md(self):
        self.assertFalse((LIB.parent / "SKILL.md").exists(),
                         "legacy-shortform-runtime must NOT be a loadable skill")

    def test_both_scripts_present_and_parse(self):
        for n in ("silence_map.py", "transcribe_groq.py"):
            p = LIB / n
            self.assertTrue(p.is_file(), f"{n} missing")
            ast.parse(p.read_text(encoding="utf-8"))


class SilenceMapContract(unittest.TestCase):
    def test_stdlib_only(self):
        t = ast.parse((LIB / "silence_map.py").read_text())
        mods = set()
        for n in ast.walk(t):
            if isinstance(n, ast.Import):
                for a in n.names: mods.add(a.name.split(".")[0])
            elif isinstance(n, ast.ImportFrom) and n.module:
                mods.add(n.module.split(".")[0])
        self.assertTrue(mods <= {"argparse","json","re","subprocess","sys","pathlib","__future__"},
                        f"unexpected non-stdlib imports: {mods}")

    def test_help_runs(self):
        r = subprocess.run([sys.executable, str(LIB / "silence_map.py"), "--help"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr[:300])
        self.assertIn("--out", r.stdout + r.stderr)

    def test_output_is_json_intervals(self):
        """edit/scripts/detect_fillers.py reads this file; the shape is a contract."""
        src = (LIB / "silence_map.py").read_text()
        self.assertIn("json", src)
        consumer = SKILLS / "edit" / "scripts" / "detect_fillers.py"
        if consumer.exists():
            c = consumer.read_text()
            self.assertIn("silence_map", c,
                          "edit/detect_fillers.py must still consume the silence map")


class TranscribeGroqContract(unittest.TestCase):
    def test_help_without_credentials(self):
        env = dict(os.environ); env.pop("GROQ_API_KEY", None)
        r = subprocess.run([sys.executable, str(LIB / "transcribe_groq.py"), "--help"],
                           capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 0, r.stderr[:300])
        self.assertNotIn("Traceback", r.stderr)

    def test_documented_runtime_contract(self):
        src = (LIB / "transcribe_groq.py").read_text()
        for token in ("GROQ_API_KEY", "faster-whisper", "FFMPEG"):
            self.assertIn(token, src, f"{token} missing from the script")
        readme = (LIB.parent / "README.md").read_text()
        for token in ("GROQ_API_KEY", "faster-whisper", "requests", "FFMPEG"):
            self.assertIn(token, readme, f"{token} undocumented in README")


class CallerResolution(unittest.TestCase):
    def test_caption_clips_training_resolves_here(self):
        for name in ("extract_oliver_style.py", "extract_caption_strips.py"):
            p = SKILLS / "caption-clips" / "training" / name
            self.assertTrue(p.is_file(), f"{name} missing")
            src = p.read_text()
            self.assertIn("legacy-shortform-runtime", src, f"{name} not repointed")
            self.assertNotIn(".agents/skills/shortform", src, f"{name} still points at a dead skill")
            tgt = p.resolve().parents[2] / "_shared/legacy-shortform-runtime/scripts/transcribe_groq.py"
            self.assertTrue(tgt.exists(), f"{name} resolves to a missing target")


class TranscriptEditBehaviour(unittest.TestCase):
    def test_dead_vars_gone_and_module_parses(self):
        p = SKILLS / "transcript-edit" / "scripts" / "apply_transcript_edit.py"
        t = ast.parse(p.read_text())
        names = {n.id for n in ast.walk(t) if isinstance(n, ast.Name)}
        self.assertNotIn("FONTS_DIR", names)
        self.assertNotIn("PRESETS", names)

    def test_skill_md_does_not_route_to_a_missing_skill(self):
        s = (SKILLS / "transcript-edit" / "SKILL.md").read_text()
        self.assertNotIn("skills/shortform", s)
        self.assertIn("legacy-shortform-runtime", s)


if __name__ == "__main__":
    unittest.main()
