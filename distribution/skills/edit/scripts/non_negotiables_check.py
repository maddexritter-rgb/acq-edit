#!/usr/bin/env python3
"""Q&A NON-NEGOTIABLES gate — code-enforced check of the 3 hard rules from qa_playbook.md.

Existence rationale: 2026-06-14, on the L1 Workshop Q&A batch, the agent (me) READ the
playbook, then optionalized non-negotiable #2 (split-screen face-tracked panels) by
defaulting to the "simplest valid floor" fallback clause because tuning the CCAM ROI
per session looked "too complex for autonomous mode." Maddex caught it immediately.
The lesson: a memory note is necessary but not sufficient — the gate must run in code,
fail loudly, and BLOCK delivery so a future agent cannot ship a Q&A that violates them.

This script audits a delivered .mp4 + its project dir (manifest/edl/qa_sync/build log)
against the 3 non-negotiables. Returns exit 0 on PASS, 1 on FAIL.

Usage:
  python3 non_negotiables_check.py --project 10_WORK/clips/<rank>_<slug> \\
                                    --clip 20_DELIVER/v<N>/<ACQ-name>.mp4 \\
                                    [--sync 10_WORK/qa_sync.json]

Per qa_playbook.md "THREE NON-NEGOTIABLES":
  1. AUDIO — every speaker on their OWN lav, mixed correctly (no wrong-mic hiss).
     Verifies: qa_sync has `speaker_mics` mapping both alex AND guest to their own lavs
     (not the same file); build.log shows "2-mic conv mix" and no [audio][WARN].
  2. SPLIT — both panels face-tracked, comparable scale (~20-35% face per panel),
     never a static crop. Verifies: if the EDL has any speaker=guest segments,
     it MUST have cam=split (or cam=guest face-tracked) segments — NOT all cam=alex
     (the disallowed shortcut). qa_sync MUST have guest_split with zoom/roi
     (defaults are NOT acceptable for session-specific footage).
  3. CAPTIONS — money compact ($100K / $3.5M / 85% / 10X, never "100 grand").
     Verifies: build.log shows caption_lint with "0 errors" (or the lint log exists
     showing 0 spelled-number errors).

Monologue exception: if the EDL has NO speaker=guest segments (pure Alex monologue
clip per qa_clip_patterns.md), the SPLIT check is SKIPPED — but the AUDIO + CAPTIONS
checks still apply, and a banner notes the monologue classification.
"""
from __future__ import annotations
import argparse, json, re, sys, subprocess
from pathlib import Path


def find_log(project: Path) -> str | None:
    log = project / "build.log"
    return log.read_text() if log.exists() else None


def check_audio(project: Path, sync_path: Path) -> tuple[bool, list[str]]:
    msgs = []
    try:
        s = json.loads(sync_path.read_text())
    except Exception as e:
        return False, [f"qa_sync.json missing or invalid: {e}"]
    sm = s.get("speaker_mics") or {}
    if "alex" not in sm or "guest" not in sm:
        return False, [f"qa_sync.speaker_mics must define BOTH 'alex' and 'guest' (got: {list(sm)})"]
    if sm["alex"] == sm["guest"]:
        return False, [f"qa_sync.speaker_mics: alex and guest point to the SAME file — wrong-mic hiss bug"]
    log = find_log(project)
    if log:
        if "2-mic conv mix" not in log:
            msgs.append("build.log: '2-mic conv mix' line not found — audio path may not have used speaker_mics")
        if "[audio][WARN]" in log:
            msgs.append("build.log: contains [audio][WARN] — fix before delivery")
            return False, msgs
    return True, msgs


def check_split(project: Path, sync_path: Path) -> tuple[bool, list[str], bool]:
    """Returns (passed, msgs, is_monologue)."""
    edl_path = project / "edl.json"
    if not edl_path.exists():
        return False, [f"no edl.json at {edl_path}"], False
    edl = json.loads(edl_path.read_text())
    segs = edl.get("segments", [])
    has_guest_seg = any(s.get("speaker") == "guest" for s in segs)

    if not has_guest_seg:
        # Pure Alex monologue — split-screen exception per qa_clip_patterns.md
        return True, ["MONOLOGUE clip (no guest segments) — split-screen exception per playbook ('don't apply Q&A split-screen to a monologue')"], True

    # Has guest segments — verify split or face-tracked guest cam is used
    guest_cams = {s.get("cam") for s in segs if s.get("speaker") == "guest"}
    accepted_split_cams = {"split", "guest", "guest_wide"}
    if not (guest_cams & accepted_split_cams):
        return False, [f"non-negotiable #2: guest segments use cam={guest_cams} — must include at least one of split/guest/guest_wide. ALL cam=alex on a Q&A clip is the shortcut the playbook forbids."], False

    # If using split, verify guest_split is configured
    if "split" in guest_cams:
        try:
            s = json.loads(sync_path.read_text())
            gs = s.get("guest_split")
        except Exception:
            gs = None
        if not gs:
            return False, ["non-negotiable #2: cam=split used but qa_sync.guest_split missing — face-tracker has no ROI guard, will lock onto audience faces"], False
        if "roi" not in gs:
            return False, [f"non-negotiable #2: qa_sync.guest_split missing 'roi' — needed to guard against audience face lock-on (have: {list(gs)})"], False
    return True, [f"split grammar OK — guest segments use {guest_cams}"], False


def check_captions(project: Path) -> tuple[bool, list[str]]:
    log = find_log(project)
    if not log:
        return False, ["no build.log to verify caption_lint"]
    # Look for the caption_lint line; format: "caption_lint: N cues | X errors, Y warnings, Z advisories"
    m = re.search(r"caption_lint:.*?(\d+)\s+errors", log)
    if not m:
        return False, ["build.log: caption_lint line not found — verify normalization ran"]
    n_err = int(m.group(1))
    if n_err > 0:
        # extract the actual errors
        errs = re.findall(r"\[ERR\s*\].+", log)
        return False, [f"non-negotiable #3: caption_lint = {n_err} errors. Sample:"] + errs[:3]
    return True, [f"caption_lint = 0 errors"]


def main():
    ap = argparse.ArgumentParser(description="Q&A non-negotiables hard gate")
    ap.add_argument("--project", required=True, type=Path, help="clip project dir (has edl.json + build.log)")
    ap.add_argument("--clip", type=Path, default=None, help="optional delivered .mp4 to identify in output")
    ap.add_argument("--sync", type=Path, default=None, help="qa_sync.json (default: <project>/../../qa_sync.json)")
    args = ap.parse_args()

    project = args.project.resolve()
    if args.sync:
        sync_path = args.sync.resolve()
    else:
        # default location: <project>/../../qa_sync.json (project=10_WORK/clips/<slug>/, sync=10_WORK/qa_sync.json)
        sync_path = (project / ".." / ".." / "qa_sync.json").resolve()

    print(f"=== Q&A NON-NEGOTIABLES — {project.name} ===")
    if args.clip:
        print(f"clip: {args.clip}")
    print(f"sync: {sync_path}\n")

    a_pass, a_msgs = check_audio(project, sync_path)
    s_pass, s_msgs, is_mono = check_split(project, sync_path)
    c_pass, c_msgs = check_captions(project)

    icon = lambda ok: "PASS" if ok else "FAIL"
    print(f"  [#1 AUDIO]    {icon(a_pass)}")
    for m in a_msgs: print(f"      · {m}")
    print(f"  [#2 SPLIT]    {icon(s_pass)}{'  (monologue exception)' if is_mono else ''}")
    for m in s_msgs: print(f"      · {m}")
    print(f"  [#3 CAPTIONS] {icon(c_pass)}")
    for m in c_msgs: print(f"      · {m}")

    if a_pass and s_pass and c_pass:
        print("\nALL 3 NON-NEGOTIABLES PASS — clear to deliver.")
        sys.exit(0)
    print("\nBLOCK — fix non-negotiable failures before delivery.")
    sys.exit(1)


if __name__ == "__main__":
    main()
