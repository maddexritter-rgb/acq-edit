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

Resolve's duplicated timeline retained the source ranges and caption input values, but its rendered picture showed small differences. An unchanged repeat render was identical to the revised render. Do not claim exact picture identity for Resolve duplication from this fixture. Native Fusion exports also contain changing cache paths and internal IDs; their hashes are conservative state guards, not semantic comparisons between duplicated timelines.

These are mechanical measurements, not real music auditioning, difficult speech-join acceptance, human approval, or proof of full finishing. Arbitrary ducking envelopes, overlapping beds, music replacement/reselection and general audio cleanup still need supported native operations and acceptance. Premiere continues to use the packaged canonical music-stage bridge and requires its own dedicated toolkit render fixture.
