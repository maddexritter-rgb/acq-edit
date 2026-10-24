# Native audio execution

The packaged `music` skill owns track eligibility, choice, source offset, auditioning and creative shape. Adapters execute its explicit plan. Music is imported as a project-owned source under `00_SOURCE`; no private music library is bundled.

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

These are mechanical measurements, not real music auditioning, difficult speech-join acceptance, human approval, or proof of full finishing. Arbitrary ducking envelopes, overlapping beds, music replacement/reselection and general audio cleanup still need supported native operations and acceptance. Premiere continues to use the packaged canonical music-stage bridge and requires its own dedicated toolkit render fixture.

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
