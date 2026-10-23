# Read-only editorial guidance and version pinning

The toolkit calls the existing `find-precedents` reader and its restricted `editorial-search` function token. It does not create a Supabase client with database write privileges, deploy functions, change policies, publish team feedback or update the shared brain. Maddex's publication workflow remains separate.

Configure `brainConfig` during setup to the teammate's external configuration directory containing `context.json` and a user-owned mode-0600 `read_token`. The context file supplies `function_url` and `project_ref`; use the actual restricted configuration shared separately, never a database service-role key. The toolkit requires this directory explicitly and does not fall back to a developer's global brain configuration. An `EDITORIAL_BRAIN_READ_KEY` supplied through the existing local credential environment remains supported by the owning reader. No credentials are written into project receipts or Git.

Before **new editorial design**, prepare a project-owned request:

```json
{
  "format": "monologue",
  "problem": "Preserve the complete source payoff while removing repetition",
  "output": "/absolute/project/10_WORK/jobs/JOB_ID/guidance-1"
}
```

Then run:

```sh
node dist/cli.js brain PROJECT_ID /absolute/project/10_WORK/brain-request.json
```

Other supported formats are `q_and_a`, `podcast` and `story`. Optional fields are `projectPrefix`, `heldOut`, `readingOverlays`, `brand`, `productionType` and `stage`, using the canonical owner's scope/overlay rules. Use the actual content-unit classification. The command always requests required reading and excludes development cards by default. It does not infer a brand from the local workstation.

The owner validates the live response, body hashes, source exclusions, card evidence and mandatory reading. Scoped guidance retains its canonical additive behavior: if unavailable, record the limitation rather than inventing policy or silently changing the core reading rules. Requests use the existing function's custom authentication; current [Supabase authentication documentation](https://supabase.com/docs/guides/functions/auth) is not a reason to replace this credential with a privileged platform key.

Each successful request writes a new directory containing:

- `request.json`: the project and requested editorial scope.
- `context.json`: the complete validated guidance and canonical timestamp/response-hash receipt.
- `versions.json`: playbook versions/hashes, required-reading policy/document identities and hashes, card revisions/evidence labels, and scoped policy versions.

Files are made read-only after success. Reusing a destination is refused before a network call. An unsuccessful fetch retains a failure record and any partial evidence; there is no automatic cached-context fallback for new design. Inspect partial attempts and issue a new request to a new directory when appropriate. Killing a client cannot certify the outcome of its remote request, but this endpoint is a reader and the toolkit does not retry it automatically.

Use the returned `receiptPath`, `sha256`, `versionsPath` and `versionsSha256` in the native plan's `brain` object. The canonical Assembly Design `brain_preflight` must refer to that same context receipt. Read the returned guidance before designing; a successful fetch does not prove reading or application.

## Existing versions remain pinned

Saved-plan validation verifies the saved response hash, required reading and content hashes **offline**. It does not refresh guidance while rendering or revising a previously designed clip. Production render receipts include a compact `brainEvidence` version summary, which is archived by publication. The full context stays in the project's original work directory, pinned by the immutable plan's hash.

A new retrieval creates another receipt and records a `brain.retrieved` event; it does not rewrite any plan, media, review decision or earlier context. New moment selection and spoken redesign fetch current guidance, while caption/color/music styling preserves the existing design's pinned guidance. Feedback remains local until Maddex separately chooses to publish a learning through the owner workflow.

## Evidence and remaining acceptance

Eight controlled transport/receipt tests use the actual packaged owner validators. They cover two different returned guidance revisions, unchanged earlier context/plan bytes, no-network validation of old receipts, refusal of overwrites and path escape, missing explicit configuration, corrupt saved content, unavailable-server behavior without a cached fallback, and a render receipt retaining its original guidance after a newer retrieval. Tokens are absent from saved artifacts. These tests simulate changed server guidance; they do not publish a real brain update.

A live toolkit CLI request on 2026-10-23 successfully retrieved two playbooks, two required-reading policies and five cards using the configured restricted reader token. Guidance content and private configuration remain outside Git. Existing read-only native fixture projects and production editors were not involved in that request.

This proves retrieval and provenance handling, not that an agent applies a new policy well or that a new clip improves. A controlled publication by Maddex, real new-design application, preserved human-approved versions and editorial review remain necessary for the full brain-update pilot scenario.
