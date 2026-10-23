---
name: horizontal-to-vertical
description: Convert footage already cut in Premiere Pro or Filmcraft into an editable native 9:16 sequence. Implements Assembly Design camera shots and split intervals from retained multicamera coverage. Uses fixed crops when stable and source-local tracking when needed. Use for reframe, vertical reframe, 16:9 to 9:16, face tracking, camera switching, or split screen. Never renders and re-imports replacement video.
---

# Horizontal to vertical — editable native framing

## Scoped production guidance

→ Load [scoped production policy](../edit/references/scoped-brand-policy.md), including on direct invocation; consume the `reframe` stage and assembly-owned mirror intent.
Implement only the current picture plan and verify the composed eyeline/top clearance; return unusable coverage to Assembly Design.

For any Premiere access, follow [Premiere Agent startup and advanced stage routing](../edit/references/premiere_start_here.md). Use the configured new bridge by default; if MCP tools are missing in this chat, use its CLI. Keep this skill’s existing creative scope and read-only limits.


This skill turns footage already cut in Premiere or Filmcraft into an editable 9:16
sequence. For multicamera assemblies, it implements Assembly Design’s revision-bound
shot and split plan, preserving explicit editor overrides. Missing plans or unusable
coverage return to Assembly Design. It never redesigns the spoken cut. It also preserves the planned camera-switch times;
→ Use Assembly Design’s [camera rhythm](../assembly-design/references/camera-decisions.md#beat-led-camera-rhythm) for those decisions.

## Backend mode

- **Premiere:** follow the native bridge route below; its sparse-key and per-item
  tracking rules remain unchanged.
- **Filmcraft:** read [Filmcraft framing mode](references/filmcraft-smooth-x.md).
  Default stable shots to fixed editable crops; track real movement only when needed.
  Never blend crop positions across a source-time cut. Keep Y and Scale calibrated
  across compatible shots; source-local dense tracking is separate from authored motion.
  Fit continuous camera/layout runs before slicing native items; check source/layout
  boundary collisions using the linked Filmcraft mode before building the picture.
  Follow [Filmcraft execution](../edit/references/filmcraft.md) for the pinned engine
  and transport; preserve the editor's current cut.

Do not switch backends or flatten panels to bypass an unsupported operation.

For a fresh Premiere conversion, the output is:

- A duplicated 1080×1920 review sequence in the active weekly Premiere project.
- Original source-linked dialogue cuts preserved; unused synchronized picture
  angles retained as editable coverage in the same project.
- Native `Motion > Anchor Point` keys on each individual picture item.
- Static Position and Y by default; sparse horizontal tracking keys in media time. For a specifically identified opening range with real stand/sit movement, Y tracking may be threshold-enabled only for that range.
- The resulting sequence opened in Premiere for review.

In Premiere, an explicitly requested seam repair on an already keyed 9:16 sequence is a
separate plan-first mode. It changes only existing Anchor Point **X** values
after a fresh edit/key baseline check; it never duplicates or rebuilds the
dialogue, captions, music, camera choices, or Y framing.

Never render a vertically cropped replacement, import a rendered file, use an adjustment-layer tracking curve, or burn the framing into media. When the selected backend is Premiere, unavailable native control is a blocker; do not silently switch to headless rendering or Computer Use. An explicitly selected Filmcraft run follows its native execution route above.


## Native bridge execution — Premiere

Follow the [shared execution contract](../edit/references/premiere_execution_contract.md). Use the configured Premiere Agent Lab reframe profile and [advanced native reframe route](references/advanced-native-reframe.md) for exact-project production scope, internal camera splits, reviewed shot maps, native panels and rendered QA. The canonical tracker/planner remains the owner.
Bind each picture item to fresh identity/source ranges and Motion state; verify exact media-time keys and protect dialogue timing, captions and music.
Keep interpolation, save/reopen and rendered crop review separate from immediate key readback; source frames alone do not prove native framing.

## Required route — Premiere

For a multicamera coverage stack, first read
[native-camera-decisions.md](references/native-camera-decisions.md) and the
[assembly picture-coverage contract](../assembly-design/references/camera_intent.md).
On a duplicate sequence in the active project, implement the planned full-frame angles and split intervals
from the revision-bound Assembly Design plan, while preserving the frozen 16:9 source and
unchanged dialogue. Keep unselected angles available on inactive source-linked
tracks/nests. Produce a selected picture sequence with no ambiguous overlapping
full-frame items, plus independent panel source sequences for intentional splits.
Only then run the native reframing driver on that selected full-frame sequence
and, separately, inside each panel source sequence. The driver intentionally
rejects a raw overlapping coverage stack; do not bypass that guard or treat
inactive alternatives as visible panels. If native camera selection cannot be
constructed or read back, stop and report it rather than silently preserving
the first camera.

For a normal full-frame timeline, run the canonical native driver:

```bash
python3 __ACQ_SKILLS__/horizontal-to-vertical/scripts/premiere_native_reframe.py \
  --preset alex-stage \
  --work-dir /absolute/path/to/native_reframe
```

## Mandatory preflight

Before running a mixed batch, inspect representative full source frames for every camera/framing family and record:

- The item boundary where the source family changes.
- Whether the source is already tightly framed; if so, use a `zoom: 1.0` preset rather than adding another punch-in.
- The intended speaker zone. A large foreground/audience face is not automatically the subject.
- Standing and seated face-center Y values for wide locked cameras.
- Whether a distant intended face falls below the detector's reliable size.

For a first range whose distant seated face may be undetectable, pass the visually measured normalized face-center with `--fallback-y-first-items <0..1>`. This value is footage calibration, never a universal preset constant. The option requires `--allow-y-first-items N` and applies only to detector failures inside that range.

If only the first `N` ordered picture items contain genuine stand/sit movement, add `--allow-y-first-items N`. Each allowed item gets its own static posture-aware Y; do not share a seated median with an adjacent standing item merely because the camera and edit seam match. An eligible item that changes posture receives two stable Y holds joined only across the detected stand/sit transition. It must never become continuous vertical face tracking; all ordinary movement remains Y-locked.

When one timeline contains materially different source framings, do not force one zoom preset across the batch. Use `--preset-after-item N --after-preset <preset>` at the known content boundary. For example, a wide stage camera may use `alex-stage` while already-tight source clips use `podcast` so the native fill crop does not receive an additional punch-in.

Choose the preset that matches the footage:

| Preset | Use |
|---|---|
| `alex-stage` | Wide stage, workshop, or Q&A camera with audience/set distractions |
| `center-stage` | Locked wide workshop/roundtable camera whose intended speaker position is centered; excludes larger foreground audience faces. Supply a measured fallback Y when the distant face is undetectable. |
| `alex-listicle` | Single desk or direct-to-camera shot |
| `guest` | Single guest camera |
| `podcast` | Already-tight produced podcast angle |
| `alex-split-top` | Host/source sequence intended for the upper split panel |

The driver performs the complete native workflow:

1. Reads the active Premiere project and sequence through the Premiere bridge.
2. Duplicates the active sequence inside the same project. A backup-only project
   copy is optional for recovery, never the active weekly default.
3. Changes only the duplicate to 1080×1920.
4. Reconciles every source-linked picture item by track, item index, media path, source in/out, and timeline in/out.
5. Detects the face inside each item’s exact source range.
6. Locks Y per item. In an explicitly allowed range, standing and seated items keep separate static posture-aware Y values; a genuine stand/sit change inside one item gets one short Y reframe between locked plateaus—never a bobbing continuous Y track. Camera/content-run changes reset X tracking. Across an eligible butt cut from the same camera and panel, match outgoing and incoming crop X while preserving each item's relative keyframed motion. Measure the boundary-frame subject X too: if the source person physically shifted, flag the remaining visible jump for rendered review instead of claiming key agreement solved it. Report crop-limited or no-face seams.
7. Simplifies the curve to a bounded rendered-pixel tolerance.
8. Clamps every X/Y Anchor value to the scale-dependent source-safe crop region so no key can reveal black outside the source frame.
9. Rechecks the inherited Motion baseline before writing anything.
10. Writes item-local Anchor Point keys at `item.inPoint + relative_time`, then saves and reads the keys back.
11. Opens the native review sequence at the first clip.

Do not reconstruct these mechanics ad hoc when the driver is available.

## Review boundary

Stop after the reframed sequence is open. The user reviews framing before captions, graphics, or other finishing begins.

Report:

- Active weekly project path.
- Active review-sequence name.
- Sequence dimensions.
- Number of source items reconciled and keyed.
- Total native key count.
- Any records that used a no-face fallback.

Do not call the result approved until it has been watched. Structural readback proves editability, not visual quality.

Before reporting the batch as done, visually inspect every picture item at minimum at its first displayed frame, midpoint, and last displayed frame, plus every posture-transition boundary and both rendered frames on either side of every camera/edit seam. Numeric X-key agreement alone does not prove visible continuity: a source-time jump can change subject/background placement even with identical keys. Fail the review if any sample shows:

- A cropped head or excessive headroom.
- A seated Y copied onto a standing item, or vice versa.
- Continuous Y bob instead of stable holds.
- The wrong person, an audience member, or a printed face being followed.
- Black source-edge exposure.
- An unnecessary punch-in on already-tight footage.
- An unexplained left-right jump when the same camera/panel continues across a cut.

Generate review sheets in timeline order and retain them with the plan/report. A sparse spot-check is not batch QA. Native key readback, zero crop-bound violations, and generated sheets are evidence, but user approval remains separate.

## Camera switching — Premiere

For Filmcraft fixed crops and tracking-run boundaries, use [Filmcraft framing mode](references/filmcraft-smooth-x.md).
Each existing Premiere item is an independent tracking run. Never interpolate across an edit.

- A different source path, track, camera angle, or non-butt timeline boundary starts a new framing group.
- Adjacent butt-cut items from the same camera may share Y only when their posture/framing state matches. Standing and seated items must retain separate static Y values.
- Adjacent butt-cut items from the same camera/panel must have continuous visible X unless source content, layout, or crop limits make that impossible; record those exceptions and check rendered frames. Keep their keys item-local and retain each shot's intended within-item movement.
- A different camera, panel, scale/layout, or non-butt join starts a new X run; do not force a match across it.
- Tracking keys use media time so later trims and razors retain the correct source motion.
- Position, rotation, speed, source range, and edit boundaries must remain unchanged unless the user separately requests an editorial change.

To repair an already keyed vertical sequence, first make a recoverable project
snapshot and verify the editor is paused. Run the canonical driver with
`--repair-existing-seams --work-dir <absolute-work-dir>`. This writes only an
`existing_x_seam_plan.json` and lists aligned and unresolved joins; inspect
that plan and the rendered frames on both sides of every proposed join. When
the active edit still matches, run `--apply-repair-plan <absolute-plan-path>`.
It uses the source boundary frames to flag subject movement that an Anchor-X
match alone cannot fix, then
rechecks the project, sequence, item ranges, and original key values before
writing only X at those existing key times. Do not use the fresh reframe route
to repair an approved keyed sequence. Save, close, reopen, and read back native
keys and non-picture tracks before handing it to the editor. If a seam remains
unresolved or the rendered subject jumps, flag it instead of claiming a clean
repair.

If the source is a produced multicamera master with angle changes inside a single timeline item, use the verified picture-only split operation in [advanced native reframe](references/advanced-native-reframe.md) at the reviewed visible camera changes first. Do not keyframe through an internal camera switch.

## Native split screen

→ Follow the panel-local framing contract in [native-split-setup.md](references/native-split-setup.md) for both execution backends. Face visibility alone does not prove complete-head clearance or phone-readable composition.

Split screen remains editable Premiere construction; it is never a baked stacked render. For left/right panels already baked into one master, use the flat native panel exception in [advanced native reframe](references/advanced-native-reframe.md). The independent-source workflow below applies to separate camera sources.

When overlapping source-linked picture tracks are detected, the canonical driver stops rather than guessing the visible panel geometry. Read [native-split-setup.md](references/native-split-setup.md), then:

1. Build or confirm independent source-linked top and bottom panel sequences.
2. Run `premiere_native_reframe.py` inside each panel’s source sequence with the appropriate preset.
3. Keep each panel’s keys item-local inside that panel sequence.
4. Assemble the panels in the finishing sequence with native Motion/Crop controls.
5. Keep the approved linked shadow duplicate beneath the clean panel; apply the supplied [split-screen-shadow.prfpset](assets/split-screen-shadow.prfpset) only to that shadow duplicate.
6. Preserve hard resets when either panel changes cameras.
7. Open the composed finishing sequence for review.

For camera-selection and listener-reaction decisions, read [native-camera-decisions.md](references/native-camera-decisions.md). Those are editorial decisions made before the reframing driver, not by face detection.
For explicitly approved 16:9 picture, consume the editor's actual panel intervals under
[assembly-design's picture-coverage contract](../assembly-design/references/camera_intent.md)
and translate their geometry to 9:16 without reselecting split timing. A missing plan requires picture-only planning by Assembly Design from retained angles.
Neither route may change the dialogue.

## Fail-closed conditions

Stop without writing when:

- The active Premiere project or sequence changes during analysis.
- A timeline item no longer matches its inspected media path or source/timeline range.
- Existing Motion keyframes changed after inspection.
- An existing-seam repair plan no longer matches its source items or native key values.
- The sequence contains overlapping source-linked tracks that have not been identified as native panels.
- A nested item cannot be resolved to source-linked picture items.
- Premiere does not create and activate the fresh 1080×1920 sequence duplicate.
- Native key readback does not cover every planned source item.

A no-face fallback may be written only when it is recorded in the report and the resulting framing is visibly reviewed. Never describe a fallback as tracked framing.

## Maintained implementation

- Premiere native runner: `scripts/premiere_native_reframe.py`
- Filmcraft fixed-crop / dense X planner/writer: `scripts/filmcraft_smooth_x.py`
- Filmcraft mode: `references/filmcraft-smooth-x.md`
- YuNet model: `scripts/yunet.onnx`
- Native split reference: `references/native-split-setup.md`
- Camera-decision reference: `references/native-camera-decisions.md`
- Native shadow preset: `assets/split-screen-shadow.prfpset`

Other historical render scripts in this folder are not part of this skill’s supported workflow. Do not call them from this skill.

## Reuse tracking safely

`premiere_native_reframe.py` caches native-plan tracking under the job work directory.
Other backend executors reuse `track_item(..., cache_dir=JOB_CACHE)` from the same
implementation. The source digest, exact source in/out, preset/ROI, sample interval,
detector model and implementation identify each entry. Timeline ordering is rebuilt
from the current cuts; a list length or existing `tracking.json` never proves reuse.
`tracking_cache.py` locks each key, validates coverage and writes atomically. A changed
source range misses even when the cut count stays the same. Consumers must bind every
ordered result to its current source interval and assert complete framing before
export; never silently truncate different-length lists with `zip`. Preserve accepted
manual framing and approved projects; cache reuse authorizes no timeline mutation.
