# Premiere publication through the native adapter

`acq-edit native PROJECT_ID render PACKET` now produces the same verified render receipt as the other adapters. It uses the packaged Agent Lab typed export tool and the existing exact-project scope/lease. No alternate editor, raw script dispatch, scope widening, project switching or automatic retry is involved.

This path has adapter contract tests but **has not passed a live toolkit Premiere fixture**. The connected production project was inspected read-only and left untouched. Do not interpret the tests as native host acceptance, saved-project reopen proof or human approval.

## Required state

The project's selected backend must be `premiere`. Its dedicated `.prproj` must already be open in the supported host with the selected Lab panel. Configuration must name an existing absolute toolkit profile path; an omitted profile cannot fall back to the global production connector. Use the packaged stage owners for native construction and finishing, save the current reviewed plan under `10_WORK`, and establish the existing exact-project export scope. The scope must include the actual preset and source inputs and the new output root. Never borrow a live project's scope or replace an installed production panel to run this test.

Obtain a fresh adapter `inspect` fingerprint and the `lab_snapshot` revision/sequence. Use the packaged `premiere_agent.py inspect lab_inspect_export_state` with exact `project_path` and `sequence_id` to capture the export baseline. The baseline includes project, sequence, bounded native track/settings state and original in/out tick marks. The full snapshot protects components/keyframes as exposed by Agent Lab; the bounded export baseline alone is not that proof.

## Render packet

Use fresh absolute paths inside the toolkit project for `output`, `inspection`, `receipt` and `receiptDirectory`. Retain the current native project path and the pinned plan. Each operation needs a new durable ID. The packet contains exactly two operations: a guarded save of the current project, then typed exact-range export.

```json
{
  "nativeProject": "<project>/10_WORK/edit.prproj",
  "expectedFingerprint": "<adapter inspect fingerprint>",
  "plan": "<project>/10_WORK/current-plan.json",
  "parentId": "<exact submitted version ID, or null for a new clip>",
  "output": "<project>/10_WORK/jobs/<job>/render/clip.mp4",
  "inspection": "<project>/10_WORK/jobs/<job>/render/inspection.json",
  "receipt": "<project>/10_WORK/jobs/<job>/render/receipt.json",
  "receiptDirectory": "<project>/10_WORK/jobs/<job>/render/operations",
  "timeoutSeconds": 3600,
  "operations": [
    {
      "schema": "edit.native-operation/v1",
      "stage": "export",
      "operation_id": "<unique-save-id>",
      "tool": "save_project",
      "target": {
        "project_path": "<project>/10_WORK/edit.prproj",
        "sequence_id": "<exact sequence ID>",
        "expected_revision": "<fresh Lab revision>"
      },
      "arguments": {},
      "intended_changes": ["Save the inspected native project at its current path"],
      "protected_state": ["All native timeline and editorial state"]
    },
    {
      "schema": "edit.native-operation/v1",
      "stage": "export",
      "operation_id": "<unique-export-id>",
      "tool": "lab_export_exact_range",
      "target": {
        "project_path": "<project>/10_WORK/edit.prproj",
        "sequence_id": "<exact sequence ID>",
        "expected_revision": "<same fresh Lab revision>"
      },
      "arguments": {
        "baseline": "<replace with the complete baseline object, not a path or string>",
        "start_ticks": "0",
        "end_ticks": "<planned frames multiplied by exact frame ticks>",
        "frame_ticks": 10160640000,
        "sample_rate": 48000,
        "preset_path": "<explicit installed and authorized H264 preset.epr>",
        "output_path": "<project>/10_WORK/jobs/<job>/render/clip.mp4"
      },
      "intended_changes": ["Export the complete clip and restore the original marks"],
      "protected_state": ["All native cuts, effects, audio, captions, track states and export marks"]
    }
  ]
}
```

The numeric values above illustrate 25 fps / 48 kHz only. Calculate the actual frame ticks as `254016000000 × fps.denominator / fps.numerator`; the adapter requires an integer result and checks the native sequence geometry and sample rate against the plan. This initial toolkit export contract covers one complete clip sequence from zero to its planned end. Range exports from a larger master remain a separate canonical export workflow until explicitly integrated; do not move marks or trim the file to make the contract pass.

The adapter checks current identity, revision, baseline, unused output/receipt paths and every operation target before dispatch. It retains per-operation evidence, requires restored marks and unchanged native state, verifies the saved project hash, and decodes the actual exported media. A success receipt is written only after these checks. Existing artifacts, uncertain jobs, mismatched output or intervening edits require reconciliation. Failed attempts retain evidence and never overwrite a prior version.

On success, use the normal `publish PROJECT_ID RECEIPT` command. Publication verifies the exact job/parent and copies immutable media and the native checkpoint into a new version. Human review remains pending. Agent jobs supply their ID through `ACQ_EDIT_JOB_ID`; standalone tests must not invent a completed job or approval.

The test suite covers complete packet preflight, duplicate operation IDs, stale baselines, wrong output/range/grid, wrong project, mark restoration failures, decode failures and saved/unsaved native changes during verification. Host connection, actual export preset behavior, saved-project reopen and native visual/audio quality still require the dedicated live fixture.
