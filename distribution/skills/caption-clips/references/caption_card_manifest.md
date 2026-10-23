# Caption card manifest

This is the older four-slot ASS/MOGRT probe contract. For approved editable native
Graphic batches, read `native_premiere_workflow.md` and use
`scripts/premiere_native_cards.py`. Do not force variable-run semantic cards through
this restricted converter or interpret its MOGRT capability gate as a ban on the
separately verified native Graphic route.

`spice.caption-cards/v1` is the shared contract between the burn renderer and
Premiere-native assembly. Times are sequence-relative seconds. A consumer must
reject a manifest with overlapping cards, non-positive durations, more than four
word slots, or a word whose onset falls after its card ends.

```json
{
  "schema": "spice.caption-cards/v1",
  "source": {"kind": "ass", "path": "/absolute/subs.ass"},
  "video": {"width": 2160, "height": 3840, "fps": 23.976},
  "cards": [
    {
      "id": "card-0001",
      "start": 0.5,
      "end": 1.25,
      "y_pct": 50.0,
      "speaker": "host",
      "text": "example caption",
      "words": [
        {"text": "example", "color": "FFFFFF", "weight": "bold",
         "scale": 100, "italic": false},
        {"text": "caption", "color": "FFFFFF", "weight": "base",
         "scale": 100, "italic": false}
      ],
      "gloss": null,
      "boundary": {"camera_cut": false, "speaker_change": false}
    }
  ]
}
```

The manifest preserves observed styling. It does not infer that a muted Premiere
caption track was visible in a shipped export. Corpus rows therefore carry an
independent evidence status and final-sequence identity.

## Premiere capability gate

The current assembler is a diagnostic prototype, not a production renderer.
Default invocation writes an offline plan and makes zero Bridge calls. An import
probe requires `--apply --probe --sequence-uid <exact-uid>` and a dedicated empty
sequence named `_CAPTION_PROBE_<slug>`; it removes its probe and does not save.
Coordinate Bridge ownership before probing. Production `--apply` and degraded
assembly are blocked until complete style controls and saved readback exist.
Control names alone never prove parity.

Native assembly may proceed only when the selected MOGRT exposes every property
required by the manifest. A template exposing only one text property is useful
for a technical import/editability probe, but it is not Oliver-style parity and
must not become the default. Unsupported per-word styling fails closed unless a
caller explicitly requests a degraded diagnostic build.

Before reading frames, exporting, or learning visual metrics, run
`scripts/caption_font_preflight.py --native-graphics <native_graphics.json>`.
Every embedded PostScript name must resolve to a locally installed font file.
An Adobe CoreSync cache hit alone is not sufficient: the application can still
substitute a fallback face. Any failed preflight marks the render
`FONT_UNRESOLVED_DO_NOT_TRAIN_RENDER`; the shipped export remains visual truth.
