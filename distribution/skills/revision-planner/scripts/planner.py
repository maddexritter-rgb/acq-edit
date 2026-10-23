#!/usr/bin/env python3
"""
Revision Planner — solo-operator clip revision engine.

Takes a clip in `needs-revision` state, parses ACQ feedback, classifies issues,
auto-patches the safe ones with ffmpeg, re-runs mozi-sf-audit, updates the tracker.

Usage:
    planner.py --clip-slug <slug> [--client <slug>] [--mode safe|plan-only|aggressive]
               [--text "feedback"] [--file feedback.txt]
    planner.py run-all-pending [--mode safe]
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

try:
    import yaml
except ImportError:
    print("error: pyyaml not installed. Run: pip3 install --user pyyaml", file=sys.stderr)
    sys.exit(1)


# Import tracker helpers
sys.path.insert(0, str(Path("__ACQ_SKILLS__") / "clip-review-tracker" / "scripts"))
try:
    import tracker as trk  # type: ignore
except ImportError:
    trk = None


# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────

AUDIT_SCRIPT = Path("__ACQ_SKILLS__") / "mozi-sf-audit" / "scripts" / "audit.py"
CATEGORIES = ["subtitle-text", "subtitle-timing", "subtitle-style",
              "audio-levels", "video-timing", "video-content"]
AUTO_PATCHABLE = {"subtitle-text", "subtitle-timing", "subtitle-style",
                  "audio-levels", "video-timing"}


# ─────────────────────────────────────────────────────────────────────────────
# Data model
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Issue:
    raw_text: str
    category: str
    confidence: float
    timestamp_sec: Optional[float] = None
    target_word: Optional[str] = None
    target_value: Optional[str] = None
    auto_patchable: bool = False
    patch_action: str = ""       # e.g. "lowercase", "trim_black_end", "normalize_peak"
    patch_result: str = "pending"  # "applied", "failed", "skipped", "edit-brief"


# ─────────────────────────────────────────────────────────────────────────────
# Utilities
# ─────────────────────────────────────────────────────────────────────────────

def sh(cmd: list[str], capture: bool = True) -> tuple[int, str, str]:
    try:
        p = subprocess.run(cmd, capture_output=capture, text=True, timeout=600)
        return p.returncode, p.stdout or "", p.stderr or ""
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"
    except FileNotFoundError:
        return 127, "", f"not found: {cmd[0]}"


def parse_timestamp(text: str) -> Optional[float]:
    """Extract a timestamp from free-form text. Handles m:ss, m:ss.ss, h:mm:ss, '0:08', 'at 8 seconds', '40-second mark'."""
    # [m:ss] or [m:ss.ss]
    m = re.search(r"\[?(\d{1,2}):(\d{2}(?:\.\d+)?)\]?", text)
    if m:
        return int(m.group(1)) * 60 + float(m.group(2))
    # "at 8 seconds" / "at 40s"
    m = re.search(r"(?:at|around)\s+(\d+(?:\.\d+)?)\s*(?:s|sec|second|seconds)", text, re.IGNORECASE)
    if m:
        return float(m.group(1))
    # "X-second mark"
    m = re.search(r"(\d+)[-\s]?second\s+mark", text, re.IGNORECASE)
    if m:
        return float(m.group(1))
    return None


def classify_issue(text: str) -> tuple[str, float]:
    """Return (category, confidence 0-1)."""
    t = text.lower()

    # Keyword signals per category
    signals = {
        "subtitle-text": [
            ("typo", 0.95), ("misspelled", 0.95), ("wrong word", 0.9),
            ("lowercase", 0.95), ("uppercase", 0.9), ("capital", 0.85),
            ("missing word", 0.95), ("double word", 0.95), ("doubled", 0.85),
            ("should be", 0.6), ("change", 0.3), ("fix", 0.3),
            ("caption", 0.7), ("subtitle", 0.7), ("text", 0.5),
        ],
        "subtitle-timing": [
            ("subtitle gap", 0.95), ("caption gap", 0.95), ("gap in", 0.7),
            ("caption timing", 0.9), ("subtitle too fast", 0.9),
            ("stays too long", 0.85), ("flash", 0.4),
        ],
        "subtitle-style": [
            ("caption color", 0.95), ("subtitle color", 0.95), ("change color", 0.8),
            ("font", 0.7), ("below face", 0.85), ("above face", 0.85),
            ("bigger", 0.5), ("smaller", 0.5),
        ],
        "audio-levels": [
            ("too quiet", 0.95), ("too loud", 0.95), ("quiet", 0.75),
            ("clipping", 0.95), ("compressed", 0.8), ("pumping", 0.9),
            ("volume", 0.8), ("normalize", 0.9), ("audio", 0.4),
            ("level", 0.6), ("hot", 0.4),
        ],
        "video-timing": [
            ("black frame", 0.95), ("black flash", 0.9), ("dead frame", 0.95),
            ("trim", 0.7), ("cut off", 0.5),
            ("add lead", 0.9), ("3 frame", 0.8), ("too short start", 0.7),
            ("ends abruptly", 0.7), ("fade", 0.5),
        ],
        "video-content": [
            ("wrong hook", 0.95), ("change the hook", 0.95), ("different hook", 0.9),
            ("re-cut", 0.95), ("recut", 0.9), ("wrong take", 0.95),
            ("different take", 0.9), ("use a different", 0.7),
            ("doesn't make sense", 0.6), ("whole clip", 0.6),
        ],
    }

    scores: dict[str, float] = {c: 0.0 for c in CATEGORIES}
    for cat, sigs in signals.items():
        for kw, weight in sigs:
            if kw in t:
                scores[cat] = max(scores[cat], weight)

    best_cat = max(scores, key=scores.get)
    best_score = scores[best_cat]

    if best_score < 0.3:
        # No strong signal — default to video-content (forces manual review)
        return "video-content", 0.3

    return best_cat, best_score


def parse_feedback(text: str) -> list[Issue]:
    """Split feedback into discrete issues, classify each."""
    # Split on double-newline OR structured prefixes
    blocks = []
    # Try structured first: lines starting with [timestamp]
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    current = ""
    for line in lines:
        # New issue starts if line begins with [timestamp] or ## or numbered "1." or similar
        if re.match(r"^(\[?\d{1,2}:\d{2}|\d+\.|#|•|-)\s", line):
            if current:
                blocks.append(current.strip())
            current = line
        else:
            current += " " + line
    if current:
        blocks.append(current.strip())

    # If no structured blocks found, try splitting on conjunctions
    if len(blocks) <= 1:
        blocks = []
        # Split on ", also " / "and also" / period/question/exclamation-space / "Also"-at-word-boundary
        split_re = re.compile(
            r"(?:[,.?!]\s+(?:also|and also|plus|and|but|oh and|also,?)\s+"
            r"|[.?!]\s+(?=[A-Z])"
            r"|\s+(?:also|plus),?\s+(?=there|the|it|i\b|at\b)"
            r")",
            re.IGNORECASE,
        )
        for chunk in split_re.split(text):
            chunk = chunk.strip(" ,.")
            if chunk:
                blocks.append(chunk)

    issues: list[Issue] = []
    for b in blocks:
        if len(b) < 4:
            continue
        cat, conf = classify_issue(b)
        ts = parse_timestamp(b)
        issues.append(Issue(
            raw_text=b,
            category=cat,
            confidence=conf,
            timestamp_sec=ts,
            auto_patchable=cat in AUTO_PATCHABLE and conf >= 0.7,
        ))
    return issues


# ─────────────────────────────────────────────────────────────────────────────
# Patch recipes
# ─────────────────────────────────────────────────────────────────────────────

def patch_subtitle_lowercase(ass_path: Path, word: str, approx_time: Optional[float],
                              out_path: Path) -> bool:
    """Find lines containing `word` (uppercase), replace with lowercase, restricted to approx_time if given."""
    text = ass_path.read_text()
    pattern = re.compile(r"\b" + re.escape(word) + r"\b")
    new_text = pattern.sub(word.lower(), text)
    if new_text == text:
        return False
    out_path.write_text(new_text)
    return True


def patch_subtitle_typo(ass_path: Path, from_word: str, to_word: str,
                         out_path: Path) -> bool:
    text = ass_path.read_text()
    pattern = re.compile(r"\b" + re.escape(from_word) + r"\b")
    new_text = pattern.sub(to_word, text)
    if new_text == text:
        return False
    out_path.write_text(new_text)
    return True


def patch_trim_black_end(clip_path: Path, audit_json: dict, out_path: Path) -> bool:
    """Use audit's check #12 result to find where black starts, trim to there."""
    # Find check #12 in audit.json
    check12 = next((r for r in audit_json.get("results", []) if r.get("id") == 12), None)
    if not check12 or check12.get("status") != "fail":
        return False
    # Parse details like "[00:41.90–00:42.10] black for 0.20s" — take earliest black_start > duration*0.8
    details = check12.get("details", [])
    duration = audit_json.get("duration_sec", 0)
    cutoff = None
    for d in details:
        m = re.search(r"\[(\d+:\d+\.?\d*)", d)
        if m:
            parts = m.group(1).split(":")
            start_sec = float(parts[0]) * 60 + float(parts[1])
            # Only trim BLACK that's near the END (>75% through the clip)
            if start_sec > duration * 0.75:
                cutoff = start_sec if cutoff is None else min(cutoff, start_sec)
    if cutoff is None:
        return False
    code, _, err = sh(["ffmpeg", "-y", "-i", str(clip_path), "-t", f"{cutoff:.3f}",
                       "-c", "copy", str(out_path)])
    return code == 0


def patch_audio_normalize_peak(clip_path: Path, target_db: float, out_path: Path) -> tuple[bool, float]:
    """Bring the peak up/down to target_db by applying a uniform volume gain.
    Returns (success, applied_gain_db)."""
    # Measure current peak
    code, _, err = sh(["ffmpeg", "-i", str(clip_path), "-af", "volumedetect",
                       "-vn", "-f", "null", "-"])
    m = re.search(r"max_volume:\s*(-?\d+\.?\d*)\s*dB", err)
    if not m:
        return False, 0.0
    current_peak = float(m.group(1))
    adjust = target_db - current_peak
    if abs(adjust) < 0.5:
        return False, 0.0  # Already within half a dB of target
    code, _, _ = sh(["ffmpeg", "-y", "-i", str(clip_path),
                     "-af", f"volume={adjust:+.2f}dB",
                     "-c:v", "copy", str(out_path)])
    return code == 0, adjust


def patch_add_lead_frames(clip_path: Path, target_lead_frames: int, fps: float,
                           out_path: Path) -> bool:
    """Duplicate the first frame N times + pad audio with silence."""
    pad_dur = target_lead_frames / fps
    code, _, _ = sh(["ffmpeg", "-y", "-i", str(clip_path),
                     "-vf", f"tpad=start_duration={pad_dur:.3f}:start_mode=clone",
                     "-af", f"apad=pad_dur={pad_dur:.3f}",
                     "-shortest", str(out_path)])
    return code == 0


# ─────────────────────────────────────────────────────────────────────────────
# Execution
# ─────────────────────────────────────────────────────────────────────────────

def apply_patches(issues: list[Issue], clip_path: Path, subtitle_path: Optional[Path],
                   audit_json_path: Optional[Path], out_v2: Path) -> list[Issue]:
    """Apply patches for auto-patchable issues, return updated issue list."""
    work_dir = clip_path.parent / "_patching" / clip_path.stem
    work_dir.mkdir(parents=True, exist_ok=True)

    # Stage 1: subtitle edits
    current_ass = subtitle_path
    current_mp4 = clip_path

    if subtitle_path and any(i.category == "subtitle-text" and i.auto_patchable for i in issues):
        patched_ass = work_dir / f"{subtitle_path.stem}.patched.ass"
        shutil.copy(subtitle_path, patched_ass)
        subtitle_edits = 0
        for issue in issues:
            if issue.category != "subtitle-text" or not issue.auto_patchable:
                continue
            # Try lowercase patch first (most common)
            m = re.search(r'["\']([A-Z][a-zA-Z]+)["\'].*(?:should be|lowercase|not capital)',
                          issue.raw_text, re.IGNORECASE)
            if m:
                word = m.group(1)
                if patch_subtitle_lowercase(patched_ass, word, issue.timestamp_sec, patched_ass):
                    issue.patch_action = f'lowercase "{word}"'
                    issue.patch_result = "applied"
                    subtitle_edits += 1
                    continue
            # Try typo X -> Y
            m = re.search(r'["\']([^"\']+)["\'].*?["\']([^"\']+)["\']', issue.raw_text)
            if m and m.group(1) != m.group(2):
                if patch_subtitle_typo(patched_ass, m.group(1), m.group(2), patched_ass):
                    issue.patch_action = f'typo "{m.group(1)}" → "{m.group(2)}"'
                    issue.patch_result = "applied"
                    subtitle_edits += 1
                    continue
            issue.patch_result = "skipped"
            issue.patch_action = "couldn't parse target from feedback — escalated to edit brief"

        if subtitle_edits > 0:
            current_ass = patched_ass
            # Note: would re-burn captions here via caption-burner.
            # For MVP, we write the patched .ass and note re-burn as pending.

    # Stage 2: video-timing (black frame trim, lead fix)
    if any(i.category == "video-timing" and i.auto_patchable for i in issues):
        audit_data = {}
        if audit_json_path and audit_json_path.exists():
            try:
                audit_data = json.loads(audit_json_path.read_text())
            except json.JSONDecodeError:
                pass
        for issue in issues:
            if issue.category != "video-timing" or not issue.auto_patchable:
                continue
            if "black" in issue.raw_text.lower():
                trimmed = work_dir / f"{current_mp4.stem}.trimmed.mp4"
                if patch_trim_black_end(current_mp4, audit_data, trimmed):
                    issue.patch_action = "trimmed black frames at end"
                    issue.patch_result = "applied"
                    current_mp4 = trimmed
                    continue
            if "lead" in issue.raw_text.lower() or "start" in issue.raw_text.lower():
                fps_probe = sh(["ffprobe", "-v", "error", "-select_streams", "v:0",
                                "-show_entries", "stream=r_frame_rate", "-of", "csv=p=0", str(current_mp4)])
                fps = 30.0
                if fps_probe[1] and "/" in fps_probe[1]:
                    num, den = fps_probe[1].strip().split("/")
                    fps = float(num) / float(den) if float(den) else 30.0
                padded = work_dir / f"{current_mp4.stem}.leadfix.mp4"
                if patch_add_lead_frames(current_mp4, 5, fps, padded):
                    issue.patch_action = "added 5-frame silent lead"
                    issue.patch_result = "applied"
                    current_mp4 = padded
                    continue
            issue.patch_result = "skipped"

    # Stage 3: audio normalization
    audio_issues = [i for i in issues if i.category == "audio-levels" and i.auto_patchable]
    if audio_issues:
        normed = work_dir / f"{current_mp4.stem}.normalized.mp4"
        # Single patch handles all audio-level issues combined
        ok, gain = patch_audio_normalize_peak(current_mp4, -6.0, normed)
        for issue in audio_issues:
            if ok:
                issue.patch_action = f"normalized peak by {gain:+.1f}dB"
                issue.patch_result = "applied"
            else:
                issue.patch_result = "skipped"
                issue.patch_action = "already within target or ffmpeg failed"
        if ok:
            current_mp4 = normed

    # Finalize
    shutil.copy(current_mp4, out_v2)
    if current_ass and current_ass != subtitle_path:
        out_ass = out_v2.with_suffix(".ass")
        shutil.copy(current_ass, out_ass)
    return issues


def write_edit_brief(issues: list[Issue], clip_slug: str, brief_path: Path) -> None:
    lines = [f"# Edit Brief — {clip_slug}", "",
             "These feedback items could not be auto-patched. Address them manually:", ""]
    manual = [i for i in issues if not i.auto_patchable or i.patch_result in ("skipped", "failed")]
    if not manual:
        lines.append("_(no manual items — everything was auto-patched)_")
    else:
        for i, issue in enumerate(manual, 1):
            ts = f"[{int(issue.timestamp_sec // 60):02d}:{issue.timestamp_sec % 60:05.2f}]" if issue.timestamp_sec else "[--:--]"
            lines.append(f"## {i}. {ts} {issue.category}")
            lines.append(f"> {issue.raw_text}")
            lines.append("")
            if issue.patch_action:
                lines.append(f"_Auto-patch attempted: {issue.patch_action}_")
                lines.append("")
    brief_path.write_text("\n".join(lines))


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def run_on_clip(client: str, clip_slug: str, mode: str, feedback_text: Optional[str]) -> int:
    if trk is None:
        print("error: clip-review-tracker not importable — is it installed as a skill?", file=sys.stderr)
        return 1

    rec = trk.load_record(client, clip_slug)
    if not rec:
        print(f"error: no clip at {client}/{clip_slug}", file=sys.stderr)
        return 1

    if rec.current_state != "needs-revision" and mode != "plan-only":
        print(f"warning: clip is in state '{rec.current_state}', not 'needs-revision'. Proceeding anyway.")

    clip_path = Path(rec.clip_path)
    subtitle_path = Path(rec.subtitle_file) if rec.subtitle_file else None
    if not clip_path.exists():
        print(f"error: clip not found at {clip_path}", file=sys.stderr)
        return 1

    # Find latest audit json (sibling .json to .md)
    audit_json_path = None
    if rec.audit_reports:
        latest_md = Path(rec.audit_reports[-1])
        candidate = latest_md.with_suffix(".json")
        if candidate.exists():
            audit_json_path = candidate

    # Get feedback: prefer passed-in text, else latest feedback file
    if feedback_text is None:
        if rec.feedback_files:
            feedback_text = Path(rec.feedback_files[-1]).read_text()
        else:
            print("error: no feedback to process (pass --text or --file, or use tracker.py feedback first)",
                  file=sys.stderr)
            return 1

    # Parse + classify
    issues = parse_feedback(feedback_text)
    print(f"\nREVISION PLAN — {client}/{clip_slug} (v{rec.current_version} → v{rec.current_version + 1})\n")
    print(f"Feedback parsed: {len(issues)} issues")
    for issue in issues:
        mark = "✅" if issue.auto_patchable else "⚠️"
        ts = f"[{int(issue.timestamp_sec//60):02d}:{issue.timestamp_sec%60:05.2f}]" if issue.timestamp_sec else "[--:--]"
        print(f"  {mark} {ts} {issue.category:<22s} conf={issue.confidence:.2f}  {issue.raw_text[:70]}")

    if mode == "plan-only":
        brief_path = clip_path.with_name(f"{clip_slug}-v{rec.current_version + 1}.edit-brief.md")
        write_edit_brief(issues, clip_slug, brief_path)
        print(f"\nEdit brief written: {brief_path}")
        return 0

    # Transition to patching
    # (We do this manually since tracker.py is a CLI; we'd invoke it here.)
    sh(["python3", str(Path("__ACQ_SKILLS__") / "clip-review-tracker" / "scripts" / "tracker.py"),
        "transition", clip_slug, "patching", "--client", client,
        "--note", f"revision-planner running on {len(issues)} issues"])

    # Apply patches
    out_v2 = clip_path.with_name(f"{clip_path.stem}.v2.mp4")
    issues = apply_patches(issues, clip_path, subtitle_path, audit_json_path, out_v2)

    applied = [i for i in issues if i.patch_result == "applied"]
    skipped = [i for i in issues if i.patch_result == "skipped"]
    non_patchable = [i for i in issues if not i.auto_patchable]

    print(f"\nPatches applied:")
    for i in applied:
        print(f"  ✅ {i.category:<22s} {i.patch_action}")
    if skipped:
        print(f"\nPatches skipped:")
        for i in skipped:
            print(f"  ⏭️  {i.category:<22s} {i.patch_action}")
    if non_patchable:
        print(f"\nNon-patchable (edit brief):")
        for i in non_patchable:
            print(f"  ⚠️  {i.category:<22s} {i.raw_text[:70]}")

    # Re-audit v2
    v2_audit_md = Path.home() / "Downloads" / "audits" / f"{clip_slug}-v2.audit.md"
    v2_audit_md.parent.mkdir(parents=True, exist_ok=True)
    subtitles_v2 = out_v2.with_suffix(".ass") if out_v2.with_suffix(".ass").exists() else (subtitle_path if subtitle_path else None)
    audit_cmd = ["python3", str(AUDIT_SCRIPT), "--clip", str(out_v2), "--out", str(v2_audit_md)]
    if subtitles_v2:
        audit_cmd += ["--subtitles", str(subtitles_v2)]
    print(f"\nRe-auditing v2...")
    code, out, _ = sh(audit_cmd)
    print(out)

    verdict_pass = code == 0
    new_state = "audited-v2-pass" if (verdict_pass and not non_patchable) else "audited-v2-fail"

    # Write edit brief if there are non-patchables
    if non_patchable or not verdict_pass:
        brief_path = out_v2.with_name(f"{clip_slug}-v2.edit-brief.md")
        write_edit_brief(issues, clip_slug, brief_path)
        print(f"Edit brief: {brief_path}")

    # Transition tracker
    sh(["python3", str(Path("__ACQ_SKILLS__") / "clip-review-tracker" / "scripts" / "tracker.py"),
        "transition", clip_slug, new_state, "--client", client,
        "--artifact", str(v2_audit_md),
        "--note", f"revision: {len(applied)} patched, {len(non_patchable)} need manual"])

    print(f"\nv2 clip: {out_v2}")
    print(f"v2 audit: {v2_audit_md}")
    print(f"Tracker: {new_state}")
    return 0 if new_state == "audited-v2-pass" else 2


def run_all_pending(mode: str) -> int:
    if trk is None:
        print("error: clip-review-tracker not importable", file=sys.stderr)
        return 1
    vault = trk.default_vault()
    deliveries = vault / "deliveries"
    if not deliveries.exists():
        print("(no deliveries found)")
        return 0
    pending_clips = []
    for client_dir in deliveries.iterdir():
        if not client_dir.is_dir():
            continue
        for md in client_dir.glob("*.md"):
            rec = trk._parse_record(md.read_text(), client_dir.name, md.stem)
            if rec.current_state == "needs-revision":
                pending_clips.append((client_dir.name, md.stem))
    if not pending_clips:
        print("(no clips in needs-revision)")
        return 0
    print(f"Processing {len(pending_clips)} clips...")
    for client, slug in pending_clips:
        run_on_clip(client, slug, mode, None)
    return 0


def main():
    ap = argparse.ArgumentParser(description="Revision Planner — auto-patch clip feedback")
    sub = ap.add_subparsers(dest="cmd")

    run_p = sub.add_parser("run", help="Run on a single clip (default if no subcommand)")
    # Allow top-level args too
    ap.add_argument("--clip-slug")
    ap.add_argument("--client")
    ap.add_argument("--mode", choices=["safe", "plan-only", "aggressive"], default="safe")
    ap.add_argument("--text")
    ap.add_argument("--file", type=Path)

    sub.add_parser("run-all-pending", help="Process every clip in `needs-revision`")

    args = ap.parse_args()

    if args.cmd == "run-all-pending":
        sys.exit(run_all_pending(args.mode))

    if not args.clip_slug:
        ap.error("--clip-slug required")

    client = args.client
    if not client and trk:
        client = trk._guess_client_from_slug(args.clip_slug)
    if not client:
        ap.error("--client required (couldn't auto-detect)")

    feedback_text = args.text
    if args.file:
        feedback_text = (feedback_text or "") + "\n" + args.file.read_text()

    sys.exit(run_on_clip(client, args.clip_slug, args.mode, feedback_text))


if __name__ == "__main__":
    main()
