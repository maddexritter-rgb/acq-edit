import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
from inspect_cut_boundaries import make_rows, pin, prepare, routing_binding


class InspectionTests(unittest.TestCase):
    def setUp(self):
        self.words = [
            {"word_index": 0, "word": "complete", "start": .15, "end": .22},
            {"word_index": 1, "word": "um", "start": .4, "end": .55},
            {"word_index": 2, "word": "next", "start": .9, "end": 1.1},
        ]
        self.clip = {"interaction_word_range": [0,2], "kept_word_ranges": [[0,0],[2,2]]}

    def test_all_edges_and_disagreeing_phoneme_locator_are_visible(self):
        ph = {"words": {"0": {**self.words[0], "aligned_start": .1, "aligned_end": .29}}}
        rows, words, phones = make_rows(self.clip, self.words, ph, context=.1)
        self.assertEqual([r["kind"] for r in rows], ["head","tail","head","tail"])
        self.assertAlmostEqual(rows[1]["end"], .39)
        self.assertEqual(words[1]["word"], "um")  # omitted neighbor remains in context
        self.assertEqual(self.words[0]["end"], .22)  # original locators never rewritten
        self.assertTrue(all(r["status"] == "DIAGNOSTIC_ONLY_NOT_INSPECTED" for r in rows))

    def test_internal_gap_and_stretched_label_are_locators_only(self):
        clip = {**self.clip, "kept_word_ranges": [[0,2]]}
        perf = {"events": [{"id":"word_2", "kind":"stretched_word"}]}
        rows, _, _ = make_rows(clip, self.words, performance=perf, pause=.2)
        self.assertTrue(any(r["kind"] == "pause_locator" for r in rows))
        self.assertTrue(any(r["kind"] == "stretched_word" for r in rows))
        self.assertFalse(any("out_window" in r or "in_window" in r for r in rows))

    def test_wrong_word_occurrence_is_not_silently_accepted(self):
        with self.assertRaisesRegex(ValueError, "identity"):
            make_rows(self.clip, self.words, {"words":{"0":{**self.words[0],"word_index":2}}})

    def test_routing_receipt_and_media_are_bound(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/"routing-evidence.json"; p.write_text("{}")
            routing = {"media":str(Path(d)/"source.wav"),"stream":0,"channel":1,"sample_rate":48000,"evidence":pin(p)}
            routing_binding(routing, routing["media"])
            with self.assertRaisesRegex(ValueError, "media mismatch"):
                routing_binding(routing, str(Path(d)/"wrong.wav"))
            p.write_text('{"changed":true}')
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                routing_binding(routing, routing["media"])

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe") and
                         all(importlib.util.find_spec(m) for m in ("numpy","scipy","matplotlib")),
                         "Requires the existing audio/plotting runtime")
    def test_actual_channel_and_quiet_release_preserved_with_no_cut_decision(self):
        import numpy as np
        from scipy.io import wavfile
        with tempfile.TemporaryDirectory() as d:
            d = Path(d); rate = 48000; data = np.zeros((rate*3,2), dtype=np.float32)
            data[:,0] = .3  # a downmix would contaminate every sample
            a,b = int(.26*rate),int(.29*rate)
            data[a:b,1] = .0001*np.sin(np.arange(b-a)*.3)  # quiet final release
            media = d/"source.wav"; wavfile.write(media,rate,data)
            words = d/"words.json"; words.write_text(json.dumps({"words":self.words}))
            selection = d/"selection.json"; selection.write_text(json.dumps({"schema":"edit.assembly-selection/v2","clips":[{
                **self.clip,"id":"fixture","media":str(media),"source_words":str(words),"source_words_sha256":pin(words)["sha256"]}]}))
            evidence = d/"receipt.json"; evidence.write_text('{"fixture":"known stereo channels"}')
            routing = d/"routing.json"; routing.write_text(json.dumps({"media":str(media),"stream":0,"channel":1,
                "sample_rate":rate,"evidence":pin(evidence)}))
            before = pin(selection); result = prepare(selection,"fixture",routing,d/"inspection",spectrogram=True)
            sr,out = wavfile.read(d/"inspection/played-source-channel.wav")
            self.assertEqual(sr,rate)
            np.testing.assert_allclose(out[a:b],data[a:b,1],rtol=0,atol=1e-9)
            self.assertEqual(float(abs(out[:a]).max()),0)
            self.assertEqual(pin(selection),before)
            self.assertEqual(result["status"],"DIAGNOSTICS_PREPARED_NOT_INSPECTED")
            self.assertTrue((d/"inspection/page-001.png").is_file())
            with self.assertRaises(FileExistsError):
                prepare(selection,"fixture",routing,d/"inspection")


if __name__ == "__main__":
    unittest.main()
