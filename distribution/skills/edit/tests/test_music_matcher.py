import importlib.util
import unittest
from unittest.mock import patch
from pathlib import Path

MATCHER = Path("__ACQ_SKILLS__/_shared/pick_music.py")
spec = importlib.util.spec_from_file_location("music_matcher", MATCHER)
music = importlib.util.module_from_spec(spec)
spec.loader.exec_module(music)


def fake(path, folder, tempo, energy, brightness, onset, mode="minor"):
    return {"path": str(music.ROOT / folder / path), "folder": folder,
            "tempo": tempo, "energy": energy, "brightness": brightness,
            "onset_density": onset, "perc_ratio": .18, "mode": mode, "duration": 180}


class MusicMatcherTests(unittest.TestCase):
 def test_transcript_profiles_are_materially_different(self):
    self.assertEqual(music.classify_text("We lost him and the grief changed my life")[0], "reflective_heavy")
    self.assertEqual(music.classify_text("This offer scaled profit to ten million")[0], "confident_modern")
    self.assertEqual(music.classify_text("A funny simple lifestyle story")[0], "playful_upbeat")

 @patch.object(music, "tag_map", return_value={})
 @patch.object(Path, "is_file", return_value=True)
 def test_profile_changes_the_winner(self, _, __):
    idx = {
        "soft.mp3": fake("soft.mp3", "(1) Calm", 82, .055, 950, 1.1),
        "hard.mp3": fake("hard.mp3", "(2) Core", 118, .155, 2250, 2.35),
    }
    review={"(1) Calm/soft.mp3":{"decision":"keep"},"(2) Core/hard.mp3":{"decision":"keep"}}
    self.assertEqual(Path(music.rank(idx, "reflective_heavy",review=review)[0]["path"]).name, "soft.mp3")
    self.assertEqual(Path(music.rank(idx, "urgent_dark",review=review)[0]["path"]).name, "hard.mp3")


 @patch.object(music, "tag_map", return_value={})
 @patch.object(Path, "is_file", return_value=True)
 def test_blacklist_rotation_and_review_rejection_are_hard_filters(self, _, __):
    idx = {
        "banned.mp3": fake("banned.mp3", "(1) Calm", 82, .055, 950, 1.1),
        "used.mp3": fake("used.mp3", "(1) Calm", 82, .055, 950, 1.1),
        "rejected.mp3": fake("rejected.mp3", "(1) Calm", 82, .055, 950, 1.1),
        "clean.mp3": fake("clean.mp3", "(1) Calm", 84, .057, 970, 1.15),
    }
    review = {"(1) Calm/banned.mp3":{"decision":"keep"},"(1) Calm/used.mp3":{"decision":"keep"},
              "(1) Calm/rejected.mp3":{"decision":"reject"},"(1) Calm/clean.mp3":{"decision":"keep"}}
    rows = music.rank(idx, "reflective_heavy", used=["used"], review=review, banned=["banned"])
    self.assertEqual([Path(x["path"]).name for x in rows], ["clean.mp3"])


 @patch.object(music, "tag_map", return_value={})
 @patch.object(Path, "is_file", return_value=True)
 def test_keep_feedback_is_profile_local_bonus(self, _, __):
    idx = {
        "a.mp3": fake("a.mp3", "(1) Calm", 82, .055, 950, 1.1),
        "b.mp3": fake("b.mp3", "(1) Calm", 85, .06, 1000, 1.2),
    }
    review = {"(1) Calm/b.mp3": {"decision": "keep", "tags": ["Emotional"]}}
    self.assertEqual(Path(music.rank(idx, "reflective_heavy", review=review)[0]["path"]).name, "b.mp3")

 @patch.object(music, "tag_map", return_value={})
 @patch.object(Path, "is_file", return_value=True)
 def test_best_song_section_is_returned(self, _, __):
    track=fake("arc.mp3","(1) Calm",82,.04,800,.8,"minor")
    track["segments"]=[{"start":0,"tempo":82,"energy":.25,"brightness":2400,"onset_density":2.6,"perc_ratio":.5,"mode":"minor"},
                       {"start":47,"tempo":82,"energy":.055,"brightness":950,"onset_density":1.1,"perc_ratio":.12,"mode":"minor"}]
    review={"(1) Calm/arc.mp3":{"decision":"keep"}}
    row=music.rank({"(1) Calm/arc.mp3":track},"reflective_heavy",review=review)[0]
    self.assertEqual(row["start"],47.0)

 @patch.object(music, "tag_map", return_value={})
 @patch.object(Path, "is_file", return_value=True)
 def test_unreviewed_inventory_is_excluded(self, _, __):
    self.assertEqual(music.rank({"x.mp3":fake("x.mp3","(1) Calm",82,.05,900,1)},"reflective_heavy",review={}),[])


if __name__ == "__main__":
    unittest.main()
