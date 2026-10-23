#!/usr/bin/env python3
"""
find-precedents — surface relevant past-clip lessons before editing a new clip.

Reads the case library (via `tracker.py export-lessons`), scores each case
against the new clip's profile, and prints the top-N matches' lesson sections
in a context-ready briefing.

Scoring is a simple weighted-overlap model:
    +5  same brand
    +3  same clip_type
    +3  same gesture_profile
    +2  same caption_style
    +2  same hook_type
    +1  same duration_band
    +1  per shared tag
    +N  per token overlap with --topic (the user's free-text description, capped)

A case earns NO score and is skipped if it has zero lessons. The output groups
cases by score so you read the strongest precedents first.

CLI:
    find_precedents.py \
        --client alex --clip-type q&a \
        --gesture-profile speaker_hand_enters_upper_frame \
        --caption-style pro --hook-type revenue-first \
        --duration-seconds 47 \
        --tags pricing-topic hand-gesture-active \
        --topic "alex pricing rant with hand gestures" \
        [--top 5] [--min-score 3] [--vault PATH] [--json]

Exits non-zero only on real errors. Empty result is fine — first clip on a
profile won't have precedents yet.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

TRACKER = Path("__ACQ_SKILLS__") / "clip-review-tracker" / "scripts" / "tracker.py"
EVIDENCE = Path("__ACQ_SKILLS__") / "clip-review-tracker" / "scripts" / "evidence.py"


def load_stage_memory(q: argparse.Namespace) -> dict:
    """Query the append-only evidence index for one editing stage."""
    cmd = [
        "python3", str(EVIDENCE), "--db", str(q.memory_db), "query",
        "--stage", q.stage, "--query", q.topic or " ".join(q.tags or []) or q.clip_type or q.stage,
        "--top", str(q.top), "--min-confidence", str(q.min_confidence), "--json",
    ]
    if q.case_id:
        cmd += ["--case-id", q.case_id]
    for case_id in q.exclude_case:
        cmd += ["--exclude-case", case_id]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode:
        print(f"error: stage memory query failed:\n{result.stderr}", file=sys.stderr)
        raise SystemExit(2)
    return json.loads(result.stdout)


def render_stage_memory(payload: dict) -> str:
    out = [
        f"# Advisory precedents — {payload['stage']}", "",
        "These are captioned-final-certified analogies, not commands. Preserve source meaning, inspect exceptions, and cite the case before changing a decision.", "",
    ]
    if payload.get("excluded_cases"):
        out.append("**Held out from retrieval:** " + ", ".join(payload["excluded_cases"]))
        out.append("")
    for i, item in enumerate(payload.get("results", []), 1):
        out += [
            f"## {i}. Case {item['case_id']} — {item['classification']} (score={item['score']:.3f}, confidence={item['confidence']:.2f})",
            f"- **Situation:** {item['situation']}",
            f"- **Chosen action:** {item['chosen_action']}",
            f"- **Why:** {item['reasoning']}",
        ]
        if item.get("exceptions"):
            out.append("- **Exceptions:** " + "; ".join(item["exceptions"]))
        out.append("- **Evidence:**")
        for ev in item.get("evidence_paths", []):
            locator = f" ({ev['locator']})" if ev.get("locator") else ""
            out.append(f"  - `{ev['path']}`{locator}")
        out.append(f"- **Decision ID:** `{item['id']}`")
        proof = item.get("final_eligibility", {}).get("proof", {})
        asset = proof.get("final_asset_path") or proof.get("final_timeline_path")
        if asset:
            out.append(f"- **Final proof:** `{asset}` ({proof.get('proof_type')})")
        out.append("")
    if not payload.get("results"):
        out.append("No eligible precedent matched. Make the decision from source evidence and record the result; do not relax the holdout.")
    out += ["", f"Retrieval receipt: `{payload['retrieval_event_id']}`"]
    return "\n".join(out)


def load_cases(vault_override: str | None = None) -> list[dict]:
    env = os.environ.copy()
    if vault_override:
        env["CONTENT_VAULT"] = vault_override
    try:
        result = subprocess.run(
            ["python3", str(TRACKER), "export-lessons", "--with-lessons-only"],
            capture_output=True, text=True, env=env, check=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"error: tracker.py export-lessons failed:\n{e.stderr}", file=sys.stderr)
        sys.exit(2)
    try:
        return json.loads(result.stdout or "[]")
    except json.JSONDecodeError as e:
        print(f"error: tracker.py output not valid JSON: {e}", file=sys.stderr)
        sys.exit(2)


def duration_band(seconds: float) -> str:
    if seconds <= 0: return ""
    if seconds < 30: return "under-30"
    if seconds < 60: return "30-60"
    if seconds < 120: return "60-120"
    return "over-120"


_TOKEN_RE = re.compile(r"[a-z0-9$]+")


def tokens(text: str) -> set[str]:
    """Lowercase token set, dropping stop-ish words. Used for free-text topic match."""
    if not text:
        return set()
    raw = _TOKEN_RE.findall(text.lower())
    stop = {"the", "a", "an", "and", "or", "of", "to", "for", "with", "in", "on", "at", "is", "it", "this", "that"}
    return {t for t in raw if t not in stop and len(t) > 1}


def score_case(case: dict, q: argparse.Namespace) -> tuple[int, list[str]]:
    """Return (score, breakdown) for a case against the query profile."""
    score = 0
    why: list[str] = []

    if q.client and case.get("client") == q.client:
        score += 5
        why.append(f"+5 client={q.client}")
    if q.clip_type and case.get("clip_type") == q.clip_type:
        score += 3
        why.append(f"+3 clip_type={q.clip_type}")
    if q.gesture_profile and case.get("gesture_profile") == q.gesture_profile:
        score += 3
        why.append(f"+3 gesture_profile={q.gesture_profile}")
    if q.caption_style and case.get("caption_style") == q.caption_style:
        score += 2
        why.append(f"+2 caption_style={q.caption_style}")
    if q.hook_type and case.get("hook_type") == q.hook_type:
        score += 2
        why.append(f"+2 hook_type={q.hook_type}")

    qband = duration_band(q.duration_seconds or 0)
    if qband and case.get("duration_band") == qband:
        score += 1
        why.append(f"+1 duration_band={qband}")

    case_tags = set(case.get("tags") or [])
    q_tags = set(q.tags or [])
    shared = case_tags & q_tags
    if shared:
        score += len(shared)
        why.append(f"+{len(shared)} tags={sorted(shared)}")

    if q.topic:
        qtok = tokens(q.topic)
        # Match topic tokens against case slug, tags, and lesson WHEN/ISSUE strings
        haystack_parts = [
            case.get("clip_slug", ""),
            " ".join(case.get("tags") or []),
        ]
        for lesson in case.get("lessons") or []:
            haystack_parts.append(lesson.get("when", ""))
            haystack_parts.append(lesson.get("issue", ""))
        ctok = tokens(" ".join(haystack_parts))
        overlap = qtok & ctok
        if overlap:
            bonus = min(len(overlap), 4)  # cap free-text contribution
            score += bonus
            why.append(f"+{bonus} topic-overlap={sorted(overlap)[:4]}")

    return score, why


def render_briefing(matches: list[tuple[int, list[str], dict]], top: int) -> str:
    """Render the top-N matches as a concise context-ready markdown briefing."""
    if not matches:
        return ""
    out: list[str] = ["# Precedents — past clips with lessons that match this profile", ""]
    for rank, (score, why, case) in enumerate(matches[:top], start=1):
        out.append(
            f"## {rank}. {case['client']} / {case['clip_slug']}  "
            f"(score={score}, v{case.get('current_version', 1)}, state={case.get('current_state', '?')})"
        )
        profile_bits = []
        for k in ("clip_type", "gesture_profile", "caption_style", "hook_type"):
            v = case.get(k) or ""
            if v: profile_bits.append(f"{k}={v}")
        if case.get("duration_band"): profile_bits.append(f"duration={case['duration_band']}")
        if case.get("tags"): profile_bits.append(f"tags={case['tags']}")
        out.append("  - **profile:** " + ", ".join(profile_bits) if profile_bits else "  - profile: (none)")
        out.append("  - **why matched:** " + "; ".join(why))
        out.append("")
        out.append("  **Lessons:**")
        for lesson in case.get("lessons") or []:
            issue = lesson.get("issue", "")
            when = lesson.get("when", "")
            then = lesson.get("then", "")
            ver = lesson.get("version", "")
            out.append(f"  - [{ver}] **ISSUE:** {issue}")
            if when:
                out.append(f"    **WHEN:** {when}")
            out.append(f"    **THEN:** {then}")
        out.append("")
    out.append("---")
    out.append(
        "_Apply these lessons proactively. If you correct a recurring issue not listed here, "
        "call `tracker.py lesson` to capture it for the next clip._"
    )
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description="Surface relevant past-clip lessons for a new clip.")
    ap.add_argument("--client", help="brand slug, e.g., alex, leila")
    ap.add_argument("--clip-type", help="q&a | monologue | story | list | comparison | reveal")
    ap.add_argument("--gesture-profile")
    ap.add_argument("--caption-style")
    ap.add_argument("--hook-type")
    ap.add_argument("--duration-seconds", type=float, default=0)
    ap.add_argument("--tags", nargs="*", default=[])
    ap.add_argument("--topic", help="free-text description of the new clip's content")
    ap.add_argument("--top", type=int, default=5, help="top-N matches to surface")
    ap.add_argument("--min-score", type=int, default=3, help="skip matches below this score")
    ap.add_argument("--vault", help="override vault path (else CONTENT_VAULT or default)")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of markdown briefing")
    ap.add_argument("--stage", choices=("assembly", "cuts", "boundaries", "camera_reformatting", "captions", "audio", "qa"), help="retrieve only evidence owned by this editing stage")
    ap.add_argument("--memory-db", type=Path, help="central SQLite evidence index (required with --stage)")
    ap.add_argument("--case-id", help="current case id, stored on the retrieval receipt")
    ap.add_argument("--exclude-case", action="append", default=[], help="case id hidden from this retrieval; repeatable")
    ap.add_argument("--min-confidence", type=float, default=.35, help="minimum evidence confidence for stage memory")
    args = ap.parse_args()

    if args.stage:
        if not args.memory_db:
            ap.error("--memory-db is required with --stage")
        payload = load_stage_memory(args)
        print(json.dumps(payload, indent=2, ensure_ascii=False) if args.json else render_stage_memory(payload))
        return

    cases = load_cases(args.vault)
    scored: list[tuple[int, list[str], dict]] = []
    for case in cases:
        score, why = score_case(case, args)
        if score >= args.min_score:
            scored.append((score, why, case))
    scored.sort(key=lambda t: -t[0])

    if args.json:
        out = [
            {"score": s, "why": w, "case": c}
            for s, w, c in scored[: args.top]
        ]
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return

    if not scored:
        print(f"# Precedents — no matches\n\nNo past clips matched this profile (min_score={args.min_score}). "
              f"Either this is a new content type for this brand, or the case library hasn't built up lessons "
              f"on this profile yet. Proceed with editing, and capture corrections via `tracker.py lesson` "
              f"so the next similar clip benefits.")
        return

    print(render_briefing(scored, args.top))


if __name__ == "__main__":
    main()
