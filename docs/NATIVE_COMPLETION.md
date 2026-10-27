# Editable Premiere completion

New Premiere build jobs freeze `completion: editable-project`. FilmCraft builds and
historical jobs without this field retain `rendered-review`. An explicit
`build PROJECT --export REQUEST` opts into export. Revision jobs for existing rendered
versions retain their original contract. Never create a placeholder MP4 or version row.

For normal Premiere work: construct the source-linked timeline, finish with owner skills,
verify and save it, safely reopen the saved project, then leave its intended sequence open.
Do not launch the room, export or upload unless separately requested. Preserve unrelated
open projects; if a safe reopen needs their owner to save/close them, report that blocker.

`native PROJECT complete PACKET` is a read-only verification operation. Packet fields:

- `plan`, `nativeProject`, `expectedFingerprint`: the final source-linked plan and exact live target.
- `reopenResult: {path, sha256}`: successful `native open` result with
  `status: inspected_native_session`, `mode: open` and its retained lifecycle receipt.
  `verified_existing_session` is insufficient: it proves no disk round trip.
- `captionBuild: {path, sha256}`: caption-clips native Graphics build receipt.
- `motionPlan: {path, sha256}`: reframe owner's native motion plan, including final
  `sharedPlanSha256`. The verifier checks the frozen per-frame curve and actual native keys.
- `audioPlans: [{path, sha256}]`: one calibrated music-owner operation plan for every
  dialogue/music item. The dialogue helper saves `item-NN-verification-plan.json`.
- `audioSharedPlanSha256`: final source plan hash used by those owner plans.
- `inspection`, `receipt`: fresh project-local output paths.

The operation verifies source paths, exact source/record clocks, independent linked audio,
editable saved caption text/font/position, native framing, audio envelopes, sequence clocks,
real reopen persistence, and unchanged native state throughout inspection. It does not
claim listening, interpolator readback, rendered appearance or human approval.

Save job `result.json` as `{"jobId":"…","operationIds":["native-complete-operation-id"]}`.
The worker and ready-reconciliation route require successful operation journals belonging
to that job and rehash every saved artifact. SQLite retains `nativeCompletions` on the job;
no rendered review version is fabricated. Existing versions and feedback stay intact.

## Qualification boundary

This new completion route needs real host acceptance. Its initial framing verifier covers
source-linked V1/A1 clips with dense tracked crops. Multi-panel construction, unsupported
processing and additional effects need their own native verifier; stop with the limitation
instead of claiming completion or dropping layers. The existing 26.3 execution scope remains;
26.5.2 is explicitly unqualified. Passing fixture tests is not native acceptance.
