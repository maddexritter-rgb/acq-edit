## Current-chat-only execution

Separate Claude/Codex worker entrypoints, auth checks and model smoke tests are no longer
available through the product. Existing-chat editing and review handoffs remain. Agents
run internal commands; users are not directed to a terminal or a second agent login.
Historical jobs and evidence are preserved for inspection/reconciliation.

# 0.2.0-preview.14

Enables Premiere Pro 26.5.2 without requiring a downgrade, editor switch or separate
qualification meeting. Installation now detects the running/installed enabled Premiere
and pins that exact host instead of always writing 26.3.0 into the integration profile.
The shared bridge accepts 26.5.2; connector isolation, exact project scopes, live version
matching and native completion evidence remain in place.

26.5.2 is enabled but not native-qualified on the development Mac. No real 26.5.2 render,
caption appearance, revision or save/reopen result is claimed by this release.

When updating an existing ACQ Edit panel, `onboard premiere-panel --update-owned` verifies
it against the prior owned runtime and retains a backup. It never overwrites modified or
foreign panels or an integration with unsettled native writers.

Validation: 209 Node tests and 105 targeted Python tests cover exact host selection,
26.5.2 routing, wrong-host rejection, connector isolation, installer preservation and
owned panel backup/upgrade. These are software tests, not a live 26.5.2 editing claim.

Upgrade the package, rerun Premiere onboarding in the new release runtime using existing
choices, upgrade the owned panel and reopen ACQ Edit Agent. Keep credentials, assets and
project paths. Continue editing in the existing chat; no extra agent CLI login is needed.

# 0.2.0-preview.13

Fixes the onboarding loop that asked already signed-in users to open another Claude CLI
and repeatedly save command permissions. The default workflow now uses the existing chat.

- Setup and ordinary doctor do not require or probe a separate Claude/Codex executable.
- `build` returns a durable request; `session-start` reserves it and `session-complete`
  validates the same native artifacts and receipts as before.
- `serve` never spawns a worker by default. Apply revisions freezes the submitted versions
  and notes and offers a request to copy into the editing chat. Feedback stays on disk.
- Unattended workers are explicitly optional: `build --background`, `serve --worker`.
  They cannot claim or recover session-owned jobs. `--no-worker` remains review-only.
- Interrupted sessions have an explicit inspection/reconciliation path; missing evidence
  cannot mark a clip finished. Historical jobs are preserved, not silently converted.

Drive intake also accepts file and folder links through one command. Guided `drive-login`
opens Google sign-in with read-only download scope, `drive-connect` remembers an existing
connection, and missing/old downloaders receive an actionable check. OAuth uses rclone's
[documented configuration flow](https://rclone.org/commands/rclone_config_create/) and
[read-only scope](https://rclone.org/drive/#drive-readonly). The existing checksum, exact-file
identity and interrupted-transfer guards remain.

Validation: 209 Node tests, 138 targeted Python tests and five portable-distribution
tests pass; source/manifest audit is clean. Live local rclone 1.75.2 connection discovery
and an authenticated read check passed using an existing work connection. Fresh browser
OAuth on a teammate Mac and a new remote footage download are not claimed by that check.

Existing installations: upgrade the Homebrew/Workbrew package, rerun the installed
engine onboarding with existing choices, then refresh owned skill links. Preserve keys,
projects and active work; settle any live or uncertain operation before updating its runtime.
Read the new installed AGENTS.md and docs/ONBOARDING.md rather than repeating the old
CLI-approval instructions. Normal host permission prompts still apply to individual commands.

# 0.2.0-preview.12

Repairs confirmed from the teammate's preview.11 installation and first FilmCraft job.
See [the issue ledger](TEAM_SESSION_REPAIR_LEDGER.md) for the evidence and classification.

- Guided FFmpeg setup preserves existing providers and tests binaries by executing them.
- Shared keys are reused; local-only users can explicitly defer delivery.
- Claude login/version checks precede editing, with an exact-project command/write smoke.
- Caption transcription defaults to the packaged AssemblyAI owner and toolkit credentials.
- Invalid brain requests fail locally; shared preparation errors retain evidence without
  demanding native reconciliation when no editor was instantiated.
- Caption boundary rounding no longer falsely rejects adjoining cards; real overlaps still fail.
- Timestamped source sheets do not depend on FFmpeg's optional drawtext filter.

Validation: 196 Node tests (including six smoke outcomes), 137 targeted Python tests,
clean distribution audit and reproducible distribution patches. A fresh archive installed
Node packages, a new Python environment and the pinned FilmCraft runtime; runtime and
asset verification passed. That rehearsal took 47.2 seconds on an already provisioned Mac
with warm dependency caches, not a cold-Mac timing claim. Isolated setup copied all 12
bundle fonts, registered exactly six skills for each agent, reused synthetic credentials,
recorded delivery deferral and passed local FilmCraft doctor checks.

A real FilmCraft mechanical fixture prepared adjoining caption boundaries, constructed and
reopened native layers, rendered 48 frames, and passed full audio/video decode. Native build
was 0.32 seconds and export plus verification 1.17 seconds. Its timestamped sheet was viewed.
The initial fixture correctly rejected an incomplete font profile; the corrected fixture
used explicit font metadata. This is mechanical validation, not a new editorial approval.

Remaining limits: Premiere 26.5.2 remains unqualified; Gemini credit and company package
policies require their normal account/admin action. Claude project trust and permissions
remain user-controlled. Full cold-Mac onboarding, exact-source editorial replay and team
acceptance remain separate: the evidence upload omitted the original source bytes and full
supervising transcript. No global skills, installed editor projects or live credentials were
changed by this repair.

## Updating

Use the existing Homebrew/Workbrew installation:

```sh
brew update
brew upgrade maddexritter-rgb/acq/acq-edit
acq-edit version
acq-edit onboard guide
```

Then onboard the chosen engine again so the new version gets its own runtime. Existing
projects, engine configuration, shared assets and credentials are preserved. The guide
should resume the existing choices; it must not ask users to recreate completed accounts.
For an explicit local-only choice, add `--defer-delivery` to engine onboarding. Do not add
that flag automatically. Refresh previously installed skill links with `--update-owned`
and reopen the agent session as described in ONBOARDING.md.
