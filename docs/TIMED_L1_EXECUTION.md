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

## Identical-plan performance qualification

For a controlled rebuild, preserve the complete finished plan byte-for-byte,
including source-word selection, boundaries, framing evidence, captions and audio
treatment. Pin the prior published media/native hashes and pass its version to
`filmcraft_pipeline.py --parent-version`. Construct a new native project from source;
do not re-export the old native checkpoint and call that a construction benchmark.
Publication preserves V1 and refuses a stale parent. This test excludes new-moment
selection and cold intake, so it cannot qualify a complete ten-minute editing run.

First-build caption animation now transports the owning skill's typed curves into
the saved native project in one batch. Text, character styles and other effects
still use native construction. The adapter reopens and verifies the complete native
caption contract. Revisions retain their existing protected-state path. No visual
quality, animation samples or export settings are reduced for this optimization.

Render verification and publication each use one full FFmpeg decode to check both
actual frame count and decoding errors, with a lightweight metadata probe. They
retain their independent checks and source-byte verification. Native operation
directories contain `performance.jsonl` for source hashing and full decode timings;
the export writes `clip.mp4.performance.json` with the native encoder result.

After rebuilding, run `scripts/compare_decoded_media.py` on the original and new
MP4s. It compares every decoded video frame and floating-point audio block, including
timestamps, and fails on differences. Keep the comparison and browser playback in
the rebuild clock. Equality establishes preservation of the prior output, not a new
listening pass or editorial approval. Record optimization time separately; keep any
in-run repair inside the original rebuild clock.

### Measured identical rebuild — 2026-10-26

The unchanged 97.347-second design was independently reconstructed from source and
reached checked V2 browser playback in **6:34**, including comparison and publication.
All 2,334 decoded video frames and 4,564 floating-point audio blocks match V1. The
entire MP4 has the same SHA-256, and the reopened native JSON has zero differences.
The original plan, published media and native checkpoint were preserved.

| Operation | Prior successful operation | Rebuild |
| --- | ---: | ---: |
| Native build | 121.03 s | 67.18 s |
| Split shadow / native inspection | 4.34 s | 2.89 s |
| Export plus integrity | 413.63 s | 246.02 s |
| Publication | 47.86 s | 6.29 s |
| Exact decoded comparison | Not performed | 13.82 s |

Comparison overlapped post-render verification. Publication completed around 5:23;
the remaining clock includes browser-tab recovery, version selection and advancing
playback. No timed rebuild failed or restarted. The new version remains unreviewed.

Source hashes took 48.69 s before build, 21.88 s before export and 27.15 s after
export; the render full decode took 4.91 s. Native encoding took 187.57 s versus
289.29 s previously despite identical settings/project/output. Cache and machine
load were not controlled, so that encoder difference is not attributed to these
code changes. Caption command batching directly removed about 49 s of measured
command work. Optimization was outside the rebuild clock.

This qualifies an identical prepared rebuild, not cold intake or new-moment editing.
The 43:29 fresh-moment run included editorial decisions and repairs. Its difference
from 6:34 is not a code-only speedup. The broader ten-minute target remains unproven.

## Third fresh-moment result — 2026-10-26

A fresh GitHub checkout beginning at `bfe1aa0` produced a new 96.263-second clip
in **31:43**, including all retries, actual-render inspection and advancing browser
playback. Sources and transcript were warm; clone installation preceded the clock.
The 20-minute target failed. Different editorial content and uncontrolled cache/load
mean the reduction from 43:29 is not a controlled code-performance comparison.

| Foreground phase | Wall time |
| --- | ---: |
| Intake and skill reading | 1:21 |
| Editorial and boundaries | 8:52 |
| Framing and caption preparation | 9:59 |
| Native build, repair, export and publication | 10:24 |
| Remaining render inspection and playback | 1:07 |

The successful build took 54.72 s, split shadow 1.34 s, native inspection 0.84 s,
export plus integrity 254.74 s, and publication 4.62 s. Native encoding alone took
182.79 s. Operations overlap phases; do not add both sets of timings.

Static anchor verification rejected a 2.27e-13 source-pixel JSON/Rust round-trip
difference. Commit `574132e` extends the existing tracking-key 1e-9 absolute tolerance
to typed finite static motion values. Seven tracking and four panel-revision tests
pass, including meaningful-change refusal. The failed native operation was inspected
and reconciled; the retry used a new directory. The repair was pushed and fetched
from main before execution resumed. No source cuts or framing decisions changed.

Preparation remains the largest cost. Camera-region corrections, occluded-profile
review, caption-width regrouping and missing handoff fields caused avoidable work.
Next work should consolidate packet/fit preflight and reuse hash-bound source-camera
calibration, while preserving source-word and actual-render checks.

Visual inspection covered 141 rendered samples including all 123 caption cards and
cut boundaries. Full decode, frame count and source verification passed. Loudness
measured -17.1 LUFS and -1.8 dBTP. Automated audio review returned HTTP 402;
listening and human editorial approval remain incomplete. Publication is unreviewed.
