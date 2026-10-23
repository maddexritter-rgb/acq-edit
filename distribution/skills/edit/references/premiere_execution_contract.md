# Native Premiere execution contract

Scope: mechanical execution and evidence for the existing editing skills. The default Premiere Agent replaces the old connector through exact-project stage scopes, without adding an editorial approval gate. The shared adapter supports scoped editing and isolated research; the four stage drivers have combined synthetic host acceptance on 26.3.0. General production compatibility remains unproven. Use only routes whose actual implementation and acceptance evidence are available.

## Shared adapter usage

`_shared/premiere_bridge.py` owns a persistent stdio MCP client, with an explicit `edit.premiere-bridge-profile/v1` profile. It resolves `default.json` unless explicitly overridden and supports `scoped-edit`, `scoped-reframe` and disposable `lab` profiles. Follow [startup and scope setup](premiere_start_here.md). The Lab remains the only operation/job journal; the adapter introduces no second server. Keep one client open for the stage so closing a one-shot process cannot terminate queued native work.

The stage runner supplies `edit.native-operation/v1` with `stage`, `operation_id`, `tool`, `arguments`, `target` (`project_path`, explicit `sequence_id`, `expected_revision`), `intended_changes` and `protected_state`. Persist the plan and returned response in the stage's existing work directory. The adapter returns a plan fingerprint alongside the original connector job; this is not the connector's request fingerprint and does not replace its journal.

`submit()` checks profile, fixture path, existing operation/job IDs, catalog eligibility, live host version and the fresh target/revision before guarded async submission. Existing IDs are inspected and refused for resubmission. Lab testing permits eligible but host-unverified operations on disposable projects; this is not production acceptance. The stage owns its concrete protected-state and meaningful postcondition comparisons—the declarations alone do not enforce them.

Poll `reconcile(operation_id)` on the same client until the original job settles. It never retries. Unknown/running/missing receipts remain unresolved; inspect native state and the connector journal. A transport timeout includes `request_id`; `transport.receive(request_id)` can collect that exact late reply without resending. `close()` refuses unresolved native jobs or pending protocol replies. There is no automatic recovery after a caller crash; reuse the saved stage receipt to inspect the original IDs, never submit replacement work based on a missing response.

The transport has executable tests against the actual Lab MCP/SDK using an isolated temporary runtime with no Premiere or UXP connection. This proves protocol interoperability and schema validation only. It does not establish native editing, safe job shutdown on every host, persistence or rendered output.

## Native reframing

The staged reframing driver accepts `--bridge-profile <absolute-profile.json>` for inspection, plan-only work, fresh duplicate/reframe and existing-X seam repair. Its default is the new connector; the old mailbox fallback is removed. The fresh route now runs through typed duplication, Motion application and readback; it never falls back to production.

`inspect_reframe_state` supplies the existing planner's Motion fields plus native IDs, exact ticks and a fresh bounded snapshot revision. New seam plans retain that bridge baseline. An old unbound plan must be re-inspected/replanned before using this route. The tracking and seam-selection algorithms remain owned by the existing driver.

`premiere_reframe_bridge.py` maps those plans to `lab_repair_anchor_x_keys`. The operation checks all targets before writing, changes only existing Anchor X values, checks every resulting key, and compares all other fields captured by the Lab snapshot. It does not add/remove keys or attempt rollback. Snapshot coverage does not include every Premiere property; native interpolation readback remains unverified.

The stage saves its original operation ID in a sidecar before submission and refuses automatic reruns when that sidecar exists. A prepared sidecar alone does not establish whether dispatch happened. After a successful repair response it saves through a separate guarded operation, then checks the timeline revision again. A save response is still not reopen/persistence proof. Failures stop before dependent writes and retain the original receipts for reconciliation.

`lab_duplicate_vertical_sequence` clones the exact inspected source in the same project, identifies the single new sequence from the ID-set difference and compares cloned source ranges/audio/settings/other bounded fields. Only new sequence/item IDs and the intended canvas may differ. It separately checks the original source after clone, resize and activation. The binding retains a duplication sidecar and refuses replay. No save or rollback is implicit, and native AV link-group membership is not verified by matching source ranges.

`lab_apply_reframe_motion` consumes the existing planner's static Position/Scale and sparse Anchor Point keys. The binding adds the exact source-in tick offset using rational arithmetic, coalesces identical same-time keys from the single-frame planner case, and rejects conflicting or out-of-source keys. The typed operation checks every target before writes, requires static Motion and verified forward unit-speed playback, and compares every resulting key plus all other bounded snapshot fields. The binding performs independent structured readback before a separate guarded save and again afterward. The fresh route requires a new work directory so prior plans and uncertain attempts remain intact.

These routes retain their per-operation evidence limits even when enabled by an exact-project stage scope. Linear interpolation is requested through the native setter but cannot yet be read back. The snapshot is bounded; immediate checks and a save response do not prove persistence, rendered framing, native AV link groups, or all Premiere properties. Save/close/reopen and rendered acceptance remain required before claiming acceptance for the current task.

## Native music application

→ Use skill: `music`, with its [native bridge reference](../../music/references/native_music_bridge.md), for selection/audition receipts, calibrated units and the owned music envelope. Current coverage includes an explicit source/empty-range placement plan followed by the owned envelope. The combined synthetic placement/envelope route has persistence and rendered audio-model review; replacement and EQ remain unfinished.

`execute_operation()` in the shared adapter now owns stage attempt sidecars and original-job waiting for both reframe and music. It does not create another connector journal or promote a reported success to persistence/listening proof.

## Before a native stage

Resolve the explicitly selected bridge profile: connector identity, host version, transport, operation schema and backend-specific evidence. A discovered tool is not an accepted route. Keep unaccepted research operations confined to disposable projects; never silently fall back between connectors or backends.

Take a fresh project/sequence snapshot. Prior receipts are comparison baselines, not current truth. Resolve each affected item by native identity plus expected source/timing state. If the API lacks stable item IDs, use a validated composite locator and reject ambiguous matches. Coordinate exclusive bridge ownership before writes.

Immediately before a target-dependent edit or export, verify the active project path
and sequence UID again. An activation response can report success while subsequent
native readback or the visible tab still shows the prior sequence. Resolve that
disagreement through the selected supported route before proceeding; an output
filename is not sequence identity. Quarantine any export made from the wrong target
as invalid evidence rather than relabeling it as the intended review.

Consume the creative plan already owned by the current skill. Preserve its source-word selection, camera decisions, semantic caption cards or music audition choice. A native failure does not authorize redesigning that plan.

## Operation contract

Every mutation needs a durable operation ID bound to its exact arguments, target identity and state preconditions. Keep exact tick values as decimal strings and frame rates as rationals. Operation-specific expected component, parameter and item state supplements the general snapshot.

Declare the intended changes and the state to protect:

| Stage | Intended changes | Protected state |
| --- | --- | --- |
| Assembly | Source-linked placement from compiled selections | Selected words, order, source ranges and planned gaps |
| Reframe | Approved picture construction and per-item Motion | Dialogue cuts/audio; existing captions/music; all Motion fields outside the requested change |
| Captions | Identified native Graphics and dependent reveal/layout boundaries | Picture edits, Motion, dialogue and music |
| Music | Owned music item, source section, gain/fades and planned processing | Dialogue cuts/channels/processing, captions and picture |

Use native locking/transactions only where the selected operation supports them. CEP/QE batches do not promise atomic rollback. Record per-step results and stop dependent steps after uncertainty.

A timeout, disconnect or partial execution is not permission to retry. Inspect the original operation/job ID and reconcile actual host state. Do not generate a replacement ID or replay through another backend. Keep long-running jobs attached to their original identity.

## Stage handoff

Keep these evidence dimensions separate:

- Execution: what the backend reported, including failures and uncertainty.
- Immediate readback: which meaningful postconditions and protected fields were compared.
- Persistence: save → close → reopen → structured readback at the stage checkpoint.
- Rendered review: frames/audio actually inspected, with their timeline ranges and artifact paths.
- Human approval/editability: only actual user decisions and any required click/edit-box checks.

Save/reopen at meaningful checkpoints, not after every keyframe. Re-snapshot before any recovery or subsequent revision; do not restore stale plans over user changes. Follow the existing stage's review boundary. Focus revision QA on changed/dependent ranges while retaining the existing final-review requirements.

## Recorded handoffs and focused review

`_shared/premiere_stage_handoff.py` is an offline artifact helper, not another bridge or operation journal. The staged fresh reframe and music placement/envelope drivers write `edit.sequence-stage-handoff/v1` after their independent readback/save checks. The record binds original operation receipt hashes, project/sequence identity, before/after native revisions, bounded snapshots and changed native item IDs. The staged assembly and caption-transfer drivers write `edit.sequence-creation-handoff/v1`: it records the sequence as absent before creation, preserves the actual whole-project baseline, and binds the new native snapshot/revision to the original import receipt. It never invents an empty native timeline. These drivers have combined synthetic native acceptance; each new run still needs its own evidence. Seam repair is not yet connected to this helper.

Changed picture and audio ranges use half-open integer tick strings. Item-local changes request review of the whole affected item; movement/removal includes the former location, so vacated frames are not omitted. Touching/overlapping intervals merge; distant ranges remain distinct. Track metadata or sequence settings changes request broader review. Boundary/dependent-effects review and the normal final review still apply; these ranges do not certify pixels or listening.

A next-stage runner can call `assert_fresh()` with an actually fresh native snapshot/revision and the prior handoff. Any target, revision or bounded-state mismatch requires inspection/replanning; the helper never restores old state. Optional chaining hashes the prior handoff without replacing it. Callers still own stage-specific protected-state checks; this record alone cannot certify every Premiere property. Local artifact hashes bind evidence but are not tamper-proof host attestation.

The helper keeps execution/readback separate from reopen persistence, rendered review, listening and human approval. No downstream skill may interpret a handoff file as approval of those unperformed checks. Store its path in the existing run ledger rather than inventing another editorial workflow.

## Bounded assembly recovery and audio precision

→ Use skill: `assembly-design`, specifically [audio-precision.md](../../assembly-design/references/audio-precision.md), for independent sample edges and the exact compiled-word/picture contract.

If a high-level import cannot serialize the existing project within its payload
bound, stop and preserve the actual failure. A tested disposable recovery used a
guarded typed XML import, an independent compiler-derived placement comparison,
whole-project preservation checks, and then the existing audio-plan driver. This
is a bounded research route, not an automatic fallback: confirm whether the first
attempt dispatched, keep fresh guards and ownership, and do not enlarge authority
or modify the installed connector to bypass the limit.

Keep operation-specific handoffs honest. A generic import or duplicate receipt is
not a compiled-import creation receipt; never substitute tool names or manufacture
that schema. Retain its actual receipt and independent checks. A subsequent audio
stage may supply its own valid handoff without pretending the earlier operation
used the canonical import driver. Save/reopen checks must include native AV link
groups separately; equality of timing fields alone cannot prove linkage.

## Assembly placement readback

The staged `scripts/bridge_readback_guard.py` accepts the existing sequence-structure shape. It prefers `startTicks`, `endTicks`, `inPointTicks` and `outPointTicks`, and reports how many fields fell back to legacy seconds. Exact values must be on the frame grid; malformed ticks never fall back to seconds.

For a build made by `review_xml.py`, pass its existing `.expected.json` through `--expected`. This optional comparison checks primary V1/A1 counts, media paths, exact source/timeline ranges, normal forward playback and online-source state. Exact planned gaps are accepted directly from that receipt. It adds no new paper-cut format or editorial approval requirement.

The Lab's `get_full_sequence_info` wrapper now exposes the exact timing fields and attempts audio reversal/offline readback as well as video. These changes have mocked execution tests; live host acceptance is still pending. Missing native fields stay unverified and prevent the stronger expected-assembly comparison from passing. Legacy seconds-only readback remains available for its original structural scope.

Paired media/range equality does not prove Premiere link-group membership. The guard explicitly leaves native linkage, persistence, rendered review and listening unverified. Additional tracks need the owning stage's protected-state comparison; V1/A1 receipt agreement cannot certify the whole sequence.

## Mechanisms that must remain distinct

- Item-local Motion versus source effects: local framing must not alter every use of the source.
- Editable native Graphics versus caption tracks and generic MOGRTs: retain the approved Graphics donor builder until another mechanism passes equivalent acceptance.
- Prepared caption project versus active weekly project: never overwrite an open project; validate the sequence-transfer mechanism before adopting it.
- Music selection versus application: consume the reviewed selection receipt and resolve actual parameter units before gain automation. Preserve existing eligibility and listening requirements.

Connector implementations own tool schemas and backend routing. Keep skill instructions focused on stage intent and postconditions rather than duplicating the connector catalog.

## Scoped production reframe

The upgraded reframe profile supports an expiring exact-project scope without widening the Lab fixture root. → Use [horizontal-to-vertical advanced native reframe](../../horizontal-to-vertical/references/advanced-native-reframe.md) for its accepted operations, preparation and evidence requirements. Other stage tools use the default scoped-edit profile; unrelated research tools remain fixture-only.
