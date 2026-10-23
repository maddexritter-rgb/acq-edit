# Live agent and review-loop qualification

This opt-in fixture exercises the real configured agent, the pinned FilmCraft runtime, native publication and the browser review room. It uses generated test media and a frozen two-cut plan. It does **not** qualify source-word design, transcription, live brain retrieval, speech joins, reference fidelity or human editorial quality. It does not qualify another editor or a clean Mac installation.

## Run a fresh fixture

Build the toolkit and materialize its packaged skills using normal setup first. The FilmCraft runtime, FFmpeg and configured agent must already work. Agent usage is billed to the operator's configured account. No keys are copied, accounts changed, approvals bypassed or host integrations installed by this fixture.

From the repository root, choose a new directory outside the checkout, with an existing parent. Use an existing FilmCraft toolkit config. `prepare` refuses to overwrite an existing run and creates its own config/database/project. It copies only runtime/agent settings, never credentials or brain configuration.

```sh
npm run build
node scripts/native_agent_fixture.mjs prepare /absolute/new-fixture /absolute/toolkit-home/config.json
```

Set `ACQ_EDIT_HOME` to the generated fixture's `home` directory. The test-only environment switch is mandatory because this fixture deliberately has no real editorial evidence. Never use that switch for production jobs.

```sh
export ACQ_EDIT_HOME=/absolute/new-fixture/home
export ACQ_EDIT_TEST_FIXTURE=1
node dist/cli.js worker
```

Wait for the worker to exit, then inspect the job in the fixture database or the project's `10_WORK/review-feedback.json`. `worked: true` alone does not mean success. If it reports reconciliation, inspect its log, native state and receipts before any retry. Do not restart an active native operation. Do not run `serve` and the standalone worker simultaneously; they share a service lock.

Start `node dist/cli.js serve` with the same environment. Open its localhost session URL, select V1 and choose **Revise**. Enter:

> Change only the on-screen caption text to REVISED AGENT LOOP. Preserve both cuts, audio, framing, timing, caption style and position. This is the same synthetic mechanical fixture with ACQ_EDIT_TEST_FIXTURE=1; no new editorial design, transcription or brain fetch is needed. Render natively in FilmCraft and publish a new version.

Add one timecoded comment at 00:00:

> Keep the opening cut exactly as it is; only replace the caption wording.

Click **Apply revisions** once. While the job is editing/rendering, add another comment without applying again:

> Added while this revision is running: leave this note for the next submission; do not alter the current job.

Wait for the job to become **ready**. Select V2 and verify the new caption, fresh **Unreviewed** decision, previous submitted feedback and separate **Saved for next revision** comment. Its timecode must open read-only V1. Do not mark the synthetic clip Yes as a substitute for editorial acceptance.

```sh
node scripts/native_agent_fixture.mjs check /absolute/new-fixture
```

The read-only checker requires exactly two completed real-agent jobs and two correctly attributed immutable versions. It independently verifies source/media/checkpoint hashes, frame geometry, complete video/audio decoding, identical decoded audio, changed pictures, caption-only plan/native-state changes, fresh review status and late-feedback separation. It fails if the late comment was added too late to belong to the active submission; keep that failed run as evidence and start a fresh directory for another attempt.

Stop the fixture server after inspection. The run remains reopenable with the same `ACQ_EDIT_HOME`; no cleanup or deletion is automatic. Remove the test environment switch before returning to normal work.

## Observed on 2026-10-23

Installed Codex completed a queued native FilmCraft build and a browser-submitted caption revision. Both jobs reached ready through the actual app-server transport, not mocked results. Each produced 50 frames at 640×360/25 fps with audio and a new native checkpoint. V1 and V2 retained their original hashes; project-owned footage was unchanged. Complete decoded audio was byte-identical. Native inspection differed only at the caption text value, and the rendered pixels visibly showed the replacement wording.

The live browser displayed V2 unreviewed, preserved the submitted V1 request, kept a comment added during the actual revision for the next submission, and opened the original read-only V1 from that comment. The checker passed against this run. Fixture preparation was separately exercised using generated media and an isolated config; that second preparation did not dispatch additional agent jobs.

This is a FilmCraft/Codex mechanical integration milestone. Successful Claude execution, Resolve/Premiere agent loops, full finishing, real-source editorial tests, clean machines and human approval remain separate pilot gates. The installed Claude account previously returned a low-credit error; this test does not resolve it.
