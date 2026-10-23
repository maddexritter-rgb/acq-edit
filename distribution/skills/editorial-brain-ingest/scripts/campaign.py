#!/usr/bin/env python3
"""Inventory and durable checkpoints for a cut-study campaign; no editorial decisions."""

import argparse
import fcntl
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from native_selection import pinned


STATUSES = {"inspected", "raw_mapped", "selection_reviewed", "published", "retrieved",
            "no_new_finding", "additional_support", "blocked"}
COMPLETE = {"retrieved", "no_new_finding", "additional_support"}


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def load(path):
    return json.loads(path.read_text())


def new_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write("\n")


def replace_json(path, value):
    # Only derived current-state files are replaced. Events and artifacts stay immutable.
    temporary = path.with_name(path.name + ".pending")
    with temporary.open("x") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def inventory(config):
    root = Path(config["project_root"])
    if not root.is_dir():
        raise ValueError("project volume/root is unavailable")
    evidence = Path(config["evidence_root"])
    projects = []
    for path in sorted(root.glob("*.prproj")):
        match = re.search(r"#\s*(\d+)", path.name)
        label = match.group(1) if match else None
        sha = digest(path)
        projects.append({"project_id": sha, "uri": str(path), "sha256": sha,
                         "size": path.stat().st_size, "label": label,
                         "inspection_status": "UNINSPECTED", "distinct_final_count": None,
                         "historical_study_uri": str(evidence / "native_studies" / label)
                         if label and (evidence / "native_studies" / label).is_dir() else None,
                         "existing_final_directory": str(evidence / "finals" / label)
                         if label and (evidence / "finals" / label).is_dir() else None})
    hashes = {}
    for project in projects:
        hashes.setdefault(project["sha256"], []).append(project["uri"])
    return {"schema": "editorial-brain.registry/v1", "created_at": now(),
            "campaign_id": config["campaign_id"], "project_file_count": len(projects),
            "unique_project_hashes": len(hashes), "distinct_final_count": None,
            "duplicate_project_files": [v for v in hashes.values() if len(v) > 1],
            "projects": projects, "cases": [],
            "note": "Filesystem identity only; no native final or editorial verification inferred."}


def record(root, entry):
    if entry.get("status") not in STATUSES or not isinstance(entry.get("case_id"), str) or not entry["case_id"]:
        raise ValueError("entry requires case_id and a supported status")
    for field in ("summary", "next_action"):
        if not isinstance(entry.get(field), str) or not entry[field].strip():
            raise ValueError(f"entry requires {field}")
    artifacts = entry.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise ValueError("checkpoint requires evidence artifacts")
    checked = []
    for ref in artifacts:
        path = Path(ref["uri"])
        if not path.is_absolute() or not path.is_file():
            raise ValueError("checkpoint evidence must be a readable absolute file")
        sha = digest(path)
        if ref.get("sha256") and sha != ref["sha256"]:
            raise ValueError("checkpoint artifact changed")
        checked.append({"uri": str(path), "sha256": sha})
    if entry["status"] in {"published", "retrieved"}:
        errors=[]
        receipt=pinned(entry.get("publication_receipt"), errors, "publication_receipt")
        if errors or not isinstance(receipt,dict):
            raise ValueError("publication receipt unreadable: " + "; ".join(errors))
        config=load(root/"campaign.json")
        if receipt.get("project_ref") != config["project_ref"] or receipt.get("case_id") != entry["case_id"]:
            raise ValueError("publication receipt project/case mismatch")
        if not receipt.get("cards") or not all(c.get("readback_matches") is True for c in receipt["cards"]):
            raise ValueError("publication receipt lacks matching card readback")
        if entry["status"] == "retrieved" and not all(c.get("problem_retrieval_passed") is True and
                c.get("transfer_retrieval_passed") is True and c.get("negative_query_reviewed") is True for c in receipt["cards"]):
            raise ValueError("publication receipt lacks required retrieval checks")
    if entry["status"] in {"no_new_finding", "additional_support"} and not entry.get("disposition_reason"):
        raise ValueError("completed disposition requires reason")
    event = dict(entry, artifacts=checked, recorded_at=now())
    events = root / "events.jsonl"
    with events.open("a") as stream:
        stream.write(json.dumps(event, ensure_ascii=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    return rebuild_state(root)


def rebuild_state(root):
    events_path = root / "events.jsonl"
    events = [json.loads(line) for line in events_path.read_text().splitlines() if line.strip()] if events_path.exists() else []
    latest = {}
    for event in events:
        latest[event["case_id"]] = event
    state = load(root / "state.json")
    completed = sum(e["status"] in COMPLETE for e in latest.values())
    state.update(completed_studies=completed,
                 blocked_cases=[k for k,v in latest.items() if v["status"] == "blocked"],
                 unpublished_cases=[k for k,v in latest.items() if v["status"] == "selection_reviewed"],
                 checkpoint_count=len(events), updated_at=now())
    if events:
        last = events[-1]
        state.update(active_case=last["case_id"], last_completed_step=last["summary"], next_action=last["next_action"])
    state["report_due"] = completed // state.get("report_every_completed_cases",10) > state.get("reported_batches",0)
    state["published_cards"] = len({cid for e in latest.values() if e["status"] in {"published","retrieved"} for cid in e.get("card_ids",[])})
    registry_path=root/"registry.json"
    if registry_path.exists():
        registry=load(registry_path)
        registry["cases"]=list(latest.values())
        replace_json(registry_path,registry)
    replace_json(root / "state.json", state)
    return state


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign",type=Path,required=True)
    sub=parser.add_subparsers(dest="command",required=True)
    sub.add_parser("inventory").add_argument("--out",type=Path,required=True)
    sub.add_parser("record").add_argument("entry",type=Path)
    sub.add_parser("resume")
    args=parser.parse_args()
    root=args.campaign.resolve(); config=load(root/"campaign.json")
    with (root/".campaign.lock").open("a") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.command == "inventory":
            result=inventory(config);new_json(args.out,result)
            print(json.dumps({"project_file_count":result["project_file_count"],"unique_project_hashes":result["unique_project_hashes"],"out":str(args.out)}))
        elif args.command == "record":
            print(json.dumps(record(root,load(args.entry)),indent=2))
        else:
            print(json.dumps(rebuild_state(root),indent=2))


if __name__ == "__main__":
    main()
