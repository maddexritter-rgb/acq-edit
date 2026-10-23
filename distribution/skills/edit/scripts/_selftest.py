#!/usr/bin/env python3
"""Offline self-test for the new tam_segment / tam_tighten / tam_pipeline / transcribe_isolated
helpers. Exercises the PURE logic (no network, no Claude, no ffmpeg) on a tiny synthetic transcript.

Run:  python3 _selftest.py
Exits non-zero on any failure. Does NOT touch the live footage or call any API.
"""
import importlib.util, json, pathlib, sys, tempfile

HERE = pathlib.Path(__file__).resolve().parent


def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main():
    seg = load("tam_segment")
    tighten = load("tam_tighten")
    pipe = load("tam_pipeline")

    SYN = {"segments": [
        {"start": 0.0, "end": 3.0, "text": "Alright lets rock. We got somebody up. Hello?",
         "words": [{"word": "Alright", "start": 0.0, "end": 0.4}, {"word": "lets", "start": 0.4, "end": 0.7},
                   {"word": "rock.", "start": 0.7, "end": 1.1}, {"word": "We", "start": 1.4, "end": 1.6},
                   {"word": "got", "start": 1.6, "end": 1.8}, {"word": "somebody", "start": 1.8, "end": 2.3},
                   {"word": "up.", "start": 2.3, "end": 2.6}, {"word": "Hello?", "start": 2.7, "end": 3.0}]},
        {"start": 3.0, "end": 7.3, "text": "Hey. I sell cowboy hats, did 500k last year, stuck for three years.",
         "words": [{"word": "Hey.", "start": 3.0, "end": 3.3}, {"word": "I", "start": 3.4, "end": 3.5},
                   {"word": "sell", "start": 3.5, "end": 3.8}, {"word": "cowboy", "start": 3.8, "end": 4.2},
                   {"word": "hats,", "start": 4.2, "end": 4.6}, {"word": "did", "start": 4.6, "end": 4.9},
                   {"word": "500k", "start": 4.9, "end": 5.4}, {"word": "last", "start": 5.4, "end": 5.7},
                   {"word": "year,", "start": 5.7, "end": 6.0}, {"word": "stuck", "start": 6.0, "end": 6.4},
                   {"word": "for", "start": 6.4, "end": 6.6}, {"word": "three", "start": 6.6, "end": 6.9},
                   {"word": "years.", "start": 6.9, "end": 7.3}]},
    ]}

    # --- tam_segment helpers ---
    p = pathlib.Path(tempfile.mktemp(suffix=".json")); p.write_text(json.dumps(SYN))
    lines = seg.load_lines(p)
    assert len(lines) == 2, lines
    rw = seg.render_window(lines)
    assert "[LINE 0]" in rw and "[WORDS 0]" in rw and "rock.@0.70" in rw, rw
    wins = seg.make_windows(lines, 600)
    assert len(wins) == 1 and wins[0][0] == 0
    assert seg.parse_json("```json\n{\"segments\":[{\"id\":1}]}\n```")["segments"][0]["id"] == 1
    print("[ok] tam_segment: load_lines / render_window (LINE+WORDS+word@ts) / make_windows / parse_json")

    # --- tam_pipeline helpers ---
    win = pipe.slice_window(SYN["segments"], 3.0, 7.3)
    assert len(win["segments"]) == 1 and "cowboy" in win["segments"][0]["text"]
    assert pipe.mmss_to_sec("01:05") == 65.0 and pipe.mmss_to_sec(42) == 42.0
    print("[ok] tam_pipeline: slice_window / mmss_to_sec")

    # --- tam_tighten trim->cuts ---
    utt = SYN["segments"][1]
    # TRIM keeping the middle run "I sell cowboy hats, did 500k last year" -> drop "Hey." lead + "stuck..." tail
    cuts = tighten.trim_to_cuts(utt, "I sell cowboy hats, did 500k last year")
    assert any(c["reason"] == "trim-lead" for c in cuts), cuts
    assert any(c["reason"] == "trim-tail" for c in cuts), cuts
    lead = [c for c in cuts if c["reason"] == "trim-lead"][0]
    assert abs(lead["start"] - 3.0) < 1e-6 and abs(lead["end"] - 3.4) < 1e-6, lead  # drops "Hey." [3.0,3.4)
    # full keep -> no cuts
    assert tighten.trim_to_cuts(utt, utt["text"]) == []
    # decision-line CLI fallback parse
    d = tighten.parse_decision_lines("[0] REMOVE\n[1] TRIM: I sell cowboy hats\n[2] KEEP")
    assert d[0]["action"] == "REMOVE" and d[1]["action"] == "TRIM" and d[1]["trimmed_text"] == "I sell cowboy hats"
    assert tighten.norm("$500k,") == "500k"
    print("[ok] tam_tighten: trim_to_cuts (lead+tail) / full-keep / parse_decision_lines / norm")

    print("\nALL SELFTESTS PASSED")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as e:
        print(f"SELFTEST FAILED: {e}", file=sys.stderr); sys.exit(1)
