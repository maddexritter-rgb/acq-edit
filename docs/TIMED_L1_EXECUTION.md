# Timed L1 Q&A construction

The target is a playable, reviewable clip within ten minutes, measured from the
request, not from encoder startup. This is a target, not a demonstrated guarantee.
Use the edit owner's run clock. Keep source-cache state explicit. Record repair
and implementation time, failed attempts, and the first playable timestamp.

For a warm, verified source session, allocate the initial target as follows:

| Stage | Target |
| --- | ---: |
| Repo/asset identity and current guidance | 30 seconds |
| Compare moments, inspect performance, freeze source-word design | 150 seconds |
| Resolve speech boundaries before any native finishing | 60 seconds |
| Framing and semantic caption preparation | 90 seconds |
| Native construction, shadow, export and integrity | 180 seconds |
| Review-room publication and playback check | 30 seconds |

Cold download/transcription time must be included in a cold test; report it
separately from the warm-source target. Never substitute an old finished render.

## Avoid known rework

1. Load the materialized owning skills once. Pin the current guidance receipt and
   consume its relevant stage bodies without rereading unrelated production modes.
2. Assembly Design compares complete moments and freezes the paper cut. For the L1
   duration/hook/banter requirements, use its current profile calibration.
3. Finish boundary resolution before generating any caption, framing or native
   project. Use the existing paired-seam, word-evidence and join-check helpers.
   A forced-alignment disagreement requires source reconciliation; it cannot be
   turned into listening approval. Keep necessary repairs in the original clock.
4. `scripts/sample_composition.py` gathers source-bound evidence in one decode per
   camera view. Use sparse review samples for fixed shots and `tracking: true`
   only for actual movement needing a dense curve. The view packet specifies
   cut ID, role, source ID, source in-frame, source dimensions and reviewed ROI.
   Detection produces evidence, not crop decisions or complete-head approval.
5. Caption-clips owns explicit semantic groups and style intent.
   `scripts/measure_caption_ink.py` measures those cards in one native session,
   reusing identical typography only within that run. Keep the measured handoff
   when words/style/size are unchanged; remap speech timing after boundary edits.
6. Build once after these inputs are checked, add the default owned split shadow,
   and export through the normal FilmCraft adapter using its pinned shadow receipt.
   The ordinary publisher then archives the version in the review room.

## Debugging the target

Separate foreground phase wall time from overlapping command durations. Capture
source bytes read, native command time, frame decoding and agent inspection time.
Repeated hashing of large sources across independent adapter invocations remains
an optimization opportunity. Any future verification cache must detect changed
media and preserve the existing post-render byte verification; do not simply
disable integrity checks to reach a timing target.

When a listener service is unavailable, record the actual failure once and proceed
with available evidence. Mark listening as incomplete. API, waveform, alignment,
native readback and visual inspection are distinct from the user's approval.
