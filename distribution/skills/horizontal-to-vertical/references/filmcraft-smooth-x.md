# Filmcraft framing — fixed crops and source-local tracking

Use for editable Filmcraft framing on an existing cut. Follow the shared
[Filmcraft execution contract](../../edit/references/filmcraft.md). Assembly Design
owns camera/layout switches and deliberate zooms/pans; this skill implements them.
The Premiere route remains unchanged.

## Choose movement before writing keys

Default stable dialogue shots to a **fixed crop per existing source cut**. Measure
an intended-subject X from that cut's valid observations; use a source-safe median
when it keeps the subject comfortably framed throughout. Static crops have no Anchor,
Position or Scale animation. Do not key an entrance pan merely because a new cut starts.
If real travel cannot fit that crop, use source-local tracking or return unusable
coverage to Assembly Design. Preserve an explicitly approved authored move.

Keep the measured Y and chosen Scale consistent across compatible shots. A paper-plan
beat or caption boundary does not justify recalibrating Y/Scale or restarting a zoom.
Different cameras, panels, geometry or posture can require separate calibrations;
never copy a seated calibration onto a standing shot. Fixed Y overrides face-box bob.

## Source continuity is different from timeline adjacency

Never Gaussian-smooth crop positions across a **source-time jump**, even if the media
file, camera label, output crop and timeline butt cut are the same. Averaging different
source compositions produces a sideways drift before the cut and a settling pan after
it. More keys, a higher sigma, or matching the outgoing/incoming anchor values do not
repair that behavior. Recenter independently at the hard cut; keep each side stable.

Dense tracking may share a filter run only across subdivisions that preserve the same
media identity and exact source continuity (`previous.sourceOut == next.sourceIn`),
compatible framing and contiguous timeline coverage. A different camera/layout or a
gap also resets the run. `--single-camera-run` cannot override a source-time jump.
A physical pose/background jump in the source is distinct from animated crop motion;
do not recut approved dialogue or invent a pan to conceal it.

Do not recalibrate a crop at an artificial subdivision of the same source-continuous
camera/layout run. Fit one fixed crop or one tracking curve for that whole run and
slice it onto the native items using media-time keys; preserve the authored zoom's
progress instead of restarting Scale at each item. Separately list source cuts and
layout cuts before construction. A layout switch a few frames away from a source
cut can expose an unintended one- or two-frame intermediate composition. Return
that collision to Assembly Design for an explicit picture-only boundary decision;
do not silently retime dialogue, insert a dissolve, or call the flash a smooth cut.

## Analysis and calibration

Reconcile the latest native project, exact item IDs, source ranges, timeline bounds,
speed, Motion baseline and protected audio/caption/effect state before planning. Use a
new output project, not a reconstruction over reviewed edits.

Use the existing YuNet `detector_for` and `select_face` in
`scripts/premiere_native_reframe.py`, with a visually calibrated intended-subject ROI.
For tracking, decode every displayed source frame; sparse interpolation is not dense
detection. Keep source/model/code identities, ROI, observations and missing detections
with the tracking artifact. Check cached source identity and exact coverage. Short
detector gaps may be interpolated; long gaps or no detections require an explicit,
visually checked fallback or coverage repair, never a success label.

For justified tracking, clean source-local observations with a short Savitzky–Golay
filter (up to7 frames, odd, order2), then Gaussian-smooth each source-continuous run.
Sigma10 frames at24000/1001 fps is a starting point, not proof of good motion. Write one
native Linear Anchor-X key per displayed frame; Y remains exactly fixed. Do not add
per-frame easing. Static crops need no keys and are not failed dense tracking.

For centered Position, square pixels and uniform scale `s = percent/100`, clamp X to
`output_width/(2*s) .. source_width-output_width/(2*s)`, and check the equivalent Y
bounds. Choose scale and headroom visually before clamping; reject source-edge exposure
rather than silently increasing zoom. Absolute calibration values are footage-specific.

## Existing native writer

`scripts/filmcraft_smooth_x.py` supports a square-pixel, unit-speed, centered, single
visible full-frame picture track. It defaults to `--motion-mode fixed`; use
`--motion-mode track` only for a needed movement. Resolve panels/coverage first; use
an explicit project-pinned panel adapter for multiple source geometries/calibrations.
Do not flatten panels or silently substitute cameras to bypass this limitation.

Supply immutable `--project`, current `--inspection` from `sequence_inspect`, and
`--tracking` containing `width`, `height`, `fps` and ordered `items`. Each item must
match `clip`, `startFrame`, `endFrame`, `sourceIn`, `sourceOut`, `samples` and normalized
per-frame `face` observations. Tracking also needs reviewed `run` IDs or an explicit
`--single-camera-run`; fixed crops do not share motion across cuts.

```bash
python3 __ACQ_SKILLS__/horizontal-to-vertical/scripts/filmcraft_smooth_x.py \
  --project /project/10_WORK/current.fcproj \
  --inspection /project/10_WORK/sequence-inspect.json \
  --tracking /project/10_WORK/dense-face-track.json \
  --plan /project/10_WORK/framing-plan.json \
  --anchor-y <measured-source-y> --scale <chosen-percent> --motion-mode fixed
```

Add `--apply --binary <pinned-cli> --session <new-directory> --output <new.fcproj>`
for application. The writer rejects stale geometry, changed protected fields and
existing outputs. For tracking it passes timeline ticks to `effects.setParam` and
verifies serialized keys at source-media ticks. Save/reopen and retain receipts;
reconcile uncertain mutations before retrying.

## Targeted rendered check and handoff

Inspect every cut's first/middle/last frames and the entry/exit boundaries, **plus a
rendered motion sequence around source cuts**, including the opening. Still frames,
constant Y, a dense key count or continuous X values alone cannot establish that the
crop does not drift. Compare source and rendered background motion to distinguish
actual camera movement from digital panning. Check headroom, full heads, correct
participants, panel coverage and source-safe edges. Correct concrete failures before
export; no recurring independent audit loop.

Reopen the project and verify the selected mode: fixed crops have zero animated
reframe keys; tracking has full key coverage, fixed Y and no unplanned Position/Scale
animation. Preserve exact source/timeline geometry, links, audio, captions and unrelated
effects. Keep native readback, rendered inspection and user approval separate. Open
the verified output in Filmcraft when framing review is requested; avoid redundant GUI
instances or closing unrelated unsaved editor sessions.
