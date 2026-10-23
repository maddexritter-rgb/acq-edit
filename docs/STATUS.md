# Implementation checkpoint — 2026-10-23

**Not pilot-ready.** This is the first development implementation, with explicit release gates.

Implemented:
- Fresh standalone repository, local TypeScript service/CLI, SQLite durable state, atomic JSON exports.
- Verified local source copying, YouTube downloader and authenticated rclone Drive route.
- Review room with queue, player, versions/comparison, decisions, autosaved notes, timecoded comments, downloads and Apply revisions.
- Snapshot/idempotent revision queue, per-project serialization, stale version protection, restart reconciliation, Codex/Claude dispatch.
- 37 canonical skill owners and shared helpers, provenance manifest, isolated runtime materialization, credential entry and doctor.
- Native FilmCraft and Resolve adapters, current Premiere Agent Lab source/panel package and scoped adapter, optional Remotion asset renderer.

Verified in this checkout:
- 8 service/state/API tests pass. Browser fixture verified autosave, duplicate submission (one job), V2 with previous feedback, fresh unreviewed state, and historical timecode navigation to read-only V1.
- FilmCraft pinned binary built/reopened a native two-cut project and exported H264/AAC: 640×360, 25 fps, exactly 50 decoded frames. Full decode passed. First visual inspection exposed text alignment; the adapter was corrected to center its text.
- Resolve Studio 21.1.1 connected and built source-native linked cuts and Fusion Text+. Native H264/AAC export and caption-color revision: 640×360, 25 fps, exactly 50 decoded frames. Full decode and sampled visible-text inspection passed. Testing corrected the Fusion render clock for trimmed sources and switched input validation to native readback. Fusion graph exports are now included in state fingerprints.
- Packaged Premiere integration installs dependencies and compiles. Runtime dependency audit is clean after lockfile-only SDK/transitive updates. Installed live host responded to read-only snapshot; its production project was left untouched.
- Canonical exported Python files parse. Distribution secret-pattern/hash scan passes.

Remaining before pilot:
- Test both agent runners end to end; permissions currently stop unattended work that needs an interactive decision.
- Complete automatic finishing orchestration and native revisions; add robust complete native-state preconditions, including stable inspection across save/reopen.
- Remove/replace remaining optional legacy path references; provide brand profiles, licensed fonts/music/templates separately.
- Prove a dedicated Premiere toolkit fixture; do not use the currently open production project.
- Real monologue/Q&A/multicamera footage, played speech joins, complex framing/music and human editorial review across all three backends.
- Clean Mac installation, disconnected host/missing media/render failure recovery, authenticated Drive verification, brain-update isolation, reference benchmarks.

Use docs/ACCEPTANCE.md as the release gate. The repository is a development handoff, not a claim that the full requested plan is complete.

GitHub Actions: the authenticated OAuth token cannot write workflow files. The CI definition is preserved as `docs/ci-workflow.yml`; an authorized repository maintainer can install it under `.github/workflows/`. No account permissions were changed.
