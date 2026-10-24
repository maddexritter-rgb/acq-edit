---
name: footage-fetch
description: Import local footage, YouTube videos or authenticated Google Drive files and folders into verified project-owned sources. Use for footage intake, checksum verification and interrupted-transfer recovery.
---

# Footage intake

Use the existing toolkit project from `project.json`. Related cameras and audio belong
to that project. If this is new work, create a project through the toolkit CLI using
the configured storage root. Keep original footage untouched and register verified
copies under `00_SOURCE`; work and final versions stay in `10_WORK` and `20_DELIVER`.

→ Follow [the intake implementation and recovery contract](__ACQ_TOOLKIT__/docs/INTAKE.md).

Use `source` for local files, `youtube` for a single non-live video, `drive` for an
exact file link, or `drive-folder` for a folder link. Supply the teammate's configured
rclone remote explicitly; its authentication is local and is not bundled. The
packaged `scripts/gdrive_pull.sh PROJECT_ID URL [REMOTE]` delegates to those same
Drive commands. It never creates or renames a project itself.

Let the toolkit own preflight, transfer processes, hashes, remote identity checks,
source registration and recovery. Inspect the persisted attempt or batch when a
transfer fails; do not start a detached downloader or bypass its project reservation.
No copying, file timestamp, filename, empty listing or successful command alone proves
that the expected source was verified. Empty remote listings can reflect missing
access; compare them with the supplied source inventory before declaring a shoot empty.

Report actual intake status and any inaccessible, unsupported or excluded sources.
Missing media or credentials require a specific repair. Never move originals,
rename tagged files, change account scopes, or switch the selected editing engine.
