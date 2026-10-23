#!/usr/bin/env python3
"""Append-only editing decision memory with stage-scoped hybrid retrieval.

The JSONL ledger is the durable project evidence. SQLite is a rebuildable index
for structured filters, FTS5, and deterministic feature-hash vector search.
No command in this module edits a canonical skill.
"""

from __future__ import annotations

import argparse
import datetime as dt
import functools
import hashlib
import json
import math
import os
import re
import sqlite3
import sys
import uuid
from pathlib import Path

STAGES = ("assembly", "cuts", "boundaries", "camera_reformatting", "captions", "audio", "qa")
CLASSES = ("implemented_rule", "retrievable_precedent", "hypothesis", "counterexample", "unresolved", "rejected")
PROMOTION = ("not_candidate", "candidate", "counterexample_reviewed", "held_out_validated", "user_approved", "implemented")
ELIGIBILITY = ("verified_captioned_final", "quarantined_nonfinal", "unresolved_final_identity")
FINAL_PROOF_TYPES = ("captioned_export", "captioned_final_timeline")
OWNERS = {
    "assembly": "assembly-design", "cuts": "cut", "boundaries": "cut",
    "camera_reformatting": "horizontal-to-vertical", "captions": "caption-clips",
    "audio": "audit-audio", "qa": "edit",
}
TOKEN_RE = re.compile(r"[a-z0-9$%]+")
VECTOR_DIMS = 256


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def default_db() -> Path:
    root = Path(os.environ.get("CONTENT_VAULT", Path("__ACQ_ASSETS__") / "content-skill-system" / "vault"))
    return root / "edit-memory" / "evidence.sqlite3"


def default_ledger(db: Path) -> Path:
    return db.with_name("evidence.jsonl")


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    cx = sqlite3.connect(path)
    cx.row_factory = sqlite3.Row
    cx.execute("PRAGMA foreign_keys=ON")
    cx.execute("PRAGMA journal_mode=WAL")
    cx.executescript("""
    CREATE TABLE IF NOT EXISTS decisions (
      id TEXT PRIMARY KEY, decision_key TEXT NOT NULL, revision INTEGER NOT NULL,
      created_at TEXT NOT NULL, case_id TEXT NOT NULL, stage TEXT NOT NULL,
      classification TEXT NOT NULL, situation TEXT NOT NULL, alternatives_json TEXT NOT NULL,
      chosen_action TEXT NOT NULL, reasoning TEXT NOT NULL, exceptions_json TEXT NOT NULL,
      confidence REAL NOT NULL, owning_skill TEXT NOT NULL, promotion_status TEXT NOT NULL,
      source_kind TEXT NOT NULL, vector_json TEXT NOT NULL, supersedes TEXT,
      content_hash TEXT NOT NULL UNIQUE
    );
    CREATE TABLE IF NOT EXISTS evidence_paths (
      decision_id TEXT NOT NULL REFERENCES decisions(id), path TEXT NOT NULL,
      locator TEXT NOT NULL DEFAULT '', sha256 TEXT, PRIMARY KEY(decision_id,path,locator)
    );
    CREATE TABLE IF NOT EXISTS retrieval_events (
      id TEXT PRIMARY KEY, created_at TEXT NOT NULL, case_id TEXT, stage TEXT NOT NULL,
      query TEXT NOT NULL, excluded_cases_json TEXT NOT NULL, returned_ids_json TEXT NOT NULL,
      changed_decision INTEGER, corrections_prevented INTEGER, cost_json TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS experiment_events (
      id TEXT PRIMARY KEY, created_at TEXT NOT NULL, case_id TEXT NOT NULL, event_type TEXT NOT NULL,
      payload_json TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS decision_eligibility_events (
      id TEXT PRIMARY KEY, created_at TEXT NOT NULL, decision_id TEXT NOT NULL REFERENCES decisions(id),
      status TEXT NOT NULL, reason TEXT NOT NULL, proof_json TEXT NOT NULL, content_hash TEXT NOT NULL UNIQUE
    );
    CREATE VIRTUAL TABLE IF NOT EXISTS decision_fts USING fts5(
      decision_id UNINDEXED, situation, alternatives, chosen_action, reasoning, exceptions,
      tokenize='porter unicode61'
    );
    CREATE INDEX IF NOT EXISTS decisions_stage_case ON decisions(stage,case_id);
    CREATE INDEX IF NOT EXISTS decisions_key_revision ON decisions(decision_key,revision);
    CREATE INDEX IF NOT EXISTS eligibility_decision_created ON decision_eligibility_events(decision_id,created_at);
    CREATE TRIGGER IF NOT EXISTS decisions_no_update BEFORE UPDATE ON decisions BEGIN SELECT RAISE(ABORT,'append-only decisions'); END;
    CREATE TRIGGER IF NOT EXISTS decisions_no_delete BEFORE DELETE ON decisions BEGIN SELECT RAISE(ABORT,'append-only decisions'); END;
    CREATE TRIGGER IF NOT EXISTS evidence_no_update BEFORE UPDATE ON evidence_paths BEGIN SELECT RAISE(ABORT,'append-only evidence'); END;
    CREATE TRIGGER IF NOT EXISTS evidence_no_delete BEFORE DELETE ON evidence_paths BEGIN SELECT RAISE(ABORT,'append-only evidence'); END;
    CREATE TRIGGER IF NOT EXISTS eligibility_no_update BEFORE UPDATE ON decision_eligibility_events BEGIN SELECT RAISE(ABORT,'append-only eligibility'); END;
    CREATE TRIGGER IF NOT EXISTS eligibility_no_delete BEFORE DELETE ON decision_eligibility_events BEGIN SELECT RAISE(ABORT,'append-only eligibility'); END;
    """)
    return cx


def tokens(text: str) -> list[str]:
    stop = {"the", "a", "an", "and", "or", "of", "to", "for", "in", "on", "is", "it", "this", "that", "with"}
    return [t for t in TOKEN_RE.findall(text.lower()) if len(t) > 1 and t not in stop]


def vector(text: str) -> list[float]:
    """Dependency-free signed feature hashing; deterministic and rebuildable."""
    out = [0.0] * VECTOR_DIMS
    ts = tokens(text)
    for item in ts + [f"{a}_{b}" for a, b in zip(ts, ts[1:])]:
        digest = hashlib.blake2b(item.encode(), digest_size=8).digest()
        n = int.from_bytes(digest, "big")
        out[n % VECTOR_DIMS] += -1.0 if (n >> 8) & 1 else 1.0
    norm = math.sqrt(sum(v * v for v in out)) or 1.0
    return [v / norm for v in out]


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def canonical_record(raw: dict) -> dict:
    missing = [k for k in ("case_id", "stage", "classification", "situation", "alternatives", "chosen_action", "reasoning", "evidence_paths", "exceptions", "confidence", "owning_skill", "promotion_status") if k not in raw]
    if missing:
        raise ValueError("missing fields: " + ", ".join(missing))
    if raw["stage"] not in STAGES: raise ValueError(f"invalid stage: {raw['stage']}")
    if raw["classification"] not in CLASSES: raise ValueError(f"invalid classification: {raw['classification']}")
    if raw["promotion_status"] not in PROMOTION: raise ValueError(f"invalid promotion_status: {raw['promotion_status']}")
    confidence = float(raw["confidence"])
    if not 0 <= confidence <= 1: raise ValueError("confidence must be 0..1")
    result = dict(raw)
    result["alternatives"] = list(raw["alternatives"])
    result["exceptions"] = list(raw["exceptions"])
    result["evidence_paths"] = [p if isinstance(p, dict) else {"path": str(p)} for p in raw["evidence_paths"]]
    result["confidence"] = confidence
    result["source_kind"] = raw.get("source_kind", "observed_case")
    result["decision_key"] = raw.get("decision_key") or hashlib.sha256((raw["case_id"] + "\0" + raw["stage"] + "\0" + raw["situation"]).encode()).hexdigest()[:24]
    result["revision"] = int(raw.get("revision", 1))
    result["supersedes"] = raw.get("supersedes")
    result["created_at"] = raw.get("created_at", now())
    result["id"] = raw.get("id", str(uuid.uuid4()))
    return result


def append_record(cx: sqlite3.Connection, ledger: Path, raw: dict) -> tuple[str, bool]:
    rec = canonical_record(raw)
    stable = {k: rec[k] for k in rec if k not in {"id", "created_at"}}
    digest = hashlib.sha256(json.dumps(stable, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    old = cx.execute("SELECT id FROM decisions WHERE content_hash=?", (digest,)).fetchone()
    if old: return old["id"], False
    text = " ".join([rec["situation"], " ".join(rec["alternatives"]), rec["chosen_action"], rec["reasoning"], " ".join(rec["exceptions"])])
    event = {"event": "decision_appended", **rec, "content_hash": digest}
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False) + "\n")
        fh.flush(); os.fsync(fh.fileno())
    with cx:
        cx.execute("""INSERT INTO decisions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
            rec["id"], rec["decision_key"], rec["revision"], rec["created_at"], rec["case_id"], rec["stage"],
            rec["classification"], rec["situation"], json.dumps(rec["alternatives"], ensure_ascii=False),
            rec["chosen_action"], rec["reasoning"], json.dumps(rec["exceptions"], ensure_ascii=False),
            rec["confidence"], rec["owning_skill"], rec["promotion_status"], rec["source_kind"],
            json.dumps(vector(text)), rec["supersedes"], digest))
        cx.execute("INSERT INTO decision_fts VALUES (?,?,?,?,?,?)", (rec["id"], rec["situation"], " ".join(rec["alternatives"]), rec["chosen_action"], rec["reasoning"], " ".join(rec["exceptions"])))
        for ev in rec["evidence_paths"]:
            p = Path(ev["path"]).expanduser()
            sha = ev.get("sha256")
            if not sha and p.is_file() and p.stat().st_size < 100_000_000:
                sha = hashlib.sha256(p.read_bytes()).hexdigest()
            cx.execute("INSERT INTO evidence_paths VALUES (?,?,?,?)", (rec["id"], str(p), ev.get("locator", ""), sha))
    return rec["id"], True


def append_eligibility(cx: sqlite3.Connection, ledger: Path, decision_id: str, status: str,
                       reason: str, proof: dict) -> tuple[str, bool]:
    """Append a final-identity judgment without rewriting the decision.

    A name containing FINAL is not proof. Active retrieval requires affirmative
    evidence of captions on the exported final or final timeline. Drafts,
    intermediates, model trials, and uncertain assets remain in the audit ledger
    but cannot teach editing decisions.
    """
    if status not in ELIGIBILITY:
        raise ValueError(f"invalid eligibility status: {status}")
    if not cx.execute("SELECT 1 FROM decisions WHERE id=?", (decision_id,)).fetchone():
        raise ValueError(f"unknown decision_id: {decision_id}")
    proof = dict(proof or {})
    if status == "verified_captioned_final":
        if proof.get("proof_type") not in FINAL_PROOF_TYPES:
            raise ValueError("verified_captioned_final requires proof_type captioned_export or captioned_final_timeline")
        if proof.get("captions_visible") is not True:
            raise ValueError("verified_captioned_final requires captions_visible=true")
        if not (proof.get("final_asset_path") or proof.get("final_timeline_path")):
            raise ValueError("verified_captioned_final requires final_asset_path or final_timeline_path")
        if proof.get("analysis_chain_complete") is True:
            if proof.get("proof_type") != "captioned_final_timeline":
                raise ValueError("complete analysis chain requires a verified captioned final Premiere timeline")
            if not proof.get("final_timeline_path"):
                raise ValueError("complete analysis chain requires final_timeline_path")
            timeline = proof.get("timeline_verification") or {}
            required_timeline_fields = {
                "project_path", "sequence_name", "sequence_id", "verified_against_export",
                "verification_method", "draft_sequences_excluded", "premiere_inspection_complete",
            }
            missing_timeline_fields = sorted(required_timeline_fields - set(timeline))
            if missing_timeline_fields:
                raise ValueError(f"complete analysis chain missing timeline verification fields: {missing_timeline_fields}")
            if timeline.get("verified_against_export") is not True:
                raise ValueError("complete analysis chain requires timeline verified against the captioned export")
            if timeline.get("draft_sequences_excluded") is not True:
                raise ValueError("complete analysis chain requires drafts to be explicitly excluded")
            if timeline.get("premiere_inspection_complete") is not True:
                raise ValueError("complete analysis chain requires Premiere inspection")
            required_stages = {"cuts", "camera_reformatting", "captions"}
            completed = set(proof.get("stages_completed") or [])
            if not required_stages.issubset(completed):
                raise ValueError("complete analysis chain requires cuts, camera_reformatting, and captions")
            if not proof.get("raw_source_paths"):
                raise ValueError("complete analysis chain requires raw_source_paths")
            if not proof.get("frame_accurate_transcript_path"):
                raise ValueError("complete analysis chain requires frame_accurate_transcript_path")
            if not proof.get("case_study_manifest_path"):
                raise ValueError("complete analysis chain requires case_study_manifest_path")
            eligible_stages = proof.get("eligible_stages")
            if eligible_stages is not None:
                unknown = set(eligible_stages) - set(STAGES)
                if unknown:
                    raise ValueError(f"eligible_stages contains invalid stages: {sorted(unknown)}")
                if not set(eligible_stages).issubset(completed):
                    raise ValueError("eligible_stages must be a subset of stages_completed")
    stable = {"decision_id": decision_id, "status": status, "reason": reason, "proof": proof}
    digest = hashlib.sha256(json.dumps(stable, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    old = cx.execute("SELECT id FROM decision_eligibility_events WHERE content_hash=?", (digest,)).fetchone()
    if old:
        return old["id"], False
    event_id, created_at = str(uuid.uuid4()), now()
    event = {"event": "decision_eligibility_appended", "id": event_id, "created_at": created_at,
             **stable, "content_hash": digest}
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False) + "\n")
        fh.flush(); os.fsync(fh.fileno())
    with cx:
        cx.execute("INSERT INTO decision_eligibility_events VALUES (?,?,?,?,?,?,?)",
                   (event_id, created_at, decision_id, status, reason,
                    json.dumps(proof, ensure_ascii=False), digest))
    return event_id, True


def latest_eligibility(cx: sqlite3.Connection, decision_id: str) -> dict:
    row = cx.execute("""SELECT status,reason,proof_json,created_at,id
        FROM decision_eligibility_events WHERE decision_id=?
        ORDER BY created_at DESC,rowid DESC LIMIT 1""", (decision_id,)).fetchone()
    if not row:
        return {"status": "unresolved_final_identity", "reason": "No captioned-final certification exists.",
                "proof": {}, "event_id": None, "created_at": None}
    return {"status": row["status"], "reason": row["reason"], "proof": json.loads(row["proof_json"]),
            "event_id": row["id"], "created_at": row["created_at"]}


def retrieval_eligible(eligibility: dict, stage: str | None = None) -> bool:
    """Activate only stages cleared by a verified final-Premiere case study.

    Older complete-chain events without ``eligible_stages`` remain all-stage
    eligible for backward compatibility. New studies can quarantine a failed or
    unresolved stage without suppressing independently verified stages.
    """
    proof = eligibility.get("proof", {})
    if not (eligibility.get("status") == "verified_captioned_final" and
            proof.get("analysis_chain_complete") is True and
            proof.get("proof_type") == "captioned_final_timeline" and
            proof.get("final_timeline_path") and
            (proof.get("timeline_verification") or {}).get("verified_against_export") is True and
            (proof.get("timeline_verification") or {}).get("draft_sequences_excluded") is True and
            (proof.get("timeline_verification") or {}).get("premiere_inspection_complete") is True):
        return False
    eligible_stages = proof.get("eligible_stages")
    if eligible_stages is None:
        return True
    if stage is None:
        return bool(eligible_stages)
    return stage in set(eligible_stages)


def latest_rows(cx: sqlite3.Connection, stage: str, exclude: set[str]) -> list[sqlite3.Row]:
    marks = ",".join("?" for _ in exclude)
    sql = """SELECT d.* FROM decisions d JOIN (SELECT decision_key,MAX(revision) r FROM decisions GROUP BY decision_key) x ON x.decision_key=d.decision_key AND x.r=d.revision WHERE d.stage=?"""
    params: list[object] = [stage]
    if exclude:
        sql += f" AND d.case_id NOT IN ({marks})"; params.extend(sorted(exclude))
    return cx.execute(sql, params).fetchall()


@functools.lru_cache(maxsize=4096)
def evidence_ancestor_case_ids(path_text: str, chosen_action: str) -> frozenset[str]:
    """Recover case IDs from the Markdown heading hierarchy around an excerpt.

    Large synthesis files contain many cases under generic filenames. Importing a
    child heading such as ``Native selected story`` loses the parent case in the
    database row, so reconstruct it from the excerpt's first distinctive tokens.
    """
    path = Path(path_text)
    if not path.is_file() or path.suffix.lower() not in {".md", ".markdown"}:
        return frozenset()
    try:
        raw = path.read_text(errors="replace")
    except OSError:
        return frozenset()
    anchors = re.findall(r"[A-Za-z0-9$%]+", chosen_action)[:16]
    if len(anchors) < 4:
        return frozenset()
    pattern = re.compile(r"\W+".join(re.escape(token) for token in anchors), re.IGNORECASE)
    found: set[str] = set()
    headings = list(re.finditer(r"(?m)^(#{1,6})\s+(.+?)\s*$", raw))
    for match in pattern.finditer(raw):
        active: dict[int, str] = {}
        for heading in headings:
            if heading.start() >= match.start():
                break
            level = len(heading.group(1))
            active = {key: value for key, value in active.items() if key < level}
            active[level] = heading.group(2)
        for title in active.values():
            found.update(re.findall(r"(?<!\d)(\d{4})(?!\d)", title))
    return frozenset(found)


def mentions_excluded_case(row: sqlite3.Row, paths: list[dict], exclude: set[str]) -> bool:
    """Fail closed when a generically labelled record leaks held-out case material.

    Imported synthesis documents and development trials are not always keyed to the
    individual cases they discuss. Checking only ``decisions.case_id`` therefore lets
    a held-out case return through a generic ``corpus`` or ``FINDINGS`` record. Search
    the retrievable record text plus its evidence identity for exact case-id tokens.
    """
    if not exclude:
        return False
    haystack = "\n".join([
        str(row["case_id"]), str(row["situation"]), str(row["alternatives_json"]),
        str(row["chosen_action"]), str(row["reasoning"]), str(row["exceptions_json"]),
        *(str(item.get("path", "")) + " " + str(item.get("locator", "")) for item in paths),
    ])
    if any(re.search(rf"(?<![A-Za-z0-9])#?{re.escape(case_id)}(?![A-Za-z0-9])", haystack)
           for case_id in exclude):
        return True
    ancestor_ids: set[str] = set()
    for item in paths:
        ancestor_ids.update(evidence_ancestor_case_ids(str(item.get("path", "")), str(row["chosen_action"])))
    return bool(ancestor_ids & exclude)


def query(cx: sqlite3.Connection, stage: str, text: str, exclude: set[str], top: int, min_confidence: float) -> list[dict]:
    qtokens, qvec = set(tokens(text)), vector(text)
    ranked = []
    class_weight = {"implemented_rule": .10, "retrievable_precedent": .08, "counterexample": .04, "hypothesis": 0, "unresolved": -.05, "rejected": -.20}
    for row in latest_rows(cx, stage, exclude):
        if row["confidence"] < min_confidence: continue
        eligibility = latest_eligibility(cx, row["id"])
        if not retrieval_eligible(eligibility, row["stage"]):
            continue
        paths = [dict(x) for x in cx.execute("SELECT path,locator,sha256 FROM evidence_paths WHERE decision_id=?", (row["id"],))]
        if mentions_excluded_case(row, paths, exclude):
            continue
        body = " ".join([row["situation"], row["alternatives_json"], row["chosen_action"], row["reasoning"], row["exceptions_json"]])
        bt = set(tokens(body)); lexical = len(qtokens & bt) / max(1, len(qtokens))
        semantic = max(0.0, cosine(qvec, json.loads(row["vector_json"])))
        score = .48 * lexical + .37 * semantic + .15 * row["confidence"] + class_weight[row["classification"]]
        ranked.append({"score": round(score, 6), "id": row["id"], "case_id": row["case_id"], "stage": row["stage"], "classification": row["classification"], "situation": row["situation"], "alternatives": json.loads(row["alternatives_json"]), "chosen_action": row["chosen_action"], "reasoning": row["reasoning"], "exceptions": json.loads(row["exceptions_json"]), "confidence": row["confidence"], "owning_skill": row["owning_skill"], "promotion_status": row["promotion_status"], "evidence_paths": paths, "final_eligibility": eligibility})
    ordered = sorted(ranked, key=lambda x: (-x["score"], -x["confidence"], x["id"]))
    # Corpus synthesis, individual case files, and copied research packets often
    # contain the same finding. Returning all copies crowds out distinct precedents.
    # Keep the highest-ranked representative while retaining its concrete citation.
    unique: list[dict] = []
    seen: set[str] = set()
    for item in ordered:
        fingerprint = re.sub(r"\s+", " ", (item["chosen_action"] + "\n" + item["reasoning"]).strip().lower())
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        unique.append(item)
        if len(unique) >= top:
            break
    return unique


def infer_stage(title: str, body: str) -> str:
    text = (title + " " + body[:800]).lower()
    tests = [
        ("captions", ("caption", "subtitle", "typography")), ("camera_reformatting", ("camera", "reframe", "crop", "split screen", "transform", "anchor")),
        ("boundaries", ("boundary", "phoneme", "seam", "clipped word", "adjacency")), ("audio", ("audio", "lufs", "mix", "microphone", "enhanced wav")),
        ("qa", ("audit", "quality gate", "verification")), ("cuts", ("cut", "trim", "omission")),
    ]
    for stage, words in tests:
        if any(w in text for w in words): return stage
    return "assembly"


def infer_class(title: str, body: str) -> str:
    text = (title + " " + body[:400]).lower()
    if any(x in text for x in ("not implemented", "unimplemented", "not promoted", "unpromoted", "no live skill")): return "hypothesis"
    if "counterexample" in text or "contrast" in text: return "counterexample"
    if "rejected" in text or "do not promote" in text: return "rejected"
    if "unresolved" in text or "remaining" in text or "open:" in text: return "unresolved"
    if "implemented" in text or "locked" in text: return "implemented_rule"
    if "candidate" in text or "hypothesis" in text: return "hypothesis"
    return "retrievable_precedent"


def markdown_sections(path: Path) -> list[tuple[str, str, str]]:
    text = path.read_text(errors="replace")
    matches = list(re.finditer(r"(?m)^(#{1,3})\s+(.+?)\s*$", text))
    if not matches: return [(path.stem, text[:6000], "")]
    out = []
    for i, m in enumerate(matches):
        body = text[m.end(): matches[i + 1].start() if i + 1 < len(matches) else len(text)].strip()
        if len(body) >= 40: out.append((m.group(2).strip(), body[:6000], f"heading={m.group(2).strip()}"))
    return out


def import_markdown(cx: sqlite3.Connection, ledger: Path, roots: list[Path], glob: str, case_regex: str) -> dict:
    stats = {"files": 0, "sections": 0, "inserted": 0, "duplicates": 0}
    pattern = re.compile(case_regex)
    for root in roots:
        files = [root] if root.is_file() else sorted(root.rglob(glob))
        for path in files:
            if not path.is_file(): continue
            stats["files"] += 1
            match = pattern.search(str(path)); case_id = match.group(1) if match else path.stem
            for title, body, locator in markdown_sections(path):
                stage = infer_stage(title, body); cls = infer_class(title, body)
                paragraphs = [p.strip().replace("\n", " ") for p in re.split(r"\n\s*\n", body) if p.strip()]
                chosen = paragraphs[0][:1800] if paragraphs else body[:1800]
                reasoning = " ".join(paragraphs[1:3])[:2400] or "Imported source study; consult cited evidence before applying."
                imported_key = hashlib.sha256((case_id + "\0" + stage + "\0" + str(path.resolve()) + "\0" + locator).encode()).hexdigest()[:24]
                rec = {"case_id": case_id, "stage": stage, "classification": cls, "situation": title,
                       "alternatives": ["Consult the cited case for alternatives and omitted branches."], "chosen_action": chosen,
                       "reasoning": reasoning, "evidence_paths": [{"path": str(path), "locator": locator}],
                       "exceptions": ["Imported research is advisory and may contain unresolved scope limits."],
                       "confidence": .78 if cls in {"implemented_rule", "retrievable_precedent", "counterexample"} else .55,
                       "owning_skill": OWNERS[stage], "promotion_status": "implemented" if cls == "implemented_rule" else "not_candidate",
                       "source_kind": "imported_research", "decision_key": imported_key}
                _, inserted = append_record(cx, ledger, rec)
                stats["sections"] += 1; stats["inserted" if inserted else "duplicates"] += 1
    return stats


def lock_manifest(path: Path, output: Path, variant: str, case_id: str, excluded: list[str], retrieval_ids: list[str]) -> dict:
    payload = path.read_bytes(); digest = hashlib.sha256(payload).hexdigest()
    receipt = {"schema": "edit-memory-manifest-lock.v1", "case_id": case_id, "variant": variant, "manifest": str(path.resolve()), "sha256": digest, "bytes": len(payload), "locked_at": now(), "excluded_cases": sorted(set(excluded)), "retrieval_ids": retrieval_ids, "reference_revealed": False}
    output.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd, "w") as fh: json.dump(receipt, fh, indent=2); fh.write("\n")
    return receipt


def promotion_candidates(cx: sqlite3.Connection, minimum_cases: int) -> list[dict]:
    groups: dict[str, dict] = {}
    for row in cx.execute("SELECT id,case_id,stage,classification,chosen_action,confidence,promotion_status FROM decisions WHERE classification NOT IN ('rejected','unresolved')"):
        if not retrieval_eligible(latest_eligibility(cx, row["id"]), row["stage"]):
            continue
        key = re.sub(r"\s+", " ", row["chosen_action"].strip().lower())
        item = groups.setdefault(key, {"stage": row["stage"], "chosen_action": row["chosen_action"], "case_ids": set(), "decision_ids": [], "counterexample_reviewed": False, "held_out_validated": False, "user_approved": False})
        item["case_ids"].add(row["case_id"]); item["decision_ids"].append(row["id"])
        status = row["promotion_status"]
        item["counterexample_reviewed"] |= status in {"counterexample_reviewed", "held_out_validated", "user_approved", "implemented"}
        item["held_out_validated"] |= status in {"held_out_validated", "user_approved", "implemented"}
        item["user_approved"] |= status in {"user_approved", "implemented"}
    out=[]
    for item in groups.values():
        if len(item["case_ids"]) < minimum_cases: continue
        item["case_ids"] = sorted(item["case_ids"]); item["supporting_case_count"] = len(item["case_ids"])
        item["eligible_for_skill_change"] = bool(item["counterexample_reviewed"] and item["held_out_validated"] and item["user_approved"])
        out.append(item)
    return sorted(out, key=lambda x: (-x["supporting_case_count"], x["stage"], x["chosen_action"]))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=default_db())
    ap.add_argument("--ledger", type=Path)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init")
    p = sub.add_parser("append"); p.add_argument("--record", type=Path, required=True)
    p = sub.add_parser("set-eligibility"); p.add_argument("--decision-id", required=True); p.add_argument("--status", required=True, choices=ELIGIBILITY); p.add_argument("--reason", required=True); p.add_argument("--proof", type=Path, required=True)
    p = sub.add_parser("import-markdown"); p.add_argument("roots", nargs="+", type=Path); p.add_argument("--glob", default="*.md"); p.add_argument("--case-regex", default=r"(?:^|/)(\d{4})(?:/|_)")
    p = sub.add_parser("query"); p.add_argument("--stage", required=True, choices=STAGES); p.add_argument("--query", required=True); p.add_argument("--exclude-case", action="append", default=[]); p.add_argument("--top", type=int, default=5); p.add_argument("--min-confidence", type=float, default=.35); p.add_argument("--case-id"); p.add_argument("--json", action="store_true")
    p = sub.add_parser("lock-manifest"); p.add_argument("--manifest", type=Path, required=True); p.add_argument("--output", type=Path, required=True); p.add_argument("--variant", choices=("baseline", "memory"), required=True); p.add_argument("--case-id", required=True); p.add_argument("--exclude-case", action="append", default=[]); p.add_argument("--retrieval-id", action="append", default=[])
    p = sub.add_parser("record-event"); p.add_argument("--case-id", required=True); p.add_argument("--event-type", required=True, choices=("research_cost", "decision_changed", "correction_prevented", "hypothesis_rejected", "rule_promoted", "qa_result", "blind_review", "reference_comparison")); p.add_argument("--payload", type=Path, required=True)
    p = sub.add_parser("promotion-candidates"); p.add_argument("--minimum-cases", type=int, default=3)
    sub.add_parser("stats")
    args = ap.parse_args(); ledger = args.ledger or default_ledger(args.db); cx = connect(args.db)
    if args.cmd == "init": print(json.dumps({"db": str(args.db), "ledger": str(ledger), "stages": STAGES}, indent=2))
    elif args.cmd == "append":
        rid, inserted = append_record(cx, ledger, json.loads(args.record.read_text())); print(json.dumps({"id": rid, "inserted": inserted}))
    elif args.cmd == "set-eligibility":
        eid, inserted = append_eligibility(cx, ledger, args.decision_id, args.status, args.reason, json.loads(args.proof.read_text())); print(json.dumps({"eligibility_event_id": eid, "inserted": inserted}))
    elif args.cmd == "import-markdown": print(json.dumps(import_markdown(cx, ledger, args.roots, args.glob, args.case_regex), indent=2))
    elif args.cmd == "query":
        results = query(cx, args.stage, args.query, set(args.exclude_case), args.top, args.min_confidence)
        event_id = str(uuid.uuid4()); cx.execute("INSERT INTO retrieval_events VALUES (?,?,?,?,?,?,?,?,?,?)", (event_id, now(), args.case_id, args.stage, args.query, json.dumps(args.exclude_case), json.dumps([r["id"] for r in results]), None, None, "{}")); cx.commit()
        print(json.dumps({"advisory": True, "stage": args.stage, "excluded_cases": args.exclude_case, "retrieval_event_id": event_id, "results": results}, indent=2, ensure_ascii=False))
    elif args.cmd == "lock-manifest": print(json.dumps(lock_manifest(args.manifest, args.output, args.variant, args.case_id, args.exclude_case, args.retrieval_id), indent=2))
    elif args.cmd == "record-event":
        payload = json.loads(args.payload.read_text()); event_id = str(uuid.uuid4()); event = {"event": "experiment_event", "id": event_id, "created_at": now(), "case_id": args.case_id, "event_type": args.event_type, "payload": payload}
        ledger.parent.mkdir(parents=True, exist_ok=True)
        with ledger.open("a", encoding="utf-8") as fh: fh.write(json.dumps(event, ensure_ascii=False) + "\n"); fh.flush(); os.fsync(fh.fileno())
        cx.execute("INSERT INTO experiment_events VALUES (?,?,?,?,?)", (event_id, event["created_at"], args.case_id, args.event_type, json.dumps(payload, ensure_ascii=False))); cx.commit(); print(json.dumps(event, indent=2))
    elif args.cmd == "promotion-candidates": print(json.dumps({"automatic_skill_changes": False, "candidates": promotion_candidates(cx, args.minimum_cases)}, indent=2, ensure_ascii=False))
    elif args.cmd == "stats":
        counts = {t: cx.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in ("decisions", "evidence_paths", "retrieval_events", "experiment_events", "decision_eligibility_events")}
        counts["by_stage"] = {r[0]: r[1] for r in cx.execute("SELECT stage,count(*) FROM decisions GROUP BY stage")}
        counts["latest_by_classification"] = {r[0]: r[1] for r in cx.execute("""WITH latest AS (SELECT decision_key,max(revision) revision FROM decisions GROUP BY decision_key) SELECT d.classification,count(*) FROM decisions d JOIN latest l ON l.decision_key=d.decision_key AND l.revision=d.revision GROUP BY d.classification""")}
        counts["latest_by_final_eligibility"] = {status: 0 for status in ELIGIBILITY}
        counts["retrieval_eligible_decisions"] = 0
        for row in cx.execute("SELECT id,stage FROM decisions"):
            eligibility = latest_eligibility(cx, row["id"])
            counts["latest_by_final_eligibility"][eligibility["status"]] += 1
            counts["retrieval_eligible_decisions"] += int(retrieval_eligible(eligibility, row["stage"]))
        counts["db"] = str(args.db); counts["ledger"] = str(ledger); print(json.dumps(counts, indent=2))


if __name__ == "__main__":
    try: main()
    except (ValueError, FileExistsError, sqlite3.Error) as exc:
        print(f"error: {exc}", file=sys.stderr); raise SystemExit(2)
