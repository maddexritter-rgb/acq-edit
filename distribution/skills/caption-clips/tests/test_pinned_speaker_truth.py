import importlib.util
import json
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "spice_caption.py"
SPEC = importlib.util.spec_from_file_location("spice_caption", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


def test_pinned_guest_labels_survive_normalized_token_merge(tmp_path):
    source = tmp_path / "source.json"
    normalized = tmp_path / "normalized.json"
    stream = tmp_path / "stream.json"
    source.write_text(json.dumps({"words": [
        {"word": "host", "start": 0.0, "end": 0.4, "speaker": "host"},
        {"word": "thank", "start": 1.0, "end": 1.2, "speaker": "guest"},
        {"word": "you", "start": 1.2, "end": 1.5, "speaker": "guest"},
    ]}))
    normalized.write_text(json.dumps({"words": [
        {"word": "host", "start": 0.0, "end": 0.4},
        {"word": "thank you", "start": 1.0, "end": 1.5},
    ]}))
    stream.write_text(json.dumps({"words": {"0": {"w": "strong"}}, "voice_spans": []}))
    result = MOD.apply_pinned_speaker_truth(source, normalized, stream)
    data = json.loads(stream.read_text())
    assert result["applied"] is True
    assert data["words"]["1"]["c"] == "guest"
    assert "c" not in data["words"]["0"]


def test_uncertain_labels_do_not_create_guest_truth(tmp_path):
    source = tmp_path / "source.json"
    normalized = tmp_path / "normalized.json"
    stream = tmp_path / "stream.json"
    source.write_text(json.dumps({"words": [
        {"word": "maybe", "start": 0.0, "end": 0.4, "speaker": "uncertain"}
    ]}))
    normalized.write_text(json.dumps({"words": [{"word": "maybe", "start": 0.0, "end": 0.4}]}))
    stream.write_text(json.dumps({"words": {}, "voice_spans": []}))
    result = MOD.apply_pinned_speaker_truth(source, normalized, stream)
    assert result["applied"] is False
