# Implementation checkpoint — 2026-10-23

**Not pilot-ready.** This is the first development implementation, with explicit release gates.

Implemented:
- Fresh standalone repository, local TypeScript service/CLI, SQLite durable state, atomic JSON exports.
- Verified local source copying, YouTube downloader and authenticated rclone Drive route.
- Review room with queue, player, versions/comparison, decisions, autosaved notes, timecoded comments, downloads and Apply revisions.
- Snapshot/idempotent revision queue, per-project serialization, stale version protection, restart reconciliation, Codex/Claude dispatch. Late or withdrawn feedback is carried to the next submission with its original version and timestamps.
- Job-attributed publication and completion: exact submitted clips/parents, complete batches, immutable media/native-checkpoint hash verification, and evidence-checked reconciliation.
- 37 canonical skill owners and shared helpers, provenance manifest, isolated runtime materialization, credential entry and doctor.
- Native source-linked music placement, explicit dialogue/bed gain, fades, and music-gain revisions in FilmCraft and Resolve; music selection remains owned by the packaged skill.
- Shared compiler binding canonical source-word selections, paired audio decisions and played-source routing to exact native ranges; production builds revalidate the binding.
- Shared source-pixel fixed-crop plans, native FilmCraft Motion / Resolve Fusion framing, and fixed-crop revisions that preserve existing layers.
- Native FilmCraft and Resolve adapters, current Premiere Agent Lab source/panel package and scoped adapter, optional Remotion asset renderer.
- Premiere render-to-publication adapter: guarded save and typed exact export, whole-packet project preflight, restored-mark and native-state checks, saved project hash, actual media decode and shared render receipt. Its live toolkit fixture is still pending; see `PREMIERE_RENDER.md`.

Verified in this checkout:
- 32 service/state/API/artifact-integrity/process tests pass. Browser fixture verified autosave, duplicate submission (one job), V2 with previous feedback, fresh unreviewed state, and historical timecode navigation to read-only V1.
- Browser pending-feedback fixture: V2 retained the original submitted request separately from later notes; a late timestamp opened V1 at 1.25 seconds; two Apply clicks created one queued V2 job containing the V1 carryover. This used identical synthetic footage for V1/V2 and does not prove an actual agent revision.
- FilmCraft pinned binary built/reopened a native two-cut project and exported H264/AAC: 640×360, 25 fps, exactly 50 decoded frames. Full decode passed. First visual inspection exposed text alignment; the adapter was corrected to center its text.
- Resolve Studio 21.1.1 connected and built source-native linked cuts and Fusion Text+. Native H264/AAC export and caption-color revision: 640×360, 25 fps, exactly 50 decoded frames. Full decode and sampled visible-text inspection passed. Testing corrected the Fusion render clock for trimmed sources and switched input validation to native readback. Fusion graph exports are now included in state fingerprints.
- Real installed Codex app-server completed a no-tool response and exact-session resume using the toolkit transport. Installed Claude reached its result channel but returned an explicit low-credit error; its successful live round trip remains blocked on usable account credentials/credit. These checks do not prove editorial execution.
- Real Codex → FilmCraft build → publication → browser Apply revisions → native caption revision → V2 publication passed on synthetic media. Both jobs reached ready; native inspection changed only the caption text, decoded audio was identical, original files retained their hashes, and V2 required fresh review. A comment added during the actual revision remained pending with a link to read-only V1. The reproducible opt-in fixture/checker is documented in `LIVE_AGENT_LOOP.md`; this does not prove real editorial design or the other agent/engine combinations.
- Agent/process regression fixtures cover missing results, malformed output, wrong turn/session, approval requests, disconnects, log failures, timeout termination and service shutdown. Shutdown waits for the owned agent and exports reconciliation state before releasing the service lock.
- Packaged Premiere integration installs dependencies and compiles. Runtime dependency audit is clean after lockfile-only SDK/transitive updates. Installed live host responded to read-only snapshot; its production project was left untouched.
- Native music fixtures in FilmCraft and Resolve measured −12 dB placement and −18 dB revision, unchanged dialogue during music revision, preserved source cut timing and complete 50-frame native exports. FilmCraft pictures were identical; Resolve duplication showed small pixel differences (49.16 dB average PSNR), documented in `NATIVE_AUDIO.md`.
- Native vertical framing fixtures in FilmCraft and Resolve rendered 50 frames at 360×640. A one-shot crop revision moved its source label exactly 40 pixels while preserving the other shot and caption bounds. FilmCraft audio was identical; Resolve audio differed by 79.05 dB relative to signal. See `NATIVE_FRAMING.md` for scope and limitations.
- FilmCraft paired-sample fixture preserved 11/17-sample offsets, independent audio durations, native links and source sync across save/reopen/render; decoded audio correlated 0.99999878 with the exact-sample reference. Resolve now preserves the same sample geometry through its own native DRT checkpoint/import route, qualified on Studio 21.1.1 build 10. Native save/reopen, render and caption revision passed; real speech acceptance remains open. See `NATIVE_ASSEMBLY.md`.
- Resolve export-state recovery reproduced and fixed a completed-but-audio-only output after an audio-only diagnostic. A built-in preset reset restores native video/audio export; all adapters now verify actual streams, geometry, frame count and full decode before issuing a success receipt. See `RESOLVE_PRECISION.md`.
- Resolve parsed Fusion fingerprints remained stable across actual save/reopen. Deliberate native caption, expression and connection changes were detected, and a stale revision was refused. Expanded snapshots detected clip enable, track mute/lock and include source paths and markers. The reopened original timeline exported 50 frames with decoded video/audio byte-identical to its prior valid render. See `RESOLVE_STATE.md` for the narrow normalization, existing-fingerprint reconciliation and host page-context limitation.
- Thirty-nine Python tests pass, including seven Fusion parser/state tests and nine Premiere adapter tests for publication and failure boundaries using explicit fake-host responses. Missing toolkit profiles cannot fall back to a global production connector. These tests do not certify a Premiere native render. Canonical exported Python files parse. Distribution secret-pattern/hash scan passes.

Remaining before pilot:
- Prove full native editorial jobs through both agent runners and all engines. Codex/FilmCraft synthetic build and caption revision passed; real editorial execution and Resolve/Premiere agent loops remain unproven. Claude live success needs usable account credentials/credit. Interactive permission requests stop for reconciliation.
- Complete automatic finishing orchestration and native revisions; broaden native-state preconditions beyond the verified Resolve Fusion/timing/property/track coverage, including unexposed color/Fairlight state and other hosts.
- Remove/replace remaining optional legacy path references; provide brand profiles, licensed fonts/music/templates separately.
- Prove a dedicated Premiere toolkit fixture; do not use the currently open production project.
- Real monologue/Q&A/multicamera footage, played speech joins, complex framing/music and human editorial review across all three backends.
- Clean Mac installation, disconnected host/missing media/render failure recovery, authenticated Drive verification, brain-update isolation, reference benchmarks.

Use docs/ACCEPTANCE.md as the release gate. The repository is a development handoff, not a claim that the full requested plan is complete.

GitHub Actions: the authenticated OAuth token cannot write workflow files. The CI definition is preserved as `docs/ci-workflow.yml`; an authorized repository maintainer can install it under `.github/workflows/`. No account permissions were changed.
