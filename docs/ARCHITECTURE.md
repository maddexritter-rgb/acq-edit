# Architecture

The TypeScript service owns durable coordination and review state. Python adapters own native execution. Packaged canonical skills own editorial decisions.

```text
Local / YouTube / authenticated Drive
                 │
          verified source copies
                 │
       transcription + source evidence
                 │
        live read-only brain guidance
                 │
       Assembly Design + precise boundaries
                 │
          project.backend (fixed)
        ┌────────┼──────────┐
    FilmCraft  Premiere   Resolve Studio
    headless   Agent Lab  scripting + Fusion
        └────────┼──────────┘
         verified native render
                 │
       immutable version + review room
                 │
     version-bound notes → Apply revisions
                 │
        durable per-project job queue
```

SQLite uses WAL, foreign keys, immediate transactions, a unique submission fingerprint, and a partial unique index for active project mutation jobs. Feedback updates use optimistic revisions, so a stale browser cannot silently erase another tab's changes. JSON exports are serialized per project and atomically replaced.

Applying a revision stores the exact old version and feedback as the job snapshot. Job execution never rereads a mutable text field as the original request. A later submission against an obsolete version fails before execution. An uncertain agent/native operation blocks further project mutations until reconciliation. Old media is never overwritten.

Publication records the exact job ID. In the same SQLite transaction it compares the submitted feedback with the latest saved feedback and preserves any changes as pending feedback tied to the source version. The next submission includes both the original request and the updated notes, so edits and withdrawals are explicit. Pending entries are consumed only when a version for that exact submission is published. Decisions do not carry forward.

Completion requires every selected clip and parent version, exact job attribution, and verified immutable media/native-checkpoint hashes. A partial batch remains in reconciliation; successful clips and pending notes remain available. Reconciliation to ready requires an actual project-owned result JSON containing the job ID and all published version IDs, followed by the same artifact verification.

Media endpoints resolve only database-registered files inside the associated project and support byte ranges. The server binds to 127.0.0.1, validates Host and Origin, and requires a random per-session HttpOnly SameSite cookie. It serves no arbitrary filesystem paths. It is not a remotely hosted collaborative service.

Contracts are in `src/contracts.ts`. Native plans use integer picture frames and audio samples with rational frame rates. The current production path still requires canonical source-word selection, paired-cut evidence and brain receipts. See engine limitations before passing a plan to an adapter.

Native state fingerprints are preconditions, not proof that every unexposed effect is captured. Resolve's snapshot records timing, properties, source paths, enabled/locked states, markers and parsed Fusion-graph hashes. Same-timeline save/reopen and deliberate-edit detection passed on the qualified host; see `RESOLVE_STATE.md` for the narrow normalization and remaining coverage. A project DRP or fcproj checkpoint does not by itself prove a rendered effect.

Agent execution uses Codex app-server stdio JSON-RPC and Claude Code headless stream JSON. Sessions are recorded by exact ID, and completion is matched to the exact Codex turn or Claude result. Process termination and log flushing finish before the worker releases ownership. The HTTP service and standalone worker share the same service lock. Interactive requests are surfaced as reconciliation rather than granting broad unattended permissions. Agent CLI policies must be configured by the operator for approved toolkit commands.

References: [Codex app-server](https://learn.chatgpt.com/docs/app-server), [Claude Code headless](https://code.claude.com/docs/en/headless).
