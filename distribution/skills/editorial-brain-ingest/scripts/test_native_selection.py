import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from test_cut_validation import map_fixture, packet_fixture
from validate_cut_map import validate as validate_map
from validate_packet import validate as validate_packet


def pin(root, name, value):
    raw = json.dumps(value).encode()
    path = root / name
    path.write_bytes(raw)
    return {"uri": str(path), "sha256": hashlib.sha256(raw).hexdigest()}


def fixture(root):
    data = map_fixture()
    identity = {k: data[k] for k in ("case_id", "project_sha256", "sequence_uid")}
    native = dict(identity, schema="editorial-brain.native-final/v1",
                  reference_authority="native_final", fully_edited_captioned_sequence=True,
                  selection_rationale="Only complete captioned sequence; source nest inspected",
                  caption_evidence="62 graphic cards cover the dialogue",
                  finished_picture_evidence="Finished switches and keyframes inspected",
                  revision_resolution="One completed version in this fixture",
                  bridge_snapshot=pin(root, "bridge.json", identity))
    row = {k: data["kept"][0][k] for k in ("passage_id", "native_item_id", "source_id",
           "source_start_sample", "source_end_sample", "timeline_start_ticks", "timeline_end_ticks")}
    row.update(source_sha256="a" * 64, text="The condition matters.", word_locator="words 1-3")
    claim = dict(claim_id="choice-1", passage_ids=["p1"], omission_ids=[],
                 before_text="The condition matters. Again, the condition matters.",
                 after_text="The condition matters.", comparison="Retains the condition",
                 occurrence_review="Exact first occurrence and following repetition checked",
                 source_occurrence_confirmed=True, spoken_selection_confirmed=True,
                 complete_raw_context=pin(root, "context.json", {"text":"complete interaction"}),
                 word_mapping=pin(root, "words.json", {"case_id":"case-1", "passages":[row]}))
    selection = dict(identity, schema="editorial-brain.selection-review/v1", claims=[claim])
    data.update(schema="editorial-brain.cut-map/v2", certification="selection_reviewed",
                reference_authority="native_final", final_asset_sha256=None,
                verification_scope={"kind":"spoken_selection", "claim_ids":["choice-1"]},
                unresolved_ranges=[{"dimension":"acoustic_boundaries", "claim_ids":[], "reason":"not auditioned"}])
    data["verification"].update(native_final_receipt=pin(root,"native.json",native),
                                selection_receipt=pin(root,"selection.json",selection))
    packet = packet_fixture()
    packet.update(schema="editorial-brain.packet/v2", reference_authority="native_final",
                  evidence_class="NATIVE_FINAL_SELECTION_VERIFIED",
                  verification_scope=copy.deepcopy(data["verification_scope"]),
                  unresolved_ranges=copy.deepcopy(data["unresolved_ranges"]))
    packet["source"].update(sequence_uid=data["sequence_uid"], final_asset_uri=None, final_asset_sha256=None)
    packet["verification"].update(audio_checked=False, visible_final_match=False, gaps=["Seams unreviewed"])
    packet["decision"].update(observed_format="q_and_a",transfer_rationale={"q_and_a":"Condition preserves answer applicability"})
    ref = pin(root,"map.json",data)
    packet["source"].update(cut_map_uri=ref["uri"],cut_map_sha256=ref["sha256"])
    return data,packet


class NativeSelectionTests(unittest.TestCase):
    def test_native_selection_passes_without_export_or_seam_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            data,packet=fixture(Path(tmp))
            self.assertEqual(validate_map(data),[])
            self.assertEqual(validate_packet(packet),[])

    def test_unresolved_occurrence_cannot_be_published(self):
        with tempfile.TemporaryDirectory() as tmp:
            data,_=fixture(Path(tmp))
            data["unresolved_ranges"]=[{"dimension":"selection","claim_ids":["choice-1"],"reason":"two possible raw occurrences"}]
            self.assertTrue(any("intersects unresolved" in e for e in validate_map(data)))

    def test_draft_receipt_rejected_even_when_rehashed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); data,_=fixture(root)
            ref=data["verification"]["native_final_receipt"]
            receipt=json.loads(Path(ref["uri"]).read_text());receipt["fully_edited_captioned_sequence"]=False
            data["verification"]["native_final_receipt"]=pin(root,"native2.json",receipt)
            self.assertTrue(any("fully edited" in e for e in validate_map(data)))

    def test_changed_native_mapping_and_receipt_bytes_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            data,_=fixture(Path(tmp)); data["kept"][0]["source_start_sample"]=10
            self.assertTrue(any("mapping source_start_sample mismatch" in e for e in validate_map(data)))
            Path(data["verification"]["selection_receipt"]["uri"]).write_text('{}')
            self.assertTrue(any("changed bytes" in e for e in validate_map(data)))

    def test_cannot_use_native_selection_to_certify_acoustic_stage(self):
        with tempfile.TemporaryDirectory() as tmp:
            _,packet=fixture(Path(tmp));packet["stage"]="boundaries"
            self.assertTrue(any("assembly-only" in e for e in validate_packet(packet)))

    def test_packet_cannot_widen_scope_or_hide_uncertainty(self):
        with tempfile.TemporaryDirectory() as tmp:
            _,packet=fixture(Path(tmp));packet["verification_scope"]["claim_ids"].append("unreviewed")
            packet["unresolved_ranges"]=[]
            errors=validate_packet(packet)
            self.assertTrue(any("scopes disagree" in e for e in errors))
            self.assertTrue(any("unresolved ranges disagree" in e for e in errors))

    def test_v1_cannot_sneak_into_new_certification(self):
        with tempfile.TemporaryDirectory() as tmp:
            data,_=fixture(Path(tmp));data["schema"]="editorial-brain.cut-map/v1"
            self.assertTrue(any("requires cut-map/v2" in e for e in validate_map(data)))


if __name__ == "__main__":
    unittest.main()
