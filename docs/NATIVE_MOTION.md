# Motion assets in the selected editor

The graphics-owning skill designs the animation. The optional pinned Remotion integration creates an asset; FilmCraft or Resolve performs the final composition and export. This path does not require another editing backend. Premiere must use its scoped native stage and still needs a dedicated toolkit qualification.

## Render a parameterized asset

Install the optional integration's locked dependencies with `npm ci` in `integrations/remotion`. Its renderer may download Remotion's Chrome Headless Shell on first use. Keep dependency notices and follow the [Remotion license requirements](https://www.remotion.dev/docs/license/faq); setup does not purchase a license. The export settings follow Remotion's [transparent ProRes guidance](https://www.remotion.dev/docs/transparent-videos).

Save parameters inside the project, for example:

```json
{
  "text": "A clear idea.",
  "accent": "#b4caff",
  "font": "Arial",
  "size": 96,
  "enterFrames": 12,
  "exitFrames": 8,
  "transparent": true,
  "frames": 90,
  "width": 1080,
  "height": 1920,
  "fps": 30
}
```

From `integrations/remotion`:

```sh
npm run render -- /absolute/project/10_WORK/title-props.json /absolute/project/10_WORK/assets/title-v1.mov
```

Use the actual timeline canvas/rate and a locally available licensed font. The current composition supports a title with an accent bar, animated entrance and exit. It does not implement arbitrary After Effects projects, font installation, reference matching or advanced templates. Unknown parameters and invalid/overlapping entrance/exit intervals fail before rendering.

The output is silent ProRes 4444 with alpha. Its adjacent JSON receipt records resolved parameters, output hash, Remotion version, and hashes of the composition, parameter resolver, renderer and dependency lockfile. Existing output, receipt or reservation paths are refused. A failed render retains its partial artifacts and `.lock` reservation for inspection; do not remove the reservation while its process is active or replay an uncertain render. Use a fresh destination after reconciliation. The receipt pins source code and output but does not guarantee identical rendering across operating systems/fonts/browser versions.

## Place assets in an edit plan

`EditPlan.graphics` is an ordered array from back to front. Each entry contains exactly:

```json
{
  "path": "/absolute/project/10_WORK/assets/title-v1.mov",
  "startFrame": 15,
  "frames": 90,
  "sha256": "<actual asset SHA-256>"
}
```

Placement starts at asset frame zero. The requested duration must fit inside both the asset and the finished picture. The shared preflight verifies project ownership, immutable hash, one video stream without audio, ProRes 4444/4444 XQ alpha, matching canvas/frame rate, square pixels, no rotation metadata, sufficient decoded frames and successful full decode. Invalid assets are rejected before native construction. It does not silently resize, retime, freeze, loop, discard unsupported properties or import embedded sound. Sound belongs to the audio owner.

FilmCraft reserves V1 for picture and V2 for captions, then places successive assets on V3, V4 and so on. Resolve captions are composed inside the source clips; its successive assets use V2, V3 and so on. Separate tracks preserve overlapping assets. Both adapters read back exact source identity, source offset, record start and duration after placement. A matching alpha pixel format is not proof of a good visual matte; inspect the actual output.

## Replace an existing graphic

FilmCraft supports `native PROJECT_ID revise PACKET` with `kind: "graphic-replacement"`. Render the replacement asset through its owning graphics skill first. Keep the old asset immutable, use a new project-owned path, and preserve the existing placement, duration and array order. The replacement must pass the same alpha/canvas/rate/full-decode checks as construction. The plan's other fields must be identical.

```json
{
  "kind": "graphic-replacement",
  "nativeProject": "<project>/10_WORK/parent.fcproj",
  "expectedFingerprint": "<fresh native inspect fingerprint>",
  "previousPlan": "<project>/10_WORK/published-plan.json",
  "previousPlanSha256": "<published plan hash>",
  "plan": "<project>/10_WORK/replacement-plan.json",
  "graphicIndices": [0],
  "outputProject": "<project>/10_WORK/revision.fcproj",
  "inspection": "<project>/10_WORK/revision-inspection.json",
  "inspectSession": "<project>/10_WORK/replacement-inspect",
  "session": "<project>/10_WORK/replacement-session",
  "reopenSession": "<project>/10_WORK/replacement-reopen"
}
```

All destinations/sessions must be fresh. Indices are zero-based positions in the pinned graphics array. The adapter inspects the current native project, verifies exact source/placement bindings, and works on a copy. It imports one new media item per target and executes native `clip.replaceFromBin`, restoring the existing clip name and retaining its label. Native clip identity, placement, effects/keyframes, track state, unrelated bin items and all other timeline data remain protected. The saved project comparison permits only selected source-item replacements, the new imported bin items/ID allocation and the copy's document name. The copy is reopened and checked again before returning a fingerprint for ordinary native render/publication.

FilmCraft rejects linked, grouped, locked, reversed, retimed, frame-held and multicamera targets before copying. Adding/removing/reordering graphics, changing timing, or replacing a native text layer requires its own supported operation. FilmCraft exports also recheck the graphics' source/placement bindings against the plan.

### Resolve replacement

Resolve uses the same `kind`, pinned previous/current plans and `graphicIndices`. Supply `expectedFingerprint` from the current parent timeline, a unique `title` for the duplicate, and fresh `nativeProject` (output `.drp`) and `inspection` paths. FilmCraft's `outputProject` and session-directory fields do not apply. The parent must already be the current timeline in the exact toolkit project.

```json
{
  "kind": "graphic-replacement",
  "expectedFingerprint": "<fresh current-timeline fingerprint>",
  "previousPlan": "<project>/10_WORK/published-plan.json",
  "previousPlanSha256": "<published plan hash>",
  "plan": "<project>/10_WORK/replacement-plan.json",
  "graphicIndices": [0],
  "title": "Clip 01 graphic revision",
  "nativeProject": "<project>/10_WORK/revision.drp",
  "inspection": "<project>/10_WORK/revision-inspection.json"
}
```

Resolve duplicates the timeline and compares its inspected state and exported Fusion graphs before editing. It imports the replacement and uses `AddTake`, `SelectTakeByIndex` and `FinalizeTake` on the existing graphic clip. Native take extents use an inclusive end frame. On Studio 21.1.1 this requires the Edit page; the adapter selects it temporarily and restores the previous page even when the operation fails. The clip name, color and flags are explicitly restored. Cuts, placement, properties, fades, links, other graphics, Fusion fingerprints, markers and track state stay protected. The parent is checked again before saving and exporting a new checkpoint. Render rechecks graphic source/placement bindings.

Flags follow Media Pool sources, so each selected target requires a distinct replacement path that has not already been registered anywhere in the project's Media Pool. Use a fresh immutable asset copy when needed. This avoids changing metadata on another clip's source. Locked/linked targets, existing take selectors, selected graphics with Fusion compositions, and source extents inconsistent with the planned placement are refused. Arbitrary retiming, color-grade stacks and advanced per-clip effects have not been qualified by this route; inspected properties and Fusion comparisons are not a complete proof of those features. Premiere replacement remains unavailable; report that limitation without changing engines.

## Observed qualification — 2026-10-23

Remotion 4.0.538 rendered a 25-frame, 640×360, 25 fps title asset with alpha ranging from fully transparent to fully opaque. FilmCraft and Resolve Studio 21.1.1 each imported two overlapping placements at frames 5 and 15 over an existing 50-frame synthetic two-cut/caption plan. Each asset occupied its own native track. Native source/range readback and complete 50-frame H264/AAC exports passed. FilmCraft also reopened its saved project before export.

Sampled actual renders showed animated title/bar content over visible source footage, retained captions, and no overlay after its final boundary. A diagnostic comparison with straight RGBA compositing measured 34.30 dB PSNR for FilmCraft and 34.37 dB for Resolve; these are observations, not acceptance thresholds or proof of identical blending/color. This fixture used the same title twice to exercise overlapping placement; it does not qualify arbitrary layering or reference fidelity.

After successful rendering, Resolve saved and reopened the motion timeline. Source ranges, graphic placement, properties and track state were stable, but both existing caption Fusion hashes initially changed. A controlled follow-up captured direct exports before render, after render and after reopening: only a successful media-query cache marker and two exact empty preference placeholders disappeared. `fusion-state-v2` now normalizes those forms while retaining other values/content. Complete native snapshots match across reopen, real caption changes remain detectable and stale revisions remain blocked. See `RESOLVE_STATE.md` for the migration and exact scope; old receipt fingerprints are never silently rewritten.

The reopened follow-up timeline rendered 50 decoded video frames identical to its pre-reopen render. Audio differed at −74.61 dB difference RMS relative to signal, retaining the separate audio qualification failure. This does not establish identical audio or human approval.

The final exports came from their respective native editors. No Remotion final-video export, cross-editor conversion, real footage or human approval was involved. Advanced animation benchmarks, Premiere graphic replacement/composition, longer assets, other frame rates and real editorial review remain open. The earlier Resolve audio-variance finding is unchanged.

A subsequent FilmCraft fixture rendered a new Remotion title and replaced only the first of the two overlapping graphics. The parent had a native custom clip name and 72% opacity. Native replacement, complete protected-project comparison, save/reopen and the 50-frame export passed. The custom name/opacity, second overlay, cuts, captions, audio and original parent files remained intact. Decoded audio was byte-identical. The 25 frames outside the replaced asset's interval differed at 57.75 dB PSNR despite unchanged protected native state; no cause or perceptual equivalence is inferred. Sampled rendered frames visibly showed the changed title/accent and retained caption. This is direct-adapter synthetic evidence; agent-driven graphic revisions, real reference quality and human acceptance remain open.

Resolve Studio 21.1.1 independently replaced the first overlay in a separate 50-frame fixture. A custom clip name, 72% opacity, Pink clip color, Green flag and timecoded marker survived. Native duplication/protected-state checks passed; save/close/reopen retained identical inspected state including metadata, and the parent timeline/checkpoint and original review timeline remained unchanged. The selected replacement rendered visibly while the second overlay and caption stayed intact. An initial guarded attempt detected the lost source flag and stopped; restoring flags on fresh media fixed that case without weakening the comparison. A separate probe confirmed that Deliver-page take creation fails while Edit-page creation succeeds.

The Resolve render is **not exact-output qualified**: decoded audio differed at −77.16 dB RMS relative to signal (maximum sample difference 0.000457704), and the 25 unselected picture frames differed at 43.20 dB PSNR. These measurements do not establish a cause, inaudibility or human approval. Native replacement and reopen evidence are separate from the unresolved output-variance and real-media acceptance gates.
