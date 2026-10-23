# Verified and recoverable source intake

Use the toolkit CLI inside an existing project. The selected editing backend is unchanged and no editor is needed to ingest footage.

```sh
acq-edit source PROJECT_ID /absolute/path/recording.mp4
acq-edit youtube PROJECT_ID https://youtu.be/VIDEO_ID
acq-edit drive PROJECT_ID https://drive.google.com/file/d/FILE_ID/view MY_REMOTE
acq-edit intakes PROJECT_ID
acq-edit intake-recover INTAKE_ID
```

Each initial request creates a distinct attempt. Recovering the same attempt is idempotent; submitting the original command again deliberately creates another attempt. Only one unresolved intake may own a project. Queued editing jobs wait for intake completion. An already-running build can perform its own intake when the CLI carries that exact `ACQ_EDIT_JOB_ID`; an unrelated active job cannot be bypassed.

## Sources and evidence

The original file is never moved or edited. A successful source is a verified read-only copy in `00_SOURCE`, with its original extension retained. SQLite records its SHA-256, byte size, media probe, origin, intake ID and pinned verification-receipt hash. `10_WORK/intake/<id>/` retains the readable stage journal, download and verification receipt. The project feedback export includes intake state as well as registered sources. Downloaded staging media is intentionally retained until separately managed; intake never deletes it automatically.

Local intake checks the original before and after copying, compares hashes, probes the copied media, checks it again after verification, and registers source/state together in one SQLite transaction. A process interruption after file placement or after the database commit can be recovered without another source registration. Missing, changed or incomplete bytes cannot become registered sources just because a filename exists.

Drive uses the operator's configured rclone remote; no credentials are copied into the repository and no scopes are changed. The [rclone `copyid` directory form](https://rclone.org/drive/#copyid) preserves the source filename. After download, the toolkit queries matching-name metadata through [rclone's Drive query command](https://rclone.org/drive/#query), then requires the **exact requested file ID**, size and MD5. Duplicate names cannot substitute a different file. Remote checks run again before registration; local SHA-256 separately proves the project copy. Missing metadata, absent MD5 or a checksum mismatch fails explicitly. The metadata query requires a current rclone version with the Drive `query` command (tested interface: 1.74.3). Encoded/unqueryable names and shortcuts without verifiable binary metadata may require a dedicated intake repair; they are never accepted as remotely verified by filename alone.

The current Drive CLI accepts single-file links. Folder enumeration and batch scheduling remain separate work. `doctor` reports rclone and yt-dlp availability but does not establish authenticated access. No authenticated Drive account has yet passed the toolkit's live acceptance fixture.

YouTube uses yt-dlp with user configuration ignored, one non-live video, a project-scoped output template, and an after-move completion-path record. The recorded output must be a regular file inside the exact download directory. This prevents a downloader response or global config from redirecting source intake to unrelated files. A local SHA-256 proves the captured bytes and project copy; it is **not** an upstream YouTube checksum. Private-video authentication, live capture and folder/batch routes require their own supported workflows.

Both remote routes reserve free space before transfer and bound the transfer/file budget to one quarter of remaining space after a 1 GiB reserve. Local copying rechecks room for the complete source plus reserve. These are guards, not a filesystem quota: other processes can still consume free space, and yt-dlp estimates may be incomplete.

## Process interruption and recovery

SQLite is authoritative. It persists the owning CLI PID, downloader/probe PID and whether a child launch has an unrecorded outcome. The journal and source/verification files are retained on failure. PID existence is conservative: a reused PID can require inspection, but it never authorizes replay.

Ctrl-C/SIGTERM aborts intake, waits for its owned subprocess to terminate and records failure. A hard kill may leave a detached downloader alive. `intake-recover` refuses while either recorded process is live. It does not infer termination from elapsed time, a stale-looking file or a stopped parent. If the parent died between launch and PID persistence, the pending-launch marker also prevents automatic recovery.

Once known processes are terminal, `intake-recover` rechecks the existing candidate and complete copy, including fresh Drive verification where applicable. It never starts yt-dlp or `rclone copyid` again. A fully downloaded file can be registered after a crash; a partial download or changed source remains a failed attempt. After a failure, start a new intake command if new transfer bytes are needed. Previous partials stay in their original attempt.

For an uncertain launch or a deliberately abandoned attempt, inspect the actual process state first and save an operator evidence file under this project:

```json
{
  "intakeId": "<exact attempt ID>",
  "processInspection": "<what process evidence was checked, and the observed terminal state>",
  "noActiveWriter": true
}
```

Then run `acq-edit intake-abandon INTAKE_ID /absolute/project/10_WORK/evidence.json`. This refuses registered sources and known live processes, retains all files, records the evidence path, and releases the attempt for a new request. The evidence is an operator assertion, not an automatic proof that an unrecorded child exited; never generate it without checking. No intake command kills an unrelated process or deletes an old source.

## Evidence and remaining acceptance

Automated fixtures cover immutable local copying, registration/journal recovery on both sides of the SQLite commit, active-process refusal, project queue serialization, partial/changed bytes, changes during probing, Drive ID/MD5 binding with duplicate names, YouTube path escape, disk guards and unrecorded-launch reconciliation. Provider responses in these tests are controlled fixtures.

On 2026-10-23 a separate real CLI/process/SQLite/file/probe fixture generated valid video, imported it locally, hard-killed an intake CLI and observed its controlled downloader still alive. Recovery refused until that exact child terminated, then registered existing bytes once without replay. A separate SIGTERM run waited for child exit, persisted failure and recovered existing bytes. These tests do not claim authenticated Drive or live YouTube acceptance, arbitrary network interruptions, source editorial quality or clean-Mac installation.
