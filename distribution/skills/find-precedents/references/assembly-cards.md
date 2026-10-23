# Live assembly context from the shared editorial brain

This is distinct from final-only historical case memory. The private Supabase project
is the operational source of truth for active assembly playbooks and cited decision
cards. `assembly-design` chooses source words; this skill owns retrieval only. Never
put credentials, full transcripts, footage, or unreviewed document dumps in a prompt.

## Required preflight and problem search

Configure the endpoint and project ref in `~/.config/editorial-brain/context.json`.
Store the dedicated function-only token in `~/.config/editorial-brain/read_token`,
owned by the user with mode `0600`; it is **not** a Supabase secret/service-role
API key. For first-time setup, the user runs
`python3 __ACQ_SKILLS__/find-precedents/scripts/setup_read_token.py` interactively,
then pastes the value it copies to the clipboard as the `EDITORIAL_BRAIN_READ_TOKEN` Edge Function
secret. Do not run the setup script for them or capture its output. Environment
variables `EDITORIAL_BRAIN_FUNCTION_URL`,
`EDITORIAL_BRAIN_PROJECT_REF`, and `EDITORIAL_BRAIN_READ_KEY` can override those
files for managed runtimes. Never put the token in a skill, shell history,
repository, or handoff. The same portable client works in Codex and Claude Code
without depending on whichever MCP plugin happens to load:

```bash
python3 __ACQ_SKILLS__/find-precedents/scripts/editorial_context.py \
  --format q_and_a --preflight \
  --out "<project>/10_WORK/brain/q_and_a.preflight.v1.json"
```

Before designing **each** clip, run this **per-clip preflight** for that content unit's
format, with a new `--out` path per clip. Add `--reading-overlay l1` for an owner-diagnosis Q&A, and/or
`--reading-overlay workshop` for Workshop-style material. The result must identify
the expected Supabase project and return hash-valid **universal** and matching format
playbooks plus the ordered, hash-valid `required_reading.policies` source bodies.
Read both playbook `body` fields and every returned `source_body` in full before
selecting words. Repeat the preflight and the full reading for every clip, single or
batch; never reuse another clip's receipt or an earlier read. A failed request, wrong
project, or absent/invalid playbook or required document means
`EDITORIAL_BRAIN_UNAVAILABLE`: stop new design. There is no local-reference fallback.
This checks knowledge availability, not whether a clip is good.

The active playbooks govern conflicts in preserved source SOPs. Their older
duration, money-hook, score, and audit commands are not newly active merely because
the original document is required reading. Classify the **content unit**, not the
recording: a podcast owner diagnosis is a Q&A with the L1 overlay; an ordinary
conversation uses the podcast pack; a Workshop monologue uses monologue plus the
Workshop overlay. Do not load all format packs into every clip.

After reading the *complete* interaction, name its concrete editorial problem and
query again, for example:

```bash
python3 __ACQ_SKILLS__/find-precedents/scripts/editorial_context.py \
  --format q_and_a --problem "question context and missing reasoning" \
  --project-prefix /path/to/current/project/ \
  --out "<project>/10_WORK/brain/clip_01.question-context.v1.json"
```

Pass each held-out source prefix with `--held-out`. Use at most three concise problem
queries and at most five non-duplicate cards total. Read each card's evidence class,
status, source, example and exception. `development` and `calibration` are decision
aids, never verified historical finals. Zero genuinely matching cards is valid, but
the active playbooks are never optional. Do not force an irrelevant card merely to
fill a quota. The new source interaction controls the choice.
This later problem-search call intentionally omits full required reading; the clip's
own preflight already supplied it. Record the playbook and policy versions, source-body
hashes, and which guidance changed or was rejected for an exact source-word choice.
Production retrieval excludes development cards by default; use
`--include-development` only when the task explicitly calls for unsettled research.

`verified_final` with evidence class `NATIVE_FINAL_SELECTION_VERIFIED` means the
cited spoken choices were checked against an inspected finished native sequence
under its campaign authority. It does not establish a delivered export, acoustic
edge review or human approval. Read the scoped packet when the decision depends on
the underlying evidence. The observed recording format is separate from the card's
applicable formats; inspect the transfer rationale and exception before applying it.

`--out` saves the validated live response, request echo, UTC fetch time, and response
hash; it refuses to replace an existing revision. Read the saved bodies, not only
the receipt metadata. This is a per-clip evidence snapshot, not a second knowledge
store or an offline fallback. Every new clip requires another live preflight. If a later problem lookup returns changed playbook versions/hashes,
fetch and read a fresh preflight, record the transition, and reconsider affected
choices before continuing; do not silently mix guidance versions.

Search currently ranks problem words within the requested format; it is not an
embedding model. Query the editing failure (for example, "competing hooks" or
"missing causal bridge"), rather than a whole transcript or broad topic. If results
are weak, refine once with the concrete failure and inspect the exceptions; never
force the top-ranked card into the edit. The existing three-query/five-card cap
applies across refinements. Source exclusions match the stored upstream `source_uri`,
not card IDs or packet filenames: include remote URI aliases with `--held-out`
when a local project prefix alone would miss them. Client validation also rejects
wrong-format, duplicate, excluded-source, or unauthorized development cards.

## What belongs in each knowledge layer

- Canonical skills hold the stable procedure, ownership, source-word and frame
  contracts, and the requirement to retrieve. Do not copy the entire library into them.
- Active Supabase playbooks hold the reviewed universal and format-specific
  decision principles. Required-reading policies select the source bodies that
  must accompany those principles; the whole archive is not required every time.
- Decision cards hold conditional choices: problem, source example, action,
  reason, applicability, exception, evidence class, and revision. One comment does
  not become a universal rule. Brand-specific guidance stays in the brand's external
  profile/source records; the reusable skill stays neutral. Ranked decision cards still filter by format, so inspect their applicability before transferring a case. Separately, optional brand/production/stage selectors return scoped policy bodies; see [scoped production policy](../../edit/references/scoped-brand-policy.md).
- Versioned source documents retain provenance and original guidance, including
  older material and disagreements. Source instructions are evidence, not authority
  to override the user's current request or an active playbook.
- Actual editor decisions pin the original and revised cuts and explain what
  changed. → Use skill: `editorial-brain-ingest` for curation and promotion.

Classify each content unit before choosing its pack. New unsupported formats must
be identified explicitly and reviewed before adding an active policy; do not silently
use monologue for every source. Tightening, factual continuity, personality, and
acoustic precision remain separate judgments. Retrieval success cannot certify a
natural seam or a compelling payoff; listen to the selected source joins and test
editorial improvements on source-held-out footage through the assembly evaluation route.

## Feedback boundary

Only after the human editor reviews a timeline, capture an actual `keep`, `change`,
or `delete` choice with its reason, original source-word selection URI, revised URI (if
any), and the card IDs shown/applied. The private `editorial_feedback` table exists,
but do not fabricate a review or write to it from the model's own assessment. A
repeated correction is a promotion candidate, not an automatic skill rule.
