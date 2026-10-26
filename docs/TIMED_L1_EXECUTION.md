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

## Measured warm-source baseline — 2026-10-26

One new 93.76-second native FilmCraft Q&A (2248 frames, 1080×1920,
24000/1001 fps, 48 kHz) reached verified review-room playback in **49:38**.
This includes 8.95 seconds before timer initialization; it is a failed ten-minute
test. Sources/transcript were already available. No cold intake speed is claimed.

| Foreground phase | Wall time |
| --- | ---: |
| Intake and skill reading | 1:04 |
| Source comparison and current guidance | 4:48 |
| Assembly design and boundaries | 10:34 |
| Framing and captions, including helper implementation | 10:10 |
| Initial native construction and integration repair | 4:21 |
| Late boundary repair and rebuild | 11:05 |
| Native export and integrity | 5:08 |
| Render inspection and publication | 2:21 |

The encoder itself took 240.29 seconds (9.36 fps). Caption ink measurement took
11.81 seconds for 143 cards; final native construction took 98.73 seconds.
A source-camera sampling pass took 76.09 seconds. These operation times overlap
foreground phases and must not be added to the table's wall time.

The largest opportunity is reducing agent preparation and avoiding late boundary
rework. Repeated verification of approximately 46.6 GB of source media and native
encoding are additional measurable costs. Batched helpers were implemented during
this run, so their existence does not yet prove an end-to-end speedup. The next
run must use the stable procedure and keep the same complete timing standard.

The actual MP4 received full-decode/frame-count checks and 186 visual samples
covering every caption card and cut boundaries. Automated listening was unavailable
because its provider returned HTTP 402. Human editorial and listening approval
remain separate; successful publication is not approval.

## Stable execution helpers

After the owning skills have authored and checked the decisions, use these
repository helpers instead of writing project-specific procedural scripts:

- `scripts/prepare_caption_handoff.py` maps explicit source-word groups, speaker
  roles and real-face emphasis onto frozen cut clocks. It refuses missing words,
  duplicate coverage, ambiguous emphasis and groups crossing cuts. It chooses no
  phrases, fonts, casing or speakers. Measure its output with `measure_caption_ink.py`.
- `scripts/prepare_composition.py` transports the framing owner's complete-head
  calibration, crop height, headroom and camera choices into geometry and source
  contact sheets. A separate `--accept` is required after actual source-frame
  inspection. No detector confidence automatically grants visual approval.
- `scripts/filmcraft_pipeline.py` takes the checked finished plan through the
  existing native build, default split shadow, inspection, native export and
  immutable publication routes. It logs each operation under the original run
  clock, refuses existing execution directories, and stops on failure. Inspect
  the published render before closing the clock; publication remains unreviewed.

FilmCraft binding now reuses the actual source-byte verification results from the
same plan check instead of hashing the same cameras again in a subprocess. There
is no persistent timestamp-only cache. Every native operation still hashes its
sources, and render completion still performs a fresh full-byte check. Resolve's
separate interpreter path remains unchanged.

The optimized preparation route was checked against the prior real clip's 368
composition measurements without changing that delivered version. Its proposal
still requires explicit visual inspection. Tests also compare old/new assembly
bindings, refuse incomplete byte-verification sets, and reject caption omissions.
These checks qualify the helpers, not the next clip's editorial choices.

## Preparation failures found in the second fresh-moment test

Caption handoffs now map emphasis to the caption owner's normalized display text,
use ceiling frame onsets to preserve the preceding speech release, and verify exact
native font faces during ink calibration. Caption semantic preflight runs before
large media verification; a passing packet still receives the full ordinary checks.
Framing decisions may supply explicit, visually inspected complete-head envelopes
when an arm or a turn occludes the detector. This is an authored observation, not a
fabricated detector confidence or automatic approval.

Finish intact-source join checks before native assembly compilation or dependent
framing/caption work. In the test, starting those stages before the boundary checks
finished caused repeated assembly binding, camera decoding, and caption-clock
remapping. Count all such repairs in the original clock. Never start the native
driver until the caption-binding command has actually succeeded.

## Second fresh-moment result — 2026-10-26

The new 97.347-second FilmCraft clip reached checked review-room playback in
**43:29** with warm sources and transcript. The ten-minute target failed. Initial
optimization work preceded the clock; every in-run repair and retry stayed inside it.
This differs from the previous moment, so the 6:09 reduction is not a controlled
performance comparison or proof of unchanged editorial quality.

| Foreground phase | Wall time |
| --- | ---: |
| Intake and skill reading | 2:34 |
| Editorial and boundaries | 17:04 |
| Framing and caption finalization | 4:48 |
| Native preparation and repairs | 7:18 |
| Native retry and early export | 2:54 |
| Remaining export, integrity and publication | 7:39 |
| Render samples and browser playback | 1:12 |

Successful native construction took 121.03 seconds, export plus integrity 413.63
seconds, and publication 47.86 seconds. These operations alone total 9:43, leaving
almost no ten-minute budget for design and inspection. Instrument encoder, hashing
and publication separately before choosing the next performance repair. Preserve
source-byte verification; do not trade it for a timestamp-only cache.

Boundary rework remains the largest preparation cost: four assembly compilations
totaled 306.87 seconds, and later changes invalidated dependent framing/caption
clocks. The prepared helpers did not prevent the agent from starting those stages
too early. Exact-font and caption-semantic failures now fail earlier, but a future
run must demonstrate the complete stable path before claiming the target.

The native export passed full decode and frame-count checks. Inspection covered
182 actual rendered samples, including every caption and cut boundaries, plus
advancing browser playback of the exact published version. Loudness measured
-16.09 LUFS and -1.36 dBTP; AAC exceeded the intended -1.5 dBTP ceiling by 0.14 dB.
Listening and human editorial approval remain incomplete. The version is unreviewed.
