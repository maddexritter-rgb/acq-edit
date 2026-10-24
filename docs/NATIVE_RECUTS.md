# Source-word recuts and dependent finishing

FilmCraft and Resolve now accept `kind: "spoken-recut"` through the native `revise` action. Assembly Design still owns word selection and speech-boundary decisions. This route executes a freshly compiled plan and fresh dependent finishing decisions in a new native project/timeline; it does not edit old source spans in place or guess a ripple operation.

Prepare the source-word selection and native cuts using `NATIVE_ASSEMBLY.md`. Recompute framing through `horizontal-to-vertical`, captions through `caption-clips`, text hooks through `text-hook`, audio/music through `music`, and graphic placement through its graphics owner. The native route currently supports the same fixed crops, text captions, explicit music and imported graphics as a native build. Complex multicamera layouts and advanced effects remain outside its qualified execution coverage.

A recut packet contains:

```json
{
  "kind": "spoken-recut",
  "parentId": "<submitted version UUID>",
  "parentVersion": "<project>/20_DELIVER/<clip>/v1-<UUID>/version.json",
  "plan": "<project>/10_WORK/jobs/<job>/finished-recut-plan.json",
  "finishingReceipt": "<project>/10_WORK/jobs/<job>/recut-finishing.json",
  "finishingSha256": "<receipt SHA-256>",
  "verification": "<project>/10_WORK/jobs/<job>/recut-execution.json",
  "construction": {"plan": "<same finished plan>", "output": "<new FilmCraft build directory>"},
  "inspectSession": "<new FilmCraft parent-inspection session directory>",
  "verifySession": "<new FilmCraft parent-verification session directory>"
}
```

For Resolve, `construction` uses its normal build fields: `plan`, a unique `versionId`, a new `nativeProject` DRP path and new `inspection` JSON path. FilmCraft session fields are unnecessary. Resolve must already have this toolkit project and the submitted parent timeline selected. The operation never switches to an unrelated project.

The finishing receipt has schema `acq-edit/recut-finishing-v1`, `parentVersionId`, `parentPlanSha256`, `planSha256`, `cutsFingerprint` and `components`. Each component has `owner`, `action` (`recomputed` or `not-used`), a concrete `reason`, and `valueFingerprint`. Required components/owners are:

| Component | Owner | Fingerprinted value |
|---|---|---|
| captions | caption-clips | Complete new `captions` array |
| framing | horizontal-to-vertical | Complete new `framing` object |
| audio | music | Complete new `audio` object |
| graphics | promo | Complete new `graphics` array |
| textHook | text-hook | Object containing new `captions` and `graphics` |

Use `common.fingerprint` for these canonical JSON fingerprints. A graphics decision may reference the specific configured graphics owner's supporting recipe in its reason; `promo` is the current shared native motion route. A `not-used` component must be empty, except `textHook`: ordinary captions may exist without an opening headline. The receipt pins decisions; it is not machine evidence of editorial quality, listening, reference fidelity or human approval.

## Parent preservation and publication

New publications pin the archived plan, native inspection and render receipt hashes alongside the media/native checkpoint hashes. A recut verifies all of these, preserves clip identity and output clocks/canvas, requires changed cuts and a changed source-word selection, and rejects missing or stale finishing decisions before native construction. Caption intervals must fit the new cut duration.

The parent native state must match the published snapshot, not merely a fresh snapshot of manually changed work. FilmCraft checks the working native file and full inspected state. Resolve checks its current native timeline snapshot, including supported Fusion/track/source/timing fields. Intervening changes stop the operation for reconciliation; they are not silently discarded. Resolve's unexposed color/Fairlight state remains an existing inspection limitation.

Construction uses new destinations. The adapter checks the parent again afterward and emits `acq-edit/recut-execution-v1` only if parent preservation and pinned inputs still hold. Resolve temporarily inspects the parent after construction and restores the new timeline only while the expected timeline remains selected. Failed constructions retain their native work and never authorize automatic replay.

Pass the returned `recutVerification` path in the native render packet. Rendering binds that proof to its exact plan, native file and inspected native fingerprint. Publication refuses changed source cuts without this proof; a plain new build cannot silently stand in for a recut. The proof is archived with the new immutable version. Job completion checks its hash, plus plan/inspection/receipt integrity. Changed clips return unreviewed and old feedback/timecodes remain bound to their original versions.

Older development publications without the new evidence hashes remain readable. They cannot satisfy the recut guard automatically. Inspect/reconcile their native state and create a verified publication before applying a spoken recut; do not rewrite historical manifests to fabricate missing provenance.

## Current qualification

Direct CLI/native fixtures in FilmCraft and Resolve removed the first of two synthetic source spans, retained the second, changed to a centered fixed crop, and replaced/retimed the caption from 50 frames to 25. Both editors produced native H264/AAC renders with the expected frame count and full decode. Sampled rendered frames visibly showed the new crop and caption. New immutable versions required review, parent bytes/state remained unchanged, and a 1.25-second comment stayed attached to the original 50-frame version.

The first FilmCraft attempt exposed an import-name collision with a canonical helper before native execution; the toolkit module is now uniquely named `recut_execution`. A repeated Resolve fixture exposed a duplicate timeline name; readback confirmed no new timeline, and the adapter now rejects name/checkpoint collisions before construction. Both were reconciled from actual state before continuing. Resolve's original review timeline was restored and its complete inspected fingerprint matched the pre-fixture state.

The direct fixtures above do not prove autonomous agent execution or played real speech. A subsequent real Codex/FilmCraft build and browser-submitted recut completed with two ready jobs and immutable versions: 50 frames became 25, preserving the surviving source picture/audio ranges and native links. The agent created fresh selection/framing/music decisions and the complete finishing receipt, retimed the caption and graphic, trimmed/offset music and published with archived recut proof. Independent checks verified native source/range/finishing state, hashes, all 25 visible graphic frames and the surviving picture region at 53.76 dB PSNR. Decoded audio retained the expected passage and music tones, with the removed passage's tone absent at the fixture threshold. The parent working project and all published/source files stayed unchanged.

The review room returned unreviewed V2, retained submitted feedback and kept a late 1.253-second comment attached to read-only V1, beyond V2's one-second duration. The reusable `recut` scenario and exact checks are in `LIVE_AGENT_LOOP.md`. This establishes agent execution of a prescribed synthetic recut with these dependent layers. It does not prove real source-word design, hook/payoff quality, word endings, acoustic joins, general finishing recomputation, other engine/agent combinations or human acceptance. Those remain pilot gates.
