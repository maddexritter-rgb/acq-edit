# Clip Review State Machine

## States

| State | Meaning | Who's blocking |
|---|---|---|
| `draft` | Raw cut rendered, not yet audited | Automation (shortify should auto-audit) |
| `audited-v1-pass` | Mozi audit v1 passed | You — decide to send to client |
| `audited-v1-fail` | Mozi audit v1 failed | You — fix internally before client sees |
| `with-client` | Delivered to client | Client |
| `needs-revision` | Client feedback received, not yet acted on | You — run revision-planner |
| `patching` | Revision-planner or user is actively fixing | Automation (in progress) |
| `audited-v2-pass` | After patches, audit passed | You — re-deliver to client |
| `audited-v2-fail` | After patches, audit still failing | You — manual intervention |
| `approved` | Client signed off | You — schedule for posting |
| `scheduled` | Queued for posting | Automation (social-publisher) |
| `posted` | Live on target platform | — (done) |
| `archived` | Rejected / pulled / stale | — (terminal) |

## Valid transitions

```
draft ──────────────→ audited-v1-pass / audited-v1-fail
audited-v1-pass ────→ with-client / archived
audited-v1-fail ────→ patching / archived
with-client ────────→ needs-revision / approved / archived
needs-revision ─────→ patching / archived
patching ───────────→ audited-v2-pass / audited-v2-fail
audited-v2-pass ────→ with-client (re-deliver) / approved
audited-v2-fail ────→ patching (another round) / archived
approved ───────────→ scheduled / posted / archived
scheduled ──────────→ posted / archived
posted              terminal (but can be archived)
archived            terminal
```

## Rules

### 1. State transitions are append-only
Every transition writes a new line to the `## State history` section with a timestamp + reason. Previous state history is never edited. A correction = a new transition that references the bad one.

### 2. Transitions must come from a known writer
Only these skills write transitions:
- `shortify` (initial create + first audit)
- `mozi-sf-audit` (audit results)
- `revision-planner` (patches + re-audit)
- `clip-review-tracker` CLI (manual transitions — user running `tracker.py transition ...`)

Random scripts should NOT write transitions. If a new skill needs to transition, add it to this allowlist.

### 3. "Pending my eye" filter
Returns clips where YOU (solo operator) are the bottleneck:
```
audited-v1-fail
needs-revision
audited-v2-fail
approved (but not scheduled yet)
```

Does not return `with-client`, `scheduled`, `patching` (waiting on someone/something else).

### 4. Staleness detection
A clip in `with-client` for >7 days gets flagged in the dashboard as "stale — follow up with client."
A clip in `approved` for >3 days gets flagged as "stale — schedule it."
A clip in `audited-v1-fail` for >2 days gets flagged as "stale — fix or archive."

### 5. Version counting
`current_version` increments only when a patch cycle completes (not every audit re-run). So: v1 = first render, v2 = after one revision cycle, v3 = after two, etc.

## Anti-patterns (don't do)

- **Skipping states** — no jumping from `draft` straight to `approved`. Always go through audit.
- **Re-using a clip_slug across clients** — slugs must be unique per client, so `<client-slug>/<clip-slug>` is always globally unique.
- **Editing state history** — to correct a misfire, add a new transition with a note like "CORRECTION: previous transition to audited-v1-pass was premature — reverting to audited-v1-fail."
- **Multiple concurrent `patching` states on same clip** — only one active revision at a time.
