# Upgraded native reframe route

The canonical runner and `premiere_reframe_bridge.ReframeSession` use the configured Premiere Agent Lab connector. `~/.config/premiere-agent/default.json` is the local default when present; `--bridge-profile` overrides it. Do not retry a failure through the retired mailbox, another bridge, UI automation, or Premiere Beta.

## Scope and ownership

The `scoped-edit` profile permits only the exact project named in its expiring `project_authorization` file. The connector independently checks the same project, exclusive lease, tool allowlist, output root and current revision. Never widen `fixture_root` to production. A new authorized job requires an exact new project scope, not a permanent all-project exemption. Inspect capabilities from the running connector; the pinned catalog may predate these operations.

The local authorization schema is `premiere-agent/edit-project-authorization-v1`: `projectPath`, ISO `expiresAt`, `tools`, exact source `readPaths`, and one `writeRoot`. Preserve other sessions' ownership. Unknown operations remain quarantined under their original IDs; no blind replay.

## Mixed-camera preparation

1. Snapshot the editor's current final timeline and save it. Duplicate it in the same project using `ReframeSession.duplicate`. Freeze the original.
2. Inspect first/middle/last source frames for every item. Search retained ranges for internal scene changes; scene scores are candidates, not editorial decisions. Review both sides, including gradual graphic entrances that scene detection can miss. Use actual native sequence-frame ticks for picture cuts.
3. Execute reviewed picture-only cuts with `picture_operation('lab_split_reframe_shots', {'cuts': [...]}, receipt)`. Each cut has `node_id`, `track_index`, and string `ticks`. This bounded QE route currently requires integer sequence FPS, unit-speed source media and static effects. Its native readback checks exact source coverage, effects and unchanged audio. Never use it to redistribute existing animation.
4. Reinspect after splitting. Create `premiere-reviewed-shots/v1`, bound to `project_path`, `sequence_id`, `revision`. Every picture item needs exactly one entry with `node_id`, `media_path`, exact `start_ticks`, `end_ticks`, `source_in_ticks`, `source_out_ticks`, reviewed `camera_id`, `layout` (`portrait` or `embedded-panels`), and optional `framing_override` (`zoom`, `eye_y`, `roi`, `fallback_y`, `min_face_height720`). Camera identity comes from the picture, not the filename. Preserve separate runs where angle identity is uncertain and inspect those seams visually.
5. Use `bind_reviewed_shots(inspection, shot_map)` with canonical `build_plan`, or `--plan-only --shot-map /absolute/map.json` on that already duplicated/split vertical sequence. `ReframeSession.apply(plan_path, plan)` performs the guarded application and exact readback. The map refuses stale revisions, missing items, duplicates and changed source clocks. Embedded panels are explicitly excluded from face tracking and must be covered by the panel plan.

For wide two-person footage, specify the intended subject's measured ROI. Already-tight shots normally need `zoom: 1.0`. YuNet confidence is its final field, following the ten landmark coordinates; never interpret an eye coordinate as confidence. Record detection failures and visually validate every fallback.

## Baked side-by-side diagrams

When two panels are already baked into a single source master, there are no alternate camera sources to select. Use the flat `lab_reframe_embedded_panels` route through `picture_operation`, with reviewed `node_id`, empty `upper_track`, `source_width`, and `source_height`; supply a visually measured `split_x` for unequal regions. It splits the source's reviewed left/right regions into two vertically stacked native picture items using Crop and Motion. The added item is a video-only subclip retaining the exact original source clock. No audio is duplicated. Original dialogue edits remain intact; no nesting or replacement render is needed.

The equal-split creation route and later static unequal-panel repair have native-host acceptance. Creating an unequal panel directly with `split_x` remains an experimental variant until that exact variant is verified on a disposable native fixture.

This route requires visually verified source panel boundaries; never assume an equal split. It is not a general split-screen camera selector. Fit each complete region inside its panel; small side margins are intentional if needed to preserve the diagram. Do not apply face tracking to overhead writing or chart panels. Apply this composition after the portrait Motion pass so overlap rejection remains intact. Crop/Motion readback, source-clock coverage and unrelated-state preservation are mandatory.

For independent camera sources, use [native-split-setup.md](native-split-setup.md).

## Native QA and persistence

`picture_operation('lab_export_reframe_frames', {'output_dir': absolute_existing_dir, 'ticks': [...]}, receipt)` exports up to 96 chosen native frames per job. Use unique directories; never overwrite evidence. Sample each item at its first displayed frame, midpoint and last displayed frame, plus both sides of camera/edit seams and posture changes. Review all sheets, not just file existence. Fix only failed ranges against a fresh baseline.

Save, close/reopen through a verified native lifecycle route, then compare current keys, source clocks, audio and protected state. Premiere may normalize preview dimensions on reopening a resized sequence; `verify_fresh(..., after_reopen=True)` permits only an exact 1080x1920 preview-raster normalization. It does not excuse any other setting or edit change.

The upgraded connector has bounded large-snapshot paging and file-backed mutation baselines. This avoids IPC truncation without removing item/key limits, script validation or mutation guards. A successful operation is not proof of visual quality. Keep execution, exact readback, persistence, native-frame review and user approval separate.

## Printed-face and set-object traps

A confidence score does not establish subject identity. Review the intended subject region for every camera family, including apparently single-person podcasts with posters or face-like set objects. The podcast preset excludes detections below 48 pixels high on a 720-high analysis frame; distant subjects require a visually calibrated override. Abrupt horizontal jumps over 20 percent of source width inside a shot stop plan generation. Tighten the ROI or split a confirmed camera switch; do not smooth a wrong-person selection into a pan. Check first-frame framing as well as the middle. For a static seated shot, a reviewed stable X hold can be preferable to chasing small motion.

For a previously constructed static panel whose split boundary needs correction, use `lab_update_static_panel_geometry` via `ReframeSession.picture_operation`. Supply exact item IDs and reviewed Anchor/Position/Scale plus Crop Left/Right; the tool refuses animated properties and compares all unrelated state. Inspect native exports afterward.
