---
name: clip-review-tracker
description: >
  State-machine tracker for every clip we render for ACQ. One markdown file per clip at
  vault/deliveries/client/clip-slug.md tracks the clip through its life: draft →
  audited-v1 → with-client → needs-revision → patching → audited-vN → approved → scheduled
  → posted. Every editing skill (shortify, mozi-sf-audit, revision-planner) writes transitions
  automatically. Solo-operator can query "what's pending my eye?", "what needs revision?",
  "what's approved this week?" and get a clean answer instead of remembering it in their head.
  Triggers: "what clips need my review", "show me pending clips", "what's the status of this clip",
  "clips waiting on client", "what got approved this week", "clip status", "delivery tracker",
  "update clip state", "mark as approved".
---

# Clip Review Tracker

For any Premiere access, follow [Premiere Agent startup and advanced stage routing](../edit/references/premiere_start_here.md). Use the configured new bridge by default; if MCP tools are missing in this chat, use its CLI. Keep this skill’s existing creative scope and read-only limits.


The single source of truth for where every rendered clip is in its life. Editing skills write state transitions automatically; you query it to know what needs attention.

Read `references/state-machine.md` for delivery state. For stage-specific editorial evidence, replay locks, and promotion safety, read `references/decision-memory.md`.

---

## The states

```
draft                → raw cut exists, not yet audited
audited-v1-pass      → mozi-sf-audit v1 passed, ready to send to client
audited-v1-fail      → mozi-sf-audit v1 failed, internal fix needed first
with-client          → delivered to client (Frame.io / Drive / Slack)
needs-revision       → client left feedback, revisions pending
patching             → revision-planner or user is actively fixing
audited-v2-pass      → after revision, passed audit again
audited-v2-fail      → revision still doesn't pass audit (loop back to patching)
approved             → client signed off, ready to ship
scheduled            → queued for posting via social-publisher
posted               → live, tracker continues for performance data later
archived             → rejected / pulled / stale (kept for history)
```

See `references/state-machine.md` for valid transitions from each state.

---

## Storage format

One markdown file per clip at `vault/deliveries/<client-slug>/<clip-slug>.md`:

```markdown
---
client: alex
clip_slug: beginner-gym-mistakes
current_state: needs-revision
current_version: 1
created: 2026-04-22T14:30:00
updated: 2026-04-22T16:12:00

source_video: ~/Downloads/alex-podcast-ep-74.mp4
script_file: vault/scripts/alex--2026-04-22--beginner-gym.md
clip_path: ~/Downloads/clips-captioned/alex-clip-v1.mp4
subtitle_file: ~/Downloads/clips-captioned/alex-clip-v1.ass

# Retrieval profile — used by find-precedents at the start of every new clip
clip_type: q&a                            # q&a | monologue | story | list | comparison | reveal
gesture_profile: speaker_hand_enters_upper_frame
caption_style: pro                        # pro | ugc | cinematic | big-word | hormozi | liquid-glass
hook_type: revenue-first                  # revenue-first | named-framework | question | story-cold-open | contrarian
duration_seconds: 47
tags: [hormozi-style, pricing-topic, hand-gesture-active]

audit_reports: [...]
feedback_files: [...]
---

# Creator A — Beginner Gym Mistakes

## State history
- 2026-04-22 14:30 — `draft` — initial render via shortify
- 2026-04-22 14:47 — `audited-v1-pass` — mozi audit: 9 pass, 2 manual, 2 skip
- 2026-04-22 14:55 — `with-client` — sent via Drive link
- 2026-04-22 16:12 — `needs-revision` — 3 comments from the reviewer

## Artifacts
- [[alex-clip-v1.audit.md]] — v1 audit report
- [[feedback/alex-clip-v1.txt]] — the reviewer's Drive comments

## Issues caught & lessons
### v1 → v2 (2026-04-22T16:30:11)
- ISSUE: Captions collided with right hand at 0:31 (was y=70%)
  WHEN: client=alex AND gesture_profile=speaker_hand_enters_upper_frame
  THEN: caption y=78% (not 70%) — gesture clearance
- ISSUE: Music at 0.10 too loud over declarative motivational delivery
  WHEN: hook_type=revenue-first AND caption_style=pro
  THEN: music ≤0.05, target -16 LUFS

## Notes
...
```

---

## Capturing lessons — the WHEN/THEN protocol

The Issues caught & lessons section is the **load-bearing piece** that lets `find-precedents` surface the right correction at the start of the next similar clip. Editing skills (`shortform`, `qa-clipper`, `caption-clips`, `revision-planner`) MUST log a lesson every time the user corrects a v1→v2 issue.

A lesson has three required parts:

- **ISSUE** — what went wrong in this version (the user's correction, in plain language)
- **WHEN** — the condition under which the lesson applies. This is what retrieval matches on. Reference profile fields (client, clip_type, gesture_profile, caption_style, hook_type) plus any tags. Example: `client=alex AND gesture_profile=speaker_hand_enters_upper_frame`
- **THEN** — the corrective setting / action / parameter for next time. Concrete and actionable. Example: `caption y=78% (not 70%)`

The point of WHEN: a lesson with `WHEN: this specific clip` is useless. A lesson with `WHEN: any alex Q&A where speaker gestures upper-frame` generalizes to the next 10 similar clips. Always frame the condition in terms that will recur.

**Never auto-promote or delete evidence.** Repetition only makes a lesson a candidate. Promotion requires counterexample review, held-out validation, explicit user approval, and a fresh backup of both protected brain roots; see `references/decision-memory.md`.

---

## Commands

### Query state
```bash
python3 __ACQ_SKILLS__/clip-review-tracker/scripts/tracker.py status <clip-slug>
python3 __ACQ_SKILLS__/clip-review-tracker/scripts/tracker.py list --state needs-revision
python3 __ACQ_SKILLS__/clip-review-tracker/scripts/tracker.py list --client alex
python3 __ACQ_SKILLS__/clip-review-tracker/scripts/tracker.py list --pending-my-eye
python3 __ACQ_SKILLS__/clip-review-tracker/scripts/tracker.py summary --client alex --month 2026-04
```

### Register a new clip (called by shortify automatically)
```bash
python3 .../tracker.py create \
  --client alex \
  --clip-slug beginner-gym-mistakes \
  --source ~/Downloads/alex-podcast-ep-74.mp4 \
  --clip ~/Downloads/clips-captioned/alex-clip-v1.mp4 \
  --subtitles ~/Downloads/clips-captioned/alex-clip-v1.ass \
  --clip-type q&a --gesture-profile speaker_hand_enters_upper_frame \
  --caption-style pro --hook-type revenue-first --duration-seconds 47 \
  --tags pricing-topic hand-gesture-active
```

### Transition state
```bash
python3 .../tracker.py transition <clip-slug> audited-v1-pass \
  --artifact ~/Downloads/audits/alex-clip-v1.audit.md \
  --note "9 pass, 2 manual, 2 skip"
```

### Attach feedback
```bash
python3 .../tracker.py feedback <clip-slug> \
  --text "Client wants captions bigger, fix typo at 0:23"
```

Feedback triggers automatic transition to `needs-revision`.

### Update the retrieval profile after the clip exists
```bash
python3 .../tracker.py profile beginner-gym-mistakes \
  --gesture-profile speaker_hand_enters_upper_frame \
  --caption-style pro --tags pricing-topic hand-gesture-active
```

### Log a lesson when correcting a v1 → v2 issue (THIS IS THE KEY COMMAND)
```bash
python3 .../tracker.py lesson beginner-gym-mistakes \
  --issue "Captions collided with right hand at 0:31 (was y=70%)" \
  --when  "client=alex AND gesture_profile=speaker_hand_enters_upper_frame" \
  --then  "caption y=78% (not 70%) — gesture clearance"
```

Every editing skill should call this whenever the user issues a correction that's likely to recur. The WHEN clause MUST reference profile fields or tags so retrieval can match it later — not the specific clip slug.

### Export lessons (consumed by find-precedents)
```bash
python3 .../tracker.py export-lessons --with-lessons-only
# emits JSON with profile + lessons across the whole library
```

### Append and index stage-specific decisions
```bash
python3 .../tracker.py memory init --db <project>/edit-memory/evidence.sqlite3
python3 .../tracker.py memory append --db <project>/edit-memory/evidence.sqlite3 --record decision.json
python3 .../tracker.py memory import-markdown --db <project>/edit-memory/evidence.sqlite3 <research-root>
python3 .../tracker.py memory stats --db <project>/edit-memory/evidence.sqlite3
```

The JSONL ledger beside the database is append-only evidence; SQLite is the searchable structured/FTS/vector index. Retrieval and manifest locking are provided by `scripts/evidence.py`.

Historical editing decisions are inactive by default. A captioned export identifies what shipped, but active memory additionally requires the exact final Premiere sequence to be opened, inspected, and verified against that export:

```bash
python3 .../evidence.py --db <project>/edit-memory/evidence.sqlite3 set-eligibility \
  --decision-id <id> --status verified_captioned_final \
  --reason "Visible captions identify the exported final" --proof final-proof.json
```

`final-proof.json` must contain `proof_type: captioned_final_timeline`, `captions_visible: true`, the exact final asset and Premiere sequence path/identity, and a `timeline_verification` receipt proving Premiere inspection, export matching, and explicit draft exclusion. Export-only observations are preliminary and inactive. Drafts and uncertain assets are recorded as `quarantined_nonfinal` or `unresolved_final_identity`; they are retained for audit but never retrieved or promoted.

---

## Query: "what's pending my eye?"

Returns clips in states where YOU (the solo operator) need to act:

- `audited-v1-fail` — internal fix needed
- `needs-revision` — client sent comments, plan the patches
- `audited-v2-fail` — loop again
- `approved` — need to schedule posting
- `scheduled` — need to check if auto-publisher posted it

Does NOT return:
- `with-client` (waiting on them)
- `posted` (done)

---

## Integration with other skills

- **`shortform` / `qa-clipper` / `caption-clips`** → call `find-precedents` BEFORE editing (loads similar past cases + their lessons into context); call `tracker.py create` after render with profile fields populated; auto-run `mozi-sf-audit` + transition to `audited-v1-pass|audited-v1-fail`
- **`mozi-sf-audit`** (when run standalone) → calls `tracker.py transition` with the audit verdict
- **`revision-planner`** → pulls clips in `needs-revision`, applies patches, re-audits, transitions to `audited-v2-pass|audited-v2-fail`. CRITICAL: for every patched issue that wasn't a one-off typo, calls `tracker.py lesson` so the correction is captured for future retrieval
- **`client-script-pipeline`** → when a script is generated, pre-registers a tracker entry in `draft` state with script + source linked
- **`find-precedents`** → reads `tracker.py export-lessons` JSON, filters to similar cases, dumps their lessons into context at the top of every editing session

---

## Output report for the solo operator (daily dashboard)

```bash
python3 .../tracker.py dashboard
```

Produces:

```
📋 Clip Review Dashboard — 2026-04-22

⚠️ PENDING YOUR EYE (act now):
  • alex-clip-mistakes       — needs-revision (v1, 3 comments)
  • alex-hormozi-comparison          — audited-v1-fail (audio peak -14dB)
  • the client-cold-approach-burnout     — approved (ready to schedule)

⏳ WAITING ON CLIENT:
  • alex-tdee-calculator             — with-client (3 days)
  • the client-bio-rewrite               — with-client (1 day)

✅ DONE TODAY:
  • alex-podcast-hook-overlay        — approved
  • the client-ryan-case-study           — posted

📊 This week: 8 created, 5 approved, 3 posted, 1 archived
```

---

## Quick reference

```
STATES       draft → audited-v1 → with-client → needs-revision → patching → audited-vN → approved → scheduled → posted
STORAGE      vault/deliveries/<client>/<slug>.md — frontmatter (profile) + state history + Issues caught & lessons
AUTO-WRITES  shortform/qa-clipper/caption-clips/mozi-sf-audit/revision-planner all call the tracker CLI
KEY QUERY    tracker.py list --pending-my-eye — shows what actually needs your attention now
KEY LEARN    tracker.py lesson <slug> --issue ... --when ... --then ...   (capture-once, retrieve-forever)
```
