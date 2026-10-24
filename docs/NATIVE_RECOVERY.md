# Native operation interruption and reconciliation

Every toolkit `native` command records a SQLite operation before launching its Python command. `10_WORK/native-operations/<id>/operation.json` mirrors its project/backend/action, exact packet path and hash, owning job (if any), owner/child PIDs, launch uncertainty and outcome. A successful command pins its returned output in `result.json`; this is command evidence, not human approval or a substitute for a verified render receipt.

Only one unresolved native operation may own a project. An active editing job also owns native access: unrelated manual commands cannot enter between that job's operations. Unresolved intake blocks native execution. Conversely, a running or uncertain native operation blocks subsequent native commands, new/recovered intake, queued editing jobs, publication and job completion/reconciliation. A service restart does not clear that reservation.

```sh
acq-edit native-operations PROJECT_ID
acq-edit native-reconcile OPERATION_ID /absolute/project/10_WORK/native-evidence.json
acq-edit reconcile JOB_ID ready /absolute/project/10_WORK/completed-result.json
# Or, when the inspected job did not complete:
acq-edit reconcile JOB_ID failed /absolute/project/10_WORK/failed-job-evidence.json
```

## Establish the actual native outcome

A hard-killed CLI can leave its Python command alive. That command can own an independent FilmCraft process or have started an export inside an external Resolve/Premiere host. CLI exit, timeout, a stale-looking log and a stopped service do not establish that the native export stopped. Do not replay the original packet, clear a reservation, cancel unrelated exports or replace an existing media file merely to get the queue moving.

The FilmCraft adapter wraps the canonical transport to record each child under the operation's `children/` directory. It records an unknown-launch marker before initialization, the PID even when initialization fails after spawn, and the observed exit on close. The transport's normal command/export behavior is unchanged. A killed Python process during initialization can leave the unknown marker; inspect processes and the retained session logs. Resolve/Premiere are external hosts, so the Python command's exit alone cannot prove their render jobs terminal. Inspect the exact host project, timeline and export-job receipts using read-only host APIs or the editor UI. For a terminated headless FilmCraft session, inspect its saved native project, job/inspection/render receipts and output bytes after confirming all recorded processes exited.

`native-reconcile` refuses any known live owner, command or FilmCraft child, even if an evidence file claims otherwise. PID checks are conservative: PID reuse can require further operator inspection. Unknown launches require explicit process inspection; elapsed time is not evidence. No reconciliation command kills processes or relaunches an editor.

Save the observed findings inside this project:

```json
{
  "operationId": "<exact native operation ID>",
  "backend": "<filmcraft | premiere | resolve>",
  "noActiveWriter": true,
  "processInspection": "<which command/editor processes were checked and their terminal state>",
  "nativeInspection": "<exact native project/export-job state, output verification and preserved parent evidence>"
}
```

These descriptions are operator assertions backed by the inspection performed, not an automatic host-status proof. Never generate them before inspecting. Reconciliation pins the evidence file's hash in the event record and marks the operation `reconciled`; it does not label an uncertain render successful. All old media, packets, logs, partial files and published versions remain in place. It does not consume review notes or reset decisions.

## Resolve the owning editing job separately

After every native operation is settled, an existing valid render receipt may be published through the normal `publish` command with its original job ID. Publication still verifies native/media/plan/inspection hashes, source-cut proofs and the exact submitted parent; it refuses a duplicate publication. If the full job already published, use those existing version IDs. `reconcile JOB_ID ready` requires the ordinary `{ "jobId": "...", "versionIds": ["..."] }` result and independently verifies all publications before releasing the job.

When a job did not finish, its failed-job evidence must identify `jobId`, set `noActiveWriter: true`, and describe `processInspection` and `nativeInspection`. An arbitrary file can no longer clear a failed job. The command refuses while any native operation is unresolved. A new request can use repaired inputs only after the prior state is reconciled; do not invent successful receipts or overwrite partial outputs. Feedback and previous versions remain available.

The journals cover commands dispatched through this toolkit. They cannot discover every manually launched editor or untracked external process. Older operations without these records still require actual host/process inspection; absence of a journal does not certify inactivity.

## Verified scope

An actual FilmCraft fixture built a 500-frame 1920×1080 sequence and started a native export. After the export job and both process identities were recorded, the calling CLI was hard-killed. Reconciliation refused while the original Python/FilmCraft processes were live. The original export then completed without replay. After both processes exited, its native hash, render receipt, exact 500-frame count and full decode passed. Twelve previous published and working artifacts retained their hashes. Only then was the operation explicitly reconciled. No clip was newly published or approved by this test.

Five service tests exercise success evidence, packet changes, failed/unknown launches, live command/editor refusal, job ownership, queue/publication boundaries and required reconciliation fields. Two Python tests verify child identity after initialization failure and retained unknown/exit outcomes. This does not qualify interrupted Resolve/Premiere exports, every host disconnect, clean-machine recovery or human editorial approval.
