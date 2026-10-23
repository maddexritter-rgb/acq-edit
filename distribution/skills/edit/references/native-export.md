# Exact native delivery export

The current approved timeline is authoritative. Resnapshot after user edits; never
reconstruct export ranges from an old assembly plan. Use the explicit supported
Premiere bridge/profile from the capability guide. Do not launch Beta, activate
another sequence implicitly, install a connector, or widen Lab permissions.

`../scripts/pp_export_clips.py` owns inspection/export-body generation and file QA.
It does not implement a second connector. The former implicit-mailbox/AME exporter
and automatic black-head trimming are replaced by this preservation-first route.

1. Generate `inspect-script --project <absolute.prproj> --sequence-uid <UID>
   --output <new-inspect.jsx>`. Execute its **body** once through the selected
   typed `lab_inspect_export_state` operation (pass project_path and sequence_id; the generated script is an offline diagnostic only) and save the returned data as `baseline.json`.
   Save the current project separately through the guarded route and retain a
   checkpoint plus project hash. The baseline covers track mute, items, source and
   timeline ticks, disabled state and sequence settings; it is not every effect value.
2. Review current picture islands and make an explicit spec: an array of
   `{name: "<approved-delivery-name>.mp4", start_ticks: "...", end_ticks: "..."}`.
   Gaps between clips separate deliverables; captions are many native cards and are
   not clip boundaries. Use the actual first/last picture frames and include all
   intended audio tails. Resolve disagreements rather than silently cutting them off.
3. Run `prepare --baseline <baseline.json> --spec <spec.json> --preset <verified.epr>
   --sample-rate <actual-rate> --frame-ticks <exact-integer> --out-dir <new-work-dir>`.
   The preset comes from the selected installed Premiere version, not a hardcoded AME
   version. No FPS, canvas, shoot date, source label, name or padding is guessed.
4. Execute typed `lab_export_exact_range` serially through `premiere_agent.py execute`, using the installed schema. Pass baseline, start_ticks/end_ticks, preset_path/output_path, sample_rate and frame_ticks; generated `.jsx` files remain diagnostic artifacts, never raw-script input,
   with durable intent and original receipt, exclusive writer ownership and a bounded
   wait. No receipt/uncertain timeout means reconcile the original operation; never
   submit again. Recheck project path + sequence UID and baseline before each export.
   The body uses direct native export, refuses existing files, and changes only
   sequence export marks. It captures original `getInPointAsTime().ticks` and
   `getOutPointAsTime().ticks`, restoring and verifying both even on failure.
5. Premiere's numeric-second setters can floor one audio sample early. The helper
   first tries exact seconds, then a positive **1/256 sample** bias only if readback
   mismatches. Both original marks and requested boundaries must lie on the supported
   sample grid; final **integer tick equality is mandatory**. This is input-rounding
   compensation, never permission to shift content or accept one-frame error. Unsupported
   mark shapes/sample grids fail closed. A restoration failure requires reconciliation.
6. Run `verify <export.mp4> --frames <expected> --width <actual> --height <actual>
   --fps <numerator/denominator> --channels <actual>`. Require decoded exact frame count,
   codec/canvas/rate/audio format, full-file black detection and separately decoded first
   and last three frames. Save the returned hash/receipt. Visually inspect the boundary
   contact sheet and check intended sound, captions, framing and loudness separately.
   A failed file stays in work, with its error evidence. **Never nudge, trim, overwrite,
   or remove a frame to make QA pass without an authorized timeline revision.**
7. When the matching production policy requests metadata sanitation, use
   `scripts/sanitize_delivery.py <native-export> --out <new-work-copy.mp4> --receipt <new-receipt.json>`
   before final file verification. It stream-copies AV, removes ordinary descriptive
   metadata/data tracks and compares decoded frames/samples and playback signalling.
   Keep the original export. A sanitation difference is a technical file issue to
   inspect, not permission to change the timeline or a claim about platform AI labels.
   Run the normal delivery verification on the exact sanitized bytes.
8. Copy only QA-passed exact bytes into `20_DELIVER/`, verify hash equality, then
   → Use skill: `monday` for the specifically approved batch.

The numeric-second correction and mark restoration have bounded 25 fps/48 kHz
native production evidence. The generalized helper has synthetic regression tests;
new host versions/rates still require exact native readback and rendered QA. A
prepared script, mock result, file presence or nonzero size is not an export pass.

Use `premiere_agent.py schema lab_inspect_export_state` and `schema lab_export_exact_range` for exact arguments. The typed wrapper is newly integrated; verify this run’s native marks and output rather than attributing the generator’s historical host evidence to every invocation.
