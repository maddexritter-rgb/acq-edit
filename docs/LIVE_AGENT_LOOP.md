# Live agent and review-loop qualification

This opt-in fixture exercises the real configured agent, the selected FilmCraft or Resolve runtime, native publication and the browser review room. It uses generated test media and a frozen plan. It does **not** qualify source-word design, transcription, live brain retrieval, speech joins, reference fidelity or human editorial quality. A run qualifies only its actual agent/backend combination, not another editor or a clean Mac installation.

## Run a fresh fixture

Build the toolkit and materialize its packaged skills using normal setup first. The selected runtime (FilmCraft CLI or Resolve Studio with configured ResolvePython), FFmpeg and configured agent must already work. Agent usage is billed to the operator's configured account. No keys are copied, accounts changed, approvals bypassed or host integrations installed by this fixture.

From the repository root, choose a new directory outside the checkout, with an existing parent. Use an existing FilmCraft or Resolve toolkit config. `prepare` refuses to overwrite an existing run and creates its own config/database/project. It copies only the selected runtime/agent settings, never another editor's configuration, credentials or brain configuration.

```sh
npm run build
node scripts/native_agent_fixture.mjs prepare /absolute/new-fixture /absolute/toolkit-home/config.json
```

For Resolve, finish host preparation **before** starting the worker: create/open the exact empty `ACQ_<projectId>` project printed by `prepare`. Do not switch or close unrelated work. Resolve may open a blank `Untitled Project` after a previous project closes; that is still a different project and the adapter correctly refuses it. The fixture generator does not mutate host projects. Do not prepare the host concurrently with a worker's inspection or native operation; the native lock is an exclusive ownership boundary.

Set `ACQ_EDIT_HOME` to the generated fixture's `home` directory. The test-only environment switch is mandatory because this fixture deliberately has no real editorial evidence. Never use that switch for production jobs.

```sh
export ACQ_EDIT_HOME=/absolute/new-fixture/home
export ACQ_EDIT_TEST_FIXTURE=1
node dist/cli.js worker
```

Wait for the worker to exit, then inspect the job in the fixture database or the project's `10_WORK/review-feedback.json`. `worked: true` alone does not mean success. If it reports reconciliation, inspect its log, native state and receipts before any retry. Do not restart an active native operation. Do not run `serve` and the standalone worker simultaneously; they share a service lock.

Start `node dist/cli.js serve` with the same environment. Open its localhost session URL, select V1 and choose **Revise**. Enter:

> Change only the on-screen caption text to REVISED AGENT LOOP. Preserve both cuts, audio, framing, timing, caption style and position. This is the same synthetic mechanical fixture with ACQ_EDIT_TEST_FIXTURE=1; no new editorial design, transcription or brain fetch is needed. Render natively in this project's selected backend and publish a new version.

Add one timecoded comment at 00:00:

> Keep the opening cut exactly as it is; only replace the caption wording.

Click **Apply revisions** once. While the job is editing/rendering, add another comment without applying again:

> Added while this revision is running: leave this note for the next submission; do not alter the current job.

Wait for the job to become **ready**. Select V2 and verify the new caption, fresh **Unreviewed** decision, previous submitted feedback and separate **Saved for next revision** comment. Its timecode must open read-only V1. Do not mark the synthetic clip Yes as a substitute for editorial acceptance.

```sh
node scripts/native_agent_fixture.mjs check /absolute/new-fixture
```

The read-only checker requires exactly two completed real-agent jobs and two correctly attributed immutable versions. It independently verifies source/media/checkpoint hashes, frame geometry, complete video/audio decoding, identical decoded audio, changed pictures, a caption-only plan change, fresh review status and late-feedback separation. FilmCraft additionally requires that its complete native inspection differ only in caption wording. Resolve duplicates timelines: its comparison preserves cuts, source paths/IDs, properties, fades, link topology, track state and Fusion-comp counts while allowing new timeline/item IDs, the new timeline name and changed Fusion hashes. It does **not** infer full Fusion graph equivalence from those hashes; inspect the rendered captions and native graph evidence separately. It fails if the late comment was added too late to belong to the active submission; keep that failed run as evidence and start a fresh directory for another attempt.

An audio mismatch is reported with measured sample and RMS differences while the checker continues its other checks. It still returns `passed: false` and exits 1; these measurements do not relax the exact-audio requirement or establish audibility. Other failed assertions also exit unsuccessfully.

Stop the fixture server after inspection. The run remains reopenable with the same `ACQ_EDIT_HOME`; no cleanup or deletion is automatic. Remove the test environment switch before returning to normal work.

## Observed on 2026-10-23

Installed Codex completed a queued native FilmCraft build and a browser-submitted caption revision. Both jobs reached ready through the actual app-server transport, not mocked results. Each produced 50 frames at 640×360/25 fps with audio and a new native checkpoint. V1 and V2 retained their original hashes; project-owned footage was unchanged. Complete decoded audio was byte-identical. Native inspection differed only at the caption text value, and the rendered pixels visibly showed the replacement wording.

The live browser displayed V2 unreviewed, preserved the submitted V1 request, kept a comment added during the actual revision for the next submission, and opened the original read-only V1 from that comment. The checker passed against this run. Fixture preparation was separately exercised using generated media and an isolated config; that second preparation did not dispatch additional agent jobs.

Installed Codex also completed both native Resolve jobs through the same queue and browser submission flow on Studio 21.1.1. Both 50-frame versions published successfully. The checker verified unchanged source/published hashes, cut/source/property/link/track geometry, caption-only plan changes, fresh review and late-feedback separation. The browser showed the replacement caption and opened read-only V1 from the historical comment. Only Resolve runtime configuration was copied into this fixture; this is not evidence of an installation on a Mac without other editors.

**The Resolve checker did not pass overall.** Decoded audio differed between V1 and V2: difference RMS was −78.04 dB relative to the original signal, with maximum sample difference 0.000370525. An unpublished repeat render of the unchanged V2 timeline also differed, at −74.70 dB relative to signal. This demonstrates variability in repeated native output; it does not establish its cause, inaudibility or speech-sync acceptance. The exact-audio failure remains open. The checker does not establish full Fusion graph equivalence across duplicated timelines.

An earlier Resolve attempt stopped at an unrelated blank project and then an exclusive native lock during operator host preparation. Inspection confirmed zero timelines/media and no render. It was explicitly reconciled as failed, with no version published, and retained separately. The successful two-job attempt used a fresh fixture and completed host preparation before dispatch.

These are mechanical integration milestones. Successful Claude execution, the Premiere agent loop, Resolve audio qualification, full finishing, real-source editorial tests, clean machines and human approval remain separate pilot gates. The installed Claude account previously returned a low-credit error; these tests do not resolve it.

## Tracking-revision scenario

The same harness supports `prepare NEW_DIRECTORY CONFIG_JSON tracking`. It creates a separate 360×640 synthetic fixture with two source-bound X curves, a fixed caption and an explicit source-time jump. It does not change an existing fixture. The queued real-agent build must execute that complete plan natively. The default scenario remains `caption`, including for older fixtures without a scenario field.

After V1 is ready, open the review room and submit the exact notes and opening comment from the fixture's `revision-request.json`. The requested change is only `cut-0`: `xByFrame[i] = 80.25 + i` for all 25 frames, starting at X 80.25. The other cut, caption, audio, Y, scale and all source ranges must stay unchanged. Use the ordinary **Apply revisions** button. While the real revision is active, add the file's `lateComment` without applying again.

Run the same `check DIRECTORY` command. It selects the scenario from the immutable fixture descriptor, verifies two real ready jobs and their published versions, checks the exact requested new curve, requires a fresh framing-decision receipt, and refuses any other plan change. For FilmCraft it independently checks typed saved-native key values/clocks/interpolation and all protected project data, allowing only the selected Anchor values/keys and exact destination-derived document labels. Source/checkpoint/media hashes, decoded audio, new review status and late-feedback separation are checked as in the caption scenario. Resolve's checker still verifies its documented timeline geometry subset; it does not infer full Fusion equivalence or waive audio differences.

New fixtures also require archived plan, receipt and inspection hashes. Tracking fixtures require those pins even when prepared before the descriptor flag was added. Older caption fixtures without those publication fields remain checkable, but the checker explicitly reports `archivedArtifactsPinned: false`; their earlier evidence does not establish those additional hashes.

Observed on 2026-10-23: installed Codex completed the native FilmCraft tracking build, then a browser-submitted tracking revision. Both jobs reached ready and published 50-frame 360×640/25 fps versions. The checker passed: every requested X key and its native clock/interpolation matched, all protected native project data remained unchanged, source/published files and archived artifact hashes matched, and decoded audio was byte-identical. The first shot changed while the complete second-shot native data and caption remained fixed. The browser displayed unreviewed V2 with the original request, kept the comment added during the actual job separately, and opened read-only V1 from that comment's timecode. The earlier caption fixture also passed its original checks with the expanded checker, explicitly without claiming its absent archival pins.

This scenario tests agent execution of a specified mechanical revision. It is not evidence that the agent can choose an appropriate face, design a real tracking curve, judge speech or complete the team pilot.

## Panel-revision scenario

Use `prepare NEW_DIRECTORY CONFIG_JSON panels` for a fresh 75-frame 360×640 fixture. Two project-owned camera sources appear in independent split occurrences around a full-frame shot. Each split has a tracked top camera and fixed bottom camera, with distinct camera/master source clocks. The frozen plan pins Assembly Design camera-layout and framing receipts. Native construction must retain independent camera inputs; a flattened movie does not satisfy the fixture.

Once the real build reaches ready, submit the exact `notes` and opening `comment` from `revision-request.json` through the review room. This swaps only the first split's panel rectangles, sets its tracked crop to `xByFrame[i] = 80.25 + 0.75*i`, and sets its fixed crop X to 60. The other split, full-frame shot, source clocks, cuts, caption, graphics and audio remain fixed. Add the file's `lateComment` after applying and before the revision completes, without submitting again.

The same read-only checker requires the exact submitted request, routing to both Assembly Design and horizontal-to-vertical, fresh camera/framing receipts, and an exact plan comparison against the requested change. It checks camera colors and marker edges in all 100 panel-frames per version. FilmCraft additionally verifies every native panel clock/geometry and compares the complete protected saved project, allowing only the targeted values/keys and copy-derived document labels. Source/media/checkpoint hashes, archived artifact pins, decoded audio, two ready real-agent jobs, fresh review and pending feedback are checked as above. Resolve still requires separate full native graph inspection; its timeline comparison alone does not prove Fusion equivalence.

This fixture uses static markers: native readback verifies source clocks, while pixels verify crop/layout transport. It does not prove real camera synchronization, subject framing, speech quality, automatic camera choice or human approval.

Observed on 2026-10-23: installed Codex completed the FilmCraft panel build and browser-submitted panel revision. Both jobs reached ready and published 75-frame versions. The checker passed exact plan/receipt/owner routing, all native panel clocks/geometry, complete protected saved-project comparison, preserved source/published hashes and archived artifact pins. All 100 panel-frames in each version passed with maximum marker-edge error 0.75 pixels. Decoded audio was byte-identical. The browser showed the swapped opening cameras, unchanged caption and unreviewed V2, retained previous feedback separately from the late comment, and opened read-only V1 from its timestamp. No other agent/backend combination is qualified by this run.

## Spoken-recut scenario

Use `prepare NEW_DIRECTORY CONFIG_JSON recut` with FilmCraft. The frozen 50-frame plan has two different source passages, fixed crops, a native caption, a generated music tone and a transparent graphic placed over the second passage. The source audio uses distinct frequencies in the two passages so retained audio can be checked independently of timeline metadata. The graphic's alpha is verified before dispatch. This is generated media, not real speech or a music audition.

After the real build reaches ready, submit `revision-request.json` through the review room. It removes the opening passage, keeps the second passage's exact picture/audio ranges, retimes the surviving crop and caption, offsets/trims music and moves the graphic to the new beginning. The agent must create fresh selection/framing/music decisions and the complete finishing receipt, use `spoken-recut`, preserve the parent and publish a 25-frame version with archived recut proof. Add the supplied late comment at 1.25 seconds on V1 while the revision is running. This time no longer exists in the shorter V2; its historical link must still open V1.

The read-only `check DIRECTORY` requires two ready real-agent jobs, exact submitted feedback, fresh review and retained late feedback. It checks pinned sources and published artifacts, exact surviving source and native AV links, caption/music/graphic timing, the native framing, matching recut fingerprints and preservation of the parent working project. Decoded pixels must retain the surviving picture region above 35 dB PSNR and show the graphic on all 25 frames. Decoded audio must contain the retained passage's tone and the correctly mixed music, while excluding the removed passage's tone. This is a source-transport check; exact audio identity is inappropriate after a deliberate passage removal. Real speech joins, music quality, human approval and other engine/agent combinations remain separate gates.

Observed: the Codex/FilmCraft recut scenario completed both native jobs and published 50-frame V1 and 25-frame V2. The independent checker passed all source/native/finishing/receipt/feedback checks. The retained picture region measured 53.7554 dB PSNR, the graphic remained visible on all 25 frames, and the decoded music-to-retained-tone amplitude ratio was 0.26308; the removed tone measured 0.00000187 against retained tone 0.16875. The browser showed the new caption and graphic, fresh review and previous feedback, and opened read-only V1 from its late 1.253-second comment. An earlier preparation exposed an entirely transparent generated overlay; that agent run was stopped gracefully and retained, the generator gained an alpha preflight, and the successful run used a fresh directory. No result from the invalid fixture counts toward acceptance.
