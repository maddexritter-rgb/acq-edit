#!/usr/bin/env python3
"""Block timestamp-window or templated plans before assembly execution."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path


SCHEMA = "assembly-design.design-comparison/v1"
WORKSHEET_SCHEMA = "assembly-design.editorial-worksheet/v1"
SCOPES = {"opening", "body", "ending"}
CONTENT_UNIT_FIELDS = (
    "viewer",
    "promise",
    "reward",
    "cold_viewer",
    "goodwill",
    "value_compression",
    "audience_growth",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("root is not an object")
    return value


def norm(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def word_rows(plan: dict) -> list[dict]:
    source = Path(plan["source_words"])
    payload = load(source)
    rows = payload.get("words")
    if not isinstance(rows, list):
        raise ValueError(f"source words missing in {source}")
    return rows


def parse_ranges(value: object, label: str, errors: list[str]) -> list[list[int]]:
    if not isinstance(value, list) or not value:
        errors.append(f"{label} lacks word_ranges")
        return []
    result = []
    for item in value:
        if (not isinstance(item, list) or len(item) != 2 or
                not all(type(n) is int for n in item) or item[0] < 0 or item[0] > item[1]):
            errors.append(f"{label} has invalid word range: {item!r}")
            continue
        result.append(item)
    return result


def quote(rows: list[dict], ranges: list[list[int]]) -> str:
    tokens = []
    for first, last in ranges:
        if first < 0 or last >= len(rows):
            raise ValueError(f"word range outside source: {[first, last]}")
        tokens.extend(norm(row.get("word")) for row in rows[first:last + 1])
    return norm(" ".join(tokens))


def selected_indices(ranges: list[list[int]]) -> set[int]:
    return {index for first, last in ranges for index in range(first, last + 1)}


def check_text(rows: list[dict], ranges: list[list[int]], actual: object,
               label: str, errors: list[str]) -> None:
    try:
        expected = quote(rows, ranges)
    except ValueError as exc:
        errors.append(f"{label}: {exc}")
        return
    if norm(actual) != expected:
        errors.append(f"{label} text is not exact source dialogue")


def check_plan_pin(clip_dir: Path, plan_path: Path, pin: object,
                   errors: list[str]) -> None:
    if not isinstance(pin, dict) or not pin.get("path") or not pin.get("sha256"):
        errors.append("reviewed_plan path/hash pin missing")
        return
    target = Path(pin["path"])
    if not target.is_absolute():
        target = (clip_dir / target).resolve()
    if not target.is_file():
        errors.append(f"reviewed_plan missing: {target}")
        return
    digest = sha256(target)
    if digest != pin["sha256"]:
        errors.append("reviewed_plan hash mismatch")
    if target.resolve() != plan_path.resolve() or digest != sha256(plan_path):
        errors.append("design comparison is not pinned to current assembly_plan.json")


def evaluate_clip(clip_dir: Path) -> dict:
    errors: list[str] = []
    plan_path = clip_dir / "assembly_plan.json"
    comparison_path = clip_dir / "design_comparison.json"
    worksheet_path = clip_dir / "editorial_worksheet.json"
    if not plan_path.is_file():
        return {"clip_id": clip_dir.name, "status": "FAIL",
                "errors": ["assembly_plan.json missing"], "fingerprints": {}}
    if not comparison_path.is_file():
        return {"clip_id": clip_dir.name, "status": "FAIL",
                "errors": ["design_comparison.json missing"], "fingerprints": {}}
    try:
        plan = load(plan_path)
        comparison = load(comparison_path)
        worksheet = load(worksheet_path) if worksheet_path.is_file() else None
        rows = word_rows(plan)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        return {"clip_id": clip_dir.name, "status": "FAIL",
                "errors": [f"unreadable design evidence: {exc}"], "fingerprints": {}}

    if comparison.get("schema") != SCHEMA:
        errors.append(f"wrong comparison schema: {comparison.get('schema')!r}")
    if worksheet is not None and worksheet.get("schema") != WORKSHEET_SCHEMA:
        errors.append(f"wrong worksheet schema: {worksheet.get('schema')!r}")
    check_plan_pin(clip_dir, plan_path, comparison.get("reviewed_plan"), errors)

    plan_ranges = [segment.get("words") for segment in plan.get("segments", [])]
    if not plan_ranges:
        errors.append("plan has no selected segments")
        plan_ranges = []
    validated_ranges = parse_ranges(plan_ranges, 'plan segments', errors)
    if any(r[1] >= len(rows) for r in validated_ranges) or len(validated_ranges) != len(plan_ranges):
        return {'clip_id': clip_dir.name, 'status': 'FAIL',
                'errors': errors + ['plan range outside source or malformed'], 'fingerprints': {}}
    plan_selected = selected_indices(validated_ranges)
    interaction = plan.get("interaction_words")

    if worksheet is not None:
        worksheet_source = worksheet.get("source_words")
        if not isinstance(worksheet_source, dict):
            errors.append("worksheet source_words pin missing")
        elif (worksheet_source.get("path") != plan.get("source_words") or
              worksheet_source.get("sha256") != plan.get("source_sha256")):
            errors.append("worksheet source pin does not match plan")
        if worksheet.get("interaction_words") != interaction:
            errors.append("worksheet interaction_words do not match plan")
        if isinstance(interaction, list) and len(interaction) == 2:
            check_text(rows, [interaction], worksheet.get("interaction_text"),
                       "worksheet interaction", errors)

        required_worksheet = (
            "source_read", "question_and_revealed_problem", "branch_ledger",
            "ranked_promises", "selected_promise", "question_policy",
            "reasoning_ladder", "payoff", "omissions", "reorder_checks",
            "proposed_assembly", "cold_read", "meaningful_alternative",
        )
        for key in required_worksheet:
            value = worksheet.get(key)
            if value is None or value == "" or value == []:
                errors.append(f"worksheet {key} missing or empty")
        ranked = worksheet.get("ranked_promises")
        if not isinstance(ranked, list) or not ranked:
            errors.append("worksheet must rank at least one viable promise")
        proposed = worksheet.get("proposed_assembly")
        if not isinstance(proposed, dict):
            errors.append("worksheet proposed_assembly missing")
        elif proposed.get("word_ranges") != plan_ranges:
            errors.append("worksheet proposed ranges do not match plan playback order")
        else:
            check_text(rows, plan_ranges, proposed.get("text"),
                       "worksheet proposed assembly", errors)

    interaction_evidence = comparison.get("interaction")
    if not isinstance(interaction_evidence, dict):
        errors.append("interaction evidence missing")
    else:
        if interaction_evidence.get("word_range") != interaction:
            errors.append("interaction evidence does not match plan interaction_words")
        if isinstance(interaction, list) and len(interaction) == 2:
            check_text(rows, [interaction], interaction_evidence.get("text"),
                       "interaction", errors)

    baseline = comparison.get("unedited_baseline")
    if not isinstance(baseline, dict):
        errors.append("unedited_baseline missing")
    elif baseline.get("word_ranges") != [interaction]:
        errors.append("unedited_baseline must contain the full continuous interaction")
    elif isinstance(interaction, list) and len(interaction) == 2:
        check_text(rows, [interaction], baseline.get("text"), "unedited_baseline", errors)

    selected = comparison.get("selected_assembly")
    if not isinstance(selected, dict):
        errors.append("selected_assembly missing")
    elif selected.get("word_ranges") != plan_ranges:
        errors.append("selected_assembly ranges do not exactly match plan playback order")
    else:
        check_text(rows, plan_ranges, selected.get("text"), "selected_assembly", errors)

    for label in ("hook", "retention_path", "payoff"):
        evidence = comparison.get(label)
        if not isinstance(evidence, dict):
            errors.append(f"{label} evidence missing")
            continue
        ranges = parse_ranges(evidence.get("word_ranges"), label, errors)
        if any(r[1] >= len(rows) for r in ranges):
            errors.append(f'{label} range outside source')
            continue
        if any(index not in plan_selected for index in selected_indices(ranges)):
            errors.append(f"{label} cites words outside the selected assembly")
        if label == 'hook':
            playback = [i for a, b in validated_ranges for i in range(a, b + 1)]
            opening = [i for a, b in ranges for i in range(a, b + 1)]
            if not opening or playback[:len(opening)] != opening:
                errors.append('hook evidence must be the actual opening prefix, not a buried line')
        if len(norm(evidence.get("why"))) < 24:
            errors.append(f"{label} why is too generic or empty")
        check_text(rows, ranges, evidence.get("quote"), label, errors)

    content_unit = comparison.get("content_unit")
    if not isinstance(content_unit, dict):
        errors.append("content_unit judgments missing")
    else:
        for field in CONTENT_UNIT_FIELDS:
            if len(norm(content_unit.get(field))) < 24:
                errors.append(f"content_unit {field} is too generic or empty")

    decisions = comparison.get("decisions")
    scopes = set()
    if not isinstance(decisions, list) or not decisions:
        errors.append("opening/body/ending design decisions missing")
    else:
        for index, decision in enumerate(decisions):
            if not isinstance(decision, dict):
                errors.append(f"decision {index} is not an object")
                continue
            scope = decision.get("scope")
            if scope in SCOPES:
                scopes.add(scope)
            else:
                errors.append(f"decision {index} has invalid scope: {scope!r}")
            decision_ranges = parse_ranges(decision.get("word_ranges"), f"decision {index}", errors)
            if any(r[1] >= len(rows) for r in decision_ranges):
                errors.append(f'decision {index} range outside source')
            if len(norm(decision.get("why"))) < 24:
                errors.append(f"decision {index} why is too generic or empty")
        missing_scopes = sorted(SCOPES - scopes)
        if missing_scopes:
            errors.append(f"missing design decision scopes: {', '.join(missing_scopes)}")

    one_span = len(plan_ranges) == 1
    if comparison.get("single_span") is not one_span:
        errors.append("single_span flag disagrees with the plan")
    if one_span and len(norm(comparison.get("clean_source_justification"))) < 60:
        errors.append("single-span plan lacks a substantive clean-source justification")

    alternative = comparison.get("alternative_review")
    if not isinstance(alternative, dict) or not isinstance(
            alternative.get("meaningful_alternative"), bool):
        errors.append("alternative_review missing meaningful_alternative decision")
    elif len(norm(alternative.get("why"))) < 24:
        errors.append("alternative_review why is too generic or empty")
    elif alternative["meaningful_alternative"]:
        alt_ranges = parse_ranges(alternative.get("word_ranges"),
                                  "alternative_review", errors)
        check_text(rows, alt_ranges, alternative.get("text"),
                   "alternative_review", errors)

    editorial = plan.get("editorial_review", {})
    review_fingerprint = norm(" | ".join(str(editorial.get(key, "")) for key in (
        "hook", "payoff", "context", "qualifications", "omitted_branches",
        "reorder_safety", "ending_continuation", "alternatives")))
    evidence_fingerprint = norm(" | ".join(
        f"{comparison.get(key, {}).get('quote', '')}::{comparison.get(key, {}).get('why', '')}"
        for key in ("hook", "retention_path", "payoff")))
    if isinstance(content_unit, dict):
        evidence_fingerprint = norm(evidence_fingerprint + " | " + " | ".join(
            str(content_unit.get(key, "")) for key in CONTENT_UNIT_FIELDS))
    return {"clip_id": clip_dir.name, "status": "FAIL" if errors else "PASS",
            "errors": errors, "fingerprints": {
                "editorial_review": review_fingerprint,
                "design_evidence": evidence_fingerprint}}


def evaluate_batch(clips_root: Path) -> list[dict]:
    rows = [evaluate_clip(path) for path in sorted(clips_root.iterdir())
            if path.is_dir() and ((path / "assembly_plan.json").exists() or
                                  (path / "design_comparison.json").exists())]
    for kind in ("editorial_review", "design_evidence"):
        grouped: dict[str, list[dict]] = defaultdict(list)
        for row in rows:
            value = row.get("fingerprints", {}).get(kind)
            if value:
                grouped[value].append(row)
        for matches in grouped.values():
            if len(matches) > 1:
                ids = ", ".join(row["clip_id"] for row in matches)
                for row in matches:
                    row["errors"].append(
                        f"templated duplicate {kind} across clips: {ids}")
                    row["status"] = "FAIL"
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--clips-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    rows = evaluate_batch(args.clips_root)
    if not rows:
        rows = [{"clip_id": None, "status": "FAIL",
                 "errors": ["no clip plans found"], "fingerprints": {}}]
    failures = [row for row in rows if row["status"] != "PASS"]
    receipt = {"schema": "assembly-design.design-quality-gate/v1",
               "status": "FAIL" if failures else "PASS",
               "included": len(rows), "passed": len(rows) - len(failures),
               "failed": len(failures), "clips": rows}
    if args.out.exists():
        print(f"refusing to overwrite {args.out}", file=sys.stderr)
        return 2
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
