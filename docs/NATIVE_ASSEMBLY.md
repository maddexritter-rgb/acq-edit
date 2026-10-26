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

Apply the existing finishing owners to the compiled plan, then build and render using the selected native adapter. Recompiling a spoken recut starts with empty dependent layers so old captions, framing and music cannot silently remain attached to changed timing. Use the guarded revision and publication route in `NATIVE_RECUTS.md` after preparing fresh dependent layers. Revisions still require fresh native state inspection and preservation of intervening user edits; this compile command is not an automatic merge tool.

## First Resolve construction and export packets

After the shared source/editorial/finishing plan is ready, run `acq-edit doctor`. If the target native project does not exist and Resolve is in its empty startup workspace, copy the entire freshly returned `native.emptyWorkspace` object into the build packet's `emptyWorkspace` field. Do not invent or reuse a stale placeholder ID/fingerprint. A selected matching toolkit project can be used directly; a closed saved project must be reopened through `RESOLVE_STATE.md`, never recreated. The project stays in Resolve throughout.

The construction packet uses a fresh UUID for `versionId` and new paths under the owning job:

```json
{
  "plan": "<project>/10_WORK/jobs/<jobId>/finished-plan.json",
  "versionId": "<fresh UUID>",
  "nativeProject": "<project>/10_WORK/jobs/<jobId>/v1.drp",
  "inspection": "<project>/10_WORK/jobs/<jobId>/built-state.json"
}
```

Add `emptyWorkspace` only when using the checked startup handoff. Run `acq-edit native PROJECT_ID build BUILD_PACKET.json`. The adapter rechecks the plan, placeholder and native project listing before creation. A saved name collision, changed/populated workspace, active render or wrong project is refused. It never imports an old checkpoint as a replacement. Successful construction returns the native fingerprint and timeline ID; it is not a render or approval.

Render the constructed timeline with a separate packet and fresh output paths:

```json
{
  "plan": "<project>/10_WORK/jobs/<jobId>/finished-plan.json",
  "nativeProject": "<project>/10_WORK/jobs/<jobId>/v1.drp",
  "expectedFingerprint": "<actual construction or current inspection fingerprint>",
  "inspection": "<project>/10_WORK/jobs/<jobId>/export-state.json",
  "media": "<project>/10_WORK/jobs/<jobId>/v1.mp4",
  "receipt": "<project>/10_WORK/jobs/<jobId>/render-receipt.json",
  "parentId": null
}
```

Run `acq-edit native PROJECT_ID render RENDER_PACKET.json`, inspect the actual output, then `acq-edit publish PROJECT_ID RENDER_RECEIPT.json`. The publisher verifies and copies the new version into `20_DELIVER`; do not write there directly. For revision exports, `parentId` must identify the submitted version and the owning revision route must preserve its native state. The job runner supplies `ACQ_EDIT_JOB_ID`; do not fabricate job attribution. Every failed native operation follows `NATIVE_RECOVERY.md` before another attempt.

New Resolve receipts and published versions include the native reopening target and its inspection hash as `nativeReopen`. Future revision submissions carry this metadata automatically. Use it through the guarded `native open` route in `RESOLVE_STATE.md` if the project was closed or a different version is selected; do not recreate the timeline from its plan.

## Native execution evidence and limits

FilmCraft's ordinary placement command snaps audio record positions and duration to frames. The adapter therefore follows the canonical assembly helper's saved-project method: construct linked source clips, save a separate frame assembly, write exact audio sample/tick geometry to the new native project, reopen it, and verify source clocks and link groups before finishing. It saves/reopens again and exports through FilmCraft. No flattened dialogue/video or alternate editor supplies the final render.

A synthetic 48 kHz / 25 fps fixture used these exact intervals:

| Span | Source samples | Timeline samples |
|---|---|---|
| 1 | 11–48017 | 11–48017 |
| 2 | 96017–143989 | 48017–95989 |

Both picture spans remained 25 frames long. Native readback preserved the unequal audio edges, continuous internal join, source sync and linked pairs. FilmCraft exported 50 frames at 640×360 with full decode passing. Decoded AAC correlated 0.99999878 with an independently assembled exact-sample reference. This is mechanical evidence using synthetic words and tones; it is not difficult-speech acceptance or human approval.

Resolve Studio 21.1.1 build 10 now uses a native DRT checkpoint to preserve sample geometry after its ordinary append/import operations rounded source trims. It reimports through Resolve, verifies every source/range/link, finishes and renders natively. The same synthetic paired plan passed save/reopen, 50-frame export and a caption-only revision with identical decoded audio across that revision. See `RESOLVE_PRECISION.md` for the version gate, measured limits and export-state recovery, and `RESOLVE_STATE.md` for stable graph inspection across reopening. Real difficult-speech acceptance remains open.

Premiere retains the canonical scoped paired-audio execution route and still needs a dedicated toolkit fixture. Multicamera source routing, rational sample grids not supported by the canonical paired compiler, general channel layouts, real speech joins and agent-driven end-to-end publication remain acceptance work.

## Separate microphone clock preparation

Assembly Design may supply an explicit `acq-edit/dialogue-conform-v1` specification
to `python/dialogue_conform.py --spec FILE --output-dir NEW_DIRECTORY`. It prepares
48 kHz mono PCM from independently recorded mono PCM microphones, with pinned
source hashes, integer `sourceStartSample` per microphone, explicit linear `gain`
(sum at most one), `durationSamples`, and pinned `clockEvidence`. The caller supplies
`transcriptOffsetSamples` and a pinned original `transcript`. Offsets are measured
upstream; the helper never estimates synchronization or chooses speaker routing.

The helper preserves original word text and speaker labels, adds original word
indices/times, and excludes words that fall outside the complete conformed clock.
It records those exclusions. This is a source-clock transform, not an editorial cut.
A fresh destination and receipt preserve failures without overwriting earlier work.
Import the prepared WAV through ordinary source intake and use that registered copy
as selection media. Preserve the mapped word file and receipt in project work, and
bind the receipt as routing evidence. Picture and prepared dialogue now share zero.

This preparation does not establish acoustic synchronization, listening, speaker
identity or mix quality. Do not apply unchanged fixed microphone weights when the
source requires different routing; supply a supported explicit preparation or report
that limitation. It does not create a replacement picture track or final render.
