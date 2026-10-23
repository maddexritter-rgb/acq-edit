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

## Observed qualification — 2026-10-23

Remotion 4.0.538 rendered a 25-frame, 640×360, 25 fps title asset with alpha ranging from fully transparent to fully opaque. FilmCraft and Resolve Studio 21.1.1 each imported two overlapping placements at frames 5 and 15 over an existing 50-frame synthetic two-cut/caption plan. Each asset occupied its own native track. Native source/range readback and complete 50-frame H264/AAC exports passed. FilmCraft also reopened its saved project before export.

Sampled actual renders showed animated title/bar content over visible source footage, retained captions, and no overlay after its final boundary. A diagnostic comparison with straight RGBA compositing measured 34.30 dB PSNR for FilmCraft and 34.37 dB for Resolve; these are observations, not acceptance thresholds or proof of identical blending/color. This fixture used the same title twice to exercise overlapping placement; it does not qualify arbitrary layering or reference fidelity.

After successful rendering, Resolve saved and reopened the motion timeline. Source ranges, graphic placement, properties and track state were stable, but both existing caption Fusion hashes initially changed. A controlled follow-up captured direct exports before render, after render and after reopening: only a successful media-query cache marker and two exact empty preference placeholders disappeared. `fusion-state-v2` now normalizes those forms while retaining other values/content. Complete native snapshots match across reopen, real caption changes remain detectable and stale revisions remain blocked. See `RESOLVE_STATE.md` for the migration and exact scope; old receipt fingerprints are never silently rewritten.

The reopened follow-up timeline rendered 50 decoded video frames identical to its pre-reopen render. Audio differed at −74.61 dB difference RMS relative to signal, retaining the separate audio qualification failure. This does not establish identical audio or human approval.

The final exports came from their respective native editors. No Remotion final-video export, cross-editor conversion, real footage or human approval was involved. Advanced animation benchmarks, graphic replacement revisions preserving manual effects, Premiere composition, longer assets, other frame rates and real editorial review remain open. The earlier Resolve audio-variance finding is unchanged.
