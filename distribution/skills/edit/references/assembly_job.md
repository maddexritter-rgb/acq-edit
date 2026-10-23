# Assembly job execution contract

New source-indexed jobs use `edit.assembly-job/v4`. Existing v1-v3 jobs remain readable;
they do not silently acquire v4 authorization or review semantics. Historical approved plans remain
readable by the pure compiler library; they cannot silently enter a new build. Do not
migrate an active job without an explicit checkpoint. Editorial ingest uses the
AssemblyAI-first profile owned by `long-form-ingest`; reviewer model choice is not prescribed.

## Job and source registration

Save revision-specific JSON under the job's `10_WORK/`. A pin is an absolute `path` plus
file-byte `sha256`. Never overwrite evidence or reuse a review after content changes.

The job contains:

- `schema`, `job_id`, `builder_id` (actual execution identity).
- `skills`: use `assembly_job.py snapshot-skills --out SKILLS.json` and copy its `skills`
  list. This pins current instructions/scripts, including new files, for all five owners.
- `sources`: one row per supplied recording. Dialogue sources have `id`, pinned `media`,
  pinned `transcript`, `participants`, `relationship`, pinned `coverage`, and
  `coverage_gaps` (empty only when no tail/gap exists). Each gap has a disposition and
  pinned inspection evidence. Do not invent coverage for inaccessible media. In v4, a
  secondary camera may instead have `role:"picture_only"`, pinned `media`,
  `primary_dialogue_source_id`, `relationship`, and `audio_not_transcribed_reason`.
  It has no transcript or coverage claim; transcribe its audio only if missing speech or
  selected-camera sync requires it. Candidates reference dialogue sources, not picture-only rows.
- Each coverage file: `transcript` pin, inclusive zero-based `read_ranges`, `interactions`.
  Each interaction has `words:[first,last]`, `kind`, `speakers`, `disposition`
  (`candidate`, `excluded`, `deferred`, `non_content`), and a specific `reason`.
  Every word must be read and accounted for. Overlapping windows are allowed.
- `batch:{kind:calibration|continuation|full}`. A v3/v4 calibration authorizes exactly three
  clips. Continuations authorize at most five and require
  `previous_job` and `human_approval` pins. During validation no automatic continuation.
  A v4 `full` batch requires a pinned `edit.full-batch-authorization/v1` record whose
  `decision` is `APPROVE_FULL_BATCH`, whose `authorized_source_ids` exactly equal the job's
  source IDs, and whose `user_message` preserves the explicit complete-batch request.
  Preserve a real `message_id` when the client exposes one; omit it rather than inventing
  one when unavailable. Full batches have no total candidate cap, but candidates must still
  be designed in groups of at most five. “Full” means every distinct, complete,
  source-supported unit that survives review, not one clip per topic or a quota.
  When primary recordings become ready at different times, use successive v4 full jobs
  scoped to the ready dialogue source and its relevant cameras. Each job needs a recorded
  authorization for its exact source IDs; a session-wide inventory must account for all
  supplied recordings, and all passing packets may feed one review sequence.
- `candidates`: keyed by authorized clip ID, each with `source_id`, `design_group`,
  `kind` (`scripted_monologue`, `monologue`, `qa`, `l1_diagnosis`, `conversation_story`),
  pinned `editorial_worksheet`, `plan`, `source_words`, and `source_mapping`, `question_policy`
  (`retain`, `self_contained`, `not_applicable`), and source-specific `question_reason`.
  `retain` also requires `question_words` in candidate transcript indices. Keep only
  necessary question context, but never automatically drop it for a brand-only brief.
  Add `compiled`, `resolved`, `reconciled` pins as these actual artifacts are produced.
  For v4, add `reviews:{final_editorial:PIN}` only after Assembly Design's frame resolution and reconciliation.
  That one fresh review contains both the seven cold-viewer checks and the five source-fidelity
  checks against the exact executable dialogue. V1-v3 retain their historical two-review shape.
  `failed_revisions` pins rejected responses. Preserve them, but v4 does not mechanically hold
  a repairable candidate after an arbitrary count; stop only when the source cannot support a
  complete clip, the editor withholds it, or further attempts repeat the same unresolved defect.

For v3/v4 jobs, each candidate plan pins Assembly Design's
`cut.candidate-performance/v2` sidecar as `performance_evidence`. Regenerate old maps;
its complete
`interaction_words`, corrected word rows and reference audio must match the job's
source mapping and transcript verification. The plan's `performance_decisions`
records `event_id`, `action:keep|remove`, and a source-specific `why` for each
flagged event touched by selected words. These checks do not judge pacing or substitute
for listening.

Generate that complete performance map after assembly-design completes its own cold read and
source-fidelity self-check. A partial map or unaccounted selected event blocks acoustic/native
preparation, not the text-first editorial compile. V4 does not spend independent review calls
on preliminary drafts.

`source_mapping` uses `edit.source-mapping/v1`: `source_id`, `discovery_transcript`,
`candidate_words`, `media`, `reference_audio` pins, and `clock_basis:identical|measured`.
Add a pinned `sync_evidence` for measured clocks or separate audio extractions; preserve
the measured source/camera map there. Native adapters must apply that mapping, not assume
identical zero points. Mapping validation checks identity, not the truth of measured sync.

`edit.human-approval/v1`: `decision:APPROVE_NEXT_BATCH`, `reviewed_job` pin, verbatim
`user_message`, actual `message_id`. This records permission, not cryptographic proof.
Only record a message the user actually sent after reviewing the identified batch.

## Execution

1. `assembly_job.py check --job JOB.json` validates complete recorded coverage and pins.
2. Individually design authorized candidates using assembly-design. Each candidate has
   `editorial_worksheet.json`, `assembly_plan.json`, and `design_comparison.json`.
3. `assembly_plan.py compile --job JOB.json --plan PLAN.json --out COMPILED.json`
   checks authorization/design evidence before compilation. Register the compiled pin.
4. Run Assembly Design's performance inspection and boundary resolution. Treat `FUSED` as a boundary
   repair request: merge truly continuous selected spans, move to a source-native seam,
   restore the minimum inseparable connective words through a new plan, drop an optional
   segment, or mark the playable candidate for human listening. It is not a candidate-level
   rejection by itself. Use `assembly_plan.py reconcile --job ...` after resolution.
5. Run `assembly_job.py review-packet --job JOB.json --clip-id ID --perspective
   final_editorial --out PACKET.json`. Give the neutral packet and rubric to one fresh
   reviewer without builder rationale or prior verdict. It assesses the exact reconciled
   dialogue with all seven cold-viewer checks and all five source-fidelity checks. Preserve
   the returned JSON verbatim. A required lexical repair creates a new plan, resolution,
   reconciliation and one new final review—not two reviews of every intermediate draft.
7. `assembly_job.py prepare-native --job JOB.json --clip-id ID --out PACKET.json`
   recomputes compilation and reconciliation, validates the final combined review, and returns exact
   source spans. No audio or human acceptance is inferred from its structural checks.
   For a complete clip with unresolved subjective listening or lexical reconciliation,
   `prepare-provisional-native --job JOB.json --clip-id ID --cut CUT.json --out PACKET.json`
   validates the authorized source, current design evidence, exact source-frame selection,
   source-word ranges and explicit unresolved issues. Its review-only packet is distinct
   from the approved native packet and cannot satisfy the clean approval gate.
8. Native adapters call `validate_native_packet(path)` before emitting/importing edits.
   Run `check-native --packet PACKET.json` immediately before mutation as well as the
   live project/sequence guard. The shared live-review XML builder supports
   `--assembly-packets` for identity-clock single-source packets; measured multicamera
   adapters must consume the verified mapping and use the same validator. The existing
   `live-clip/scripts/live_review_xml.py --multicam-plan PLAN.json --out REVIEW.xml`
   branch uses `edit.native-measured-multicam-plan/v1`: a pinned current native packet,
   that packet's exact pinned `sync_index`, a pinned guest camera, explicit tiled
   `audio` and `picture` intervals on the selected assembly frame clock, and a review
   sequence name. The audio intervals identify one speaker/source at every frame;
   picture intervals name each occurrence, cite pinned visual evidence and carry one
   full-frame panel or independently framed left/right panels. Panel `framing` contains
   editable native Motion `scale` and normalized `position`, plus Crop percentages for
   `left`, `right`, `top`, and `bottom`. Picture intervals may subdivide a continuous
   audio route without creating an acoustic seam. The adapter verifies source bounds,
   master-to-child mapping direction, at least three accepted anchors, residuals,
   frame rate, frame rounding and one-frame maximum item drift. It writes an adjacent
   `.adapter.json` receipt with its path/hash, plan/packet/sync pins and XML hash.
   Premiere 26 may ignore XMEML Crop. After import, call the same adapter module's
   `apply_native_layout(RECEIPT, PROJECT)` under exclusive bridge ownership. It sets
   intrinsic native Motion/Crop per named source-linked picture item and saves/reopens
   the exact project for value and one-audio-track readback. The XML and receipts are
   construction evidence, not audiovisual verification: inspect the visible panels,
   trial-trim a picture boundary, check sync, and listen to the assembled audio. Keep
   the identity-clock branch unchanged.
9. Reconcile saved native spans, then perform the existing native assembly review and
   handoff gate. Native item changes invalidate that review. Stop for human approval.

The compiler library remains a structural primitive used by tests and historical tooling;
only the job-aware CLI and guarded native path are supported for new jobs. Arbitrary
scripts can bypass them: a native sequence without matching current packets/readback is
UNVERIFIED, never silently grandfathered into a pass.

## Independent reviewer response

Return `edit.editorial-review/v1` with `clip_id`, `perspective`, actual `agent_id`,
`packet` pin, `invocation` pin, `verdict:PASS|REVISE|UNKNOWN`, `checks`, and `fixes`.
The orchestrator provides the invocation identity/path before review; retain the actual
tool output in the run ledger. The invocation file has `agent_id`, `tool_call_id`,
`packet` pin and `fresh_context:true`. Do not invent an identity when delegation failed.

Every check has `verdict`, inclusive source `word_ranges`, exact `quote`, and `reason`.
Cold-viewer checks are the seven audit-script criteria: `content_unit`, `hook`, `retain`,
`reward`, `goodwill`, `value_compression`, `audience_growth`. Cite selected words only.
Fidelity checks are `context`, `question`, `qualifications`, `causality`, `omitted_value`;
they may cite omitted source words. Follow the rubric's source-fidelity companion section.
`fixes` is a list of `{required:boolean,evidence,edit}`; PASS cannot contain required fixes.
Different perspectives need separate actual reviewer executions, distinct from builder.

Checks can reject fabricated quotes, stale pins and recorded identity reuse. They cannot
authenticate a forged tool response or replace editorial judgment. Preserve raw responses
and never describe evidence validation as human acceptance.
