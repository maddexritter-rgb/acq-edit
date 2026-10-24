# Native camera panels

FilmCraft and Resolve construction accept `panel-layout` as a framing decision for a cut. In FilmCraft, each panel remains a native source-linked sequence; a native layout sequence composes them, and the master contains that layout for the exact cut interval. Dialogue stays on the master's original audio track. Captions and imported graphics remain outside the panel nests. There is no intermediate stacked movie or editor conversion.

Assembly Design owns camera choice, sync ranges and layout intervals. The packaged horizontal-to-vertical skill owns panel-specific crop/tracking and visual inspection; use its `references/native-split-setup.md` contract. The adapter consumes those decisions and never detects a subject or invents synchronization. Hashes prove which decisions were executed, not that camera sync or composition is editorially correct.

## Plan and camera receipt

The ordinary `acq-edit/framing-v1` receipt still pins the framing decision. A `shots[cutId]` entry can be:

```json
{
  "mode": "panel-layout",
  "cameraReceiptPath": "<project>/10_WORK/camera-decision.json",
  "cameraReceiptSha256": "<sha256>",
  "panels": [
    {
      "id": "top",
      "sourceRange": {"sourceId": "<camera-a>", "sha256": "<source-hash>", "inFrame": 50, "frames": 25},
      "rect": {"x": 0, "y": 0, "width": 360, "height": 320},
      "crop": {"mode": "fixed-crop", "sourceWidth": 640, "sourceHeight": 360, "x": 80, "y": 20, "width": 360, "height": 320}
    },
    {
      "id": "bottom",
      "sourceRange": {"sourceId": "<camera-b>", "sha256": "<source-hash>", "inFrame": 75, "frames": 25},
      "rect": {"x": 0, "y": 320, "width": 360, "height": 320},
      "crop": {"mode": "fixed-crop", "sourceWidth": 640, "sourceHeight": 360, "x": 120, "y": 20, "width": 360, "height": 320}
    }
  ]
}
```

This example targets a 360×640 output. The camera receipt has `schema: "acq-edit/camera-layout-v1"`, `owner: "assembly-design"`, the output `width`, `height`, `fps`, and `cutsSha256` from `common.fingerprint(spec['cuts'])`. Its `layouts[cutId]` is the exact ordered list of each panel's `id`, `sourceRange` and `rect` (excluding `crop`). This binds camera choices to the complete current assembly. The framing owner cannot change those choices by changing a crop receipt alone.

Each cut has two to four uniquely identified panels. Integer output rectangles must tile the whole frame without overlap or gaps. Each camera's range must have the cut's duration, a nonnegative source in-frame, a registered source hash and enough source frames. Indexed frame counts are used when available; otherwise frame counting runs once per source during that validation. Nominal and average source rates must match the timeline. These checks are not complete packet-level VFR certification.

Each panel crop must match its own rectangle's aspect ratio, not the master frame. It can use the existing fixed-crop contract or a source-bound `tracked-crop` curve. Tracking's source ID/hash/in-frame/count must match that panel camera, which can differ from the dialogue cut. Nested panel layouts, output gaps, border/shadow effects, arbitrary opacity and retiming are not supported by this construction path.

## FilmCraft construction and inspection

Each occurrence gets distinct `ACQ_Panel_<cut>_<panel>` sequences and its own `ACQ_Layout_<cut>` container. Panel sequences contain one original camera item and no audio. Their dimensions crop the source to the panel, and their parent nests use static native Motion to place them in the output. Tracking keys live inside each camera sequence at the camera's source clock. Separate occurrences do not share editable framing state.

The new master is initially assembled with its original linked sources. After creating the native nests, a typed saved-project construction step changes only each panel cut's picture reference/source-in to its generated layout and resets that new parent's Motion to identity. Existing master clip identities, record intervals, links, dialogue, captions and graphics remain. The project is reopened natively before use. This is new-project construction, never an in-place reconstruction of an inspected user project.

Saved-native verification checks the master and nested clocks, source paths, dimensions, panel rectangles, all tracking keys, unique nest identities, enabled tracks/clips, lack of nested audio, identity parent transforms and the supported effect stack. It refuses flattened replacements, unexpected masks, rotation, opacity, time-remap, track effects and shared occurrences. Render rechecks the plan and native graph before invoking FilmCraft's exporter.

Caption-only revisions retain and reverify the complete layout. `fixed-framing` and `tracking-framing` cannot edit a panel target. Existing panel crop/tracking/rectangle changes use the guarded `panel-framing` route below; unsupported camera replacement or count/mode changes must not rebuild the user's timeline or change dialogue. Review text mentioning panels/layouts routes to both Assembly Design and horizontal-to-vertical without automatically requesting a spoken recut.

Premiere explicitly rejects this shared panel-layout transport before native mutation. Its native implementation remains required for the pilot. Do not substitute another engine, a converter or a flattened panel file.

## Resolve construction and inspection

Resolve Studio 21.1.1 build 10 constructs a Fusion composition directly on each selected picture cut. Each camera is a native MediaIn bound to its imported Media Pool ID and original file, with independent source trim and composition clocks. Fixed Crop/BetterResize nodes or the native horizontal Transform/XYPath/BezierSpline route frame each camera. Merge nodes position the panels over a transparent output-sized canvas. Captions follow the composite, and imported graphics remain separate timeline tracks. The original dialogue cuts and links remain unchanged; panel inputs add no timeline audio. No Premiere or FilmCraft process executes this route.

The adapter verifies source paths, persistent Media Pool IDs, native source dimensions, trim/global clocks, per-panel crop/tracking, connections, masks/bypass, output format, rectangles and the final caption/output chain. It removes only the unused default MediaIn in the newly created composition. Existing user graphs are never reconstructed. Construction writes the persistent native media identity and sets the output format after camera initialization, so save/close/reopen retains the complete fingerprint without weakening Fusion state checks.

Caption-only revisions duplicate and reverify the native layout. Fixed-framing requests targeting native panels are rejected before timeline duplication, even when the new plan incorrectly claims a single fixed crop. Resolve panel crop/tracking/rectangle revisions use the guarded route below. Camera replacement, source retiming and adding/removing panels remain unsupported. The native calls use Blackmagic’s installed scripting interfaces and the [Fusion scripting reference](https://documents.blackmagicdesign.com/UserManuals/Fusion8_Scripting_Guide.pdf), including tool deletion and composition preferences; live behavior was verified on the stated Studio version.

## Panel revisions

FilmCraft and Resolve share the owner-supplied `panel-framing` plan/target contract. Use `native PROJECT_ID revise PACKET`. Resolve uses this packet:

```json
{
  "kind": "panel-framing",
  "previousPlan": "<project>/10_WORK/published-plan.json",
  "previousPlanSha256": "<published-plan-hash>",
  "plan": "<project>/10_WORK/revised-plan.json",
  "expectedFingerprint": "<fresh-inspected-parent-fingerprint>",
  "title": "Clip 01 panel revision",
  "targets": [{"cutId": "<cut-id>", "panelIds": ["top", "bottom"]}],
  "nativeProject": "<project>/10_WORK/panel-revision.drp",
  "inspection": "<project>/10_WORK/panel-revision-inspection.json"
}
```

The previous plan is hash-pinned and both plans undergo ordinary source, editorial, caption and framing validation. The new plan needs a fresh horizontal-to-vertical decision receipt. Crop-only adjustments retain the original camera receipt. Rectangle changes additionally require a fresh Assembly Design camera receipt matching the complete new layout. This route does not make editorial camera choices.

Only explicitly selected existing panels may change. Supported changes are source crop X/Y/width/height, the existing horizontal tracking curve, and output rectangle placement/size. Every rectangle must still tile the canvas without gaps or overlap, and every crop must match its panel aspect. Panel identities/order/count, source IDs/ranges/sync, source geometry, fixed/tracked mode, dialogue cuts, audio, captions, graphics and all unselected panels/shots stay fixed. Changing cameras or converting framing modes requires another operation; never substitute a recut or rebuild approved work.

The Resolve adapter reads the full native fingerprint, checks the previous geometry, duplicates the timeline, and compares the duplicate against the parent before editing. That comparison accounts only for new timeline/item identities and duplicate-specific Resolve cache paths; same-timeline fingerprints retain those fields. It then updates owned Crop/BetterResize/Merge values and existing spline keys. Complete native snapshots and exported Fusion graphs are compared around the mutation, omitting only the exact selected value slots. Connections, expressions, other inputs, captions, tracks and sources remain protected. A changed parent or uncertain result stops for reconciliation. Export produces a new checkpoint and media file; publish through the ordinary job-bound review workflow, requiring a fresh review decision.

FilmCraft uses the same `kind`, previous/new plan fields and `targets`, with these native paths instead of Resolve's `title` and output `nativeProject`:

```json
{
  "nativeProject": "<project>/10_WORK/published.fcproj",
  "expectedFingerprint": "<fresh-inspected-parent-fingerprint>",
  "outputProject": "<project>/10_WORK/panel-revision.fcproj",
  "inspection": "<project>/10_WORK/panel-revision-inspection.json",
  "inspectSession": "<project>/10_WORK/panel-inspect-session",
  "session": "<project>/10_WORK/panel-revision-session",
  "reopenSession": "<project>/10_WORK/panel-reopen-session"
}
```

Each session directory and output path must be new. FilmCraft verifies the parent, copies its saved project, opens the existing layout/camera sequences, and uses native `sequence.settings` and Motion commands to change selected fields. Sequence resizing explicitly disables automatic motion scaling; the adapter applies the reviewed geometry itself. Changed curves keep source-local native keys. The master sequence is restored before save and reopen. A complete saved-project comparison permits only the selected setting/parameter values and curve keys, plus the expected copy-derived document names. All other native fields, identities, sources, dialogue, captions, effects, tracks and unselected camera occurrences remain protected. The parent file hash must stay unchanged.

Premiere must report its missing panel-revision route. Neither backend may replace cameras, change sync, add/remove panels or change fixed/tracked mode through this operation. The direct native fixtures below are separate from the agent/review-room qualification in `LIVE_AGENT_LOOP.md`.

## Observed mechanical evidence — 2026-10-23

FilmCraft built, saved/reopened and natively exported a 50-frame 360×640/25 fps fixture containing two generated camera sources: a tracked top panel, fixed bottom panel and later full-frame shot. Sampled first/middle/last panel frames and the full-frame boundary were viewed; both cameras and the master caption were visible with the expected crop. A native caption-only revision preserved every other project field except expected copy-derived document labels. Original checkpoint hashes were unchanged. Decoded audio was byte-identical across the single-camera baseline, panel render and caption revision.

A second 75-frame fixture used two independent split occurrences around a full-frame shot, nonzero camera source in-points and a later master record time. Native readback verified all panel source clocks and independent occurrences, and the native render passed frame count/geometry/full decode. Corruption checks refused disabled panel tracks, nested audio, shifted nest placement, changed opacity and shifted source clocks. Unit tests additionally cover missing camera receipts/binding, gap/overlap geometry, source duration/hash/rate changes, flattened/shared nests, masks and rotation.

Every decoded panel frame in both fixtures retained the intended camera color at all panel corners. The top source marker followed the supplied horizontal curve with at most 0.75 output-pixel edge error and fixed vertical bounds; the lower marker's rectangle remained fixed. Split entry/exit and repeated-occurrence contact-sheet frames were viewed. These measurements establish synthetic geometry transport, not human headroom or real-camera synchronization.

Resolve independently rendered a 75-frame 360×640/25 fps moving-marker fixture containing two split occurrences around a full-frame cut. Each camera used a different source clock; the top panel tracked horizontally and the bottom used a fixed crop. Save/close/reopen retained an identical complete native fingerprint. A caption-only revision rendered 75 frames, retaining the parent timeline/checkpoint and all inspected timeline fields after accounting for duplicated item identities. Exported Fusion graphs differed only in the requested caption wording and duplicate-specific Resolve cache paths.

Every panel frame in both Resolve versions passed camera-color and moving-marker checks. Maximum marker-edge error was 0.75 pixels in the top panel and 1.0 pixel in the lower panel. Sampled entry/exit, middle and repeated-occurrence frames were visually inspected. Decoded audio was not byte-identical: the difference measured −77.44 dB relative to signal. This remains an open audio qualification; no listening or audibility conclusion is inferred. These fixtures use simple test captions and do not qualify the production caption handoff on panel layouts.

Resolve panel revisions also exercised two changes on the first split occurrence while preserving the later split and full-frame shot. One swapped panel rectangles, moved both source crops and replaced the tracked camera's X curve. Another resized the split from 320/320 to 240/400 output pixels with matching 480×320 and 288×320 source crops. Both saved/reopened with identical complete fingerprints and exported 75 frames, retaining parent timelines/checkpoints. All changed and unchanged panel frames passed source-marker checks: maximum edge errors were 0.75/1.0 pixels for the swap and 1.0625/0.75 pixels for the resize. Sampled rendered frames were viewed.

Both revision fixtures retained byte-identical decoded audio. Unselected picture frames were identical for the resize; the swap differed at 62.19 dB PSNR despite unchanged inspected native state. These successful audio comparisons do not resolve the earlier Resolve output-variability cases or establish real-speech acceptance.

FilmCraft exercised the same swap/crop/tracking revision and unequal-height resize through its native commands on a 75-frame project. Both copied projects reopened, passed complete protected-project comparison, exported 75 frames and preserved the original native hash. Every panel frame retained the selected camera color and measured geometry: maximum marker-edge errors were 0.75 pixels for the changed tracked panel in the swap and 0.6875 pixels in the resize. Fixed-panel edges matched exactly. Both decoded audio streams were byte-identical to the parent. Unselected rendered pictures were not byte-identical: PSNR measured 64.92 dB for the swap and 86.57 dB for the resize, despite unchanged inspected native fields. These measurements do not identify the cause or establish perceptual equivalence.

These direct native-adapter fixtures do not establish real multicamera synchronization, headroom/phone composition, automatic panel planning, both-agent acceptance, Premiere panel support or human approval.

A separate real Codex/FilmCraft run executed the frozen 75-frame panel build, then a browser-submitted swap/crop/curve revision through Apply revisions. Both jobs published immutable versions and reached ready. The independent checker passed exact plan/receipt/owner routing, all native clocks/geometry, protected saved-project comparison and byte-identical decoded audio. All 100 panel-frames per version passed, with maximum marker-edge error 0.75 pixels. V2 required fresh review, late feedback stayed pending and its timestamp opened read-only V1. This qualifies only synthetic execution of specified geometry; see `LIVE_AGENT_LOOP.md` for reproduction and limits.
