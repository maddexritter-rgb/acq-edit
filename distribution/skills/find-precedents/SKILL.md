---
name: find-precedents
description: >
  Retrieve live, evidence-labeled editing playbooks and relevant decision precedents
  from the shared editorial brain before assembly design, or find stage-specific
  historical clip lessons. Owns retrieval, not source-word selection or cutting.
---

# find-precedents

## Scoped production guidance

For brand/source-production guidance, → Load [scoped production policy](../edit/references/scoped-brand-policy.md).
Optional brand, production-type and stage selectors retrieve versioned scoped policies separately from universal/format playbooks and ranked cards.

For any Premiere access, follow [Premiere Agent startup and advanced stage routing](../edit/references/premiere_start_here.md). Use the configured new bridge by default; if MCP tools are missing in this chat, use its CLI. Keep this skill’s existing creative scope and read-only limits.


The retrieval mechanism for the case library. Legacy clip-profile lookup remains available; `/edit` uses the stage-scoped evidence index before each owning capability makes a high-judgment decision.

The historical-finals lane is final-only. The legacy delivered-final index requires
a matched captioned export and inspected native sequence. The live assembly-card lane
also accepts scoped `NATIVE_FINAL_SELECTION_VERIFIED` cards from campaign-authorized,
inspected fully edited captioned native sequences. Read their verification note:
they establish named spoken choices, not delivery, acoustic seams or human approval.
Drafts, rough cuts, model trials and uncertain FINAL names establish neither route.

The separate [assembly-context lane](references/assembly-cards.md) retrieves the
mandatory active playbooks and evidence-labeled *research and SOP decision aids*
from the private shared database.
Its development cards are hypotheses, never claims about a verified historical final.
For adding or revising cards, → Use skill: `editorial-brain-ingest`.
Run its live batch preflight for the universal, applicable format, and any L1 or
Workshop required-reading pack before new moment selection; after `assembly-design` has read
the complete interaction and diagnosed the actual problem, retrieve at most five cards
with source and exception. Exclude the current project and held-out cases. It owns
retrieval only, not the edit.

Without retrieval, the case library is an archive that only the human reads. With retrieval,
past corrections become active context at decision time — the closest analog the architecture
can support to "I remember this from six months ago."

---

## Legacy profile lookup (not the assembly-context lane)

The profile matcher below is retained for older, non-assembly lesson lookups. It
does not satisfy the mandatory live Supabase playbook preflight. For new assembly
design, follow [assembly-context lane](references/assembly-cards.md) instead.

### How legacy lookup works

1. The new clip's profile is collected (client, clip_type, gesture_profile, caption_style,
   hook_type, duration_seconds, tags, free-text topic).
2. `tracker.py export-lessons --with-lessons-only` dumps every past case with its profile +
   lessons as JSON.
3. Each case is scored against the new clip:
   - **+5** same client
   - **+3** same clip_type
   - **+3** same gesture_profile
   - **+2** same caption_style
   - **+2** same hook_type
   - **+1** same duration_band (under-30 / 30-60 / 60-120 / over-120)
   - **+1** per shared tag
   - **+N** topic-token overlap (capped at 4)
4. Top-N matches at or above `--min-score` are rendered as a markdown briefing showing each
   case's profile, why it matched, and its lessons (ISSUE / WHEN / THEN).
5. The model reads the briefing as the first thing in the editing session.

---

## CLI

```bash
python3 __ACQ_SKILLS__/find-precedents/scripts/find_precedents.py \
  --memory-db <project>/edit-memory/evidence.sqlite3 \
  --stage captions --case-id 0001 --exclude-case 0001 \
  --topic "long-form grouping, emphasis and timing" --top 5

python3 __ACQ_SKILLS__/find-precedents/scripts/find_precedents.py \
  --client alex \
  --clip-type q&a \
  --gesture-profile speaker_hand_enters_upper_frame \
  --caption-style pro \
  --hook-type revenue-first \
  --duration-seconds 47 \
  --tags pricing-topic hand-gesture-active \
  --topic "alex pricing rant with hand gestures" \
  --top 5 --min-score 3
```

Flags:
- `--client` — narrows to one client; omit to search across all clients
- `--clip-type` — q&a | monologue | story | list | comparison | reveal
- `--gesture-profile` — speaker_hand_enters_upper_frame | head_only | podium_static | full_body
- `--caption-style` — pro | ugc | cinematic | big-word | hormozi | liquid-glass
- `--hook-type` — revenue-first | named-framework | question | story-cold-open | contrarian
- `--duration-seconds` — used to compute duration_band match
- `--tags` — free-form match keys (space-separated)
- `--topic` — free-text description of what this clip is about; tokenized and matched against
  past slugs, tags, and lesson WHEN/ISSUE text
- `--top` — number of matches to surface (default 5)
- `--min-score` — drop weak matches below this score (default 3)
- `--vault` — override `CONTENT_VAULT` env var if needed
- `--json` — emit raw JSON for programmatic consumers instead of the markdown briefing

---

## Output (markdown briefing)

```markdown
# Precedents — past clips with lessons that match this profile

## 1. alex / 2026-04-22-pricing-rant  (score=14, v3, state=approved)
  - **profile:** clip_type=q&a, gesture_profile=speaker_hand_enters_upper_frame, caption_style=pro, hook_type=revenue-first, duration=30-60, tags=['pricing-topic']
  - **why matched:** +5 client=alex; +3 clip_type=q&a; +3 gesture_profile=...; +2 caption_style=pro; +1 tags=['pricing-topic']

  **Lessons:**
  - [v1 → v2] **ISSUE:** Captions collided with right hand at 0:31 (was y=70%)
    **WHEN:** client=alex AND gesture_profile=speaker_hand_enters_upper_frame
    **THEN:** caption y=78% (not 70%) — gesture clearance
  - [v2 → v3] **ISSUE:** Music too loud over declarative motivational delivery
    **WHEN:** hook_type=revenue-first AND caption_style=pro
    **THEN:** music ≤0.05, target -16 LUFS
```

When this **legacy** lookup has no matches, it can report "no precedents yet." That
does not authorize new assembly design without live active Supabase playbooks.

---

## Integration with editing skills

For new assembly design, this skill first retrieves the mandatory universal and
format playbooks **and full required reading** with the applicable overlays, then
retrieves up to five problem-matched cards after the full interaction is read.
The older profile lookup is optional stage-specific context,
never a substitute for that live read. For later-stage lessons, use the relevant
stage's historical lookup only when its owning skill calls for it.

After actual editor feedback, `editorial-brain-ingest` owns curating any new
assembly decision card; a legacy `tracker.py lesson` alone does not publish one.

---

## Promotion ladder — when a lesson outgrows the case library

Evidence stays append-only. Three supporting cases only create a promotion candidate; they do not authorize a skill change.

| Recurrence  | Action                                                              |
|-------------|---------------------------------------------------------------------|
| 1 case      | Stays a per-case lesson                                             |
| 2 cases     | Stays a per-case lesson; flag for review                            |
| 3+ cases    | Candidate: review counterexamples and run a held-out validation     |

Promotion additionally requires no held-out meaning/factual regression, explicit user approval, and a fresh backup of both protected brain roots. Never delete the supporting or rejected evidence, and never modify a canonical skill automatically.

Run a weekly consolidation pass:
```bash
python3 __ACQ_SKILLS__/clip-review-tracker/scripts/tracker.py export-lessons --with-lessons-only \
  | jq '.[].lessons[].then' | sort | uniq -c | sort -rn | head -20
```
Anything appearing 3+ times is a promotion candidate.

---

## Quick reference

```
USE       live playbooks before every new assembly design; profile lookup only for legacy stage lessons
INPUT     new clip's profile (client, clip_type, gesture_profile, caption_style, hook_type, tags, topic)
OUTPUT    live assembly context or a legacy markdown briefing, never interchangeably
SCORING   legacy weighted profile overlap only; live assembly uses problem/format search
PROMOTE   lessons recurring in 3+ cases → tool defaults / audit checks / trigger phrases
```
