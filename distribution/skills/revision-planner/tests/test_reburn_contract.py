"""Caller-contract test for the subtitle-reburn recipe in references/patch-recipes.md.

The recipe used to call a `caption-burner/scripts/burn.py` that no longer exists in any
skill root (recorded in migration/DEPENDENCY_DEFECTS.md). Its successor is
caption-clips/scripts/burn_captions.py, which has a DIFFERENT interface: positional
`input subs` plus REQUIRED --start/--end, because it trims out of a source while burning.

For the revision-planner reburn case the input is an ALREADY-CUT v1 clip, so the correct
translation is --start 0 --end <clip duration>. These tests pin that translation so the
recipe cannot silently rot again: they assert the documented flags match the real argparse
interface, and they run an actual burn end to end.
"""
import json, re, subprocess, sys, tempfile, unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
RECIPES = SKILL / "references" / "patch-recipes.md"
BURN = SKILL.parents[0] / "caption-clips" / "scripts" / "burn_captions.py"


def reburn_block() -> str:
    """The fenced shell block that invokes the burner — not the prose that names it."""
    for m in re.finditer(r"```(?:bash|sh)?\n(.*?)```", RECIPES.read_text(), re.S):
        if "burn_captions.py" in m.group(1):
            return m.group(1)
    raise AssertionError("no fenced block invokes burn_captions.py")


def ffmpeg_libass():
    sys.path.insert(0, str(SKILL.parents[0] / "_shared"))
    from ffmpeg_bin import require_libass
    return require_libass("test_reburn_contract")


class TestRecipeMatchesRealInterface(unittest.TestCase):
    def test_successor_exists(self):
        self.assertTrue(BURN.exists(), f"successor burner missing: {BURN}")

    def test_recipe_does_not_reference_the_dead_burner(self):
        t = RECIPES.read_text()
        self.assertNotIn("caption-burner/scripts/burn.py", t,
                         "recipe still points at the removed caption-burner")

    def test_recipe_names_the_successor(self):
        self.assertIn("caption-clips/scripts/burn_captions.py", RECIPES.read_text())

    def test_every_flag_in_the_recipe_is_a_real_flag(self):
        block = reburn_block()
        used = set(re.findall(r"(--[a-z-]+)", block))
        real = set(re.findall(r'ap\.add_argument\("(--[a-z-]+)"', BURN.read_text()))
        self.assertTrue(used, "recipe shows no flags")
        self.assertEqual(used - real, set(), f"recipe uses flags the burner does not accept: {used - real}")

    def test_required_flags_are_present_in_the_recipe(self):
        real = BURN.read_text()
        required = {m for m in re.findall(r'ap\.add_argument\("(--[a-z-]+)"[^)]*required=True', real)}
        block = reburn_block()
        missing = {r for r in required if r not in block}
        self.assertEqual(missing, set(), f"recipe omits required flags: {missing}")

    def test_recipe_passes_the_two_positionals(self):
        block = reburn_block()
        # positionals appear as bare <placeholder> tokens, not behind a flag
        self.assertIn("<v1_clip>", block)
        self.assertIn(".patched.ass", block)


class TestRealBurn(unittest.TestCase):
    """End-to-end: an already-cut clip + patched .ass, burned with --start 0 --end <dur>."""

    def test_reburn_of_an_already_cut_clip(self):
        ff = ffmpeg_libass()
        probe = ff.replace("/ffmpeg", "/ffprobe")
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            clip, subs, out = d / "v1.mp4", d / "v1.patched.ass", d / "reburn.mp4"
            subprocess.run([ff, "-y", "-hide_banner", "-loglevel", "error",
                            "-f", "lavfi", "-i", "color=c=black:s=320x180:d=2:r=24",
                            "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono",
                            "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                            "-c:a", "aac", str(clip)], check=True)
            subs.write_text(
                "[Script Info]\nScriptType: v4.00+\nPlayResX: 320\nPlayResY: 180\n\n"
                "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, Alignment, MarginV\n"
                "Style: D,Arial,48,&H00FFFFFF,5,10\n\n"
                "[Events]\nFormat: Layer, Start, End, Style, Text\n"
                "Dialogue: 0,0:00:00.00,0:00:02.00,D,PATCHED\n")

            dur = float(subprocess.run(
                [probe, "-v", "error", "-show_entries", "format=duration",
                 "-of", "csv=p=0", str(clip)], capture_output=True, text=True).stdout.strip())

            # THE CONTRACT under test: already-cut input -> start 0, end = duration.
            r = subprocess.run([sys.executable, str(BURN), str(clip), str(subs),
                                "--start", "0", "--end", f"{dur}", "--out", str(out)],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, f"burn failed:\n{r.stdout}\n{r.stderr}")
            self.assertTrue(out.exists() and out.stat().st_size > 0, "no output written")

            got = float(subprocess.run(
                [probe, "-v", "error", "-show_entries", "format=duration",
                 "-of", "csv=p=0", str(out)], capture_output=True, text=True).stdout.strip())
            self.assertAlmostEqual(got, dur, delta=0.25,
                                   msg=f"reburn changed duration: {dur} -> {got}")

            # Captions actually burned: the source is pure black, so any bright pixel is the text.
            # metadata=print writes at the "info" log level; file=- sends it to stdout so
            # the probe does not depend on ffmpeg's verbosity.
            probe_run = subprocess.run(
                [ff, "-v", "error", "-i", str(out), "-vf",
                 "select=eq(n\\,12),signalstats,metadata=print:key=lavfi.signalstats.YMAX:file=-",
                 "-vframes", "1", "-f", "null", "-"],
                capture_output=True, text=True)
            stats = probe_run.stdout + probe_run.stderr
            m = re.search(r"YMAX=(\d+)", stats)
            self.assertIsNotNone(m, f"could not read luma stats:\n{stats}")
            self.assertGreater(int(m.group(1)), 100,
                               "output frame is still black — captions were not burned in")


if __name__ == "__main__":
    unittest.main(verbosity=2)
