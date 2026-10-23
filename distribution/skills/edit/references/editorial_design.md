# Editorial design and restart contract

Use this before selecting and designing clips, including a retry in an existing task.
The goal is complete useful ideas with little human correction. Clip count, cut count,
short duration, and mechanical PASS results are not substitutes for that outcome.

## Route by the interaction

- Business-owner diagnosis from raw footage: use [l1_qa_cuts.md](l1_qa_cuts.md), then this source-value contract. A human-selected draft instead uses [l1_draft_finishing.md](l1_draft_finishing.md).
- Ordinary podcast interview/cohost conversation or free-form podcast passage: use
  [podcast_mining.md](podcast_mining.md) for the editorial procedure and its format-specific
  precedence; retain this document's shared coverage, evidence and repair contracts.
- Monologue or host-read chat question: preserve the argument and applicable question context.

Assembly Design owns spoken selection, cleanup, and acoustic boundary resolution for
new assembly cuts. This historical reference supplies source-aware design guidance;
the default route does not require an independent cold-viewer review before the
editor receives a playable timeline.

## Restart without inheriting a failed answer

When the user rejects the editorial work, preserve the old project for history and reuse
verified source media/transcripts. Reselect from the full source; old candidate pools,
acceptance labels, cut-count filters and project-local repair scripts have no authority.
Inspect any reused helper for conflicting rules before executing it. Keep already approved
clips excluded from new delivery unless the user asks to revisit them. A retry must preserve previously approved clips while replacing rejected work.

Record source coverage in `10_WORK/mining/coverage.json`: source identity, transcript hash,
read-window ranges and failures; list each encountered topic/exchange as KEEP, REJECT or
MERGE with a reason and candidate IDs. Account for the tail and window overlaps. Coverage
proves exposure/accounting, not comprehension. No mandatory transcript-mining backend:
direct in-session reading is valid if full coverage and source-grounded design are done.

## Design first, then clean within it

For each candidate, write the actual kept words plus the intended viewer, hook, necessary
context, explanation/example, and delivered reward. Identify the smallest source phrases
that carry the value. Do not choose boundaries merely because they are easy to cut.
For business-mechanism work, preserve the practical explanation or action; a claim with its
useful example removed is not automatically a complete lesson. Story/entertainment rewards
remain valid when they fit the brief. Do not require a fixed number of beats or cuts.

Read the surrounding exchange through its actual completion, including the next source
sentences. Check whether the proposed ending discarded the answer, and whether an added
example opens a new unresolved thread. Sometimes restore the continuation; sometimes trim
the unfinished tail. Preserve exact source wording and speaker identity.

Before boundary work, save `design_evidence.json` per clip using the schema below. Select
minimal essential phrases, not whole paragraphs containing optional filler. These anchors
describe the original editorial intent, not a justification retrofitted to an arbitrary cut.
After resolving boundaries, update only `keep_spans`, run the evidence command, and read
its assembled transcript against the source. An omitted anchor returns to redesign. A
legitimate change in intent is allowed: retain the old evidence file, explain the change
in a new revision, and re-evaluate source value. Do not quietly remove failing anchors.

```json
{
  "schema": "edit.design-evidence/v1",
  "clip_id": "clip_001",
  "source_words": "/absolute/path/source.words.json",
  "source_sha256": "SHA256_OF_SOURCE_WORDS_FILE",
  "intent": "The useful idea this clip delivers",
  "essential": [
    {"role": "reward", "words": [10, 14], "why": "This phrase carries the usable payoff"}
  ],
  "keep_spans": [[1.0, 8.0]],
  "cleanup_review": "What was removed and why remaining continuous speech earns its place"
}
```

Indices are zero-based inclusive in the source JSON's `words` array. Source words use
`word`, `start`, `end` in seconds and optional `spk`/`speaker`. `keep_spans` are actual
resolved source seconds in playback order; reordering is allowed, overlap is not.
Essential roles are context, reasoning, example, reward; require at least one reward.

```bash
python3 scripts/design_evidence.py --input <clip>/design_evidence.json --out <clip>/design_receipt.json
```

Exit 0 verifies source identity, range integrity and retention of declared essential words.
It also writes `design_receipt.assembled.txt`. This is not an acoustic or semantic PASS:
word-label membership cannot certify intact phonemes or that the anchors were well chosen.
The builder must read the output; existing boundary/ear gates and blind review still apply.
Run after every span change and before assembly review. Record the receipt in the ledger.
The receipt hashes both design and actual kept-word transcript, so old receipts are not
evidence for a changed edit. Never alter punctuation to manufacture a complete ending.

## Repair and human review

An independent REVISE is a task to fix the cited words against source, not an automatic
delete operation. Preserve a good body when only its intro or tail needs work. After two
unsuccessful editorial repair cycles, withhold with the unresolved defect and attempted
repairs. Do not withhold solely for low cut density or repeatedly restore flawed clips
under a different quality label. Honor an explicit human-QA exception with exact remaining
issues; do not silently downgrade the review standard.

After human review, read the current native source ranges, ignoring stale markers. Record
kept/deleted groups and source seconds added/removed in retained clips. Movement and harmless
razors are not structural revisions. Keep user-reported effort separate from inferred metrics.
Preserve the approved timeline through finishing using the existing live-readback contract.
