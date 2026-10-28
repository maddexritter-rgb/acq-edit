# Verified and recoverable source intake

Use the toolkit CLI inside an existing project. The selected editing backend is unchanged and no editor is needed to ingest footage.

```sh
acq-edit source PROJECT_ID /absolute/path/recording.mp4
acq-edit youtube PROJECT_ID https://youtu.be/VIDEO_ID
acq-edit drive-status
acq-edit drive-login  # only if no existing connection; browser Google sign-in
acq-edit drive-connect MY_REMOTE  # select one of several existing connections
acq-edit drive PROJECT_ID https://drive.google.com/file/d/FILE_ID/view
acq-edit drive-folder PROJECT_ID https://drive.google.com/drive/folders/FOLDER_ID MY_REMOTE
acq-edit drive-batches PROJECT_ID
acq-edit drive-resume BATCH_ID
acq-edit intakes PROJECT_ID
acq-edit intake-recover INTAKE_ID
```

Each initial request creates a distinct attempt. Recovering the same attempt is idempotent; submitting the original command again deliberately creates another attempt. Only one unresolved intake may own a project. Queued editing jobs wait for intake completion. An already-running build can perform its own intake when the CLI carries that exact `ACQ_EDIT_JOB_ID`; an unrelated active job cannot be bypassed.

## Sources and evidence

The original file is never moved or edited. A successful source is a verified read-only copy in `00_SOURCE`, with its original extension retained. SQLite records its SHA-256, byte size, media probe, origin, intake ID and pinned verification-receipt hash. `10_WORK/intake/<id>/` retains the readable stage journal, download and verification receipt. The project feedback export includes intake state as well as registered sources. Downloaded staging media is intentionally retained until separately managed; intake never deletes it automatically.

Local intake checks the original before and after copying, compares hashes, probes the copied media, checks it again after verification, and registers source/state together in one SQLite transaction. A process interruption after file placement or after the database commit can be recovered without another source registration. Missing, changed or incomplete bytes cannot become registered sources just because a filename exists.

Drive reuses the operator's selected rclone remote, or the only existing Drive connection. `drive-login` creates a separate read-only connection through browser OAuth; it never overwrites existing connections or changes their scopes. The selected connection name is stored beside shared credentials, and tokens remain in the local rclone configuration. See [the guided steps](ONBOARDING.md#pasted-google-drive-footage-links). No credentials are copied into the repository. The [rclone `copyid` directory form](https://rclone.org/drive/#copyid) preserves the source filename. After download, the toolkit queries matching-name metadata through [rclone's Drive query command](https://rclone.org/drive/#query), then requires the **exact requested file ID**, size and MD5. Duplicate names cannot substitute a different file. Remote checks run again before registration; local SHA-256 separately proves the project copy. Missing metadata, absent MD5 or a checksum mismatch fails explicitly. The metadata query requires a current rclone version with the Drive `query` command (tested interface: 1.74.3). Encoded/unqueryable names and shortcuts without verifiable binary metadata may require a dedicated intake repair; they are never accepted as remotely verified by filename alone.

The `drive` command detects either file or folder links; `drive-folder` also accepts folder links and follows the batch contract below. `doctor` reports rclone and yt-dlp availability but does not establish authenticated access. No authenticated Drive account has yet passed the toolkit's live acceptance fixture.

YouTube accepts an explicit watch, shortened, Shorts, embed or archived-live video URL. It extracts one video ID before creating an attempt; channel, playlist-only and ambiguous links fail before a transfer. Downloads use the canonical watch URL for that ID, so time/share/playlist parameters do not select an excerpt or expand the request. Assembly Design handles requested cuts after full-source intake.

The importer uses yt-dlp with user configuration ignored, one non-live video, a project-scoped output template and an after-move completion-path record. The recorded media must be a regular file inside the exact download directory. It also requests a clean per-video [info JSON](https://github.com/yt-dlp/yt-dlp#filesystem-options), without playlist metadata. Before copying and again after probing, the importer requires the YouTube extractor, exact requested ID and webpage, a processed non-live recording and a valid reported duration. It pins the metadata hash in the durable attempt; changed metadata fails recovery without downloading again. Missing metadata in an older unfinished attempt requires a fresh transfer attempt with the old files preserved. Previously registered sources and receipts remain unchanged.

The small verification receipt retains the video ID, canonical webpage, title/channel, reported duration/status and metadata path/hash. It does not copy signed media URLs, request headers or the complete extractor response into exported review state. Raw metadata stays in the private intake work directory for troubleshooting; do not publish it. Provider-reported duration can be rounded and is not a frame count. A local SHA-256 proves the captured bytes and project copy; the extractor identity is **not** an upstream YouTube checksum. Private-video authentication and live capture require their own supported workflows.

Both remote routes reserve free space before transfer and bound the transfer/file budget to one quarter of remaining space after a 1 GiB reserve. Local copying rechecks room for the complete source plus reserve. These are guards, not a filesystem quota: other processes can still consume free space, and yt-dlp estimates may be incomplete.

## Drive folder batches

`drive-folder` recursively enumerates exact parent IDs using the documented [Drive query command](https://rclone.org/drive/#query). Before transferring files, it seals `10_WORK/drive-batches/<id>/manifest.json` and pins its SHA-256 in SQLite. The manifest records file IDs, original names, folder provenance, byte sizes and MD5s, plus discovered folders and explicitly excluded non-media files. Duplicate filenames never serve as identities; each file uses the existing exact-ID intake and gets a unique project-owned source path. Folder names are provenance, not filesystem destinations.

Audio/video MIME types and recognized footage/audio extensions are included. Non-media files are listed as exclusions. Shortcuts are refused with an explicit target-intake requirement; they cannot silently expand the requested scope. Unverifiable media, duplicate IDs, malformed parent evidence, more than 10,000 entries or nesting beyond 32 levels stop the batch. Split large sets explicitly. This does not claim arbitrary raw-camera codec support: each included file still needs a successful media probe. Resource-key-only links and inaccessible folders need their own access repair.

Downloads run serially. Each file's fresh Drive metadata must still match the sealed ID, name, parent, byte size and MD5 before registration. A remote change fails the attempt instead of silently replacing the selected footage. Files added after enumeration are not part of this snapshot; create a new request to include them. Free-space preflight covers both the remaining downloads and project copies plus the existing reserve, while each file retains its own transfer guard.

SQLite persists the batch owner, query process and unknown-launch marker, and each file retains its existing intake process records. An unresolved batch, including a failed one, blocks unrelated intake and queued editing jobs. An agent already owning the project can initiate its own batch. `drive-batches` and the project feedback export expose batch status; `batch.json` mirrors it on disk.

`drive-resume BATCH_ID` refuses live or unrecorded processes. It keeps the sealed manifest, validates already-registered files and recovers completed existing download bytes without restarting a downloader. If a file is incomplete, it fails with that file's intake evidence retained. After confirming recorded processes are terminal, explicitly use `drive-resume BATCH_ID --retry-failed` to create fresh download attempts for failed files. Successful files are reused and old partials remain untouched. An interrupted attempt that is still marked downloading is reconciled through ordinary recovery first; a second explicit retry can then start fresh bytes if needed. An interrupted enumeration can be repeated because no transfers start until its manifest is sealed.

To abandon an unresolved batch, inspect its batch/query and all child intake processes and save an evidence file inside the project with `batchId`, `noActiveWriter: true`, and a concrete `processInspection` description. Run `drive-abandon BATCH_ID EVIDENCE_JSON`. It refuses known live processes, retains all files and registered sources, records the assertion, and releases the batch's queue reservation. A ready batch cannot be abandoned through this command. Do not use a generated assertion to bypass an unknown process outcome.

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

A folder-batch CLI fixture used two generated videos with the same filename under different parent IDs. After the first source registered, the actual CLI was hard-killed while the second controlled downloader remained live. Batch recovery refused until that child exited, then recovered the existing bytes and completed with exactly two downloads and two sources. A further resume did not duplicate registration. Seven batch tests cover nested identity/provenance/exclusions, changed snapshots, partial-transfer retry, registration interruption, live/unknown process refusal, manifest tampering and project queue ownership. Provider listing/download responses are controlled; authenticated Drive and real network acceptance remain open.


### Actual public YouTube qualification

On 2026-10-24, the real CLI downloaded Blender's [Sintel trailer](https://www.youtube.com/watch?v=HOfdboHvshg) using yt-dlp 2026.08.19. The project source was a 12,069,472-byte MKV containing 1920×818 H264 at 24 fps and stereo 48 kHz Opus. Full audio/video decoding passed. Both staging and the read-only project copy had identical hashes and stream readback, including 1,253 video frames and a 52.241-second container duration. The provider's rounded 52-second metadata was not used to infer a frame count; an initial fixture assumption of 1,248 frames was corrected against the measured source without changing the media.

The updated importer matched the requested ID and canonical webpage to the extractor metadata, then pinned its hash in the journal and receipt. Separate CLI project reopening and two intake-recovery calls retained one ready attempt, one source and unchanged source/metadata/receipt bytes. No editing jobs or native operations ran. An earlier successful download without the new metadata binding remains a separate preserved attempt. The sample is credited to © copyright Blender Foundation | durian.blender.org under its [published sharing terms](https://durian.blender.org/sharing/); footage and extractor metadata are not committed.

Six added service cases cover URL scope, exact identity, live/invalid/missing metadata, changes during probing, pinned recovery without replay and omission of raw extractor fields from the receipt. All 132 service tests pass. This qualifies the public single-video intake path on the development Mac; authenticated/private YouTube, live-network interruptions, Drive access, clean-Mac setup and native/editorial use of the source remain separate gates.
