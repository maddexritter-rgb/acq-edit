#!/usr/bin/env python3
"""Prepare a new-card Supabase transaction from a validated evidence packet; never executes it."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

from validate_packet import validate

SOURCE_KINDS = {
    "raw_native_study": "research",
    "editor_feedback": "editor_feedback",
    "sop": "sop",
    "research_commentary": "research",
    "analytics": "research",
}


def sql_text(value):
    if value is None:
        return "null"
    if not isinstance(value, str):
        raise TypeError("SQL text value must be a string or null")
    return "convert_from(decode('%s','hex'),'UTF8')" % value.encode("utf-8").hex()


def sql_array(values):
    return "array[%s]::text[]" % ",".join(sql_text(value) for value in values)


def render(packet, packet_path, digest):
    decision = packet["decision"]
    verification = packet["verification"]
    body = packet_path.read_bytes().decode("utf-8")
    if hashlib.sha256(body.encode("utf-8")).hexdigest() != digest:
        raise ValueError("packet changed after validation; prepare it again")
    note = (verification["method"] + " Gaps: " + "; ".join(verification["gaps"]) +
            " Stored source_body is the exact evidence packet JSON; source_sha256 pins "
            "that packet, while source_uri points to its cited upstream evidence.")
    if packet.get("reference_authority") == "native_final":
        note += " Authority: inspected native final. Scope: spoken selection only; no delivered-export, acoustic-seam or human-approval claim."
    src = [packet["packet_id"], packet["provenance"]["source_uri"], digest,
           SOURCE_KINDS[packet["evidence_kind"]], packet["evidence_class"], note,
           decision["title"], "r" + str(packet["revision"]), body]
    card = [packet["card_id"], packet["packet_id"], decision["title"],
            decision["problem"], decision["observed_choice"],
            decision["transferable_lesson"], decision["exception_note"]]
    return "\n".join([
        "-- New card only. Confirm project, schema, duplicates and evidence before execution.",
        "-- Existing source/card IDs intentionally fail rather than overwrite history.",
        "begin;",
        "insert into editorial_brain.source_documents",
        "  (source_id, source_uri, source_sha256, source_kind, evidence_class, verification_note,",
        "   source_title, source_revision, source_body)",
        "values (" + ", ".join(sql_text(x) for x in src) + ");",
        "insert into editorial_brain.decision_cards",
        "  (card_id, source_id, title, problem, observed_choice, transferable_lesson,",
        "   exception_note, applicable_formats, stage, evidence_class, status, revision)",
        "values (" + ", ".join(sql_text(x) for x in card) + ", " +
        sql_array(decision["applicable_formats"]) + ", " +
        ", ".join(sql_text(packet[x]) for x in ("stage", "evidence_class", "status")) +
        ", " + str(packet["revision"]) + ");",
        "commit;",
        "-- Read back both rows and test one bounded retrieval query separately.",
    ]) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packet", type=Path)
    parser.add_argument("--out", type=Path, help="write a new SQL file instead of stdout")
    args = parser.parse_args()
    try:
        raw = args.packet.read_bytes()
        packet = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"INVALID: cannot load packet: {exc}", file=sys.stderr)
        return 2
    errors = validate(packet, args.packet)
    if errors:
        for error in errors:
            print(f"INVALID: {error}", file=sys.stderr)
        return 1
    sql = render(packet, args.packet, hashlib.sha256(raw).hexdigest())
    if args.out:
        if args.out.exists():
            print(f"REFUSED: output exists: {args.out}", file=sys.stderr)
            return 2
        args.out.write_text(sql)
        print(f"PREPARED_NOT_EXECUTED: {args.out}")
    else:
        sys.stdout.write(sql)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
