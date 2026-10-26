# Native audio execution

The packaged `music` skill owns track eligibility, choice, source offset, auditioning and creative shape. Adapters execute its explicit plan. Music is imported as a project-owned source under `00_SOURCE`; no private music library is bundled.

For Premiere, the packaged `apply_native_music.py` selection receipt can carry
`project_source` with schema `edit.music-project-source/v1`, the project-owned
`path`, `catalog_sha256`, `sha256`, and `decoded_pcm_sha256`. Eligibility still
runs against the original catalog candidate. Both full recordings must decode
to the same SHA256 of 48 kHz stereo signed 24-bit PCM; a changed offset, gain,
fade or replacement recording fails before native dispatch. This allows a
verified WAV normalization without losing catalog approval provenance. Exact
fractional source times can use rational strings such as `796/15`; retain the
original decision and audition evidence when preparing the native receipt.
Placement still requires the existing calibrated envelope, native readback,
save/reopen and rendered-mix checks. A source-binding check is not mix approval.

### Premiere calibration runner

`scripts/premiere_music_calibration.py` prepares a four-second, stereo 24-bit PCM
tone fixture and a local stereo copy of the installed `Wave48mono24.epr` preset.
Create `10_WORK/ACQ_Music_Level_Calibration.prproj` through Premiere UI beneath
the selected isolated integration's `lab/runtime/fixtures/<fixture>/` directory.
Use a separate profile with `mode: lab` and the same isolated integration. The
runner refuses production paths; its lease command requires the current owner
and no unresolved writer. Keep the real clip's existing scope and lease receipt.

Run `setup`, `lease --owner <current-owner>`, then `build`, supplying `--skills`,
`--profile`, `--fixture` on each command and `--preset-source` on setup. Run each
`sample` with a fresh `--attempt`, an intended `--db`, and a raw
`--native-value` hypothesis. Samples apply constant native keys and render WAV
through Premiere. The existing music validator checks native/export receipts,
exact source/output formats and each channel's measured RMS ratio before writing
`verified.json`. An assumed mapping is never accepted without that render.
Retain failed attempts; do not replay their IDs. Return to the real project,
restore its exact-project scope and selection, and verify its snapshot unchanged
before applying an envelope through the music owner.

On the isolated 26.3.0 host, raw values `0.00707945784384138` and
`0.00017782794100389227` measured −28.000 and −60.000 dB respectively on both
channels. These are bounded stereo Volume samples, not a universal formula or
mono calibration. They do not certify the real mix, fade shape or human review.

`EditPlan.audio` accepts `gainDb` for dialogue and an ordered `music` list. Each placement contains:

| Field | Meaning |
|---|---|
| `id`, `sourceId` | Stable placement ID and exact project source |
| `startFrame` | Timeline start in the plan's frame rate |
| `sourceInSample`, `samples` | Source offset and duration in the plan's sample rate |
| `gainDb` | Constant bed level before fades |
| `fadeInSamples`, `fadeOutSamples` | Optional linear-amplitude fade durations |
| `receiptPath`, `receiptSha256` | Project-owned music selection/audition receipt and its pinned hash |

Placements must fit inside the picture, be ordered and not overlap on the owned music track. Missing sources, changed receipts, invalid gain, unknown effects and unqualified timing fail explicitly. Dialogue and music gain are bounded to −60 through +12 dB. A receipt hash binds the decision; it does not prove listening or licensing.

FilmCraft places source-linked audio on A2 and uses native volume automation. Linear-amplitude fades are approximated in the dB lane with sample-positioned points (normally 5 ms spacing, bounded to 128 intervals per fade), a −96 dB endpoint floor and linear interpolation. Source offsets are included in native keyframe time. Resolve places the source directly on its second native audio track, uses `AudioVolume` and `SetFades`, and reads timing, level and fades back. Resolve music timing currently requires whole timeline frames; fractional-frame sample placements are refused without rounding. Neither path uses another editor or a pre-mixed final video.

`kind: "music-gain"` revision packets preserve the existing native project/timeline and adjust only explicit inspected targets:

- FilmCraft: `edits: [{"clip": <native clip ID>, "deltaDb": -6}]`; only a clip on A2 is allowed. Clip gain changes while the existing fade automation remains intact.
- Resolve: `edits: [{"track": 2, "itemIndex": 0, "deltaDb": -6}]`; `itemIndex` is zero-based. The timeline is duplicated before changing native volume.

The packet must include the current `expectedFingerprint`, new checkpoint/inspection destinations and the other adapter-specific fields described in the native adapter. Update the render plan's bed level to the resulting level. Both paths check that source identities and cut timing remain unchanged. FilmCraft fingerprints include saved project bytes so edits to keyframe values cannot hide behind unchanged keyframe counts. Always inspect again after a saved native change.

## Mechanical evidence

Synthetic 640×360, 25 fps tests used a 440 Hz dialogue signal and an 880 Hz stereo music signal. The music began at frame 5, used a one-second source offset, lasted 1.6 seconds, and had 0.2-second fades. Both editors rendered their own H264/AAC files with 50 video frames and successful full decode.

| Measurement | FilmCraft | Resolve Studio 21.1.1 |
|---|---:|---:|
| Initial music level | −11.999 dB | −11.999 dB |
| Revised music level | −17.998 dB | −17.997 dB |
| Dialogue change against same-engine baseline | −3.000 dB | −3.000 dB |
| Dialogue change during music revision | <0.001 dB | <0.001 dB |
| Native cut ranges preserved | Yes | Yes |
| Decoded picture frames identical after revision | Yes | No; 49.16 dB average PSNR |

Resolve's duplicated timeline retained the source ranges and caption input values, but its rendered picture showed small differences. An unchanged repeat render was identical to the revised render. Do not claim exact picture identity for Resolve duplication from this fixture. Native Fusion exports contain changing cache paths and internal IDs. `RESOLVE_STATE.md` now qualifies stable graph inspection across reopening the same timeline; different native IDs/cache paths still prevent treating duplicated timeline fingerprints as equivalent.

These are mechanical measurements, not real music auditioning, difficult speech-join acceptance, human approval, or proof of full finishing. Arbitrary ducking envelopes, overlapping beds, changed music sections and general audio cleanup still need supported native operations and acceptance. Premiere continues to use the packaged canonical music-stage bridge and requires its own dedicated toolkit render fixture.

## FilmCraft music-source replacement

`kind: "music-replacement"` replaces selected existing beds on an inspected copy. The `music` owner must choose/audition the replacement first, import it as a new project-owned source, and write a new immutable selection receipt. Append the new source record to the plan; retain all old records. Only selected beds' `sourceId`, `receiptPath` and `receiptSha256` may change. Cuts, other beds, framing, captions, graphics, dialogue treatment, placement, source offset, duration, gain and fades remain fixed.

```json
{
  "kind": "music-replacement",
  "previousPlan": "<project>/10_WORK/published-plan.json",
  "previousPlanSha256": "<pinned hash>",
  "plan": "<project>/10_WORK/replacement-plan.json",
  "musicIndices": [0],
  "nativeProject": "<project>/10_WORK/parent.fcproj",
  "expectedFingerprint": "<fresh inspection fingerprint>",
  "outputProject": "<project>/10_WORK/replacement.fcproj",
  "inspection": "<project>/10_WORK/replacement-inspection.json",
  "inspectSession": "<project>/10_WORK/replacement-preflight",
  "session": "<project>/10_WORK/replacement-session",
  "reopenSession": "<project>/10_WORK/replacement-reopen"
}
```

Indices are zero-based. Replacement sources must be distinct audio-only PCM files, at the project sample rate, with the original mono/stereo channel count and enough samples for the preserved source range. Preflight probes and fully decodes them. The adapter refuses locked, linked, grouped, retimed or custom-channel-routed targets. It imports through FilmCraft and replaces only the selected clip's media binding. A complete saved-project comparison protects names, labels, effects, source-relative fade keys, other clips, tracks and existing bin items, both before and after reopen. The parent is never overwritten. Rendering revalidates native music source bindings/timing against the plan; use the usual native render/publication path afterward. Failed operations retain their journal and require reconciliation; inspection session paths must be fresh on a reconciled retry.

A direct native fixture replaced the first of two mono music placements at a one-second source offset, keeping 80 ms fades and a 0.6-second duration. Both native exports decoded 50 frames; all picture pixels were identical. The selected 220 Hz test tone was replaced by 1320 Hz, with more than 40 dB separation in each direction. The second bed and the 440/880 Hz dialogue signals changed by less than 0.01 dB in the checked windows. All protected native fields, twelve prior artifacts, source/parent files and feedback remained intact. An initial preflight assumption that audio had an intrinsic time-remap effect was corrected from native evidence; no replacement had occurred in that failed attempt. The measurement script's original assumed music frequency was also corrected against the actual source.

A subsequent real Codex build and browser-submitted replacement also passed with two immutable 50-frame versions, identical decoded pictures, preserved dialogue/other-bed levels within 0.01 dB, protected native state and source/parent hashes. Both saved versions reproduced their complete archived inspections and checkpoint hashes on fresh reopen. Late feedback remained bound to V1 and V2 required fresh review. See `LIVE_AGENT_LOOP.md` for the reproducible scenario.

These fixtures prove bounded synthetic native execution and the Codex/FilmCraft review loop; they do not prove real auditioning, audio-quality approval, other agent/engine combinations or reference fidelity. Different source offsets, channel conversions, overlapping beds, and new automation remain unsupported by this operation. Premiere does not yet implement music-source replacement; report that limitation without switching engines.

## Resolve music-source replacement

Resolve Studio **21.1.1 build 10** supports the same pinned previous/new plan and `musicIndices` contract through its own DRT timeline archive. Resolve's native audio `AddTake` returned false; audio take-count/selection getters returned null, with the disposable probe unchanged. Video take replacement must not be assumed to work for audio. Media-pool-wide `ReplaceClip` would also change the parent and other occurrences, so this operation does not use it.

The Resolve packet uses these fields alongside `kind`, `previousPlan`, `previousPlanSha256`, `plan`, `musicIndices`, and a fresh `expectedFingerprint`:

```json
{
  "nativeProject": "<project>/10_WORK/music-revision.drp",
  "inspection": "<project>/10_WORK/music-revision-inspection.json",
  "archiveDirectory": "<project>/10_WORK/music-revision-archives",
  "title": "Clip music revision 2"
}
```

All destinations and timeline names must be fresh. The selected replacement paths must not already exist in Resolve's Media Pool; CLI source registration alone does not import them into the editor. Each source must meet the shared prepared-PCM, sample-rate, channel-count and duration requirements. Source offsets, duration and fades currently require whole timeline frames, without rounding. Native frame comparisons ignore at most `1e-9` frame of floating-point representation noise; a one-sample timing displacement is still rejected.

The adapter exports the inspected parent as DRT, imports each replacement source into a temporary native donor timeline, and exports its media descriptors. It creates a new DRT by changing only selected music clips' `MediaRef` and `MediaFilePath` leaves and appending the new native media descriptors. All other original archive bytes—including effects, automation and channel routing—remain intact. Native import creates a new timeline, after which explicit readback verifies sources/ranges, the full protected state, Fusion graphs, markers, flags, names and audio channel mappings. Fresh source flags are copied and selected names restored because native import otherwise uses the new filename. The existing parent timeline is rechecked, then the project is saved and exported as a new DRP. Archive/hash and native-readback receipts remain in `archiveDirectory`; failed intermediate timelines and donor media stay available for reconciliation. The operation never invokes Premiere or FilmCraft.

A fresh Resolve-only fixture independently built and replaced one of two stereo music beds using a one-second source offset, 0.6-second placements and 80 ms fades. Both final exports decoded 50 frames and 97,216 audio sample frames. Every decoded picture pixel was identical. The selected 220 Hz tone changed to 1320 Hz; measured dialogue and the unselected bed changed by less than 0.01 dB in the checked windows. Custom name, color, marker, source flags, native fades/properties and channel mappings survived save/close/reopen; parent checkpoint/source hashes stayed unchanged. The previously open review project's complete snapshot and render queue were restored. Earlier failed probes were retained and reconciled; the successful fixture has no unresolved operations.

This is direct native execution on synthetic tones. The subsequent Codex/Resolve review-room scenario also passes: two immutable versions, identical picture pixels, preserved dialogue/second-bed levels, complete native-state inspection, final save/reopen and retained late feedback opening historical V1. See `LIVE_AGENT_LOOP.md`. Claude execution, real music auditioning, speech/audio quality, other Resolve/archive versions, nested archive bins, changed sections and new envelopes remain separate acceptance work. The auxiliary native donor timeline is retained for recovery; it is not the final composition or render path.

## Live Resolve agent-loop audio finding

The 2026-10-23 Codex/Resolve caption-wording fixture completed native build and revision publication, but its strict decoded-audio identity check failed. Both versions decoded to 97,216 stereo sample frames. The difference RMS was −78.04 dB relative to the original signal, maximum float-sample difference 0.000370525, and correlation 0.9999999922. Inspected cut geometry, source identity, audio properties, fades and links were unchanged.

An additional unpublished render of the unchanged V2 timeline also produced different decoded audio (−74.70 dB difference RMS relative to signal). Repeated native output can therefore vary in this fixture; the mismatch alone does not establish an editorial audio mutation. Its cause remains unqualified, and no human listening or speech-sync approval is claimed. The checker retains the exact-audio failure rather than accepting a newly chosen numerical tolerance.

Both exports reported 2.000000 seconds of video and 2.069333 seconds of AAC audio in the container, with both streams starting at zero; decoded PCM duration was 2.025333 seconds. These observations do not by themselves establish an AV offset or explain codec padding. Real speech and duration/padding qualification remain open. See `LIVE_AGENT_LOOP.md` for the reproducible isolated fixture.

## Resolve source-codec isolation

A controlled follow-up on Studio 21.1.1 build 10 used a separate native copy of the synthetic review project. The existing review timeline's complete inspected snapshot and original render queue were verified unchanged after every probe and restored to the original page. Ten native exports completed and decoded with 50 video frames each.

| Source / native output | Repeat decoded-audio comparison | Decoded sample frames |
|---|---|---:|
| Existing AAC source / AAC output | Different, −80.62 dB difference RMS relative to signal | 97,216 |
| Existing AAC source / 24-bit PCM output | Different, −79.59 dB | 96,000 |
| Fresh native AAC-source cuts / 24-bit PCM output | Different, −79.74 dB | 96,000 |
| Same cuts from a prepared PCM source / 24-bit PCM output | Exactly identical | 96,000 |
| Prepared PCM-source cuts / AAC output | Exactly identical | 97,216 |

The PCM source retained the source's compressed picture stream and used decoded 24-bit audio. This control points to the AAC source path under test, rather than only final AAC encoding; it does not identify Resolve's internal cause. The best local alignment over ±8 samples was zero in each comparison. PCM output duration was exactly two seconds, while AAC retained the previously observed container/decoded padding. These measurements do not certify speech joins, audibility or padding behavior in other players.

The production Assembly Design compiler already requires matched-rate PCM for played dialogue. The old synthetic agent fixture bypassed that production binding and used AAC input directly. Future Resolve `native_agent_fixture.mjs prepare` runs now call the existing `assembly-design/scripts/prepare_audio_precision.py` owner before design: retain the original registered source, prepare PCM-in-MOV without re-encoding picture, verify all packet payload hashes/presentation times, and register a separate prepared source. The fixture pins helper/receipt hashes and both source identities; its checker verifies the lineage and unchanged bytes. Historical fixtures remain unchanged and retain their failed exact-audio results.

A new preparation check preserved all 100 picture packets and clocks and registered the verified PCM source. The subsequent full Codex/Resolve build → browser caption revision → native V2 loop passed in a fresh Resolve-only toolkit installation. Both exports decoded to identical audio, with zero maximum sample difference. The exact-audio rule was not relaxed. Historical AAC-source failures remain recorded; real speech, padding and the other finishing/agent combinations still require independent qualification. See `LIVE_AGENT_LOOP.md`.

## Explicit FilmCraft dialogue treatment

`audio.dialogueEffects` transports an owner-selected chain per cut, with a project-owned receipt and SHA-256. Schema `acq-edit/dialogue-effects-v1` requires exact cut coverage and bounded highpass, amplify, single-band compressor and hard-limiter parameters. The adapter applies native effects and verifies their order, enabled state, static values and absence of masks before export. Other engines refuse this transport explicitly. It does not select settings, establish listening evidence, or imply audible quality. Keep native clip gain at the owner-selected level; FilmCraft applies intrinsic volume after the effect chain.
