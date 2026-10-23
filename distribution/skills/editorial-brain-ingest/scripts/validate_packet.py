#!/usr/bin/env python3
"""Structural checks for one editorial-brain evidence packet; does not certify truth."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

from validate_cut_map import validate as validate_cut_map
from native_selection import scope_ids

STAGES = {"assembly", "cuts", "boundaries", "camera", "captions", "audio", "qa"}
KINDS = {"raw_native_study", "editor_feedback", "sop", "research_commentary", "analytics"}
STATUSES = {"development", "calibration", "verified_final", "retired"}


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def validate(packet, packet_path=None):
    errors = []

    def need(condition, message):
        if not condition:
            errors.append(message)

    need(isinstance(packet, dict), "packet must be a JSON object")
    if not isinstance(packet, dict):
        return errors
    need(packet.get("schema") in {"editorial-brain.packet/v1", "editorial-brain.packet/v2"}, "unsupported schema")
    for key in ("packet_id", "card_id", "evidence_class"):
        need(nonempty(packet.get(key)), f"{key} is required")
    need(type(packet.get("revision")) is int and packet.get("revision", 0) > 0,
         "revision must be a positive integer")
    need(packet.get("stage") in STAGES, "stage must match a supported owning stage")
    need(packet.get("status") in STATUSES, "invalid status")
    need(packet.get("evidence_kind") in KINDS, "invalid evidence_kind")

    source = packet.get("source")
    decision = packet.get("decision")
    verification = packet.get("verification")
    provenance = packet.get("provenance")
    for name, value in (("source", source), ("decision", decision),
                        ("verification", verification), ("provenance", provenance)):
        need(isinstance(value, dict), f"{name} must be an object")
    if not all(isinstance(x, dict) for x in (source, decision, verification, provenance)):
        return errors

    need(nonempty(source.get("case_id")), "source.case_id is required")
    need(nonempty(source.get("source_locator")), "source.source_locator is required")
    for key in ("title", "problem", "observed_choice", "transferable_lesson",
                "exception_note"):
        need(nonempty(decision.get(key)), f"decision.{key} is required")
    formats = decision.get("applicable_formats")
    need(isinstance(formats, list) and bool(formats) and
         all(nonempty(x) for x in formats) and len(formats) == len(set(formats)),
         "decision.applicable_formats needs distinct nonempty values")
    need(isinstance(decision.get("alternatives"), list) and
         all(nonempty(x) for x in decision.get("alternatives", [])),
         "decision.alternatives must be a list (empty is allowed if none found)")
    need(nonempty(verification.get("method")), "verification.method is required")
    need(isinstance(verification.get("gaps"), list) and
         all(nonempty(x) for x in verification.get("gaps", [])),
         "verification.gaps must be a list of nonempty strings")
    need(nonempty(provenance.get("author_type")), "provenance.author_type is required")
    need(nonempty(provenance.get("source_uri")), "provenance.source_uri is required")
    need(nonempty(provenance.get("created_at")), "provenance.created_at is required")

    kind = packet.get("evidence_kind")
    status = packet.get("status")
    native = packet.get("schema") == "editorial-brain.packet/v2" and packet.get("reference_authority") == "native_final"
    if packet.get("schema") == "editorial-brain.packet/v2":
        need(native, "packet/v2 currently requires native_final authority")
        need(nonempty(decision.get("observed_format")), "v2 requires observed_format")
        reasons = decision.get("transfer_rationale")
        need(isinstance(reasons, dict) and isinstance(formats, list) and
             all(nonempty(reasons.get(fmt)) for fmt in formats), "v2 requires transfer rationale for every applicable format")
        need(scope_ids(packet.get("verification_scope")) is not None, "v2 requires named verification_scope claims")
        need(isinstance(packet.get("unresolved_ranges"), list), "v2 requires unresolved_ranges")
    if kind == "editor_feedback":
        ctx = packet.get("feedback_context", {})
        need(isinstance(ctx, dict), "feedback_context must be an object")
        if isinstance(ctx, dict):
            for key in ("clip_revision_uri", "editor_decision", "editor_identity",
                        "feedback_locator"):
                need(nonempty(ctx.get(key)), f"feedback_context.{key} is required")
            need(ctx.get("editor_decision") in {"keep", "change", "delete"},
                 "feedback_context.editor_decision must be keep/change/delete")
        need(provenance.get("author_type") == "human_editor",
             "editor feedback must be attributed to a human editor")
    if kind == "analytics":
        ctx = packet.get("analysis_context", {})
        need(isinstance(ctx, dict), "analysis_context must be an object")
        if isinstance(ctx, dict):
            for key in ("metric_definition", "unit", "population", "time_window",
                        "sample_size", "comparator", "data_uri", "confounders"):
                need(ctx.get(key) is not None and ctx.get(key) != "",
                     f"analysis_context.{key} is required (state unknown explicitly)")
        need(status != "verified_final", "analytics alone cannot verify a final edit")
    if kind in {"sop", "research_commentary"}:
        need(status != "verified_final", "SOP/commentary alone cannot verify a final edit")
    if status == "verified_final":
        need(kind == "raw_native_study", "verified_final requires raw_native_study")
        fields = ["project_uri", "project_sha256", "raw_media_uri", "raw_media_sha256",
                  "premiere_sequence", "source_locator", "timeline_locator"]
        if native:
            need(packet.get("stage") == "assembly", "native selection verification is assembly-only")
            need(packet.get("evidence_class") == "NATIVE_FINAL_SELECTION_VERIFIED", "native selection evidence_class mismatch")
            need(packet.get("verification_scope", {}).get("kind") == "spoken_selection", "native verification_scope must be spoken_selection")
        else:
            fields += ["final_asset_uri", "final_asset_sha256"]
        for key in fields:
            need(nonempty(source.get(key)), f"verified_final requires source.{key}")
        for key in (("native_source_mapping",) if native else
                    ("native_source_mapping", "visible_final_match", "captions_checked", "audio_checked")):
            need(verification.get(key) is True, f"verified_final requires verification.{key}=true")
        if not native:
            need(verification.get("gaps") == [], "verified_final cannot have unresolved gaps")
        need(len(verification.get("method", "")) >= 40,
             "verified_final needs a specific raw/native/final matching method")
        if packet.get("stage") in {"assembly", "cuts", "boundaries"}:
            map_uri = source.get("cut_map_uri")
            map_sha = source.get("cut_map_sha256")
            need(nonempty(map_uri), "verified_final assembly/cuts/boundaries requires source.cut_map_uri")
            need(nonempty(map_sha) and len(map_sha) == 64 and
                 all(c in "0123456789abcdef" for c in map_sha),
                 "verified_final assembly/cuts/boundaries requires source.cut_map_sha256")
            if nonempty(map_uri):
                map_path = Path(map_uri).expanduser()
                if not map_path.is_absolute() and packet_path is not None:
                    map_path = packet_path.parent / map_path
                try:
                    raw = map_path.read_bytes()
                    cut_map = json.loads(raw)
                except (OSError, json.JSONDecodeError) as exc:
                    errors.append(f"cannot inspect pinned cut map: {exc}")
                else:
                    need(hashlib.sha256(raw).hexdigest() == map_sha,
                         "source.cut_map_sha256 does not match cut map")
                    for problem in validate_cut_map(cut_map):
                        errors.append(f"cut map: {problem}")
                    if isinstance(cut_map, dict):
                        need(cut_map.get("certification") == ("selection_reviewed" if native else "frame_reviewed"),
                             "verified_final requires " + ("selection_reviewed" if native else "frame_reviewed") + " cut map")
                        need(cut_map.get("case_id") == source.get("case_id"),
                             "packet and cut map case_id disagree")
                        need(cut_map.get("project_sha256") == source.get("project_sha256"),
                             "packet and cut map project hashes disagree")
                        if native:
                            need(source.get("sequence_uid") == cut_map.get("sequence_uid"), "packet and cut map sequence UIDs disagree")
                            need(packet.get("verification_scope") == cut_map.get("verification_scope"), "packet and cut map scopes disagree")
                            need(packet.get("unresolved_ranges") == cut_map.get("unresolved_ranges"), "packet and cut map unresolved ranges disagree")
                            need(any(s.get("uri") == source.get("raw_media_uri") and s.get("sha256") == source.get("raw_media_sha256") for s in cut_map.get("raw_sources", []) if isinstance(s, dict)), "packet raw media is not pinned in cut map")
                        else:
                            need(cut_map.get("final_asset_sha256") == source.get("final_asset_sha256"),
                                 "packet and cut map final hashes disagree")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packet", type=Path)
    args = parser.parse_args()
    try:
        packet = json.loads(args.packet.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        print(f"INVALID: cannot load packet: {exc}", file=sys.stderr)
        return 2
    errors = validate(packet, args.packet)
    if errors:
        for error in errors:
            print(f"INVALID: {error}", file=sys.stderr)
        return 1
    print(f"STRUCTURE_VALID: {packet['packet_id']} ({packet['status']}); evidence not independently verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
