#!/usr/bin/env python3
"""Invisible punctuation must still force semantic caption-card boundaries."""
from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import tempfile
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
FORMATTER = SKILL / "scripts/oliver_format.py"
GEN = SKILL / "scripts/generate_spice.py"
PRESET = SKILL / "presets/spice.json"
spec = importlib.util.spec_from_file_location("oliver_format", FORMATTER)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

raw = [
    {"word": "you", "start": 0.0, "end": 0.2},
    {"word": "feel", "start": 0.2, "end": 0.4},
    {"word": "guilt.", "start": 0.4, "end": 0.7},
    {"word": "She", "start": 0.7, "end": 0.9},
    {"word": "doesn't", "start": 0.9, "end": 1.1},
    {"word": "feel", "start": 1.1, "end": 1.3},
    {"word": "guilt.", "start": 1.3, "end": 1.6},
]
formatted = module.format_words(raw)
assert formatted[2]["word"] == "guilt" and formatted[2]["sentence_end"] is True, formatted
assert module.format_words(formatted)[2]["sentence_end"] is True

with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    words = root / "words.json"
    out = root / "out.ass"
    words.write_text(json.dumps({"words": formatted}))
    subprocess.run(["python3", str(GEN), str(words), "--preset", str(PRESET),
                    "--out", str(out)], check=True, capture_output=True, text=True)
    cues = []
    for line in out.read_text().splitlines():
        if line.startswith("Dialogue: 1,"):
            cues.append(re.sub(r"\{[^}]*\}", "", line.split(",", 9)[9]).strip())
    assert not any("guilt she" in cue.lower() for cue in cues), cues
    assert any(cue.lower() == "you feel guilt" for cue in cues), cues
    assert any(cue.lower().startswith("she doesn't") for cue in cues), cues
print("PASS invisible sentence punctuation survives normalization and splits cards")
