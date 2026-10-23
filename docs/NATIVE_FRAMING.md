# Native fixed framing

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

Dense subject tracking, animated crop revisions, multi-panel/multicamera layouts, mixed source rates and complete real-footage finishing remain separate acceptance work. Premiere continues through its canonical native reframe stage and still requires a dedicated toolkit fixture. These measurements do not grant human editorial approval or satisfy the three-engine pilot gate.
