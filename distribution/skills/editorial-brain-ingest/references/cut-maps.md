# Cut-only raw → final evidence

Use this for `raw_native_study` packets about spoken selection/order (`stage=assembly`)
or the execution of a seam (`stage=cuts`). It does not analyze captions or camera
decisions. Visible captions establish final identity only; a name containing `FINAL`
does not. Read the exact project and final through the Premiere Bridge when the
project is available, and retain the Bridge receipt. Do not switch an unrelated
active project without coordination.

One case has one machine-readable `editorial-brain.cut-map/v1` file. Record:

- Exact project, final-export, and original-recorder hashes; native sequence UID;
  sequence ticks-per-second and rational frame rate. Keep the source session identity
  with each recorder, because many sessions reuse filenames.
- Each *audible* kept passage in final playback order: native item ID, source media ID,
  source sample in/out, final-timeline frame in/out, and the exact Premiere tick range.
  Include overlapping speech and replacement patches as separate passages rather than
  forcing a false one-track map. Record intermediates such as enhanced WAVs in the
  lineage, but never call them original raw audio.
- Meaningful removed passages in `omissions` with source ID, sample range, observed
  function, and evidence URI. Put moved kept passages in `reordered` with passage ID,
  original-order relation, and evidence URI. Preserve qualifications, speaker, and
  causal meaning; do not call a selected branch a complete answer to an omitted one.
- Classify every adjacent kept pair by its native timeline intervals in `transitions`:
  `serial_seam` when the first ends exactly as the next begins, `overlap` when the
  first continues under the next, or `gap` when neither passage covers the interval.
  Overlap is parallel audio, **not** an audible join. Record the right passage's
  start frame, actual audio-listening result, evidence URI, and measured frame
  uncertainty for each transition. Review outer boundaries through each passage's
  start/end edge fields. A transcript, waveform, correlation score, or native item
  alone cannot certify any audible edge. Legacy `joins` may remain on development
  maps, but cannot substitute for typed transitions at certification.

For the historical v1 delivered-final route, use `certification=development` until the exact captioned asset, native sequence,
raw-source mapping, final-audio correspondence, and all claimed boundaries have been
checked. `certification=frame_reviewed` needs complete audible coverage, no unresolved
matches, each reviewed edge within one sequence frame, and readable, SHA-256-pinned
local receipts for native/final identity, boundary listening, and editorial comparison.
The structural validator checks the map's arithmetic and receipt bytes; it cannot hear the audio or independently
establish that Oliver approved an export.

The packet's `source.cut_map_uri` and `source.cut_map_sha256` pin this file. A
v1 `verified_final` packet in the assembly/cuts stages must point to a frame-reviewed map;
otherwise keep the packet `development` and state its gaps. Publish a short decision
card only after the packet is checked. The cut map is evidence behind the card, not a
transcript dump for retrieval.

## Native selection v2

For campaign-accepted native finals, retain the clock/source/kept/omission/transition
fields below and use `schema: editorial-brain.cut-map/v2`,
`certification: selection_reviewed`, `reference_authority: native_final`.
`final_asset_sha256` may be null. Add:

```json
{
  "verification_scope": {"kind":"spoken_selection", "claim_ids":["choice-1"]},
  "unresolved_ranges": [
    {"dimension":"acoustic_boundaries", "claim_ids":[], "reason":"Edges not auditioned"}
  ],
  "verification": {
    "native_final_receipt": {"uri":"/absolute/native-final.json", "sha256":"..."},
    "selection_receipt": {"uri":"/absolute/selection-review.json", "sha256":"..."},
    "audible_coverage":"partial", "unresolved":["Acoustic edges unreviewed"]
  }
}
```

Receipts are JSON objects with matching `case_id`, `project_sha256`, `sequence_uid`:

- `editorial-brain.native-final/v1`: `reference_authority: native_final`,
  `fully_edited_captioned_sequence: true`, actual `selection_rationale`,
  `caption_evidence`, `finished_picture_evidence`, `revision_resolution`, and a pinned
  `bridge_snapshot` object (`uri`, `sha256`). Record what was inspected; naming a
  final or setting a Boolean does not establish it.
- `editorial-brain.selection-review/v1`: `claims` each contain `claim_id`,
  `passage_ids`, `omission_ids`, `before_text`, `after_text`, `comparison`,
  `occurrence_review`, `source_occurrence_confirmed`, `spoken_selection_confirmed`,
  and pinned `complete_raw_context` and `word_mapping` artifacts. Omissions named by
  claims need stable `omission_id` values in the map.
- Each word-mapping artifact contains `case_id` and `passages`. Each row repeats the
  mapped passage's `passage_id`, `native_item_id`, `source_id`, source sample range,
  timeline tick range, `source_sha256`, exact `text` and `word_locator`. This makes
  changed native/source mappings detectable rather than accepting free-floating prose.

Unresolved entries name `dimension` (selection, native_identity, delivery, or
acoustic_boundaries), affected `claim_ids` and `reason`; empty claim IDs mean the
whole case. Selection/native uncertainty cannot intersect a verified claim. A
selection-reviewed map is not frame-reviewed, even when its native ticks are exact.
Validators bind artifacts and reject inconsistent claims; they do not independently
hear audio, choose a final or establish semantic truth.

## Minimal shape

```json
{
  "schema": "editorial-brain.cut-map/v1",
  "case_id": "case-001",
  "certification": "development",
  "project_sha256": "64 lowercase hex characters",
  "sequence_uid": "native sequence UID",
  "final_asset_sha256": "64 lowercase hex characters",
  "timebase": {
    "ticks_per_second": 254016000000,
    "frame_rate_num": 30000,
    "frame_rate_den": 1001,
    "frame_ticks": 8475667200,
    "final_duration_frames": 1740
  },
  "raw_sources": [{
    "source_id": "guest-recorder",
    "uri": "/absolute/source/recorder.wav",
    "sha256": "64 lowercase hex characters",
    "sample_rate": 48000
  }],
  "kept": [{
    "passage_id": "p1",
    "native_item_id": "1234",
    "source_id": "guest-recorder",
    "source_start_sample": 1000,
    "source_end_sample": 48000,
    "timeline_start_ticks": 0,
    "timeline_end_ticks": 254016000000,
    "final_start_frame": 0,
    "final_end_frame": 30,
    "audible_role": "primary",
    "delivery_audio_lineage": ["enhanced WAV item or original patch"],
    "final_audio_match": "unresolved",
    "start_edge_error_frames": null,
    "end_edge_error_frames": null,
    "evidence_uri": "/absolute/or/shared/evidence"
  }],
  "omissions": [],
  "reordered": [],
  "joins": [],
  "transitions": [],
  "verification": {
    "final_native_identity_receipt_uri": null,
    "final_native_identity_receipt_sha256": null,
    "audible_coverage": "partial",
    "boundary_review_receipt_uri": null,
    "boundary_review_receipt_sha256": null,
    "editorial_comparison_receipt_uri": null,
    "editorial_comparison_receipt_sha256": null,
    "unresolved": ["Final audio and seams not yet checked"]
  }
}
```
