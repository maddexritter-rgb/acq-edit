# Source-word plans and native sample timing

Assembly Design remains the sole owner of spoken selections and acoustic decisions. The toolkit now compiles its canonical v2 design and paired-seam decisions into the shared native plan. It does not derive cuts by rounding transcript timestamps.

## Compile a reviewed assembly

Prepare the canonical selection and compiled assembly, inspect the paired boundaries, and pin the played source using the existing skill helpers. Create a plan template with the ordinary identity, geometry, source and brain fields plus:

```json
{
  "editorial": {
    "selectionPath": "<project>/10_WORK/selection.json",
    "sha256": "<selection hash>",
    "compiledPath": "<project>/10_WORK/compiled.json",
    "compiledSha256": "<compiled hash>",
    "reviewed": true,
    "execution": {
      "decisionsPath": "<project>/10_WORK/paired-decisions.json",
      "decisionsSha256": "<decision hash>",
      "routingPath": "<project>/10_WORK/played-routing.json",
      "routingSha256": "<routing hash>"
    }
  },
  "cuts": [],
  "captions": [],
  "graphics": [],
  "framing": {},
  "audio": {}
}
```

When using an inspected phoneme map, add `phonemesPath` and `phonemesSha256` to `execution`. The routing file identifies `media` (the played PCM), `picture`, `stream`, `channel`, `source_clock_offset_samples`, and a pinned `evidence` object with `path` and `sha256`. Both media files must be registered project sources under `00_SOURCE`. This initial shared route requires explicitly prepared mono PCM, matching sample rate, zero source-clock offset and matching constant picture/sequence frame rates. It refuses unqualified stereo channel selection and mixed clocks.

The compile packet contains `template` and a fresh `output` path, both inside the project:

```sh
acq-edit native PROJECT_ID compile /absolute/project/10_WORK/compile-packet.json
```

This command uses the configured shared Python interpreter. Canonical `compile_assembly.validate_compiled`, `pair_audio_seams.compile_pairs` and `validate_paired_word_coverage.validate` perform the existing design/geometry checks. Sources, selection, brain receipt, decisions and routing are checked against pinned identities. Proposed joins, uninspected outer edges, stale inputs and selected words wholly outside played audio are refused. Locator containment remains distinct from acoustic completeness and human review.

The resulting cuts contain exact picture frames, `audioSourceId`, `audioInSample`, `audioSamples`, and `audioRecordSample`, plus the original word IDs. Production native builds rederive these fields and reject any mismatch, including a different picture source or timing range with unchanged word IDs. Resolve's bundled Python delegates this analysis to the configured shared Python; it does not need FilmCraft or Premiere installed.

Apply the existing finishing owners to the compiled plan, then build and render using the selected native adapter. Recompiling a spoken recut starts with empty dependent layers so old captions, framing and music cannot silently remain attached to changed timing. Revisions still require fresh native state inspection and preservation of intervening user edits; this compile command is not an automatic merge tool.

## Native execution evidence and limits

FilmCraft's ordinary placement command snaps audio record positions and duration to frames. The adapter therefore follows the canonical assembly helper's saved-project method: construct linked source clips, save a separate frame assembly, write exact audio sample/tick geometry to the new native project, reopen it, and verify source clocks and link groups before finishing. It saves/reopens again and exports through FilmCraft. No flattened dialogue/video or alternate editor supplies the final render.

A synthetic 48 kHz / 25 fps fixture used these exact intervals:

| Span | Source samples | Timeline samples |
|---|---|---|
| 1 | 11–48017 | 11–48017 |
| 2 | 96017–143989 | 48017–95989 |

Both picture spans remained 25 frames long. Native readback preserved the unequal audio edges, continuous internal join, source sync and linked pairs. FilmCraft exported 50 frames at 640×360 with full decode passing. Decoded AAC correlated 0.99999878 with an independently assembled exact-sample reference. This is mechanical evidence using synthetic words and tones; it is not difficult-speech acceptance or human approval.

Resolve Studio 21.1.1 preserved fractional timeline placement but rounded `AppendToTimeline` source trims and duration to whole frames. For example, an intended 11-sample source offset read back as zero. The adapter now refuses such source trims before creating a timeline, with a specific native-precision limitation. A before/after fingerprint check confirmed the refusal leaves the current fixture state unchanged. Whole-frame source cuts remain supported; **Resolve exact-sample execution is still an open pilot requirement**, not satisfied by this refusal. Investigate version-matched native sample insertion/import interfaces without routing through another editor.

Premiere retains the canonical scoped paired-audio execution route and still needs a dedicated toolkit fixture. Multicamera source routing, rational sample grids not supported by the canonical paired compiler, general channel layouts, real speech joins and agent-driven end-to-end publication remain acceptance work.
