"""Evidence bindings for scoped native-final spoken choices, not acoustic proof."""

import hashlib
import json
import re
from pathlib import Path


def pinned(ref, errors, label, as_json=True):
    if not isinstance(ref, dict) or not isinstance(ref.get("uri"), str):
        errors.append(f"{label}: pinned artifact requires uri and sha256")
        return None
    path = Path(ref["uri"])
    if not path.is_absolute() or not re.fullmatch(r"[0-9a-f]{64}", str(ref.get("sha256", ""))):
        errors.append(f"{label}: absolute path and SHA-256 required")
        return None
    try:
        raw = path.read_bytes()
        if not raw or hashlib.sha256(raw).hexdigest() != ref["sha256"]:
            raise ValueError("empty artifact or changed bytes")
        return json.loads(raw) if as_json else raw
    except (OSError, ValueError) as exc:
        errors.append(f"{label}: {exc}")
        return None


def words(value):
    return isinstance(value, str) and bool(value.strip())


def scope_ids(scope):
    ids = scope.get("claim_ids") if isinstance(scope, dict) else None
    return ids if isinstance(ids, list) and ids and all(words(x) for x in ids) and len(ids) == len(set(ids)) else None


def validate_selection(data):
    errors = []

    def need(ok, message):
        if not ok:
            errors.append(message)

    need(data.get("reference_authority") == "native_final", "selection_reviewed requires native_final authority")
    scope = data.get("verification_scope", {})
    ids = scope_ids(scope)
    need(isinstance(scope, dict) and scope.get("kind") == "spoken_selection" and ids,
         "selection_reviewed requires named spoken_selection claims")
    unresolved = data.get("unresolved_ranges")
    need(isinstance(unresolved, list), "unresolved_ranges must be an explicit list")
    if isinstance(unresolved, list):
        for row in unresolved:
            if not isinstance(row, dict):
                errors.append("unresolved range must be an object")
                continue
            need(row.get("dimension") in {"selection", "native_identity", "delivery", "acoustic_boundaries"}
                 and words(row.get("reason")), "unresolved range requires dimension and reason")
            affected = row.get("claim_ids")
            need(isinstance(affected, list) and all(words(x) for x in affected),
                 "unresolved range requires affected claim_ids (empty means whole case)")
            if row.get("dimension") in {"selection", "native_identity"}:
                need(isinstance(affected, list) and affected and not set(affected).intersection(ids or []),
                     "verified selection intersects unresolved identity/selection")
    verification = data.get("verification", {})
    for key, schema in (("native_final_receipt", "editorial-brain.native-final/v1"),
                        ("selection_receipt", "editorial-brain.selection-review/v1")):
        receipt = pinned(verification.get(key), errors, key)
        if receipt is None:
            continue
        if not isinstance(receipt, dict):
            errors.append(f"{key} must contain an object")
            continue
        need(receipt.get("schema") == schema, f"{key}: invalid receipt schema")
        for identity in ("case_id", "project_sha256", "sequence_uid"):
            need(receipt.get(identity) == data.get(identity), f"{key}: {identity} disagrees")
        if key == "native_final_receipt":
            need(receipt.get("reference_authority") == "native_final", "native receipt authority disagrees")
            need(receipt.get("fully_edited_captioned_sequence") is True,
                 "native reference must be an inspected fully edited captioned sequence")
            for field in ("selection_rationale", "caption_evidence", "finished_picture_evidence", "revision_resolution"):
                need(words(receipt.get(field)), f"native receipt requires {field}")
            pinned(receipt.get("bridge_snapshot"), errors, "native bridge snapshot")
        else:
            claims = receipt.get("claims")
            if not isinstance(claims, list):
                errors.append("selection receipt requires claims")
                continue
            by_id = {}
            passages = {p["passage_id"]: p for p in data.get("kept", []) if isinstance(p, dict) and words(p.get("passage_id"))}
            omissions = {o["omission_id"]: o for o in data.get("omissions", []) if isinstance(o, dict) and words(o.get("omission_id"))}
            raw_sources = {s.get("source_id"): s for s in data.get("raw_sources", []) if isinstance(s, dict)}
            for claim in claims:
                if not isinstance(claim, dict) or not words(claim.get("claim_id")):
                    errors.append("selection claim needs claim_id")
                    continue
                cid = claim["claim_id"]
                need(cid not in by_id, "duplicate selection claim_id")
                by_id[cid] = claim
                for field in ("before_text", "after_text", "comparison", "occurrence_review"):
                    need(words(claim.get(field)), f"{cid}: requires {field}")
                need(claim.get("source_occurrence_confirmed") is True, f"{cid}: unresolved source occurrence")
                need(claim.get("spoken_selection_confirmed") is True, f"{cid}: unresolved spoken selection")
                pinned(claim.get("complete_raw_context"), errors, f"{cid} complete raw context", as_json=False)
                selected = claim.get("passage_ids")
                removed = claim.get("omission_ids")
                need(isinstance(selected, list) and selected and all(x in passages for x in selected),
                     f"{cid}: invalid passage_ids")
                need(isinstance(removed, list) and all(x in omissions for x in removed), f"{cid}: invalid omission_ids")
                mapping = pinned(claim.get("word_mapping"), errors, f"{cid} word mapping")
                if isinstance(mapping, dict):
                    need(mapping.get("case_id") == data.get("case_id"), f"{cid}: mapping case mismatch")
                    rows = mapping.get("passages")
                    need(isinstance(rows, list), f"{cid}: mapping requires passages")
                    mapped = {}
                    for row in rows if isinstance(rows, list) else []:
                        if not isinstance(row, dict):
                            errors.append(f"{cid}: malformed mapping row")
                            continue
                        pid = row.get("passage_id")
                        need(isinstance(pid, str) and pid in passages and pid not in mapped, f"{cid}: invalid mapped passage")
                        if not isinstance(pid, str) or pid not in passages:
                            continue
                        mapped[pid] = row
                        native = passages[pid]
                        for field in ("native_item_id", "source_id", "source_start_sample", "source_end_sample",
                                      "timeline_start_ticks", "timeline_end_ticks"):
                            need(row.get(field) == native.get(field), f"{cid}/{pid}: mapping {field} mismatch")
                        src = raw_sources.get(native.get("source_id"), {})
                        need(bool(re.fullmatch(r"[0-9a-f]{64}", str(src.get("sha256", "")))), f"{cid}/{pid}: raw hash missing")
                        need(row.get("source_sha256") == src.get("sha256"), f"{cid}/{pid}: raw identity mismatch")
                        need(words(row.get("text")) and words(row.get("word_locator")), f"{cid}/{pid}: exact words and locator required")
                    need(isinstance(selected, list) and set(selected).issubset(mapped), f"{cid}: incomplete word mapping")
                else:
                    need(False, f"{cid}: word mapping must be an object")
            need(set(ids or []).issubset(by_id), "verified scope names missing claims")
    return errors
