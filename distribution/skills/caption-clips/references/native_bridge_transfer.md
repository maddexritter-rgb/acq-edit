# Native Graphics bridge transfer

Use the default Premiere Agent profile and exact-project captions scope from [startup](../../edit/references/premiere_start_here.md). Follow the shared Premiere execution contract. The existing `premiere_native_cards.py` builder owns text, profiles, semantic cards, reveal clocks and saved-file verification. This adds transport evidence and identity mapping, not another caption engine.

## Prepared artifact checks

`premiere_caption_handoff.py --project <prepared.prproj> --receipt <builder.receipt.json> --manifest <resolved-manifest.json> --output <handoff.json>` checks the original builder input hashes, invokes its verifier, binds exact rational-frame/tick times, and rejects contradictory generated-media canvas descriptors. The output is offline preflight evidence only. It sends no Premiere commands.

Generated Graphics may share the same synthetic media implementation/path identity through multiple cached Media/VideoStream objects. A tested donor had both 2160×3840 and 1080×1920 descriptors for that identity. Its imported caption items looked correct in a render, but the saved Graphics media reverted to the larger frame and failed the existing edit-box geometry verifier. Normalizing all matching descriptors in a separate prepared copy fixed that bounded fixture.

The staged `retarget_native_donor.py --normalize-generated-aliases` option applies that correction to exact generated donor identities in its output copy. Its default behavior is unchanged. It rejects missing/non-Graphics aliases before writing; the source is never overwritten. This option has one native-equivalent fixture proof, not universal donor compatibility. Require save/reopen and the existing geometry verifier on each transferred result. Never repair the project file while Premiere has it open.

## Identity and postconditions

Snapshot all destination sequences immediately before transfer. Reuse the shared adapter's original operation receipt; do not retry an uncertain import. The generic import wrapper detecting a new sequence is not sufficient acceptance. The Lab now implements `lab_import_prepared_caption_sequence` with these checks, input-byte staging and full declared track/item/source layout verification. The wrapper and staged driver passed combined synthetic import, protected-state checks, saved-file verification, reopen and native export on 26.3.0.

`map_import(prepared, before, after)` checks every existing bounded sequence snapshot, requires exactly the expected new sequence, validates its canvas and caption lane, and maps each semantic/render segment to the actual native timeline item ID using exact timeline/source clocks and the Text component. This narrow route rejects nested/dependent sequence additions. It does not verify arbitrary imported picture/audio structure.

XML ObjectIDs are file-local; never pass them as CEP timeline node IDs. Generated Graphics can have no exposed ProjectItem: null source ID is recorded, not fabricated. Resolve the native item through exact project, sequence, track and item IDs against a fresh snapshot.

CEP Source Text can return an opaque binary-like string. That is not decoded text verification. Use the saved-file verifier to check text runs, font names/sizes, available style fields, source/reveal clocks and geometry after native save/reopen. Keep sampled rendered evidence and human text-editability verification distinct.

## Evidence and revisions

The accepted synthetic specimen contains three render segments across two semantic cards at 24000/1001, with a continuation clock and regular/bold text. Import protected all previous sequences. Preview size normalized on first reopen; the change was reported, and a second save/reopen matched exactly. Nine sampled native-export frames showed expected text and continuity. This does not approve a production style, spoken-word accuracy, full animation behavior, split layouts, click/edit interaction, or complete end-to-end editing.

For revisions, expand the affected scope through the owning skill's semantic-card, reveal-clock and layout dependencies. A valid item map is only a locator baseline; reread before writing. `plan_caption_revision.py` now resolves that scope from before/after resolved manifests, a native card map, and a bounded sequence snapshot/revision. Scoped rebuilding and separate revised-sequence transfer passed synthetic native acceptance. In-place replacement remains unavailable.

## Staged driver

`apply_native_captions.py` consumes `--bridge-profile`, `--project`, `--receipt`, `--manifest`, `--structure`, and a new `--output-dir`. The explicit `edit.caption-transfer-structure/v1` artifact binds the prepared SHA and declares every track/item, source kind/path, exact clocks, playback direction, component match names and markers. It must come from the owning stage’s prepared composition evidence; the driver does not invent picture/audio structure.

The driver repeats the existing preflight, invokes the typed command through the shared adapter, compares independent all-sequence and full-sequence readbacks, maps semantic cards, and saves with a separate guarded operation. The canonical verifier then checks the actual saved file. The result explicitly still requires reopening, rendered review and editability evidence. Existing attempt directories refuse replay. No sequence activation or replacement is implicit, and imported effect parameter values remain a separate verification requirement.

## Creation handoff and revision planning

The transfer driver now emits the shared `edit.sequence-creation-handoff/v1` after independent native readback, save and the canonical saved-file text/geometry verifier. It binds the actual new sequence snapshot/revision and original import receipt. It records sequence absence before import, never a fabricated empty native timeline. `assert_fresh` rejects changes before the next stage. This artifact still does not prove reopen persistence, rendered output or edit-box behavior.

`plan_caption_revision.py --before <resolved.json> --after <revised-resolved.json> --native-map <map.json> --snapshot <bounded-native-snapshot.json> --revision <native-revision> --output <new-plan.json>` computes dependencies without changing text, styles or timings. A changed segment includes its entire semantic card; source-content changes propagate through shared source occurrences, and changed cut boundaries extend the scope. A layout-only change does not automatically rebuild a separate repetition of the same source. The plan records native items to replace, unchanged picture/audio/Graphics items to protect, exact tick review ranges, and before/at/after boundary frames. It rejects stale mappings, mismatched source/timeline clocks, unresolved cut boundaries, changed animation origins and canvas/rate retargets. Changes to semantic cards without corresponding resolved segment changes return to the existing resolver.

Inputs must be newly inspected before mutation. A historical snapshot produces a replay plan only. The prepared `caption-revision-v1` fixture replays accepted saved native IDs and targets two continuation Graphics while protecting the third; it is not live revision proof.

The staged existing `premiere_native_cards.py build --revision <request.json>` rebuilds only the plan's affected render segments on a scratch project, retains unaffected item objects, and reuses the existing validated track insertion. The hash-bound `edit.caption-partial-build/v1` request includes the source project hash and before manifest, prior receipt, native map, snapshot and revision plan artifacts. The builder recomputes dependencies, verifies the original caption lane and checks every original XML object before the existing new-sequence identity rewrite. Empty final lanes require a separate clear route. This creates a separate prepared project/sequence; it does not replace items in the open Premiere sequence.

For an explicitly planned per-segment Y change, the profile may carry `position_adapter: {"schema":"native-text-position-offset/v1", "segment_y_pct":{"<segment-id>":35}}`. The donor route offsets normalized text Position by the difference from profile Y, preserving the paragraph-box origin convention; the explicit-centered point route uses centered coordinates. Default donor positioning is unchanged. The existing saved-file geometry verifier must pass. Render before/at/after the layout boundary and check the edit box; offline geometry is not native or visual acceptance.

`premiere_caption_handoff.prepare()` carries partial-build provenance into the existing transfer driver. It rechecks all dependency hashes and the recomputed revision scope. Immediately before dispatch, the driver requires the original project/sequence and complete bounded source snapshot to match fresh all-sequence readback. The typed import's whole-project revision guard then protects the read-to-dispatch interval. A different active sequence alone does not select a different source. Drift requires a fresh snapshot and rebuild; no mutation is dispatched. Dependency files are checked again before save. Result evidence explicitly says separate revised-sequence import, not in-place replacement. A combined synthetic revision passed this route: two affected segments rebuilt, the repeated card retained, exact reopened state, unchanged PCM, and native ProRes decoded frames changed only in the planned layout interval. This does not prove in-place replacement or human edit-box behavior.

## Visibility and combined dependency integrity

An empty donor video lane may be muted even when every new native card passes text
and geometry verification. Explicitly declare the newly owned caption lane visible
in the preparation/transfer structure. `apply_native_captions.structure_request`
rejects a muted owned lane before dispatch. Use the selected supported native track
visibility operation to enable **only that owned lane**, with exact target and item
identity checks; do not unmute unrelated or intentionally user-muted tracks.
Read back visibility after save/reopen and inspect rendered caption pixels. Item
count, Source Text and editability alone do not establish visible captions.

`premiere_native_cards` now checks complete BinaryHash closure at build and saved-file
verification. When combining additional media dependencies, use the shared
`../_shared/premiere_graph_integrity.py:materialize_aliases` with the exact authoritative
source roots before grafting. Resolve metadata aliases as well as Source Text,
reject conflicts and missing providers, and preserve protected objects and input
hashes. The Source Text pool remains specialized; this does not authorize arbitrary
cross-project graph merging or online project-file edits.
