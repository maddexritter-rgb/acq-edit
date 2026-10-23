#!/usr/bin/env python3
"""
Clip Review Tracker — state machine for every short-form clip this agency renders.

Stores one markdown file per clip at:
    <vault>/deliveries/<client-slug>/<clip-slug>.md

CLI usage:
    tracker.py create     --client <slug> --clip-slug <slug> --source <path> [--clip <path>] [--subtitles <path>]
    tracker.py transition <clip-slug> <new-state> [--client <slug>] [--artifact <path>] [--note <text>]
    tracker.py feedback   <clip-slug> [--client <slug>] [--text <text> | --file <path>]
    tracker.py status     <clip-slug> [--client <slug>]
    tracker.py list       [--state <state>] [--client <slug>] [--pending-my-eye]
    tracker.py dashboard  [--vault <path>]
    tracker.py summary    [--client <slug>] [--month YYYY-MM]
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

try:
    import yaml
except ImportError:
    print("error: pyyaml not installed. Run: pip3 install --user pyyaml", file=sys.stderr)
    sys.exit(1)


# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

VALID_STATES = {
    "draft", "audited-v1-pass", "audited-v1-fail",
    "with-client", "needs-revision", "patching",
    "audited-v2-pass", "audited-v2-fail",
    "approved", "scheduled", "posted", "archived",
}

VALID_TRANSITIONS = {
    "draft": {"audited-v1-pass", "audited-v1-fail", "archived"},
    "audited-v1-pass": {"with-client", "approved", "archived"},
    "audited-v1-fail": {"patching", "archived"},
    "with-client": {"needs-revision", "approved", "archived"},
    "needs-revision": {"patching", "archived"},
    "patching": {"audited-v2-pass", "audited-v2-fail", "draft", "archived"},
    "audited-v2-pass": {"with-client", "approved", "archived"},
    "audited-v2-fail": {"patching", "archived"},
    "approved": {"scheduled", "posted", "archived"},
    "scheduled": {"posted", "archived"},
    "posted": {"archived"},
    "archived": set(),
}

PENDING_MY_EYE = {
    "audited-v1-fail", "needs-revision", "audited-v2-fail", "approved",
}

STALENESS_RULES = {
    "with-client": 7,       # days — follow up with client
    "approved": 3,          # days — schedule it
    "audited-v1-fail": 2,   # days — fix or archive
    "scheduled": 2,         # days — check if social-publisher worked
}


def default_vault() -> Path:
    """Default vault location — respects CONTENT_VAULT env var, else hard-coded path."""
    import os
    override = os.environ.get("CONTENT_VAULT")
    if override:
        return Path(override)
    return Path("__ACQ_ASSETS__") / "content-skill-system" / "vault"


# ─────────────────────────────────────────────────────────────────────────────
# Data model
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ClipRecord:
    client: str
    clip_slug: str
    current_state: str = "draft"
    current_version: int = 1
    created: str = ""
    updated: str = ""
    source_video: str = ""
    script_file: str = ""
    clip_path: str = ""
    subtitle_file: str = ""
    audit_reports: list[str] = field(default_factory=list)
    frameio_notes: list[str] = field(default_factory=list)
    feedback_files: list[str] = field(default_factory=list)
    history: list[dict] = field(default_factory=list)
    body_notes: str = ""  # free-form user notes
    # Profile fields — feed find-precedents retrieval
    clip_type: str = ""           # q&a, monologue, story, list, comparison, reveal
    gesture_profile: str = ""     # speaker_hand_enters_upper_frame, head_only, podium_static, full_body
    caption_style: str = ""       # pro, ugc, cinematic, big-word, hormozi, liquid-glass
    hook_type: str = ""           # revenue-first, named-framework, question, story-cold-open, contrarian
    duration_seconds: float = 0.0
    tags: list[str] = field(default_factory=list)  # free-form match keys
    # Lessons captured across revisions — what find-precedents surfaces
    lessons: list[dict] = field(default_factory=list)
    # Each lesson: {version, timestamp, issue, when, then}

    @property
    def file_path(self) -> Path:
        return default_vault() / "deliveries" / self.client / f"{self.clip_slug}.md"

    @property
    def duration_band(self) -> str:
        d = self.duration_seconds
        if d <= 0: return ""
        if d < 30: return "under-30"
        if d < 60: return "30-60"
        if d < 120: return "60-120"
        return "over-120"


# ─────────────────────────────────────────────────────────────────────────────
# Persistence
# ─────────────────────────────────────────────────────────────────────────────

FM_SEP = "---\n"


def _now_iso() -> str:
    return dt.datetime.now().replace(microsecond=0).isoformat()


def load_record(client: str, clip_slug: str, vault: Optional[Path] = None) -> Optional[ClipRecord]:
    vault = vault or default_vault()
    path = vault / "deliveries" / client / f"{clip_slug}.md"
    if not path.exists():
        return None
    text = path.read_text()
    return _parse_record(text, client, clip_slug)


def _parse_record(text: str, client: str, clip_slug: str) -> ClipRecord:
    fm_match = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.DOTALL)
    meta: dict = {}
    body = text
    if fm_match:
        meta = yaml.safe_load(fm_match.group(1)) or {}
        body = fm_match.group(2)

    # Parse state history from body
    history = []
    for line in body.split("\n"):
        m = re.match(r"^-\s+(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2})?)\s+—\s+`([^`]+)`\s+—\s*(.*)$", line.strip())
        if m:
            history.append({
                "timestamp": m.group(1).replace(" ", "T"),
                "state": m.group(2),
                "note": m.group(3).strip(),
            })

    # Free-form notes = anything between "## Notes" and the next "## " heading (or EOF)
    notes_match = re.search(r"##\s+Notes\s*\n(.*?)(?=\n##\s|\Z)", body, re.DOTALL)
    body_notes = notes_match.group(1).strip() if notes_match else ""

    # Parse lessons from "## Issues caught & lessons" section
    lessons = _parse_lessons(body)

    rec = ClipRecord(
        client=client,
        clip_slug=clip_slug,
        current_state=meta.get("current_state", "draft"),
        current_version=int(meta.get("current_version", 1)),
        created=meta.get("created", ""),
        updated=meta.get("updated", ""),
        source_video=meta.get("source_video", ""),
        script_file=meta.get("script_file", ""),
        clip_path=meta.get("clip_path", ""),
        subtitle_file=meta.get("subtitle_file", ""),
        audit_reports=meta.get("audit_reports", []) or [],
        frameio_notes=meta.get("frameio_notes", []) or [],
        feedback_files=meta.get("feedback_files", []) or [],
        history=history,
        body_notes=body_notes,
        clip_type=meta.get("clip_type", "") or "",
        gesture_profile=meta.get("gesture_profile", "") or "",
        caption_style=meta.get("caption_style", "") or "",
        hook_type=meta.get("hook_type", "") or "",
        duration_seconds=float(meta.get("duration_seconds", 0) or 0),
        tags=meta.get("tags", []) or [],
        lessons=lessons,
    )
    return rec


def _parse_lessons(body: str) -> list[dict]:
    """Parse the '## Issues caught & lessons' section into structured records.

    Format expected:
        ### v1 → v2 (2026-05-09T14:32:11)
        - ISSUE: <text>
          WHEN: <text>
          THEN: <text>
    """
    section_match = re.search(
        r"##\s+Issues caught\s*&\s*lessons\s*\n(.*?)(?=\n##\s|\Z)", body, re.DOTALL,
    )
    if not section_match:
        return []
    section = section_match.group(1)

    lessons: list[dict] = []
    current_version = ""
    current_ts = ""
    # Track in-progress lesson while iterating lines
    cur: dict = {}
    for raw_line in section.split("\n"):
        line = raw_line.rstrip()
        h = re.match(r"^###\s+(v\d+\s*(?:→|->)\s*v\d+|v\d+|unversioned)\s*(?:\((.*?)\))?\s*$", line)
        if h:
            # Normalize "->" to "→" but preserve spacing the user wrote
            current_version = h.group(1).replace("->", "→")
            current_ts = (h.group(2) or "").strip()
            continue
        m_issue = re.match(r"^-\s*ISSUE:\s*(.*)$", line)
        if m_issue:
            if cur:
                lessons.append(cur)
            cur = {
                "version": current_version,
                "timestamp": current_ts,
                "issue": m_issue.group(1).strip(),
                "when": "",
                "then": "",
            }
            continue
        m_when = re.match(r"^\s+WHEN:\s*(.*)$", raw_line)
        if m_when and cur:
            cur["when"] = m_when.group(1).strip()
            continue
        m_then = re.match(r"^\s+THEN:\s*(.*)$", raw_line)
        if m_then and cur:
            cur["then"] = m_then.group(1).strip()
            continue
    if cur:
        lessons.append(cur)
    return lessons


def save_record(rec: ClipRecord, vault: Optional[Path] = None) -> None:
    vault = vault or default_vault()
    path = vault / "deliveries" / rec.client / f"{rec.clip_slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)

    rec.updated = _now_iso()
    if not rec.created:
        rec.created = rec.updated

    meta = {
        "client": rec.client,
        "clip_slug": rec.clip_slug,
        "current_state": rec.current_state,
        "current_version": rec.current_version,
        "created": rec.created,
        "updated": rec.updated,
        "source_video": rec.source_video,
        "script_file": rec.script_file,
        "clip_path": rec.clip_path,
        "subtitle_file": rec.subtitle_file,
        "audit_reports": rec.audit_reports,
        "frameio_notes": rec.frameio_notes,
        "feedback_files": rec.feedback_files,
        # Profile (only emitted if set, to keep frontmatter clean for legacy clips)
        **({"clip_type": rec.clip_type} if rec.clip_type else {}),
        **({"gesture_profile": rec.gesture_profile} if rec.gesture_profile else {}),
        **({"caption_style": rec.caption_style} if rec.caption_style else {}),
        **({"hook_type": rec.hook_type} if rec.hook_type else {}),
        **({"duration_seconds": rec.duration_seconds} if rec.duration_seconds else {}),
        **({"tags": rec.tags} if rec.tags else {}),
    }
    fm = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True, default_flow_style=False)

    history_lines = ["## State history", ""]
    for h in rec.history:
        history_lines.append(f"- {h['timestamp']} — `{h['state']}` — {h['note']}")

    artifacts_lines = ["", "## Artifacts", ""]
    for a in rec.audit_reports:
        artifacts_lines.append(f"- [[{Path(a).name}]] — audit report")
    for f in rec.feedback_files:
        artifacts_lines.append(f"- [[{Path(f).name}]] — client feedback")

    # Lessons section — grouped by version pair, preserves insertion order
    lessons_lines: list[str] = []
    if rec.lessons:
        lessons_lines = ["", "## Issues caught & lessons", ""]
        seen_headers: set[str] = set()
        for lesson in rec.lessons:
            ver = lesson.get("version", "") or "unversioned"
            ts = lesson.get("timestamp", "") or ""
            header_key = f"{ver}|{ts}"
            if header_key not in seen_headers:
                header = f"### {ver}" + (f" ({ts})" if ts else "")
                lessons_lines.append(header)
                seen_headers.add(header_key)
            lessons_lines.append(f"- ISSUE: {lesson.get('issue', '')}")
            if lesson.get("when"):
                lessons_lines.append(f"  WHEN: {lesson['when']}")
            if lesson.get("then"):
                lessons_lines.append(f"  THEN: {lesson['then']}")
            lessons_lines.append("")

    body = "\n".join([
        f"# {rec.client} — {rec.clip_slug}",
        "",
        *history_lines,
        *artifacts_lines,
        *lessons_lines,
        "",
        "## Notes",
        "",
        rec.body_notes,
    ])

    path.write_text(f"---\n{fm}---\n{body}\n")


# ─────────────────────────────────────────────────────────────────────────────
# Operations
# ─────────────────────────────────────────────────────────────────────────────

def op_create(args) -> ClipRecord:
    existing = load_record(args.client, args.clip_slug)
    if existing:
        print(f"error: clip {args.client}/{args.clip_slug} already exists (state: {existing.current_state})",
              file=sys.stderr)
        sys.exit(1)

    rec = ClipRecord(
        client=args.client,
        clip_slug=args.clip_slug,
        source_video=str(args.source) if args.source else "",
        clip_path=str(args.clip) if args.clip else "",
        subtitle_file=str(args.subtitles) if args.subtitles else "",
        script_file=str(args.script) if args.script else "",
        clip_type=getattr(args, "clip_type", "") or "",
        gesture_profile=getattr(args, "gesture_profile", "") or "",
        caption_style=getattr(args, "caption_style", "") or "",
        hook_type=getattr(args, "hook_type", "") or "",
        duration_seconds=float(getattr(args, "duration_seconds", 0) or 0),
        tags=list(getattr(args, "tags", []) or []),
    )
    rec.history.append({
        "timestamp": _now_iso(),
        "state": "draft",
        "note": f"created by {args.source or 'manual'}",
    })
    save_record(rec)
    print(f"  ✓ created {rec.client}/{rec.clip_slug} in `draft`")
    return rec


def op_transition(args) -> ClipRecord:
    client = args.client or _guess_client_from_slug(args.clip_slug)
    if not client:
        print(f"error: couldn't find clip-slug {args.clip_slug} — specify --client", file=sys.stderr)
        sys.exit(1)

    rec = load_record(client, args.clip_slug)
    if not rec:
        print(f"error: no clip at {client}/{args.clip_slug}", file=sys.stderr)
        sys.exit(1)

    if args.new_state not in VALID_STATES:
        print(f"error: invalid state '{args.new_state}' (valid: {sorted(VALID_STATES)})", file=sys.stderr)
        sys.exit(1)

    allowed = VALID_TRANSITIONS.get(rec.current_state, set())
    if args.new_state not in allowed and not args.force:
        print(f"error: invalid transition {rec.current_state} → {args.new_state}", file=sys.stderr)
        print(f"       allowed from {rec.current_state}: {sorted(allowed)}", file=sys.stderr)
        print(f"       use --force to override", file=sys.stderr)
        sys.exit(1)

    note = args.note or ""
    if args.artifact:
        # attach artifact
        if "audit" in str(args.artifact).lower():
            rec.audit_reports.append(str(args.artifact))
            if not note:
                note = f"audit report: {Path(args.artifact).name}"
        elif "frameio" in str(args.artifact).lower():
            rec.frameio_notes.append(str(args.artifact))
        elif "feedback" in str(args.artifact).lower():
            rec.feedback_files.append(str(args.artifact))

    # version bump only on specific transitions
    if args.new_state == "patching" and rec.current_state in ("needs-revision", "audited-v1-fail", "audited-v2-fail"):
        # actual bump happens when patching completes successfully
        pass
    if args.new_state in ("audited-v2-pass", "audited-v2-fail") and rec.current_version == 1:
        rec.current_version = 2

    rec.history.append({
        "timestamp": _now_iso(),
        "state": args.new_state,
        "note": note or f"transition from {rec.current_state}",
    })
    rec.current_state = args.new_state

    save_record(rec)
    print(f"  ✓ {rec.client}/{rec.clip_slug} → `{args.new_state}`")
    return rec


def op_feedback(args) -> ClipRecord:
    client = args.client or _guess_client_from_slug(args.clip_slug)
    if not client:
        print(f"error: specify --client", file=sys.stderr)
        sys.exit(1)
    rec = load_record(client, args.clip_slug)
    if not rec:
        print(f"error: no clip at {client}/{args.clip_slug}", file=sys.stderr)
        sys.exit(1)

    # Gather feedback text
    text = args.text or ""
    if args.file:
        text = Path(args.file).read_text() + "\n" + text

    if not text.strip():
        print("error: no feedback text provided (--text or --file)", file=sys.stderr)
        sys.exit(1)

    # Write feedback to a file next to the record
    feedback_dir = rec.file_path.parent / "feedback"
    feedback_dir.mkdir(exist_ok=True)
    feedback_path = feedback_dir / f"{rec.clip_slug}-v{rec.current_version}.txt"
    feedback_path.write_text(text)
    rec.feedback_files.append(str(feedback_path))

    # Auto-transition to needs-revision
    rec.history.append({
        "timestamp": _now_iso(),
        "state": "needs-revision",
        "note": f"feedback received ({len(text)} chars) — see {feedback_path.name}",
    })
    rec.current_state = "needs-revision"
    save_record(rec)
    print(f"  ✓ feedback attached; {rec.client}/{rec.clip_slug} → `needs-revision`")
    print(f"    feedback: {feedback_path}")
    return rec


def op_profile(args) -> ClipRecord:
    """Set or update the retrieval-profile fields on a clip."""
    client = args.client or _guess_client_from_slug(args.clip_slug)
    if not client:
        print(f"error: specify --client", file=sys.stderr)
        sys.exit(1)
    rec = load_record(client, args.clip_slug)
    if not rec:
        print(f"error: no clip at {client}/{args.clip_slug}", file=sys.stderr)
        sys.exit(1)

    changed: list[str] = []
    if args.clip_type is not None:
        rec.clip_type = args.clip_type
        changed.append(f"clip_type={args.clip_type}")
    if args.gesture_profile is not None:
        rec.gesture_profile = args.gesture_profile
        changed.append(f"gesture_profile={args.gesture_profile}")
    if args.caption_style is not None:
        rec.caption_style = args.caption_style
        changed.append(f"caption_style={args.caption_style}")
    if args.hook_type is not None:
        rec.hook_type = args.hook_type
        changed.append(f"hook_type={args.hook_type}")
    if args.duration_seconds is not None:
        rec.duration_seconds = float(args.duration_seconds)
        changed.append(f"duration_seconds={args.duration_seconds}")
    if args.tags:
        # tags is additive — pass --tags to add, --replace-tags to overwrite
        if args.replace_tags:
            rec.tags = list(args.tags)
        else:
            existing = set(rec.tags)
            for t in args.tags:
                if t not in existing:
                    rec.tags.append(t)
                    existing.add(t)
        changed.append(f"tags={rec.tags}")

    if not changed:
        print("(no profile fields changed)")
        return rec

    save_record(rec)
    print(f"  ✓ {rec.client}/{rec.clip_slug} profile updated: {', '.join(changed)}")
    return rec


def op_lesson(args) -> ClipRecord:
    """Append a structured lesson to a clip's case file.

    A lesson has three parts:
        ISSUE — what went wrong in this version
        WHEN  — the condition under which the lesson applies (for retrieval)
        THEN  — the corrective action / setting
    """
    client = args.client or _guess_client_from_slug(args.clip_slug)
    if not client:
        print(f"error: specify --client", file=sys.stderr)
        sys.exit(1)
    rec = load_record(client, args.clip_slug)
    if not rec:
        print(f"error: no clip at {client}/{args.clip_slug}", file=sys.stderr)
        sys.exit(1)

    if not args.issue:
        print("error: --issue required", file=sys.stderr)
        sys.exit(1)
    if not args.then:
        print("error: --then required (the corrective action)", file=sys.stderr)
        sys.exit(1)

    # Default version label = "v{N-1} → v{N}"; user can override with --version
    version = args.version
    if not version:
        n = rec.current_version
        version = f"v{max(1, n - 1)} → v{n}" if n >= 2 else f"v{n}"

    lesson = {
        "version": version,
        "timestamp": _now_iso(),
        "issue": args.issue.strip(),
        "when": (args.when or "").strip(),
        "then": args.then.strip(),
    }
    rec.lessons.append(lesson)
    save_record(rec)
    print(f"  ✓ lesson recorded for {rec.client}/{rec.clip_slug} ({version})")
    print(f"    ISSUE: {lesson['issue']}")
    if lesson["when"]:
        print(f"    WHEN:  {lesson['when']}")
    print(f"    THEN:  {lesson['then']}")
    return rec


def op_export_lessons(args):
    """Emit JSON of lessons across all clips, with profile fields, for find-precedents.

    Output schema (one object per clip):
        {client, clip_slug, current_state, current_version,
         clip_type, gesture_profile, caption_style, hook_type,
         duration_seconds, duration_band, tags, source_video,
         lessons: [{version, timestamp, issue, when, then}, ...]}
    """
    vault = default_vault()
    deliveries = vault / "deliveries"
    if not deliveries.exists():
        print("[]")
        return

    out: list[dict] = []
    for client_dir in sorted(deliveries.iterdir()):
        if not client_dir.is_dir():
            continue
        if args.client and client_dir.name != args.client:
            continue
        for md_file in sorted(client_dir.glob("*.md")):
            rec = _parse_record(md_file.read_text(), client_dir.name, md_file.stem)
            if args.with_lessons_only and not rec.lessons:
                continue
            out.append({
                "client": rec.client,
                "clip_slug": rec.clip_slug,
                "current_state": rec.current_state,
                "current_version": rec.current_version,
                "clip_type": rec.clip_type,
                "gesture_profile": rec.gesture_profile,
                "caption_style": rec.caption_style,
                "hook_type": rec.hook_type,
                "duration_seconds": rec.duration_seconds,
                "duration_band": rec.duration_band,
                "tags": rec.tags,
                "source_video": rec.source_video,
                "clip_path": rec.clip_path,
                "lessons": rec.lessons,
            })
    print(json.dumps(out, indent=2, ensure_ascii=False))


def op_memory(args):
    """Thin compatibility bridge to the append-only stage evidence store."""
    evidence = Path(__file__).with_name("evidence.py")
    cmd = [sys.executable, str(evidence)]
    if args.db:
        cmd += ["--db", str(args.db)]
    if args.ledger:
        cmd += ["--ledger", str(args.ledger)]
    cmd.append(args.memory_command)
    if args.memory_command == "append":
        cmd += ["--record", str(args.record)]
    elif args.memory_command == "import-markdown":
        cmd += [str(p) for p in args.roots]
        cmd += ["--glob", args.glob, "--case-regex", args.case_regex]
    result = subprocess.run(cmd)
    if result.returncode:
        raise SystemExit(result.returncode)


def op_status(args):
    client = args.client or _guess_client_from_slug(args.clip_slug)
    if not client:
        print(f"error: specify --client", file=sys.stderr)
        sys.exit(1)
    rec = load_record(client, args.clip_slug)
    if not rec:
        print(f"error: no clip at {client}/{args.clip_slug}", file=sys.stderr)
        sys.exit(1)

    print(f"Clip: {rec.client}/{rec.clip_slug}")
    print(f"  State:   {rec.current_state}")
    print(f"  Version: v{rec.current_version}")
    print(f"  Created: {rec.created}")
    print(f"  Updated: {rec.updated}")
    if rec.clip_path:
        print(f"  Clip:    {rec.clip_path}")
    if rec.source_video:
        print(f"  Source:  {rec.source_video}")
    print(f"\nHistory:")
    for h in rec.history:
        print(f"  {h['timestamp']} — {h['state']:<24s}  {h['note']}")


def op_list(args):
    vault = default_vault()
    deliveries = vault / "deliveries"
    if not deliveries.exists():
        print("(no deliveries tracked yet)")
        return

    records: list[ClipRecord] = []
    for client_dir in sorted(deliveries.iterdir()):
        if not client_dir.is_dir():
            continue
        if args.client and client_dir.name != args.client:
            continue
        for md_file in sorted(client_dir.glob("*.md")):
            rec = _parse_record(md_file.read_text(), client_dir.name, md_file.stem)
            records.append(rec)

    if args.pending_my_eye:
        records = [r for r in records if r.current_state in PENDING_MY_EYE]
    elif args.state:
        records = [r for r in records if r.current_state == args.state]

    if not records:
        print("(no matching clips)")
        return

    # Sort by urgency: state order + recency
    state_order = {s: i for i, s in enumerate([
        "audited-v1-fail", "needs-revision", "audited-v2-fail",
        "approved", "scheduled", "draft", "patching",
        "audited-v1-pass", "audited-v2-pass", "with-client",
        "posted", "archived",
    ])}
    records.sort(key=lambda r: (state_order.get(r.current_state, 99), r.updated), reverse=False)

    for r in records:
        age = _age(r.updated)
        stale = _is_stale(r.current_state, r.updated)
        stale_mark = " ⚠️ stale" if stale else ""
        print(f"  [{r.current_state:<22s}] v{r.current_version}  {r.client}/{r.clip_slug:<40s}  {age}{stale_mark}")


def op_dashboard(args):
    vault = default_vault()
    deliveries = vault / "deliveries"
    if not deliveries.exists():
        print("(no deliveries tracked yet — run shortify or tracker.py create to start)")
        return

    records: list[ClipRecord] = []
    for client_dir in sorted(deliveries.iterdir()):
        if not client_dir.is_dir():
            continue
        for md_file in sorted(client_dir.glob("*.md")):
            rec = _parse_record(md_file.read_text(), client_dir.name, md_file.stem)
            records.append(rec)

    today = dt.date.today().isoformat()
    print(f"📋 Clip Review Dashboard — {today}\n")

    pending = [r for r in records if r.current_state in PENDING_MY_EYE]
    waiting_client = [r for r in records if r.current_state == "with-client"]
    scheduled = [r for r in records if r.current_state == "scheduled"]
    done_today = [r for r in records if r.current_state in ("approved", "posted") and r.updated.startswith(today)]

    if pending:
        print("⚠️  PENDING YOUR EYE (act now):")
        for r in pending:
            age = _age(r.updated)
            extra = _extra_for_state(r)
            print(f"  • {r.client}/{r.clip_slug:<40s}  {r.current_state} {extra}  ({age})")
    else:
        print("✅ nothing pending — inbox zero")

    print()
    if waiting_client:
        print("⏳ WAITING ON CLIENT:")
        for r in waiting_client:
            age = _age(r.updated)
            stale_mark = " ⚠️ STALE — follow up" if _is_stale(r.current_state, r.updated) else ""
            print(f"  • {r.client}/{r.clip_slug:<40s}  ({age}){stale_mark}")
        print()

    if scheduled:
        print("📤 SCHEDULED TO POST:")
        for r in scheduled:
            age = _age(r.updated)
            print(f"  • {r.client}/{r.clip_slug:<40s}  ({age})")
        print()

    if done_today:
        print("✅ DONE TODAY:")
        for r in done_today:
            print(f"  • {r.client}/{r.clip_slug:<40s}  {r.current_state}")
        print()

    # Weekly stats
    week_ago = (dt.date.today() - dt.timedelta(days=7)).isoformat()
    week = [r for r in records if r.updated >= week_ago]
    by_state: dict[str, int] = {}
    for r in week:
        by_state[r.current_state] = by_state.get(r.current_state, 0) + 1
    if by_state:
        parts = [f"{v} {k}" for k, v in sorted(by_state.items(), key=lambda x: -x[1])]
        print(f"📊 Last 7 days: {', '.join(parts)}")


def op_summary(args):
    vault = default_vault()
    deliveries = vault / "deliveries"
    client_dirs = [deliveries / args.client] if args.client else [d for d in deliveries.iterdir() if d.is_dir()]
    month = args.month

    for client_dir in client_dirs:
        if not client_dir.exists():
            continue
        print(f"\n=== {client_dir.name}{f' — {month}' if month else ''} ===")
        records = []
        for md_file in sorted(client_dir.glob("*.md")):
            rec = _parse_record(md_file.read_text(), client_dir.name, md_file.stem)
            if month and not rec.created.startswith(month):
                continue
            records.append(rec)

        if not records:
            print("  (no clips)")
            continue

        by_state: dict[str, int] = {}
        for r in records:
            by_state[r.current_state] = by_state.get(r.current_state, 0) + 1
        print(f"  Total: {len(records)}")
        for k, v in sorted(by_state.items(), key=lambda x: -x[1]):
            print(f"    {k:<22s} {v}")


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _guess_client_from_slug(clip_slug: str) -> Optional[str]:
    """Look across all clients for a clip with this slug."""
    vault = default_vault()
    deliveries = vault / "deliveries"
    if not deliveries.exists():
        return None
    matches = []
    for client_dir in deliveries.iterdir():
        if not client_dir.is_dir():
            continue
        if (client_dir / f"{clip_slug}.md").exists():
            matches.append(client_dir.name)
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        print(f"warning: clip-slug {clip_slug} exists in multiple clients: {matches}", file=sys.stderr)
        return None
    return None


def _age(iso_ts: str) -> str:
    try:
        t = dt.datetime.fromisoformat(iso_ts)
        delta = dt.datetime.now() - t
        if delta.days > 0:
            return f"{delta.days}d ago"
        hours = delta.seconds // 3600
        if hours > 0:
            return f"{hours}h ago"
        minutes = (delta.seconds % 3600) // 60
        return f"{minutes}m ago"
    except (ValueError, TypeError):
        return "?"


def _is_stale(state: str, updated: str) -> bool:
    threshold = STALENESS_RULES.get(state)
    if threshold is None:
        return False
    try:
        t = dt.datetime.fromisoformat(updated)
        return (dt.datetime.now() - t).days >= threshold
    except (ValueError, TypeError):
        return False


def _extra_for_state(rec: ClipRecord) -> str:
    if rec.current_state == "needs-revision" and rec.feedback_files:
        return f"(v{rec.current_version}, feedback)"
    if rec.current_state == "audited-v1-fail" and rec.audit_reports:
        return f"(v{rec.current_version}, see audit)"
    if rec.current_state == "approved":
        return "(ready to schedule)"
    return ""


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Clip Review Tracker CLI")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_create = sub.add_parser("create", help="Register a new clip in `draft` state")
    p_create.add_argument("--client", required=True)
    p_create.add_argument("--clip-slug", required=True)
    p_create.add_argument("--source", type=Path)
    p_create.add_argument("--clip", type=Path)
    p_create.add_argument("--subtitles", type=Path)
    p_create.add_argument("--script", type=Path)
    # Optional profile fields at creation time — feeds find-precedents retrieval
    p_create.add_argument("--clip-type", help="q&a | monologue | story | list | comparison | reveal")
    p_create.add_argument("--gesture-profile", help="speaker_hand_enters_upper_frame | head_only | podium_static | full_body")
    p_create.add_argument("--caption-style", help="pro | ugc | cinematic | big-word | hormozi | liquid-glass")
    p_create.add_argument("--hook-type", help="revenue-first | named-framework | question | story-cold-open | contrarian")
    p_create.add_argument("--duration-seconds", type=float)
    p_create.add_argument("--tags", nargs="*", default=[], help="free-form match keys (space-separated)")

    p_trans = sub.add_parser("transition", help="Move a clip to a new state")
    p_trans.add_argument("clip_slug")
    p_trans.add_argument("new_state", choices=sorted(VALID_STATES))
    p_trans.add_argument("--client")
    p_trans.add_argument("--artifact", type=Path, help="attach an artifact (audit.md, frameio.txt, feedback.txt)")
    p_trans.add_argument("--note")
    p_trans.add_argument("--force", action="store_true", help="allow invalid transitions")

    p_fb = sub.add_parser("feedback", help="Attach client feedback (auto-transitions to needs-revision)")
    p_fb.add_argument("clip_slug")
    p_fb.add_argument("--client")
    p_fb.add_argument("--text")
    p_fb.add_argument("--file", type=Path)

    p_st = sub.add_parser("status", help="Show the state + history of one clip")
    p_st.add_argument("clip_slug")
    p_st.add_argument("--client")

    p_ls = sub.add_parser("list", help="List clips by filter")
    p_ls.add_argument("--state", choices=sorted(VALID_STATES))
    p_ls.add_argument("--client")
    p_ls.add_argument("--pending-my-eye", action="store_true")

    p_dash = sub.add_parser("dashboard", help="Daily dashboard — what needs my eye, what's stale, week stats")
    p_dash.add_argument("--vault", type=Path)

    p_sum = sub.add_parser("summary", help="Per-client summary, optionally filtered to a month")
    p_sum.add_argument("--client")
    p_sum.add_argument("--month")

    p_prof = sub.add_parser("profile", help="Set retrieval-profile fields on a clip (clip_type, gesture, caption_style, hook, tags)")
    p_prof.add_argument("clip_slug")
    p_prof.add_argument("--client")
    p_prof.add_argument("--clip-type")
    p_prof.add_argument("--gesture-profile")
    p_prof.add_argument("--caption-style")
    p_prof.add_argument("--hook-type")
    p_prof.add_argument("--duration-seconds", type=float)
    p_prof.add_argument("--tags", nargs="*", default=[])
    p_prof.add_argument("--replace-tags", action="store_true", help="overwrite tags instead of appending")

    p_les = sub.add_parser("lesson", help="Append a structured lesson (issue/when/then) to a clip's case file")
    p_les.add_argument("clip_slug")
    p_les.add_argument("--client")
    p_les.add_argument("--issue", required=True, help="What went wrong in this version")
    p_les.add_argument("--when", help="Condition under which the lesson applies (used for retrieval matching)")
    p_les.add_argument("--then", required=True, help="Corrective action / setting to apply next time")
    p_les.add_argument("--version", help="Version label (e.g., 'v1 → v2'); defaults to current_version")

    p_exp = sub.add_parser("export-lessons", help="Emit JSON of all lessons + profiles (consumed by find-precedents)")
    p_exp.add_argument("--client")
    p_exp.add_argument("--with-lessons-only", action="store_true", help="skip clips that have no lessons recorded")

    p_mem = sub.add_parser("memory", help="append/index stage-specific editing evidence")
    p_mem.add_argument("memory_command", choices=("init", "append", "import-markdown", "stats"))
    p_mem.add_argument("roots", nargs="*", type=Path)
    p_mem.add_argument("--db", type=Path)
    p_mem.add_argument("--ledger", type=Path)
    p_mem.add_argument("--record", type=Path)
    p_mem.add_argument("--glob", default="*.md")
    p_mem.add_argument("--case-regex", default=r"(?:^|/)(\d{4})(?:/|_)")

    args = ap.parse_args()

    if args.cmd == "create":
        op_create(args)
    elif args.cmd == "transition":
        op_transition(args)
    elif args.cmd == "feedback":
        op_feedback(args)
    elif args.cmd == "status":
        op_status(args)
    elif args.cmd == "list":
        op_list(args)
    elif args.cmd == "dashboard":
        op_dashboard(args)
    elif args.cmd == "summary":
        op_summary(args)
    elif args.cmd == "profile":
        op_profile(args)
    elif args.cmd == "lesson":
        op_lesson(args)
    elif args.cmd == "export-lessons":
        op_export_lessons(args)
    elif args.cmd == "memory":
        if args.memory_command == "append" and not args.record:
            ap.error("tracker.py memory append requires --record")
        if args.memory_command == "import-markdown" and not args.roots:
            ap.error("tracker.py memory import-markdown requires one or more roots")
        op_memory(args)


if __name__ == "__main__":
    main()
