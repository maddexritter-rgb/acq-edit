# Native framing

The packaged `horizontal-to-vertical` skill owns subject inspection, crop selection, camera decisions and tracking. `python/framing_plan.py` only validates that decision and translates source geometry for native execution. No detector or competing shot planner is introduced.

`EditPlan.framing` accepts this explicit contract:

```json
{
  "schema": "acq-edit/framing-v1",
  "receiptPath": "<project>/10_WORK/framing-decision.json",
  "receiptSha256": "<sha256>",
  "shots": {
    "cut-id": {
      "mode": "fixed-crop",
      "sourceWidth": 640,
      "sourceHeight": 360,
      "x": 70,
      "y": 20,
      "width": 180,
      "height": 320
    }
  }
}
```

Every source cut needs exactly one decision. Coordinates are integer source pixels, with a top-left origin. The crop must stay within the source and exactly match the output aspect ratio. The validator probes actual source dimensions and refuses stale geometry, rotated/anamorphic sources, unknown operations and changed or external receipts. Receipt hashes bind the decision; they do not prove visual inspection or human approval.

FilmCraft applies native Motion anchor, position and uniform scale, leaving caption graphics in output coordinates. Resolve applies native Fusion Crop followed by BetterResize before caption composition. The adapter converts top-left source coordinates to Fusion's bottom-left crop offsets. Text+ explicitly uses output frame dimensions. Final exports remain native to the selected editor.

Resolve clamps timeline dimensions below 256 pixels on the qualified host. Those sizes are rejected, and actual timeline geometry is always read back. Text+ normalized size is not interchangeable with FilmCraft pixel size: caption profiles may supply `style.fusionSize`. A profile must be visually calibrated for its font and output geometry; the fallback calculation is not a parity guarantee.

## Fixed-framing revisions

A `kind: "fixed-framing"` packet includes a complete updated plan, a fresh decision receipt, the current `expectedFingerprint` and new native checkpoint/inspection paths. It changes only explicitly targeted cuts:

- FilmCraft: `edits: [{"cutId": "cut-id", "clip": <inspected native clip ID>}]`.
- Resolve: `edits: [{"cutId": "cut-id", "track": 1, "itemIndex": 0}]`; the index is zero-based.

Both adapters verify source identity, source range, record range and output dimensions before applying geometry. FilmCraft works from a new project copy; Resolve duplicates the timeline. Cut ranges are checked afterward. Existing caption and audio layers remain in place. Animated FilmCraft Motion parameters and animated/expression-driven Resolve crop inputs are refused, preserving their tracking rather than replacing it. Missing owned Fusion nodes require reconciliation, not replacement of an arbitrary user graph.

Render the resulting checkpoint using the returned fingerprint. Old native checkpoints and rendered media remain unchanged. A new render still needs a fresh review decision.

## Mechanical evidence

Synthetic 640×360 source media contained labeled red and blue regions plus a 440 Hz audio signal. Two source-linked cuts were cropped to 360×640 at 25 fps, with visible captions composed after framing. Both editors exported 50 frames, passed full decode, maintained the expected source color at all four sampled corners of every frame, and switched source regions at frame 25.

A revision moved only the first crop 20 source pixels horizontally. At 2× scale, its visible source label moved exactly 40 output pixels; the second crop and caption bounds stayed unchanged at the first, middle and last frames of each cut. Native picture/audio cut ranges remained unchanged.

| Measurement | FilmCraft | Resolve Studio 21.1.1 |
|---|---|---|
| First source label shift | −40 output pixels | −40 output pixels |
| Second source label bounds | Unchanged | Unchanged |
| Caption bounds across revision | Unchanged | Unchanged |
| Decoded audio exactly identical | Yes | No |
| Audio signal-to-difference ratio | Identical samples | 79.05 dB |

Resolve's duplicated timeline produced a small decoded audio difference despite identical native ranges and levels. This evidence does not establish sample identity or explain the native encoder's variation. The caption fixture used FilmCraft size 36 and Resolve normalized size 0.14, with equal measured glyph width/height but different baselines; this is a fixture calibration, not universal font parity.

Dense subject detection and planning, framing-mode/scale changes, multi-panel/multicamera layouts, mixed source rates and complete real-footage finishing remain separate acceptance work. Native construction from a reviewed X curve is described below. Premiere continues through its canonical native reframe stage and still requires a dedicated toolkit fixture. These measurements do not grant human editorial approval or satisfy the three-engine pilot gate.

## Source-bound horizontal tracking

The same framing schema also accepts `mode: "tracked-crop"` for FilmCraft and Resolve. The existing `horizontal-to-vertical` owner still chooses the subject, stable Y, scale, camera runs, source-local smoothing and fallback policy. The adapter consumes its finished curve; it does not perform face detection or add another planner. Stable shots should retain `fixed-crop`.

A tracked shot includes the fixed-crop geometry plus:

```json
{
  "mode": "tracked-crop",
  "sourceWidth": 640, "sourceHeight": 360,
  "x": 100.25, "y": 20, "width": 180, "height": 320,
  "xByFrame": [100.25, 100.5, 101.0],
  "sourceRange": {
    "sourceId": "<source-id>", "sha256": "<source-hash>",
    "inFrame": 50, "frames": 3
  }
}
```

This example covers a three-frame cut; real curves require exactly one finite X value per displayed frame. X uses top-left source pixels and preserves fractional values. Y, crop width/height and source dimensions remain integers. Every sample must stay source-safe. The source ID/hash/in-frame/count must match the exact cut, and source/timeline frame rates must match. A changed source interval requires a newly mapped owner handoff. Source average/nominal rate checks reject obvious mismatches; they do not independently certify every packet timestamp of arbitrary VFR media.

The owner must fit a continuous source/camera/layout run before slicing its curve across artificial subdivisions. Separate source-time jumps reset the run. The adapter writes each supplied cut independently and never interpolates between different cut items. It neither invents a settling pan nor repairs a bad owner decision.

FilmCraft writes one native Linear Motion Anchor key per frame, with fixed Y, Position and Scale. The API receives timeline ticks; typed saved-project verification checks source-media ticks, every value and interpolation after save and before render. Resolve uses a native Transform → Crop → BetterResize chain: a source-bound XYPath/BezierSpline drives Transform X, with fixed Y/scale. The Crop stays at an integer base offset. This preserves subpixel motion because native Crop offsets themselves round fractional values. Captions are composed after the resize in output coordinates.

Resolve's spline readback may return relative one-third Bezier handles instead of a Linear flag. The verifier checks the actual handle geometry, exact key coverage, values, fixed controls, evaluation and graph connections. It rejects easing, steps, changed drivers, changed source clocks and missing nodes. Complete graph fingerprints continue to protect unknown fields.

The existing `fixed-framing` revision refuses a tracked target or tracked replacement. Use `tracking-framing` below for changes to existing horizontal curves; do not use a static crop edit to erase tracking. Caption-only plans retain the complete framing contract and reverify it before publication. Premiere continues through its owning native reframe stage; this transport never switches to Premiere.

### Tracking construction evidence

On 2026-10-23, a synthetic two-cut fixture with a source-time jump rendered 50 frames at 360×640/25 fps independently in FilmCraft and Resolve Studio 21.1.1 build 10. Both retained fractional source-X values and fixed Y. The first cut moved 0.5 source pixels per frame; the second reset to a different source region and moved in the opposite direction. Every decoded frame had the expected region at its four corners. The white source label's right edge moved exactly one output pixel per frame within each cut, with fixed vertical bounds. Sampled first/middle/last frames of both cuts were viewed. Thresholded centroids varied with compression and were not used as proof of exact motion.

FilmCraft saved/reopened and verified every typed key before native export. This is mechanical curve-transport evidence, not face-tracking quality, real-speech acceptance, reference fidelity or human approval. The same construction fixture does not qualify multicamera panels. Subsequent curve-revision evidence is recorded below.

Resolve also passed an actual save/close/reopen of the task-owned project: the complete native snapshot fingerprint remained identical and every tracking key/graph control was reverified. Direct pre/post Fusion exports first exposed modifier auto-naming and its transient explicit-name flag. Construction now uses the host's persisted `ACQ_FramingPathX` name without an explicit-name flag. No new graph-field exclusions or fingerprint-schema changes were introduced. The pre-existing review timeline was restored and its complete fingerprint verified unchanged.

## Revising an existing tracking curve

Review feedback such as “track the speaker,” “keep the subject centered,” or “fix the tracking drift” routes to `horizontal-to-vertical` without requesting a spoken recut. The agent reads the complete feedback and prepares the revised owner decision. The native `tracking-framing` action accepts only changes to selected existing tracked crops' `x` and `xByFrame`. Y, crop size/scale, source ranges, all unselected shots, cuts, captions, graphics, audio, project identity and guidance stay identical in the plans. Mode changes or broader framing changes need another supported operation.

Write a new plan and fresh framing-decision receipt, retaining the old files. Common revision fields are:

```json
{
  "kind": "tracking-framing",
  "previousPlan": "<project>/10_WORK/published-plan.json",
  "previousPlanSha256": "<published-plan-hash>",
  "plan": "<project>/10_WORK/revision/plan.json",
  "cutIds": ["<exact-cut-id>"],
  "expectedFingerprint": "<fresh-native-inspection-fingerprint>",
  "inspection": "<project>/10_WORK/revision/native-inspection.json"
}
```

Add the selected engine's fields:

| Field | FilmCraft | Resolve |
|---|---|---|
| `nativeProject` | Existing native parent checkpoint | New DRP output path |
| `outputProject` | New `.fcproj` output path | Omit |
| `inspectSession` | New parent-inspection session folder | Omit |
| `session` | New revision session folder | Omit |
| `title` | Omit | New duplicate timeline name |

Call `acq-edit native PROJECT_ID revise PACKET`, then render the returned checkpoint/fingerprint with the updated plan and publish through the ordinary version/job workflow. The new version requires fresh review; old comments retain their original version/timecode. Repeated operations must go through the durable job queue, not direct command replay. Existing outputs require reconciliation.

Before mutation, both adapters validate the old plan hash, both source-bound framing contracts and exact current native state. FilmCraft revises a new project copy. It compares all native project data while allowing only the selected Anchor values/keys and the two document labels that the host derives from the destination basename. Those labels are checked against that exact basename, not ignored. View/selection UI data are outside this project-data comparison. All source geometry, other curves, effects, captions, tracks and audio remain protected.

Resolve duplicates the timeline and checks its previous framing contract. Before writing, it snapshots the duplicate and parses each targeted Fusion graph. A separate protected-state comparison permits only `ACQ_FramingCrop.XOffset.Value` and `ACQ_FramingPathX.KeyFrames` to change. Every other parsed graph field and the duplicate's full timeline snapshot stay represented. Exact new curve/handle/geometry verification checks those permitted values afterward. This operation-specific comparison does not weaken ordinary complete graph fingerprints. The parent timeline is reselected and verified unchanged before saving the new native checkpoint.

### Recorded revision evidence

Both backends revised only the first of two synthetic tracked cuts, changing its initial X and doubling its per-frame motion. Each exported 50 frames at 360×640/25 fps. Every first-shot frame's measured white-label right edge advanced two output pixels, with fixed Y; sampled revised frames were viewed. Native protected-data checks passed, and original checkpoint hashes remained unchanged. Resolve also restored the pre-existing review timeline with its original complete fingerprint.

FilmCraft's unselected second shot and decoded audio were byte-identical to the parent render. Resolve's second shot had 68.84 dB PSNR relative to the parent, and decoded audio differed at −77.61 dB RMS relative to signal. Native state preservation therefore does not establish byte-identical Resolve exports, explain their variation, or prove inaudibility. The existing Resolve output qualification remains open. This is direct native revision evidence; a live review-room/agent tracking job, real subject tracking, broad framing changes and human approval remain separate acceptance work.
