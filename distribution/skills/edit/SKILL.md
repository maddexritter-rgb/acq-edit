---
name: edit
description: >
  Master editing orchestrator for raw footage to finished clips: monologue, Q&A, hotline,
  podcast, listicle and multicam. Routes editorial construction to assembly-design, detects speaker/camera
  count, and routes to source-intel, assembly-design, horizontal-to-vertical, caption-clips, book-doodle
  (approved drawing cutaways), render, with pre-render construction checks and optional requested audits. Supports Premiere Agent Lab and Filmcraft execution. Assembly requests stop at
  timeline review; explicit end-to-end requests continue through finishing and local export. Use for mine clips, cut clips,
  pull clips, make clips, make shorts, shortify, edit raw footage, find good moments,
  Q&A clips, hotline clips, podcast clips, multicam edits and text-based cuts.
---

# Edit — orchestration, not a second editorial designer

## Scoped production guidance

→ Load [scoped production policy](references/scoped-brand-policy.md) for the run's brand and source production family after starting the run clock.
Pass its pinned stage policies through the existing handoffs; consume orchestration/audio/delivery defaults without adding a new quality gate.

Current-revision handoff: pass the assembly-owned format and picture plan to
`horizontal-to-vertical`, and its exact picture-cut frames plus mapped speech clocks
to `caption-clips`. Recompute those handoffs after spoken edits; never reuse stale clocks.

## Default: timed construction, no audit loop

Start the run clock as the first executable action, before reading further skills,
notes, or scaffolding. Follow [timed execution](references/timed-execution.md).
Default runs build once from source-inspected decisions and check construction before
export. Model audits, second-ASR sweeps, scorecards and independent review loops are
opt-in when the user asks for an audit/strict evaluation; they are not delivery gates.
This policy overrides older audit mandates in this skill, RUNBOOK and routed sibling
references during a normal `/edit` run. Keep targeted source inspection for actual
ambiguities and a single post-export file-integrity check. Do not certify listening
or approval from a machine check.

→ Use skill: `assembly-design` for [pre-render construction](../assembly-design/references/pre-render-construction.md).


For any Premiere access, follow [Premiere Agent startup and advanced stage routing](references/premiere_start_here.md). Use the configured new bridge by default; if MCP tools are missing in this chat, use its CLI. Keep this skill’s existing creative scope and read-only limits.


Use the canonical sibling skills from this directory. Approved timeline edits are
preserved unless the user explicitly requests a recut. Choose run mode and backend using [execution backends](references/execution-backends.md).
Preserve the current project's backend. Assembly-only requests stop at review;
explicit end-to-end requests continue through finishing and local export. Publishing
and external delivery require separate authorization.


For Premiere final timeline delivery, follow [exact native export](references/native-export.md).
It preserves current edits and export marks; failed black-frame QA never auto-trims content.

## Topaz: explicit request only

Topaz enhancement/upscaling is disabled by default. Run it only when the user explicitly requests Topaz processing for identified media; storing credentials, asking for crisp footage, or invoking `/edit` does not authorize processing.
→ Follow [Topaz API workflow](references/topaz.md), including the user’s picture-lock and manual-grade checkpoints.

## Backend routing

→ Follow [execution backends](references/execution-backends.md) for mode, authorization
and backend choice; [Filmcraft execution](references/filmcraft.md) for its code and
command route. Both routes use the same sibling skills and source decisions.

## Native bridge handoffs

Before Premiere native work, follow the [shared execution contract](references/premiere_execution_contract.md) on the configured default profile and exact-project stage scope; research routes remain confined to disposable projects.
Carry the fresh target, source linkage/timing, stage-owned items, protected state, changed review ranges and separate verification receipts in the existing run ledger.
→ Use the owning sibling skill for each stage's creative plan and postconditions; the bridge contract adds no editorial approval gate.

## Default assembly: transcript → designed cuts → 16:9 timeline → editor

For a request to make assembly cuts, stop at a playable, source-linked 16:9 timeline in the selected backend. The editor reviews it. Do not require an audit, independent review, score,
worksheet, job hash, provisional packet, or approval receipt before placing a complete
designed clip. Those are optional strict-mode tools only when specifically requested.
Use `long-form-ingest` to obtain one primary dialogue word transcript; use
`assembly-design` to turn promising interactions into exact spoken hook → reasoning/story
→ payoff assemblies, selecting only the words and passages that earn that arc. The
active session model is the editorial designer; no second model API call is needed.
Assembly-design's live Supabase playbook preflight is required before **new** moment
selection; if unavailable, stop the design stage and report it rather than silently
falling back to older SOPs. This does not add an audit before the editor's timeline.
The design is compiled against the source transcript into literal playback text, which
the model reads and repairs before frame resolution. Assembly Design owns **every
selected span and internal edit**, tries measured quiet-gap source frames and
resolves paired audio edges using its default waveform-first method without deleting selected speech, then builds
the source-linked 16:9 review timeline via the
RUNBOOK. A topic window, whole Q&A, or long
monologue excerpt is a lead, not a clip. Do not send it to Premiere unchanged merely
because its outer edges are clean. A truly continuous clean take may remain one span,
but explicitly identify its spoken arc and why nothing inside should be removed. If
most of a batch becomes one-span excerpts, stop selecting more and redesign the batch;
do not present it as finished assembly work. Build the first useful cuts promptly and
add more as found.
Check media/ranges, source-word preservation, exact native picture/audio clocks and links through Assembly Design’s existing verification. No new editorial audit gate is added.
This technical readback is not an editorial audit. Never label the timeline approved.

## Ownership and order

1. Reuse the active ISO-week ACQ project package; scaffold it once with `new_project.sh <YYYY-Www>_Weekly_Edit` if absent. Copy sources into its brand/shoot `00_SOURCE` subfolder, never move originals. Prioritize the
   primary dialogue source and let unrelated camera/source copies continue in the
   background. Use `footage-fetch` for downloads and `source-intel` for camera/audio
   inspection. Related cameras belong to one session.
2. Use `long-form-ingest` for AssemblyAI-first transcript identity, speaker turns,
   complete interaction indexing and correction evidence.
3. Use [assembly-design](../assembly-design/SKILL.md) for complete-source discovery,
   moment classification, exact spoken construction, targeted performance inspection,
   source-frame resolution, camera/layout decisions, and source-linked native construction. It reads its retained
   cutting playbook and owns any word/order repair. AssemblyAI locates words; shared
   waveform/paired-boundary code supports inspected decisions without editorial authority; a refused
   edge is provisional on the review timeline, not permission to shorten a clip.
4. Follow [RUNBOOK.md](RUNBOOK.md) for native mechanics. Assembly-review mode stops
   after the 16:9 timeline; an explicit end-to-end run continues. An independent
   editorial review is strict mode only.
5. After cuts approval, or within the authorized end-to-end run: use `book-doodle` for the optional recommendation checkpoint,
   `horizontal-to-vertical` to implement the assembly-owned picture plan through native framing, `caption-clips` for captions, and
   `music` when requested/applicable. Paid workshop finishing routes to `ad-edit`.
   Opening text headlines are not part of this toolkit. Preserve assembly-only stopping points.
6. Export through RUNBOOK after Assembly Design's pre-render check. Verify file
   completion, expected streams/dimensions/rate/frame count once; repair a concrete
   failure only. Audit skills remain individually usable or opt-in for requested
   strict evaluation. Publishing is never implied by editing.

Do not duplicate these capabilities here. Candidate windows are not cuts; no selector,
legacy CLIPPER prompt, regex editorial score, or project-local generator replaces
assembly-design. Historical lift tables are contextual observations, not rules imposing
question suppression, duration bands, keep percentages, chronology or cut density.

## Job control — optional strict mode

Only when strict mode is specifically requested, read [references/assembly_job.md](references/assembly_job.md). Create a versioned
`10_WORK/assembly_job.json` before designing; register the job's exact source set, coverage,
participants, camera relationships, authorized candidates, and skill hashes.
Use `edit.assembly-job/v4` for new jobs. It pins the editorial worksheet before the plan,
then resolves frames within Assembly Design before spending an independent review on the exact executable dialogue.
For a full-source batch, establish a playable first group after ingest coverage; continue
source mining in design groups of at most five while adding complete candidates to the
native review sequence. Do not finish optional camera sync or every candidate's paperwork
before building the first reviewable group.
An explicitly authorized full batch may use successive source-scoped v4 jobs as primary
recordings become ready; keep one session-wide source inventory and one Premiere review
sequence so later jobs cannot silently omit supplied recordings.
Its default calibration and continuation limits remain unchanged. When the user explicitly
authorizes complete-source mining without calibration, use the source-scoped `full` batch
mode: inventory the entire source, authorize every viable candidate, and design in bounded
groups of at most five without imposing a total clip quota. Existing v1-v3 jobs retain their
original semantics until explicitly repinned.
`scripts/assembly_job.py` validates the job; assembly-design's compile CLI requires it.
Its native-preparation command checks the exact reviewed and reconciled revision.

Brand identity does not exclude audience/questioner speech. Route each interaction from
the dialogue, not filename, camera count or brand. Missing guest picture does not mean
missing guest audio. Human-selected drafts use
[references/l1_draft_finishing.md](references/l1_draft_finishing.md), not a new mine.

A job record is an auditable execution contract, not proof that somebody read/listened.
Use actual tool results for source checks, reviewers and native readback. No fake PASS.
Verify each stable project-owned media copy once, then reuse its validated digest for
candidate compiles. Source-word and clock pins remain checked on each candidate.
If the active skills changed since the job was pinned, stop that batch and explicitly
adopt the new revision at a safe checkpoint; never silently migrate a live job.

## Project and approval safety

- For new Premiere work, keep one active Premiere project per ISO production week across
  assembly, picture, captions, music, and export. Reuse the weekly package and
  `.prproj` named in the vault's `AGENTS.md`; create sequences/bins for each shoot
  and stage, never a competing active `.prproj` per stage. Existing projects stay
  where they are. Use bins `01_FOOTAGE`, `02_AUDIO`,
  `03_SEQUENCES/01_ASSEMBLY`, `03_SEQUENCES/02_FINALS`,
  `03_SEQUENCES/03_REVISION_HISTORY`, and `04_GRAPHICS`. Keep one combined
  `01_CUTS__<session>` review sequence and one combined
  `02_FINALS__<session>__CURRENT` sequence. Stable clip IDs and readable markers
  connect both timelines to `_project.json` and the decision records.
- Before each revision round, duplicate the current finals sequence into revision
  history and read back its name and UID. Revise only the current combined finals
  sequence, then log feedback, affected clip IDs and exported versions using
  `project_library.py`. Do not flatten editable media to make revisions.
- After completion, archive the entire project-owned package through
  `project_library.py` only after the 14-day hold and checksum/restore gates.
  Keep local files until Premiere reopens the restored package without offline media.
- Before every Premiere mutation, coordinate bridge ownership and verify exact live
  project/sequence identity. Never change an unrelated active project.
- In optional strict calibration, authorize exactly three candidates. Only authorized candidates may be designed/built. Discovery may
  continue. A structural or editorial PASS cannot authorize the next batch.
- An explicit v4 `full` batch is not calibration. It authorizes all viable candidates from
  the exact pinned source set while retaining the per-design-pass limit of five.
- User changes on the timeline become the truth. Read them back; do not regenerate
  old selections over them. Scope revisions to the requested layers.
- Preserve the frozen assembly's exact source spans and the editor's revised
  native source spans by clip ID. Attribute only reasons the editor actually gave;
  send this evidence to `editorial-brain-ingest` after review, without adding an
  automatic approval gate or promoting one case into a universal rule.
- Retain every rejected revision. Do not reroll unchanged work for a different verdict.
  In v4, a numeric failure count does not kill a repairable candidate: make the specific
  source-supported repair, place subjective but playable uncertainty in editor review,
  and withhold only when the source cannot support a complete clip or the same defect recurs.

## Evidence and precedents

Use the shared `audit-script` rubric for editorial judgment. Independent reviewers
receive neutral dialogue/evidence, not the builder's desired verdict. Structural,
editorial, acoustic, native and human statuses are separate.

For a user-selected positive precedent, verify the exact approved revision and correction
history. This is explicit calibration, not automatic memory promotion. Stage-memory
retrieval follows [references/stage_memory.md](references/stage_memory.md); an empty
retrieval does not excuse skipping a user-supplied benchmark. Never treat an earlier
shortlist or failed project as approved.

## Technical operations

RUNBOOK owns native operations and delivery. Use `render` for an explicitly
requested headless route, including the selected Filmcraft end-to-end route; preserve its manifest/cache workflow and rerun delivered-file
file-integrity checks after renders and revisions; do not start an audit loop. Do not use legacy window/length/ending heuristics to
rewrite a source-indexed assembly: resolve conflicts through its current selection,
acoustic evidence and editorial review. Never restore removed words to satisfy a helper.

Load detailed references only for the current capability. Assembly-design routes its
own format references; finishing skills own current layouts, presets and audio rules.
