# Teammate session repair ledger — 2026-10-27

Baseline: preview.11, commit e5adfaf879f3f1dea35024661d775d2a646bcdce.
Evidence ZIP: 201,357,753 bytes; SHA-256
`84952ebdb22d7357ed1b19a6e0f2180adede6ee2a61c4b5bf316a35794dfd4a2`.
Private logs/media remain outside Git. This ledger contains sanitized reproductions.

| Finding | Classification | Change / acceptance evidence |
| --- | --- | --- |
| Existing tap FFmpeg conflicted with mandatory core formula and stopped launching after a shared-library upgrade | Newly repaired | Formula/Brewfile no longer force core FFmpeg; media-check preserves present/unlinked providers. Execute both binaries before install and on resume. Fake broken dylib, missing, unlinked, managed brew and timeout regressions. |
| Core FFmpeg lacked drawtext; visual-sheet commands failed repeatedly | Newly repaired | Pillow-labeled source_sheet helper and worker routing; no optional drawtext dependency. |
| Saved editing keys were requested again for the second editor | Newly repaired | Reuse shared private credentials, explicit reentry, malformed/unsafe file refusal. Presence remains distinct from authentication. |
| User deferred delivery, but onboarding form cancellation marked failure | Newly repaired | Explicit --defer-delivery state and resume path; cancellation never implies consent. |
| First worker had no CLI login despite desktop access | Newly repaired | Configured CLI auth check before enqueue/dispatch and doctor; sanitized actionable result. |
| Second worker used 2.1.195; selected model required >=2.1.251 | Newly repaired | Observed minimum baseline check; newer versions do not imply every-model qualification. |
| Project trust missing; 68 allow rules ignored | Onboarding repaired; user interaction remains required | Exact-project interactive trust guidance and observable command/write smoke. No trust DB edits or automatic permission grants. |
| Later worker encountered compound-command permission refusals | Guidance and diagnostics repaired | Simple absolute commands, toolkit helper routing, stop on denied actions; existing user/managed policies remain authoritative. |
| Brain problem longer than 240 characters reported a service outage | Newly repaired | Local request validation before reservation/network; invalid-request classification and concise problem guidance. |
| Caption helper imported optional faster-whisper before help/default execution | Newly repaired | AssemblyAI shared owner by default; optional Whisper is explicit and lazily imported. |
| Shared transcription helper could read personal shell/backup keys | Newly repaired during code review | Toolkit credential store/environment only; no implicit alternate provider for editorial ingest. |
| Clip UUID did not match compiled selection | Guard worked; recovery improved | Register UUID first; retained packet-bound preparation failures settle without claiming an editor ran. |
| Caption comparison rejected ~7.1e-15 seconds of floating-point noise | Newly repaired | Normalize at most four ULPs at adjoining speech boundaries; genuine subframe overlap still fails. |
| Pure preparation errors required manual native reconciliation | Newly repaired | Explicit shared-only preparation failure envelope, hashed result and packet, no adapter construction; native/uncertain failures still require reconciliation. |
| Worker emitted early success while native rendering continued | Existing transport behavior retained and regression-covered | Wait for process exit, preserve final result/receipt validation; test early success followed by delayed success and failure. |
| Speech cut clipped a word by 16 ms | Correct safety gate | Preserve speech-boundary refusal. Do not weaken it to speed up production. |
| Gemini generation returned 402 | Provider credit limitation | Read authentication does not certify generation/listening. Waveforms never count as listening or approval. |
| Premiere 26.5.2 connected but was unqualified | Known qualification limitation | Keep native execution guard. No new version support claimed. |
| Prebuilt FilmCraft, browser key entry, six public skills, delivery onboarding, connector lock | Already shipped | Retain and regression-check; no duplicate implementation. |

## Release verification

See RELEASE_NOTES.md for the final test counts and fresh-package rehearsal result.
A clean package and mechanical native fixture do not establish clean-Mac acceptance,
managed Workbrew policy approval, human editorial approval, or Premiere 26.5.2 qualification.
The uploaded archive contains worker logs and final artifacts but omits original source
bytes and the full supervising chat transcript. Exact-source editorial replay remains
separate from sanitized regression replay and native mechanical verification.
