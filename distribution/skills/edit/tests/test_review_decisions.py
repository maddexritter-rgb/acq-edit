"""Regression for the pick_music.reviews defect.

vibe_music.py imported a symbol `reviews` that existed in no version of pick_music,
so MODE-music selection raised ImportError before it could run. The canonical
selector's own CLI loads review decisions with load_json(value, default); this test
pins that contract: the JSON is read AND handed to rank(review=...).
"""
import json, sys, tempfile, unittest
from pathlib import Path

SHARED = Path("__ACQ_SKILLS__") / "_shared"
sys.path.insert(0, str(SHARED))


class ReviewDecisionsTests(unittest.TestCase):
    def test_symbols_importable(self):
        import pick_music
        for name in ("ROOT", "classify_text", "load_rules", "rank",
                     "load_json", "DEFAULT_REVIEW"):
            self.assertTrue(hasattr(pick_music, name), f"pick_music.{name} missing")
        self.assertFalse(hasattr(pick_music, "reviews"),
                         "pick_music.reviews reappeared — vibe_music must use load_json")

    def test_load_json_reads_decisions(self):
        from pick_music import load_json
        payload = {"track-a.mp3": {"verdict": "approved"}, "track-b.mp3": {"verdict": "rejected"}}
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump(payload, fh); path = fh.name
        self.assertEqual(load_json(path, {}), payload)

    def test_load_json_defaults_when_absent(self):
        from pick_music import load_json
        self.assertEqual(load_json("/nonexistent/review.json", {}), {})

    def test_review_reaches_rank(self):
        """rank() must accept the loaded decisions via review= and not crash."""
        from pick_music import rank, load_json
        review = load_json("/nonexistent/review.json", {})
        rows = rank({}, review=review)
        self.assertIsInstance(rows, list)

    def test_vibe_music_uses_load_json(self):
        src = (Path(__file__).resolve().parents[1] / "scripts" / "vibe_music.py").read_text()
        self.assertIn("load_json(DEFAULT_REVIEW, {})", src)
        self.assertNotIn("reviews(DEFAULT_REVIEW)", src)


if __name__ == "__main__":
    unittest.main()
