# Implementation checkpoint — 2026-10-23

**Not pilot-ready.** This is the first development implementation, with explicit release gates.

Implemented:
- Fresh standalone repository, local TypeScript service/CLI, SQLite durable state, atomic JSON exports.
- Verified local source copying, YouTube downloader and authenticated rclone Drive route.
- Review room with queue, player, versions/comparison, decisions, autosaved notes, timecoded comments, downloads and Apply revisions.
- Snapshot/idempotent revision queue, per-project serialization, stale version protection, restart reconciliation, Codex/Claude dispatch. Late or withdrawn feedback is carried to the next submission with its original version and timestamps.
- Job-attributed publication and completion: exact submitted clips/parents, complete batches, immutable media/native-checkpoint hash verification, and evidence-checked reconciliation.
- 37 canonical skill owners and shared helpers, provenance manifest, isolated runtime materialization, credential entry and doctor.
- Native FilmCraft and Resolve adapters, current Premiere Agent Lab source/panel package and scoped adapter, optional Remotion asset renderer.

Verified in this checkout:
- 32 service/state/API/artifact-integrity/process tests pass. Browser fixture verified autosave, duplicate submission (one job), V2 with previous feedback, fresh unreviewed state, and historical timecode navigation to read-only V1.
- Browser pending-feedback fixture: V2 retained the original submitted request separately from later notes; a late timestamp opened V1 at 1.25 seconds; two Apply clicks created one queued V2 job containing the V1 carryover. This used identical synthetic footage for V1/V2 and does not prove an actual agent revision.
- FilmCraft pinned binary built/reopened a native two-cut project and exported H264/AAC: 640×360, 25 fps, exactly 50 decoded frames. Full decode passed. First visual inspection exposed text alignment; the adapter was corrected to center its text.
- Resolve Studio 21.1.1 connected and built source-native linked cuts and Fusion Text+. Native H264/AAC export and caption-color revision: 640×360, 25 fps, exactly 50 decoded frames. Full decode and sampled visible-text inspection passed. Testing corrected the Fusion render clock for trimmed sources and switched input validation to native readback. Fusion graph exports are now included in state fingerprints.
- Real installed Codex app-server completed a no-tool response and exact-session resume using the toolkit transport. Installed Claude reached its result channel but returned an explicit low-credit error; its successful live round trip remains blocked on usable account credentials/credit. These checks do not prove editorial execution.
- Agent/process regression fixtures cover missing results, malformed output, wrong turn/session, approval requests, disconnects, log failures, timeout termination and service shutdown. Shutdown waits for the owned agent and exports reconciliation state before releasing the service lock.
- Packaged Premiere integration installs dependencies and compiles. Runtime dependency audit is clean after lockfile-only SDK/transitive updates. Installed live host responded to read-only snapshot; its production project was left untouched.
- Canonical exported Python files parse. Distribution secret-pattern/hash scan passes.

Remaining before pilot:
- Prove full native editing jobs through both agent runners; Codex transport/start/resume passed but editorial execution remains unproven. Claude live success needs usable account credentials/credit. Interactive permission requests stop for reconciliation.
- Complete automatic finishing orchestration and native revisions; add robust complete native-state preconditions, including stable inspection across save/reopen.
- Remove/replace remaining optional legacy path references; provide brand profiles, licensed fonts/music/templates separately.
- Prove a dedicated Premiere toolkit fixture; do not use the currently open production project.
- Real monologue/Q&A/multicamera footage, played speech joins, complex framing/music and human editorial review across all three backends.
- Clean Mac installation, disconnected host/missing media/render failure recovery, authenticated Drive verification, brain-update isolation, reference benchmarks.

Use docs/ACCEPTANCE.md as the release gate. The repository is a development handoff, not a claim that the full requested plan is complete.

GitHub Actions: the authenticated OAuth token cannot write workflow files. The CI definition is preserved as `docs/ci-workflow.yml`; an authorized repository maintainer can install it under `.github/workflows/`. No account permissions were changed.
