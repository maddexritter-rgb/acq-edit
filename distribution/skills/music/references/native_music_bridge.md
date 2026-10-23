# Native music application through Premiere Agent

This is the mechanical counterpart to the existing music selector and audition process. It does not choose tracks, redesign the music arc or certify listening. Use the default Premiere Agent profile and exact-project music scope from [startup](../../edit/references/premiere_start_here.md). An explicit Lab profile remains available for disposable research. Omit --bridge-profile for routine authorized work.

Follow `edit/references/premiere_execution_contract.md`. The shared adapter owns transport, guarded operation receipts and reconciliation. Unknown outcomes stop dependent writes and retain their original IDs.

## Current implemented scope

`scripts/apply_native_music.py` can inspect audio items, prepare a plan, and replace only the explicitly owned item's native Volume/Level envelope. The source may already be placed, or an explicit placement plan may prepare/import it and add one owned audio item into an empty range. Source replacement, new-track construction and intentional EQ remain unfinished. Do not alter dialogue to accommodate the bed.

- `--inspect --bridge-profile <profile>` reads exact item/source/timeline IDs, Volume/Level descriptor, raw value/keys and a bounded protected-state snapshot.
- `--prepare --selection <music_selection.json> --envelope <envelope.json> --calibration <calibration.json> --item-id <native-id> --out <plan.json> --bridge-profile <profile>` creates an exclusive plan artifact without mutation.
- `--apply-plan <plan.json> --bridge-profile <profile>` verifies evidence hashes, reconstructs the plan from its recorded inputs, applies it with its original operation ID, checks native keys/protected state, then saves through a separate guarded operation and checks again.

Existing attempt sidecars are never silently replayed. Use a new inspected/reviewed plan only after reconciling the previous operation and actual state. A successful save is not close/reopen proof.

## Source preparation and placement

Use `--prepare-placement --selection <music_selection.json> --placement <placement.json> --out <plan.json> --bridge-profile <profile>` for an inspected `edit.music-placement/v1` request. It contains the exact project/sequence `target`, audio `track_index` and native `track_id`, and exact `start_ticks`/`end_ticks`. Optional `source_item_id` resolves an existing source when the media path is ambiguous. Source start and duration must agree with the existing audition receipt; the driver does not choose them.

`--apply-placement <plan.json> --bridge-profile <profile>` executes source preparation, checks that the timeline remained unchanged, places one item, independently verifies the new native identity/ranges and protected timeline, then saves and checks again. Separate source/placement/save sidecars retain their original operation IDs. An ownership receipt identifies the created timeline item and source. The returned status is `PLACED_ENVELOPE_STILL_REQUIRED`: use that item ID with fresh inspection and the envelope preparation/application path above. It never reports a finished mix merely because a bed was placed.

The Lab probes the actual selected file and requires exactly one mono/stereo audio stream with representable duration. It resolves an existing source or imports an absent file, then creates an owned subclip without changing shared source marks. Placement requires a known unlocked/unmuted existing track, no track transitions and an empty destination range. No overwrite of existing music/dialogue or ripple is permitted. Existing project-tree audio marks and all bounded pre-existing timeline fields must match after the operation. Files with cover-art video/other streams, ambiguous source IDs or unsupported native clocks stop with an explicit limitation.

One stereo PCM fixture has passed exact Time-object placement, offset-aware source readback, save/reopen, and a native PCM render matching the selected file section on both channels. The combined generated-speech fixture additionally passed calibrated envelope readback, save/reopen, full-mix measurements and an actual-audio model review. This is bounded fixture evidence, not human listening or general source-effects/routing acceptance. An interrupted source preparation or placement may leave added project items or timeline state; reconcile the existing receipts before another write. There is no automatic rollback or import replay.

## Selection receipt additions

Keep the selector's `edit.music-selection.v2`, `brief`, and `picks`. Add the final `winner` as an exact candidate ID, `recent_track_exclusions` as a list (including an explicit empty list), and `target` with the project path and sequence ID.

`audition` records `winner_id`, exact `source_start_ticks`, `duration_ticks`, the actual audition clip's absolute `clip_path` and `clip_sha256`, and `listening_notes`. This records the existing audition decision; the driver cannot establish that listening occurred. Existing rejected candidates and decision reasons remain in the receipt.

Optional `eligibility_inputs` points to the exact `index`, `review_decisions`, and `blacklist` used for this library. Otherwise, the existing selector's defaults apply. The driver calls the unchanged selector's eligibility logic again: Keep status, blacklist, recent-use exclusions, source existence and duration remain hard filters. It never treats an approved folder as blanket eligibility. These inputs and the selected audio are hashed into the plan and checked before application.

## Envelope

`edit.music-envelope/v1` contains the exact `target`, `interpolation: "linear_native"` and ordered `points` with decimal-string `offset_ticks` and finite `db` values. Points must cover zero through the exact item duration. The driver adds native item-local source-in ticks with integer arithmetic. File-relative audition times are checked separately using the evidenced source offset. One nonzero-offset stereo subclip passed native local-key readback, persistence and a rendered dip in the intended interval; interpolation-type readback and gain mappings outside the individually measured calibration points remain unverified.

`linear_native` requests Premiere’s linear keyframe mode. Rendered 26.3 evidence shows a nonlinear amplitude ramp between calibrated points; it is not a promise of linear amplitude, perceived loudness, or dB interpolation. Check the rendered curve against the intended timing and musical shape. The musical shape and any denser sampling belong to the existing music decision. The driver does not invent ducking or fades.

## Units and calibration evidence

Adobe's [ComponentParam API](https://developer.adobe.com/premiere-pro/uxp/ppro-reference/classes/componentparam/) exposes native values and key actions, but the inspected public interface does not supply a dB unit descriptor. The upstream wrapper's hardcoded conversion is not sufficient local calibration evidence.

The typed endpoint accepts raw native values only. The stage's `edit.music-level-calibration/v1` must name host `26.3.0`, backend `CEP/ExtendScript`, and the exact parameter descriptor (`component_index`, `component_match_name`, `parameter_index`, `display_name`). Every requested dB value needs its own measured sample; there is no guessed conversion or interpolation between samples.

Each sample includes `db`, `native_value`, and hash-bound absolute paths for `source_wav`, `rendered_wav`, `native_receipt`, and `export_receipt`. The native receipt must report the same constant raw envelope on that source, allowing only observed binary32 storage and bounded native JSON serialization precision; the export receipt must identify the same project/sequence and output. The validator measures each PCM channel's RMS ratio, rejects mismatched formats, clipping and stale artifacts, and requires agreement within 0.15 dB. Supported measurements are 1–60-second signed integer PCM WAV fixtures. Silence, encoded audio, or an arbitrary report claiming PASS does not establish a mapping.

Calibration still depends on the supplied host/export provenance and controlled fixture. It is not tamper-proof attestation, a complete audio-routing audit, or production acceptance. Build the samples on a dedicated synthetic sequence with unchanged routing and no other audible material/processing. The isolated 26.3 stereo fixture now has measured native samples at −12, −24 and −60 dB. The −60 dB check uses 24-bit output because 16-bit quantization exceeded the calibration tolerance; software test samples remain explicitly simulated. A whole rendered mix still needs comparison and listening against the dialogue-only baseline.

## Evidence boundary

Structured readback compares the owned envelope and all other fields available in the bounded Lab snapshot, preserving dialogue, picture, graphics and Motion captured there. The snapshot does not expose every routing, channel or source-processing property in Premiere. Native source/placement and envelope persistence now have bounded stereo fixture evidence. The combined full mix passed actual-audio model review and calibrated rendered measurements. Human listening, broader source-channel/processing preservation and interpolation readback remain unverified. Never label these verified from a tool success or the synthetic unit tests.

After successful independent readback and a separate save, placement and envelope application emit a shared `edit.sequence-stage-handoff/v1` artifact. It retains the original operation receipts and native item identity and requests listening over the affected timeline range. It does not claim a listened mix or reopened-project persistence. See the [shared execution contract](../../edit/references/premiere_execution_contract.md#recorded-handoffs-and-focused-review).

## Explicit source clocks

Placement plans keep `source_in_ticks` and `source_out_ticks` in original-file time, matching the audition decision. Prepared hard subclips also return `native_source_in_ticks`, `native_source_out_ticks` and `source_offset_ticks`. Native audio inspection retains item-local ranges and the offset separately. The driver checks file time = local time + offset using integer arithmetic. It never treats subclip-local zero as the beginning of the original music file.

The current 26.3 reader requires matching exact offsets in the native project metadata's AudioInPoint and AudioOutPoint fields. Unsupported metadata shapes or missing/contradictory offsets fail closed; this is an observed host format, not a universal API promise. Nested subclip parents are rejected. `startTime()` is not substituted: the test host returned zero for both the original source and its nonzero-offset subclip.

Native Volume match names are resolved exactly: observed mono/stereo internal Volume descriptors and the existing `audioVolume` descriptor. Channel Volume is distinct and remains protected. Envelope plans carry the source offset as a precondition. No conversion to dB is inferred from these names or raw parameter values.

The accepted placement route stays within the existing picture/dialogue timeline extent. Empty-sequence or tail-extending placement is rejected before importing a source: a native fixture changed project-item state after insertion and returned uncertain. Do not loosen project-tree protection to accept that case.

## Prepared-copy track routing and actual audibility

A newly grafted audio track can contain valid items and Volume keys yet be absent
from the master's `AudioTrackInlet/Sources`. Native item/envelope readback cannot
prove it is audible. On an explicitly owned offline prepared project, run
`scripts/check_music_routing.py --project <prepared.prproj> --sequence-uid <UID>
--track-uid <owned-new-track-UID>`. For the supported direct-master graph only,
`--output <new.prproj> --expected-sources '<ordered UID JSON>'` adds just that
track's missing inlet reference and checks all other objects are unchanged.
Never edit an open project file, assume submix routing, connect unrelated tracks,
or generalize this prepared-copy operation into permission to create native tracks.

When transferring media dependencies, use the shared
`../_shared/premiere_graph_integrity.py:materialize_aliases` on the transferred nodes
against the exact authoritative source graph **before** ID remapping/insertion.
It resolves all binary metadata, including `ModificationState`; Source Text's
caption-specific payload pool is insufficient. Then validate the complete graph,
retain input hashes and compare protected objects. Missing/conflicting aliases stop
before writing. This helper does not select dependencies or approve graph grafting.

After import/save/reopen, confirm the owned track is unmuted and routed, then render
the actual native full mix. Compare with dialogue-only audio and audition the music
head, ducked body and tail: the intended source and envelope must actually be heard.
A non-silent full mix can contain only dialogue; silence detection alone is insufficient.
