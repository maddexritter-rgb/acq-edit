#!/usr/bin/env python3
"""Fetch the mandatory Supabase editorial playbooks and bounded assembly cards."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

from scoped_policy import STAGES, validate_scope, validate_scoped_policies


FORMATS = ("q_and_a", "monologue", "podcast", "story")
READING_OVERLAYS = ("l1", "workshop")
MAX_READING_DOCUMENTS = 32
MAX_READING_BYTES = 256_000


class BrainUnavailable(RuntimeError):
    pass


def validate_cards(cards: object, fmt: str, include_development: bool,
                   excluded_prefixes: list[str]) -> None:
    """Check the returned evidence boundary as well as trusting server filters."""
    if not isinstance(cards, list) or len(cards) > 5:
        raise BrainUnavailable("Supabase returned an invalid card list")
    seen = set()
    allowed = {"calibration", "verified_final"}
    if include_development:
        allowed.add("development")
    for card in cards:
        if not isinstance(card, dict):
            raise BrainUnavailable("Supabase returned a malformed decision card")
        required = ("card_id", "title", "problem", "observed_choice", "transferable_lesson",
                    "exception_note", "evidence_class", "source_uri", "verification_note")
        if any(not isinstance(card.get(k), str) or not card[k].strip() for k in required):
            raise BrainUnavailable("decision card is missing its lesson or evidence provenance")
        if card["card_id"] in seen or card.get("status") not in allowed or \
                type(card.get("revision")) is not int or card["revision"] < 1 or \
                not isinstance(card.get("applicable_formats"), list) or \
                fmt not in card["applicable_formats"]:
            raise BrainUnavailable("decision card identity, status, revision, or format is invalid")
        if any(card["source_uri"].startswith(prefix) for prefix in excluded_prefixes):
            raise BrainUnavailable("decision card leaked a current-project or held-out source")
        seen.add(card["card_id"])


def save_context(result: dict, out: Path) -> dict:
    """Pin the verified response without replacing an earlier batch/revision."""
    encoded = json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    saved = dict(result)
    saved["client_receipt"] = {
        "schema": "editorial-brain.fetch-receipt/v1",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "response_sha256": hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
        "response_encoding": "UTF-8 JSON, sorted keys, compact separators, ensure_ascii=false",
        "purpose": "Verified live retrieval; does not certify reading, application, or clip quality",
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("x", encoding="utf-8") as handle:
        json.dump(saved, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return saved


def configuration() -> tuple[str, str, str]:
    config_dir = Path(os.environ.get("EDITORIAL_BRAIN_CONFIG_DIR", "~/.config/editorial-brain")).expanduser()
    config_path = config_dir / "context.json"
    stored = {}
    if config_path.is_file():
        try:
            stored = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise BrainUnavailable("editorial brain project configuration is unreadable") from exc
        if not isinstance(stored, dict):
            raise BrainUnavailable("editorial brain project configuration is invalid")
    endpoint = os.environ.get("EDITORIAL_BRAIN_FUNCTION_URL", "").strip() or stored.get("function_url", "")
    expected_project = os.environ.get("EDITORIAL_BRAIN_PROJECT_REF", "").strip() or stored.get("project_ref", "")
    key = os.environ.get("EDITORIAL_BRAIN_READ_KEY", "").strip()
    token_path = config_dir / "read_token"
    if not key and token_path.is_file():
        try:
            stat = token_path.stat()
            if stat.st_uid != os.getuid() or stat.st_mode & 0o077:
                raise BrainUnavailable("editorial brain read-token file permissions are too broad")
            key = token_path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise BrainUnavailable("editorial brain read-token file is unreadable") from exc
    if not all(isinstance(value, str) for value in (endpoint, key, expected_project)):
        raise BrainUnavailable("editorial brain configuration contains invalid values")
    return endpoint, key, expected_project


def validate_required_reading(result: dict, fmt: str, overlays: list[str]) -> None:
    expected = ["universal", fmt, *overlays]
    reading = result.get("required_reading")
    policies = reading.get("policies") if isinstance(reading, dict) else None
    if not isinstance(policies, list) or len(policies) != len(expected):
        raise BrainUnavailable("required reading policies are missing or incomplete")
    seen_sources: set[str] = set()
    document_count = 0
    byte_count = 0
    for policy, profile in zip(policies, expected):
        if not isinstance(policy, dict) or policy.get("format") != profile or \
                not isinstance(policy.get("policy_id"), str) or not policy["policy_id"] or \
                type(policy.get("version")) is not int or policy["version"] < 1 or \
                not isinstance(policy.get("priority_note"), str) or not policy["priority_note"]:
            raise BrainUnavailable("required reading policy identity or version is invalid")
        documents = policy.get("documents")
        if not isinstance(documents, list) or not documents:
            raise BrainUnavailable("required reading source set is missing")
        document_count += len(documents)
        if document_count > MAX_READING_DOCUMENTS:
            raise BrainUnavailable("required reading exceeds document limit")
        for ordinal, document in enumerate(documents, start=1):
            if not isinstance(document, dict) or document.get("ordinal") != ordinal or \
                    not isinstance(document.get("source_id"), str) or not document["source_id"] or \
                    document["source_id"] in seen_sources or \
                    not isinstance(document.get("source_title"), str) or not document["source_title"] or \
                    not isinstance(document.get("source_body"), str) or not document["source_body"] or \
                    not isinstance(document.get("source_sha256"), str) or \
                    len(document["source_sha256"]) != 64:
                raise BrainUnavailable("required reading source identity or order is invalid")
            seen_sources.add(document["source_id"])
            body = document["source_body"].encode("utf-8")
            byte_count += len(body)
            if byte_count > MAX_READING_BYTES or \
                    hashlib.sha256(body).hexdigest() != document["source_sha256"]:
                raise BrainUnavailable("required reading source body hash or size is invalid")


def fetch_context(*, problem: str, fmt: str, project_prefix: str | None = None,
                  held_out: list[str] | None = None, include_development: bool = False,
                  required_reading: bool = False, reading_overlays: list[str] | None = None,
                  timeout: float = 12.0, brand: str | None = None,
                  production_type: str | None = None, stage: str | None = None) -> dict:
    if not isinstance(problem, str) or not 3 <= len(problem.strip()) <= 240:
        raise BrainUnavailable("editorial problem must be 3–240 characters")
    problem = problem.strip()
    endpoint, key, expected_project = configuration()
    if not endpoint or not key or not expected_project:
        raise BrainUnavailable("editorial brain configuration missing: URL, read key, or project ref")
    if not endpoint.startswith("https://") or not endpoint.endswith("/functions/v1/editorial-search"):
        raise BrainUnavailable("editorial brain function URL is invalid")
    if expected_project not in endpoint.split("/")[2].split("."):
        raise BrainUnavailable("function URL does not match configured Supabase project")
    if fmt not in FORMATS:
        raise BrainUnavailable(f"unsupported assembly format: {fmt}")
    overlays = reading_overlays or []
    if len(overlays) > 2 or len(set(overlays)) != len(overlays) or \
            any(overlay not in READING_OVERLAYS for overlay in overlays) or \
            ("l1" in overlays and fmt != "q_and_a") or (overlays and not required_reading):
        raise BrainUnavailable("unsupported required-reading overlay")
    try:
        scope = validate_scope(brand, production_type, stage)
    except ValueError as exc:
        raise BrainUnavailable(str(exc)) from exc
    payload = {
        "problem": problem,
        "format": fmt,
        "limit": 5,
        "include_development": include_development,
        "current_project_prefix": project_prefix,
        "held_out_source_prefixes": held_out or [],
        "include_required_reading": required_reading,
        "reading_overlays": overlays,
    }
    if scope is not None:
        payload.update(scope)
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(endpoint, data=body, method="POST", headers={
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            result = json.load(response)
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise BrainUnavailable(f"Supabase editorial context request failed: {type(exc).__name__}") from exc
    if not isinstance(result, dict) or result.get("schema") != "editorial-brain.context/v1" or result.get("project_ref") != expected_project:
        raise BrainUnavailable("Supabase context schema or project identity mismatch")
    query = result.get("query")
    expected_query = {"problem": problem, "format": fmt, "limit": 5,
                      "includeDevelopment": include_development,
                      "currentProjectPrefix": project_prefix,
                      "heldOutSourcePrefixes": held_out or [],
                      "includeRequiredReading": required_reading, "readingOverlays": overlays}
    if not isinstance(query, dict) or any(query.get(k) != v for k, v in expected_query.items()):
        raise BrainUnavailable("Supabase response does not match the requested context")
    playbooks = result.get("playbooks")
    if not isinstance(playbooks, list):
        raise BrainUnavailable("Supabase response has no playbooks")
    by_format = {row.get("format"): row for row in playbooks if isinstance(row, dict)}
    if len(playbooks) != 2 or set(by_format) != {"universal", fmt}:
        raise BrainUnavailable("required universal or format playbook is missing")
    for row in playbooks:
        text = row.get("body")
        digest = row.get("body_sha256")
        version = row.get("version")
        if not isinstance(version, int) or isinstance(version, bool) or version < 1:
            raise BrainUnavailable("active playbook version is missing or invalid")
        if not isinstance(text, str) or not isinstance(digest, str) or \
                hashlib.sha256(text.encode("utf-8")).hexdigest() != digest:
            raise BrainUnavailable("playbook body hash mismatch")
    validate_cards(result.get("cards"), fmt, include_development,
                   [p for p in [project_prefix, *(held_out or [])] if p])
    if required_reading:
        validate_required_reading(result, fmt, overlays)
    if scope is not None:
        try:
            if any(query.get(k) != v for k, v in
                   {'brand': brand, 'productionType': production_type, 'stage': stage}.items()):
                raise ValueError('scoped response does not match the requested brand/production/stage')
            validate_scoped_policies(result.get("scoped_policy"), scope)
        except ValueError as exc:
            # Reject unusable scoped data without turning additive guidance into
            # another assembly/export gate. Core playbooks/readings were validated
            # above and keep their existing fail-closed semantics.
            result['scoped_policy'] = {
                'policies': [], 'status': 'unavailable',
                'note': 'Scoped guidance rejected: '+str(exc)+
                        '. Record this limitation in the existing handoff; no new quality gate.',
            }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", required=True, choices=FORMATS)
    parser.add_argument("--problem", help="actual editorial problem; optional for --preflight")
    parser.add_argument("--out", type=Path,
                        help="save verified response with a timestamp/hash; refuses replacement")
    parser.add_argument("--project-prefix")
    parser.add_argument("--held-out", action="append", default=[])
    parser.add_argument("--include-development", action="store_true",
                        help="also retrieve explicitly labeled unverified development research")
    parser.add_argument("--preflight", action="store_true", help="connectivity and active-playbook check")
    parser.add_argument("--reading-overlay", action="append", choices=READING_OVERLAYS, default=[],
                        help="batch preflight overlay; repeat for L1 or Workshop context")
    parser.add_argument("--brand", help="brand slug from source/run identity")
    parser.add_argument("--production-type", help="production family independent of the content-unit format")
    parser.add_argument("--stage", choices=(*STAGES, "all"), help="scoped policy stage; all is the run handoff")
    args = parser.parse_args()
    if not args.preflight and not (args.problem and args.problem.strip()):
        parser.error("--problem is required unless --preflight is used")
    if args.out and args.out.exists():
        parser.error("--out already exists; choose a new revision path")
    try:
        result = fetch_context(problem="assembly preflight" if args.preflight else args.problem,
                               fmt=args.format, project_prefix=args.project_prefix,
                               held_out=args.held_out,
                               include_development=args.include_development,
                               required_reading=args.preflight,
                               reading_overlays=args.reading_overlay, brand=args.brand,
                               production_type=args.production_type,
                               stage=None if args.stage == "all" else args.stage)
        if args.out:
            result = save_context(result, args.out)
    except BrainUnavailable as exc:
        print(f"EDITORIAL_BRAIN_UNAVAILABLE: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"EDITORIAL_CONTEXT_NOT_SAVED: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
