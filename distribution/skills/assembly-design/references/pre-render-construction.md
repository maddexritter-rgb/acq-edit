# Construct from evidence, then export once

This is the default for `/edit` and direct assembly-design use. It supersedes older
whole-batch audition and second-ASR prerequisites. No independent model audit loop.
Use existing source-word selection, waveform/paired-seam, framing and caption owners;
this reference adds deterministic preparation, not another editorial designer.

1. Read the exact user notes and current native state first. Protect accepted edits.
   Repair only the affected source phrase, framing or payoff. Read the full relevant
   continuation before choosing an ending; grammar alone does not establish payoff.
2. Reuse decoded PCM, source transcript and bound waveform evidence. Rank ambiguous
   edges with the existing boundary inspector; resolve them in intact phrase context
   before construction. A fused selected/excluded word edge cannot be made safe by
   a minimum-energy point alone. Retain a source-native phrase or inspect the exact
   release. Do not blindly extend audio, add fixed padding or disguise speech with fades.
3. Assembly Design owns source-bound shot/layout choices under [camera intent](camera_intent.md).
   → Use skill: `horizontal-to-vertical` to implement the plan and verify crops/panels.
   Zero detections, fallback-center crops and missing tracking are unresolved picture,
   not successful framing. Inspect source visibility before rendering. If the person
   is actually off-camera, choose a justified source-backed cutaway or revise the
   passage; never zoom an empty room. Do not manufacture a missing person.
4. Compile the current source/sample ranges and build the intended lead, captions,
   framing and audio levels once. → Use skill: `caption-clips` for caption construction.
   Every changed range invalidates dependent artifacts. Keep audio samples independent
   of video frame rounding. Preserve native link groups and record any subframe skew;
   this validator's one-frame ceiling is not permission to introduce drift.
5. Create the bound packet below from **current native readback and owning evidence**.
   Run the wrapper immediately before exporting. Check failure returns to the owning
   construction decision before encoding; do not launch render/score/retry loops.
   For assembly-only work, do not invent finishing requirements or a final export.

## Executable contract

```bash
python3 edit/scripts/run_clock.py --log /workspace/run-unique/events.jsonl run --stage checked_export -- \
  python3 assembly-design/scripts/pre_render.py --packet /project/10_WORK/pre-render.json \
  --out /project/10_WORK/pre-render-result.json -- python3 /path/to/backend-export.py
```

Omit the command after `--` for a preparation check. Use the same wrapper for
Filmcraft or Premiere's existing scoped export launcher. Backend permissions,
exact-project guards and exclusive leases are unchanged. For direct MCP export,
run this check immediately before the call on the same frozen input revision.
It does not install a universal interceptor into third-party exporters: invoking
an unrelated export command directly bypasses it and violates this procedure.

Packet schema `edit.pre-render/v1`:

- `native_project`, `source_words`, `picture_source`, `audio_source`,
  `picture_evidence`: `{path: absolute_file, sha256: current_digest}`.
- `source_words` file: existing `{words:[{start:seconds,end:seconds,...}]}`.
- `picture_evidence` file: `{source: same_picture_source_pin, spans:[...]}`.
  Each ordered visual span has `source_frames:[in,out]` and `status` equal to
  `subject_visible`, `intentional_cutaway`, or an unresolved value. A cutaway also
  has `treatment:{path,sha256}` for its actual planned picture. The framing owner
  supplies evidence; never mark every span visible just to satisfy this check.
- `fps`: exact rational string; `sample_rate`: integer; `duration_frames`: integer.
- `required_picture_lead_frames`: explicit requirement from the selected finishing
  preset, default zero. Do not bake one brand's lead into all footage.
- `spans`: ordered `{source_samples:[in,out], timeline_samples:[in,out],
  source_frames:[in,out], timeline_frames:[in,out], word_range:[first,last]}`.
  Samples/frames are half-open; source-word indices are inclusive. Unit speed only.
- Optional `dependencies`: file pins for current preset, caption recipe, native
  readback, processing and adapter versions. Include all dependencies used by the
  export recipe. Native project/source hashes do not replace the existing renderer
  cache manifest.

A selected word release with less than 40ms separation in the transcript and a cut
before its end plus20ms is **triage**, not automatic proof of clipping. It refuses
unresolved construction. If intact-source inspection or exact user acceptance
resolves it, that span may carry `release_resolution:{source_sample: exact_out,
method: source_inspected|user_accepted,evidence:{path,sha256}}`. The evidence must
identify this source occurrence, kept/excluded words and exact current boundary.
Never synthesize a resolution from a successful command or an energy threshold.
These thresholds detect known risky contexts; they do not guarantee phoneme safety.

The validator checks pinned files, ordered picture coverage, selected edge-word
intersection, sample continuity, frame geometry, duration, required lead and risky
release context. Word timing remains a locator; use the existing paired-word coverage
validator for full selection reconciliation. It does not evaluate the meaning of a
payoff, recognize faces itself, inspect every waveform or claim perfect listening.

## Output and stop behavior

`CONSTRUCTION_VALID` allows the exact exporter command to start. `BLOCKED` returns
code2 and never starts it; stale or missing evidence also blocks. Keep a playable
provisional assembly when source ambiguity remains, but do not mark it approved.
After export, check job completion, streams/dimensions/rate/decoded frame count and
expected range once. Preserve exact native readback and source correspondence.
No automatic remote listener, scorecard or repeated six-audit chain.

For feedback changes, preserve accepted native geometry and compare it exactly.
No new listening claim transfers to changed edges. Keep the old revision and the
user's notes. Timing begins before this work, via the parent `/edit` run clock.

## Multicamera picture-plan binding

For new multicamera runs, include `picture_plan` and `spoken_selection` file pins.
The plan uses `edit.picture-plan/v2`, the same spoken-selection pin, a recorded
`split_opportunities` decision and ordered `shots`. Each shot has a stable `id`,
`timeline_frames`, `layout` (`single`/`split`), `editorial_reason` and `panels`.
Each panel identifies `role`, `visible_participant`, `participant_matches_intent`,
`placement` (`full`, or distinct split panel positions), pinned `media`,
`source_ticks`, integer `session_offset_ticks` on the backend-neutral 254016000000
ticks/second clock, `quality`, `face_visible`, `observed_picture`, and pinned
`visual_evidence`. Scope this face-visible contract to dialogue panels; object or
demonstration layouts need their own explicit inspected treatment instead of
mislabeling an invisible face as visible.

The check rejects stale spoken revisions, gaps, missing panels, unusable dialogue
coverage, wrong/unresolved participants, mismatched durations and unsynchronized
splits. It validates recorded evidence, not facial identity from pixels. Native
readback must independently verify the panel mappings and one deliberate dialogue
mix; bind that receipt in packet dependencies. Historical packets remain readable;
new multicamera packets must not omit the plan to bypass these checks.

Split dialogue panels additionally require `panel_framing`: status `INSPECTED`,
final-output `panel_rect` [left,top,right,bottom], project-selected positive
`minimum_headroom_px`, `maximum_head_height_fraction`, and `samples` containing
complete `head_bounds` in that same output coordinate system plus a pinned
rendered-frame `evidence`. Include hair through chin; label conservative manually
measured envelopes as such. The validator checks those bounds and size against the
recorded framing intent. It does not measure heads itself or certify unsampled
frames. → Use skill: `horizontal-to-vertical` for measurements and composition.
