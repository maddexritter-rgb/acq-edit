# Pilot acceptance matrix

A pilot release is blocked until every required row passes on actual media and each engine independently. Unit tests, mocks, API success, native project readback, file verification, listening and human approval are distinct evidence.

| Scenario | Current evidence | Remaining acceptance |
|---|---|---|
| Fresh clone, Codex, clean Mac | TypeScript builds; packaged sources audited; installed Codex start/resume and real FilmCraft synthetic build/review revision passed | Setup and full editorial job on clean Mac |
| Fresh clone, Claude, clean Mac | Headless result/error handling tested; installed CLI returned explicit low-credit error | Real permitted editing job and exact-session recovery |
| FilmCraft only | Native two-cut/text fixture, save/reopen, 50-frame H264/AAC render; actual Codex build and browser-submitted caption revision passed | Real source-word design, precision joins, all finishing, broader revisions |
| Resolve only | Studio 21.1.1 native cuts/Fusion/render; actual Codex build and browser-submitted caption revision published two 50-frame versions, with an exact-audio check failure | Resolve audio qualification, real source-word design, complex finishing and independent clean installation |
| Premiere only | Packaged Lab builds; read-only installed-host response; guarded render/publication adapter and failure-boundary tests | Fresh isolated toolkit scope, actual native complete render/revision, save/reopen and human review |
| Intake | Local/YouTube/Drive implementations | Real authenticated Drive checksum and restart scenarios |
| Monologue/Q&A/multicamera | Canonical design/ingest skills packaged | Blind review of real examples in every engine |
| Difficult speech joins | Canonical compiled-word/paired-range binding added; FilmCraft exact-sample synthetic native render verified; Resolve version-gated native sample checkpoint/import, save/reopen, render and caption revision verified | Real played-audio proof, identity, endings and AV sync in every engine; broader host/source qualification |
| Caption-only changes | Resolve native caption-color revision and actual Codex wording revision preserved inspected cuts/properties; FilmCraft actual Codex wording revision preserved all other native state and decoded audio | Resolve decoded-audio variance and full Fusion equivalence, Premiere toolkit fixture, broader styling and real footage |
| Music placement/revision | FilmCraft and Resolve native gain/fade fixtures and music-only revision measured; dialogue and cuts preserved | Real approved music auditions, envelopes/replacement, Premiere toolkit fixture, human listening |
| Fixed framing/revision | FilmCraft Motion and Resolve Fusion vertical crops rendered; one-shot shift, caption bounds and cuts verified; audio identity limitation recorded | Real subject inspection/tracking, multicamera layouts, Premiere toolkit fixture and human review |
| Spoken recuts/hook replacement | Dependent owners routed | Full layer recomputation in each engine |
| Duplicate/stale submission | SQLite tests and browser duplicate-click fixture pass | Actual agent race test |
| Notes added during rendering | Pending feedback, withdrawals, exact old timestamps, next submission and partial batches tested; actual Codex/FilmCraft and Codex/Resolve revisions preserved late comments separately | Premiere, long-running batches and human review |
| Completion integrity | Rejects unrelated/omitted versions and modified media/checkpoints | Native interrupted-batch reconciliation |
| Restart/disconnect/render failure | Reconciliation state and shutdown/process termination tested; Resolve audio-only export-state recovery reproduced, and false success receipt prevented | Kill native exports/agent sessions and recover on each host |
| Version history/timecodes | Passing persistence/API tests | Browser fixture verified V2/history/timecode behavior; real editorial review pending |
| Brain updates | Existing restricted reader packaged | New guidance affects new design only; no approval rewrite |
| Reference fidelity | Recipe contract + dense-frame utility + motion integration | Supplied benchmark, complete viewing/listening, human assessment |

No automatic check grants human approval. Record acceptance artifacts under project work folders and summarize non-sensitive results here; never commit private footage or tokens.
