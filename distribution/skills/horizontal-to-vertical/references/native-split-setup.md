# Native, revision-friendly split-screen setup

Use this for editable Premiere deliverables. Camera choice and keyframe decisions remain in [native-camera-decisions.md](native-camera-decisions.md). This skill never substitutes a headless stacked render for the native split-screen master.

## Toolkit native construction

Use the repository `python/premiere_panels.py:request` to translate the frozen
`panel-layout` decision into `lab_place_camera_split`. Submit through the verified
ACQ Edit Agent stage helper with an exact project scope and fresh native baseline.
Each camera must already be imported from its verified original source. The current
route supports two 1080×960 panels in a 1080×1920 master, with dense source-frame
Anchor Point curves and a linked upper-panel shadow. It retains the original
source-linked V1/A1 assembly under the panels. Captions and music remain separate.

The handler corrects newly created panel items to exact tick boundaries, checks
all keys, removes only silent audio nests introduced by its own insertions, and
verifies protected sequences and existing dialogue. Preserve partial artifacts and
reconcile the original operation after any failure; never replay a failed build.
Store each request and native result as `{cutId, request, result}` in the framing
handoff's `panelSplits` array. Native completion uses the independent panel verifier,
including original source paths, clocks, keys, panel graph and shadow controls.
This transport does not choose sync, supply missing detections or approve composition.

For planned single-camera intervals between splits, use the repository
`scripts/apply_premiere_camera_shots.py` and guarded `lab_place_tracked_camera_shot`
on a duplicate master. Supply the Assembly Design source/timeline ranges and the
framing owner's dense curve and calibrated full-frame geometry. The tool replaces
only the selected picture-track interval, preserving residual source clocks,
captions, dialogue, lower camera coverage and original sequences. Do not stretch a
960-high panel to imitate a full-frame source shot. Verify the original-camera
paths, every native key, uninterrupted picture coverage and protected tracks with
`scripts/verify_premiere_camera_test.py`; then inspect native pixels and save/reopen.
This is a camera-stage test route, not an automatic full-job completion receipt.

## Project organization

Keep original media and reference projects untouched. In a working project, separate `RAW/FOOTAGE`, `RAW/AUDIO`, `SEQ`, and `ASSETS`. These bin roles and a source/edit/finishing sequence hierarchy were observed in a verified final's dependency graph. The descriptive names below are a recommended reusable convention, not a claim that every reference uses them.

- `00_SYNC_<slug>`: original linked camera and isolated audio sources; synchronization and full handles preserved.
- `10_EDIT_<slug>`: dialogue cuts, camera selections, split occurrences, and per-item reframing.
- `20_FINISH_<slug>`: nested edit plus separately editable captions/graphics and approved finishing controls.
- `PANEL_<occurrence>_TOP` and `PANEL_<occurrence>_BOTTOM`: independently editable panel nests under `SEQ/PANELS`. Use a distinct occurrence when its source or framing must change independently.

A draft-named sequence used by the verified final is part of that final's dependency graph. Unused drafts are not style authority. Preserve existing sequence names/IDs in reference projects; apply the clearer naming only to new working builds.

## Layer architecture

Recommended relative order in the edit, top to bottom (absolute track numbers need not match a reference):

| Layer | Content and responsibility |
| --- | --- |
| TOP IMAGE | Clean occurrence of the top-panel nest; no shadow-only preset |
| TOP SHADOW | Second occurrence of that **same** top-panel nest, exactly aligned, approved shadow preset |
| BOTTOM IMAGE | Independently framed bottom-panel nest/camera cuts |
| BASE CAMERAS | Source-linked single-angle edit and retained alternatives; explicitly control visibility |

The duplicate shadow and image must share nest identity, source in/out, speed, and timeline boundaries. Editing the camera framing inside the panel then updates both. Do not duplicate into an unrelated nest for the shadow, and do not flatten either panel into a movie. Nest video only or explicitly suppress duplicated nest audio; maintain one deliberate dialogue mix.

Inside each panel keep actual source clips, dense per-frame item-local Motion/Transform keys, and editable crop/mask geometry. A panel crop must create transparency outside the panel, not an opaque black fill that blocks the other camera. Preserve effect order. Camera-named adjustment layers are not additional camera footage. Do not copy a reference's crop/rotation/scale numbers to differently sized media without checking the composed frame.

Lock content cuts first, then key each source item. When a bottom-panel camera changes, cut/reframe that panel without disturbing the top panel's timing or motion. A shared clean/shadow nest is intentional linkage; different split occurrences should not share editable source geometry accidentally. Finishing captions stay outside the panel/shadow nests.

## Panel framing is independent of full-screen framing

This geometry contract applies to both Premiere and Filmcraft native adapters.
An approved full-screen crop does not establish a usable split crop. Frame each
panel against its own final visible rectangle after all Motion, Crop, masks and
parent transforms. Keep the complete head, including hair, inside that rectangle
with deliberate headroom. A face-center detection alone does not measure headroom.
Include hats and the complete crown/beard silhouette in that measurement. A fixed
expansion of a detected face rectangle can miss a hat; a batch median can also hide
an opening lean. Calibrate a distinct posture as a stable run, not animated Y bobbing.

Before writing panel keys, record the panel bounds, intended subject, source head
extent (hair/top through chin), desired headroom and shot size. Choose scale and
vertical placement together from those measurements. Inspect source-bound movement
samples and split entry/exit, not just one median face position. If the detector
has no head extent, measure it from source frames; do not invent it from confidence.
Use stable Y holds unless actual movement requires a deliberate correction.

Never reuse a full-frame eye-line fraction, hardcoded panel zoom or fixed face-center
pixel offset without validating the resulting complete head. A source-safe crop can
still clip a person's head at the panel boundary. Reducing zoom and lowering the
subject must preserve the panel rectangle and transparency, not slide the panel or
expose black edges. Check both panels independently at final output resolution and
at a phone-sized preview. Record actual top-of-head clearance and subject size,
including closest approach during motion. Required safe areas come from the output
profile or explicit user preference; do not claim a universal phone crop margin.

Reject a split when any sampled head intersects its panel boundary, an intended
subject is too large for the requested composition, or the reserved safe area is
violated. Numeric clock/sync/face-visible checks cannot establish this. Return
framing failures to this skill before export, preserving the assembly-owned layout,
full-screen shots, dialogue, captions and other approved state. No audit loop.

## Default split-screen shadow preset

→ Follow the [default split-screen shadow contract](split-shadow-default.md).
This treatment is required for new splits unless the user explicitly opts out.

By default, use the bundled [split-screen-shadow.prfpset](../assets/split-screen-shadow.prfpset), containing exactly one named preset: **Q&A Split Screen Drop Shadow**. It was isolated from the user-approved bundle with its dependency objects intact. No color-grade or other named presets are included. XML references were validated; native Premiere import and rendered appearance still require the test below.

Important: this one preset contains **two constituent controls**, Drop Shadow (`AE.ADBE Drop Shadow`) and intrinsic Motion (`AE.ADBE Motion`). Motion is part of the approved shadow setup, not a separate color/look preset. Apply the complete named preset only to the dedicated shadow duplicate, never to an already-keyframed visible source clip or the full finishing nest.

Saved static values include Shadow Only=true, Direction=180, Distance=49.700008392334, Softness=150, and Motion Scale=115 with centered Position/Anchor and zero rotation/crop. Opacity is serialized as249.899993896484 on a0–255 range; this is **not249.9%**. The native-controls route uses the explicit conversion 249.9/255 × 100 = 98%; never pass 249.9 as a percent. Several `CurrentValue` fields differ from `StartKeyframe`; do not reconstruct from `CurrentValue` (for example Scale1105 and Shadow Only=false are not the saved static settings).

The toolkit's native constructor writes the measured native controls directly to
TOP SHADOW: Opacity 98%, Direction 180, Distance 49.700008392334, Softness 150,
Shadow Only true, and parent Motion Scale 115. It verifies their stored values.
This is a native-controls implementation, not a claim that Premiere imported the
preset file. The clean TOP IMAGE stays at Scale 100 and shares the same panel nest.
Do not apply the preset again on top of that treatment. If explicitly using the
preset-import route instead, import only the isolated asset and read back the same
controls. Preserve the original bundle. In either route, inspect actual seam pixels;
matching values alone do not establish a match to the approved look.

## Revision and visual acceptance test

Coordinate exclusive Premiere/Bridge access with other active tasks before opening, switching, importing or changing a project. Work in an isolated editable copy, never save or close another task's project.

1. Verify nest/sequence dimensions, frame rate, source identity, sync and panel transparency before applying the preset.
2. Toggle TOP SHADOW: only the seam shadow should change; the clean subject stays visible. Toggle TOP IMAGE separately to confirm the lower occurrence is genuinely shadow-only.
3. Inspect split entry/exit and intermediate movement frames for gaps, clipped faces, unintended darkening, doubled imagery and shadow edges. Check the actual target resolution rather than treating distance/softness as resolution-independent.
4. Change a source-item horizontal framing key and trim one split boundary in the scratch copy. Confirm the shadow follows, both duplicates remain aligned, the other panel stays independent, and dialogue/captions stay synchronized.
5. Save/reopen the scratch project and render a short comparison. Report separately: structure inspected, preset extracted, native import verified, editable revision verified, rendered match accepted. Never claim full cross-project reproduction merely from XML similarity.
