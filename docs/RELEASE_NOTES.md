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
