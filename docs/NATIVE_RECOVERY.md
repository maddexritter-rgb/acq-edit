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

## Review-room guidance

The Activity panel shows unresolved editor and source-transfer reservations even when no editing job exists. It distinguishes awaiting a result from an outcome requiring recovery review. These labels describe persisted state; they do not certify that a process is still running. Queued revisions wait, and existing clips and feedback remain available.

Use **Copy request for your agent** to obtain the exact project, backend and outstanding operation identifiers. Paste the request into the editing chat; the room does not send a message or clear any reservation. Expand **Recovery details** for original diagnostics and a selectable request if clipboard copying is unavailable. The agent must reread current state and inspect actual processes/native results before reconciliation.

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

## Failure before the native command starts

New operation records include `dispatchPhase`. `not-started` is committed before runtime verification; `launching` is committed to SQLite and exported to the operation journal before the process runner is invoked. A spawn callback records `spawned`, and a returned command records `returned`. The phase never moves backward. Missing phase data on older operations is not proof that no command started, and null PIDs alone are insufficient.

If the runtime check or cancellation fails while the phase is still `not-started`, inspect the exact operation and its process records. After its owner is confirmed dead, the evidence above may additionally specify:

```json
"nativeOutcome": "not-dispatched"
```

Describe the observed preflight failure in `nativeInspection`, making clear that no host inspection or native outcome is claimed. This route works even when Python or the chosen engine is unavailable. It requires the explicit durable phase, null child PID, no pending launch, no native result and no child journals. It refuses live owners, legacy records, contradictory evidence and every phase at or after `launching`. Do not also provide a `premiereLifecycle` outcome: no lifecycle request was made.

Recovery writes a separate immutable proof containing the original operation and the submitted evidence hash, then marks only that operation reconciled. It starts no native command, contacts no editor, and does not claim that the host is globally idle. The owning job, if any, still needs its normal reconciliation. Setup must be repaired before a new editing attempt; this does not retry the failed request.

A real CLI check used an intentionally absent configured Python: runtime verification failed, the operation retained `not-started`, and a new CLI process reconciled it without a working Python or Premiere connection. The original packet was unchanged. An additional subprocess regression kills a real owner during preflight, refuses recovery while it is live, then reopens SQLite and recovers after confirmed termination; its native-command sentinel is never created. This establishes preflight recovery only, not interrupted editor/export or clean-Mac acceptance.

## Premiere lifecycle recovery

For Premiere `native ... open` operations that reached dispatch, generic evidence alone cannot clear the reservation. Add the observed `premiereLifecycle.outcome` and follow [PREMIERE_STATE.md](PREMIERE_STATE.md). The CLI journals recovery attempts separately, refuses live or uncertain prior recovery processes, and verifies the Lab's immutable report before settling its own operation. The original native request is never replayed. Missing/legacy/non-uncertain lifecycle journals require explicit repair; this route does not infer that their locks are safe to remove.

## Resolve the owning editing job separately

After every native operation is settled, an existing valid render receipt may be published through the normal `publish` command with its original job ID. Publication still verifies native/media/plan/inspection hashes, source-cut proofs and the exact submitted parent; it refuses a duplicate publication. If the full job already published, use those existing version IDs. `reconcile JOB_ID ready` requires the ordinary `{ "jobId": "...", "versionIds": ["..."] }` result and independently verifies all publications before releasing the job.

When a job did not finish, its failed-job evidence must identify `jobId`, set `noActiveWriter: true`, and describe `processInspection` and `nativeInspection`. An arbitrary file can no longer clear a failed job. The command refuses while any native operation is unresolved. A new request can use repaired inputs only after the prior state is reconciled; do not invent successful receipts or overwrite partial outputs. Feedback and previous versions remain available.

The journals cover commands dispatched through this toolkit. They cannot discover every manually launched editor or untracked external process. Older operations without these records still require actual host/process inspection; absence of a journal does not certify inactivity.

## Verified scope

An actual FilmCraft fixture built a 500-frame 1920×1080 sequence and started a native export. After the export job and both process identities were recorded, the calling CLI was hard-killed. Reconciliation refused while the original Python/FilmCraft processes were live. The original export then completed without replay. After both processes exited, its native hash, render receipt, exact 500-frame count and full decode passed. Twelve previous published and working artifacts retained their hashes. Only then was the operation explicitly reconciled. No clip was newly published or approved by this test.

An actual Resolve Studio fixture built a separate 2000-frame 640×360 timeline and started a native export. After the exact operation, command PID and native render-job identity were recorded and Resolve reported rendering, only the calling CLI was hard-killed. A fresh native command was refused while the operation remained reserved. The detached Python command and Resolve export completed without replay; exactly one render job was added. After the command exited and that native job reported complete with the host idle, the original receipt, native checkpoint hash, full native fingerprint, 2000-frame count and full decode passed. Only then was the operation explicitly reconciled. Both previous published native snapshots, twelve published/working artifacts, source hashes, version metadata and feedback were preserved. No new version was published or approved.

Restoring the prior synthetic review project initially triggered the existing Fusion source-clock inspection guard. No clocks or fingerprints were rewritten. A subsequent complete inspection matched its original snapshot and render queue, and its previous page was restored. This records that observed restoration outcome; it does not establish that source-clock inspection failures are generally harmless.

Five service tests exercise success evidence, packet changes, failed/unknown launches, live command/editor refusal, job ownership, queue/publication boundaries and required reconciliation fields. Two Python tests verify child identity after initialization failure and retained unknown/exit outcomes. The live interruption evidence covers loss of the CLI owner while the original render continues. It does not qualify a killed Resolve Python command, a Resolve application crash, interrupted Premiere exports, every host disconnect, clean-machine recovery or human editorial approval.

## Missing or changed input media

Plan validation checks every source and graphics asset before native construction/export. Failures list the affected file, source/asset identity, expected hash and the observed problem. No editor may substitute another file, offline placeholder or alternate backend to satisfy that request. Preserve the original plan and previous versions. Recover the exact source bytes from a verified copy, or import genuinely different footage as a new source and redesign its dependent selections and layers.

After native export and output decoding, the shared completion step rereads the plan and hashes all planned sources and graphics again. A changed plan, missing input or hash mismatch prevents a success receipt. The completed render and native artifacts stay available for inspection; they are not silently published. Successful new receipts record `inputMediaVerification` with the post-render expected/actual hashes. These are checks at the boundaries, not continuous filesystem monitoring. Existing historical receipts remain readable.

Two actual FilmCraft fixtures exercised this path. With a generated source temporarily unavailable, render failed before any FilmCraft child/session or output was created; exact-byte restoration and explicit reconciliation allowed a valid 50-frame native export. In a separate 500-frame export, the generated source copy changed after the export job started. The output still decoded, but completion refused the success receipt. The changed copy and output were retained, exact source bytes were restored, and the operation was reconciled without publishing it. Both checks preserved twelve previous published/working artifacts and existing feedback. The separate Resolve qualification follows; Premiere live missing-media and mid-render-change qualification remains open.


Resolve Studio now has separate live evidence for both input failures. A new generated H264/PCM source copy and a separate 2000-frame native timeline were added to the existing synthetic review project; neither published version used the fault-injection source. Temporarily making that copy unavailable caused the real CLI render command to return its exact source identity, expected hash and missing-file diagnostic. No native render job, output or success receipt was created. The native snapshot and render queue stayed unchanged. The source was restored with its original hash, the failed operation was explicitly reconciled from a new CLI process, and a new attempt produced a fully decoded 2000-frame native export with post-render input verification.

A second export was observed actively rendering in the exact Resolve project before bytes were appended to that generated copy. The native job completed and its output fully decoded 2000 frames, but post-render source verification rejected the changed SHA-256 and produced no success receipt. The output and changed copy were retained. After verifying the command had exited and the exact native job was complete with Resolve idle, the original source bytes were restored and the reservation explicitly reconciled. This did not publish the output or replay the render.

Both cases preserved the native test checkpoint and snapshot, twelve prior published/working files, both published native timeline snapshots, original source hashes, version metadata, ordinary feedback and deferred feedback. No new clip version was published. The prior synthetic review project's snapshot, render queue, page and playhead were restored. The eight existing media-integrity regression tests also passed. This qualifies these generated-media failures through the real CLI/Resolve adapter; it does not prove arbitrary missing-media repair, application-crash recovery, agent interpretation, clean-Mac behavior, Premiere execution or human editorial acceptance.

To repeat this qualification, use a dedicated synthetic project with existing published versions and saved feedback. Pin their hashes and native snapshots first. Build a separate timeline from a newly generated, project-owned copy with an untouched original outside the fault-injection path. Test absence before export, restore exact bytes, inspect and reconcile, and verify a new native export. For the changed-media case, confirm the exact native job is actively rendering before changing only that copy; require the completion receipt to be absent even if output decoding succeeds. Preserve failed packets, outputs and changed bytes, verify actual process/host termination before reconciliation, and finish by checking every pinned version and restoring the prior selected project. Never apply fault injection to production footage or a source used by an approved clip.

## Native response integrity

The native command's stdout must be one JSON object. The service retains the exact raw stdout in the operation's hashed `result.json` before parsing it. Malformed JSON, progress mixed into stdout, arrays, null or a JSON string leave the operation in `reconciliation_required`; exit zero does not qualify the response. The result path/hash remain available for inspection and no automatic replay occurs. Successful CLI calls print the parsed object once, removing the older double-encoded string that caused an actual agent inspection retry.

The shared-service tests cover five invalid response forms and retained evidence/queue protection. A real FilmCraft inspection through the updated CLI returned an object after one parse, matched the complete published native inspection and preserved thirteen source/version files plus feedback. This verifies the transport boundary, not additional editor capabilities or human acceptance.
