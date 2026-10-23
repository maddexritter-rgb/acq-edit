#!/usr/bin/env python3
"""Check cut-map structure and clock arithmetic; never certify audible truth."""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from native_selection import validate_selection


SHA256 = re.compile(r"^[0-9a-f]{64}$")


def text(value):
    return isinstance(value, str) and bool(value.strip())


def integer(value, minimum=0):
    return type(value) is int and value >= minimum


def validate(data):
    errors = []

    def need(condition, message):
        if not condition:
            errors.append(message)

    if not isinstance(data, dict):
        return ["cut map must be an object"]
    need(data.get("schema") in {"editorial-brain.cut-map/v1", "editorial-brain.cut-map/v2"}, "unsupported cut-map schema")
    need(text(data.get("case_id")), "case_id is required")
    need(data.get("certification") in {"development", "frame_reviewed", "selection_reviewed"}, "invalid certification")
    if data.get("certification") == "selection_reviewed":
        need(data.get("schema") == "editorial-brain.cut-map/v2", "selection_reviewed requires cut-map/v2")
    need(text(data.get("sequence_uid")), "sequence_uid is required")
    for key in ("project_sha256", "final_asset_sha256"):
        value = data.get(key)
        need(value is None or bool(SHA256.fullmatch(value or "")), f"{key} must be SHA-256 or null")

    clock = data.get("timebase")
    if not isinstance(clock, dict):
        return errors + ["timebase must be an object"]
    for key in ("ticks_per_second", "frame_rate_num", "frame_rate_den", "frame_ticks", "final_duration_frames"):
        need(integer(clock.get(key), 1), f"timebase.{key} must be a positive integer")
    if all(integer(clock.get(key), 1) for key in ("ticks_per_second", "frame_rate_num", "frame_rate_den", "frame_ticks")):
        need(clock["frame_rate_num"] * clock["frame_ticks"] ==
             clock["ticks_per_second"] * clock["frame_rate_den"],
             "frame ticks and rational frame rate disagree")

    sources = data.get("raw_sources")
    if not isinstance(sources, list) or not sources:
        return errors + ["raw_sources must be a nonempty list"]
    source_ids = set()
    source_by_id = {}
    for index, source in enumerate(sources):
        if not isinstance(source, dict):
            errors.append(f"raw_sources[{index}] must be an object")
            continue
        source_id = source.get("source_id")
        need(text(source_id) and source_id not in source_ids, f"raw_sources[{index}] needs a unique source_id")
        if text(source_id):
            source_ids.add(source_id)
            source_by_id[source_id] = source
        need(text(source.get("uri")), f"raw_sources[{index}].uri is required")
        need(source.get("sha256") is None or bool(SHA256.fullmatch(source.get("sha256") or "")),
             f"raw_sources[{index}].sha256 must be SHA-256 or null")
        need(integer(source.get("sample_rate"), 1), f"raw_sources[{index}].sample_rate is required")
        need(source.get("sample_count") is None or integer(source.get("sample_count"), 1),
             f"raw_sources[{index}].sample_count must be positive or null")

    kept = data.get("kept")
    if not isinstance(kept, list) or not kept:
        return errors + ["kept must be a nonempty list"]
    passage_ids = set()
    previous_start = -1
    for index, passage in enumerate(kept):
        if not isinstance(passage, dict):
            errors.append(f"kept[{index}] must be an object")
            continue
        prefix = f"kept[{index}]"
        passage_id = passage.get("passage_id")
        need(text(passage_id) and passage_id not in passage_ids, f"{prefix} needs a unique passage_id")
        if text(passage_id):
            passage_ids.add(passage_id)
        need(text(passage.get("native_item_id")), f"{prefix}.native_item_id is required")
        source_id = passage.get("source_id")
        need(source_id in source_ids, f"{prefix}.source_id is unknown")
        for key in ("source_start_sample", "source_end_sample", "timeline_start_ticks", "timeline_end_ticks",
                    "final_start_frame", "final_end_frame"):
            need(integer(passage.get(key)), f"{prefix}.{key} must be a nonnegative integer")
        sample_start, sample_end = passage.get("source_start_sample"), passage.get("source_end_sample")
        tick_start, tick_end = passage.get("timeline_start_ticks"), passage.get("timeline_end_ticks")
        frame_start, frame_end = passage.get("final_start_frame"), passage.get("final_end_frame")
        if integer(sample_start) and integer(sample_end):
            need(sample_end > sample_start, f"{prefix} has empty/reversed source range")
            sample_count = source_by_id.get(source_id, {}).get("sample_count")
            if integer(sample_count, 1):
                need(sample_end <= sample_count, f"{prefix} runs past source samples")
        if integer(tick_start) and integer(tick_end):
            need(tick_end > tick_start, f"{prefix} has empty/reversed timeline range")
            need(tick_start >= previous_start, f"{prefix} is not in final playback order")
            previous_start = tick_start
        if integer(frame_start) and integer(frame_end):
            need(frame_end > frame_start, f"{prefix} has empty/reversed final-frame range")
            if integer(clock.get("final_duration_frames"), 1):
                need(frame_end <= clock["final_duration_frames"], f"{prefix} exceeds final duration")
        if all(integer(value) for value in (tick_start, tick_end, frame_start, frame_end)) and integer(clock.get("frame_ticks"), 1):
            need(abs(tick_start - frame_start * clock["frame_ticks"]) <= clock["frame_ticks"],
                 f"{prefix} start tick/frame mismatch exceeds one frame")
            need(abs(tick_end - frame_end * clock["frame_ticks"]) <= clock["frame_ticks"],
                 f"{prefix} end tick/frame mismatch exceeds one frame")
        need(passage.get("audible_role") in {"primary", "overlap", "patch", "unknown"},
             f"{prefix}.audible_role is invalid")
        need(isinstance(passage.get("delivery_audio_lineage"), list),
             f"{prefix}.delivery_audio_lineage must be a list")
        need(passage.get("final_audio_match") in {"confirmed", "unresolved", "mismatch"},
             f"{prefix}.final_audio_match is invalid")
        need(text(passage.get("evidence_uri")), f"{prefix}.evidence_uri is required")
        for edge in ("start_edge_error_frames", "end_edge_error_frames"):
            value = passage.get(edge)
            need(value is None or (type(value) in (int, float) and 0 <= value <= 1000),
                 f"{prefix}.{edge} must be a nonnegative frame error or null")

    omissions = data.get("omissions")
    need(isinstance(omissions, list), "omissions must be a list")
    if isinstance(omissions, list):
        for index, omission in enumerate(omissions):
            if not isinstance(omission, dict):
                errors.append(f"omissions[{index}] must be an object")
                continue
            need(omission.get("source_id") in source_ids,
                 f"omissions[{index}].source_id is unknown")
            start, end = omission.get("source_start_sample"), omission.get("source_end_sample")
            need(integer(start) and integer(end) and end > start,
                 f"omissions[{index}] needs an ordered source sample range")
            need(text(omission.get("observed_function")),
                 f"omissions[{index}].observed_function is required")
            need(text(omission.get("evidence_uri")),
                 f"omissions[{index}].evidence_uri is required")
    reordered = data.get("reordered")
    need(isinstance(reordered, list), "reordered must be a list")
    if isinstance(reordered, list):
        for index, movement in enumerate(reordered):
            if not isinstance(movement, dict):
                errors.append(f"reordered[{index}] must be an object")
                continue
            need(movement.get("passage_id") in passage_ids,
                 f"reordered[{index}].passage_id is unknown")
            need(text(movement.get("relation")),
                 f"reordered[{index}].relation is required")
            need(text(movement.get("evidence_uri")),
                 f"reordered[{index}].evidence_uri is required")
    joins = data.get("joins")
    need(isinstance(joins, list), "joins must be a list")
    if isinstance(joins, list):
        for index, join in enumerate(joins):
            if not isinstance(join, dict):
                errors.append(f"joins[{index}] must be an object")
                continue
            left, right = join.get("left_passage_id"), join.get("right_passage_id")
            need(left in passage_ids and right in passage_ids and left != right,
                 f"joins[{index}] references unknown passages")
            need(integer(join.get("final_frame")), f"joins[{index}].final_frame is required")
            need(join.get("listening_status") in {"pass", "unresolved", "fail"},
                 f"joins[{index}].listening_status is invalid")
            need(text(join.get("evidence_uri")), f"joins[{index}].evidence_uri is required")
            value = join.get("edge_error_frames")
            need(value is None or (type(value) in (int, float) and 0 <= value <= 1000),
                 f"joins[{index}].edge_error_frames must be nonnegative or null")

    # Adjacent timeline starts are not necessarily audible joins: another track may
    # already be playing, or the previous passage may continue under the next one.
    # Keep legacy `joins` readable for development maps, but certify only explicit,
    # interval-checked transitions.
    transitions = data.get("transitions")
    need(transitions is None or isinstance(transitions, list), "transitions must be a list when present")
    expected = {}
    for left, right in zip(kept, kept[1:]):
        if not isinstance(left, dict) or not isinstance(right, dict):
            continue
        left_end, right_start = left.get("timeline_end_ticks"), right.get("timeline_start_ticks")
        if not integer(left_end) or not integer(right_start):
            continue
        pair = (left.get("passage_id"), right.get("passage_id"))
        expected[pair] = ("overlap" if right_start < left_end else
                          "gap" if right_start > left_end else "serial_seam")
    seen_transitions = set()
    if isinstance(transitions, list):
        for index, transition in enumerate(transitions):
            if not isinstance(transition, dict):
                errors.append(f"transitions[{index}] must be an object")
                continue
            pair = (transition.get("left_passage_id"), transition.get("right_passage_id"))
            need(pair in expected, f"transitions[{index}] must reference an adjacent kept pair")
            need(pair not in seen_transitions, f"transitions[{index}] duplicates a pair")
            seen_transitions.add(pair)
            need(transition.get("kind") == expected.get(pair),
                 f"transitions[{index}].kind disagrees with timeline intervals")
            need(transition.get("listening_status") in {"pass", "unresolved", "fail"},
                 f"transitions[{index}].listening_status is invalid")
            need(text(transition.get("evidence_uri")), f"transitions[{index}].evidence_uri is required")
            frame = transition.get("final_frame")
            need(integer(frame), f"transitions[{index}].final_frame is required")
            right = next((p for p in kept if isinstance(p, dict) and p.get("passage_id") == pair[1]), None)
            if right is not None and integer(frame) and integer(right.get("final_start_frame")):
                need(abs(frame - right["final_start_frame"]) <= 1,
                     f"transitions[{index}].final_frame differs from right passage start")
            value = transition.get("edge_error_frames")
            need(value is None or (type(value) in (int, float) and 0 <= value <= 1000),
                 f"transitions[{index}].edge_error_frames must be nonnegative or null")

    verification = data.get("verification")
    if not isinstance(verification, dict):
        return errors + ["verification must be an object"]
    need(verification.get("audible_coverage") in {"partial", "complete"},
         "verification.audible_coverage is invalid")
    need(isinstance(verification.get("unresolved"), list), "verification.unresolved must be a list")

    if data.get("certification") == "selection_reviewed":
        need(bool(SHA256.fullmatch(data.get("project_sha256") or "")), "selection_reviewed requires project_sha256")
        errors.extend(validate_selection(data))

    if data.get("certification") == "frame_reviewed":
        for key in ("project_sha256", "final_asset_sha256"):
            need(bool(SHA256.fullmatch(data.get(key) or "")), f"frame_reviewed requires {key}")
        for index, source in enumerate(sources):
            if not isinstance(source, dict):
                continue
            need(bool(SHA256.fullmatch(source.get("sha256") or "")),
                 f"frame_reviewed requires raw_sources[{index}].sha256")
            need(integer(source.get("sample_count"), 1),
                 f"frame_reviewed requires raw_sources[{index}].sample_count")
        for key in ("final_native_identity_receipt_uri", "boundary_review_receipt_uri",
                    "editorial_comparison_receipt_uri"):
            uri = verification.get(key)
            digest_key = key.removesuffix("_uri") + "_sha256"
            digest = verification.get(digest_key)
            need(text(uri), f"frame_reviewed requires verification.{key}")
            need(isinstance(digest, str) and bool(SHA256.fullmatch(digest)),
                 f"frame_reviewed requires verification.{digest_key}")
            if text(uri):
                path = Path(uri)
                if not path.is_absolute():
                    errors.append(f"frame_reviewed receipt must use an absolute local path: {key}")
                else:
                    try:
                        raw = path.read_bytes()
                    except OSError as exc:
                        errors.append(f"frame_reviewed receipt not readable: {key}: {exc}")
                    else:
                        need(bool(raw), f"frame_reviewed receipt is empty: {key}")
                        need(hashlib.sha256(raw).hexdigest() == digest,
                             f"frame_reviewed receipt hash mismatch: {key}")
        need(verification.get("audible_coverage") == "complete", "frame_reviewed requires complete audible coverage")
        need(verification.get("unresolved") == [], "frame_reviewed cannot have unresolved matches")
        for index, passage in enumerate(kept):
            if not isinstance(passage, dict):
                continue
            need(passage.get("audible_role") != "unknown" and passage.get("final_audio_match") == "confirmed",
                 f"frame_reviewed requires confirmed audible kept[{index}]")
            for edge in ("start_edge_error_frames", "end_edge_error_frames"):
                value = passage.get(edge)
                need(type(value) in (int, float) and 0 <= value <= 1,
                     f"frame_reviewed requires kept[{index}].{edge} <= 1")
        need(isinstance(transitions, list), "frame_reviewed requires typed transitions")
        for pair, kind in expected.items():
            need(pair in seen_transitions,
                 f"frame_reviewed requires {kind} transition {pair[0]} -> {pair[1]}")
        if isinstance(transitions, list):
            for index, transition in enumerate(transitions):
                if not isinstance(transition, dict):
                    continue
                value = transition.get("edge_error_frames")
                need(transition.get("listening_status") == "pass" and
                     type(value) in (int, float) and 0 <= value <= 1,
                     f"frame_reviewed requires reviewed transition[{index}] within one frame")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cut_map", type=Path)
    args = parser.parse_args()
    try:
        data = json.loads(args.cut_map.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 2
    errors = validate(data)
    if errors:
        for error in errors:
            print(f"INVALID: {error}", file=sys.stderr)
        return 1
    print(f"STRUCTURE_VALID: {data['case_id']} ({data['certification']}); audio not independently heard")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
