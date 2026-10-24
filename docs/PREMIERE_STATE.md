# Premiere project creation and reopening

The toolkit has a dedicated lifecycle route through the isolated Agent Lab integration. It creates a new native `.prproj` or reopens an exact saved project from an empty Premiere workspace. If the intended project is already active, reopening verifies it without switching, saving or changing it. An unrelated or unsaved open project is preserved and stops lifecycle mutation.

**Licensed-host acceptance is pending.** The TypeScript service, generated host script and Python adapter have simulated failure tests. A fresh installation discovers the new MCP endpoints. This does not prove actual `app.projects`, project creation, reopening, persistence or rendering in the installed Premiere host.

## Create a project

After normal toolkit project creation and isolated panel setup, save this packet under that project's `10_WORK` and run:

```sh
node dist/cli.js native PROJECT_ID open /absolute/project/10_WORK/create-native.json
```

```json
{
  "mode": "create",
  "nativeProject": "/absolute/project/10_WORK/native/edit.prproj",
  "receipt": "/absolute/project/10_WORK/lifecycle/create.json",
  "ownershipConfirmed": true
}
```

`ownershipConfirmed` records the caller's actual coordination of exclusive Premiere ownership. Do not set it merely to get past a refusal. It is not editorial approval or proof that another writer has stopped. Existing unexpired Lab stage leases must be released through their owning workflow first. The lifecycle route does not expire or replace them automatically.

The target must be a new `.prproj` inside this project's `10_WORK`. Original project files are never overwritten. The receipt must also be new. All open projects must be closed by their owner before a lifecycle mutation; the toolkit will not close an unrelated or unsaved document for them.

The successful response includes `inspection.reopen` and explicitly requires a subsequent ordinary editing-stage scope. Creating a project does not authorize assembly, captions, framing, music or export. Use the existing canonical scope and stage owners once the project is open.

## Reopen a saved version

A normal native `inspect` now returns saved-file SHA-256 plus a `reopen` object containing the native path, sequence identity and full inspected-state fingerprint. Save the owned project before capturing a durable reopening target; an unsaved snapshot is not reproducible from older saved bytes.

Render receipts also carry this identity, bound to the archived native inspection hash. Publication preserves it in `Version.nativeReopen`, and revision submissions freeze that exact metadata beside the submitted version and feedback. For a published version, use that version's `nativeReopen` object. Do not invent or substitute a fingerprint after a mismatch.

```json
{
  "mode": "open",
  "nativeProject": "/absolute/project/10_WORK/native/edit.prproj",
  "receipt": "/absolute/project/10_WORK/lifecycle/reopen-02.json",
  "ownershipConfirmed": true,
  "reopen": {
    "schema": "acq-edit/premiere-reopen-v1",
    "nativeProject": "/absolute/project/10_WORK/native/edit.prproj",
    "nativeSha256": "<saved project SHA-256 from inspection/version>",
    "expectedFingerprint": "<complete native state fingerprint>",
    "sequenceId": "<exact sequence ID, or null for an empty project>"
  }
}
```

Use JSON `null`, not the placeholder string, for an actual empty project's sequence. Published metadata additionally includes `inspectionSha256`; retain it when copying the version's metadata.

Before opening, the adapter checks the saved bytes. After opening, it requires the original complete snapshot fingerprint and sequence identity. Reopening does not save the project. If the target is already active, the adapter performs those checks read-only, including any unsaved changes. A stale saved file or changed current timeline stops the operation while preserving the user's work.

This route reopens the original working path. It does not silently restore an archived checkpoint over a changed working file, clone an old version to another path, or switch between unrelated open projects. Those operations need their own native state-preservation contracts. A mismatch remains a specific repair task, never permission to rebuild an approved clip or change editors.

## Authority, serialization and recovery

`lab_inspect_toolkit_workspace` reads open-project identities and a workspace revision. `lab_toolkit_project` is a separate typed lifecycle endpoint, not an escape hatch into the general `create_project`, `open_project`, `close_project` or Save As tools. Those general operations remain blocked.

The adapter creates an exclusive, five-minute scope at `lab/runtime/toolkit-scopes/<operation-id>.json`. It pins the toolkit `project.json` hash, backend, project root, exact target, workspace revision, requested mode and saved bytes when opening. Scope files and receipts remain for diagnosis. The server independently checks the scope, current disk state, edit/filesystem authority and existing stage leases.

The service shares `writer.lock` and the durable operations directory with ordinary Lab edits. It rechecks workspace and disk state under that lock, writes the running journal before dispatch, then checks workspace identity and saved bytes after the host responds. The generated native script independently checks the host version, empty workspace, target existence and scope deadline immediately before creation/opening. A delayed queued command cannot start after the scope expires. Reusing an operation ID returns its original journal and never repeats the native action.

A failed or lost response after dispatch leaves the operation `unknown` and retains the Lab writer lock. The outer toolkit native operation also requires reconciliation. Original media, prior versions, feedback, scope and host receipts remain intact. Do not remove the lock or resend the request because a timeout elapsed. A dedicated lifecycle reconciliation command is still outstanding; host/process inspection and explicit repair are required before proceeding. `native-reconcile` alone does not clear the Lab lock or establish what happened in Premiere.

## Verification

Run the shared Python/service tests normally. The explicit integration tests additionally require the packaged Lab to be compiled:

```sh
integrations/premiere-agent/node_modules/.bin/tsc -p integrations/premiere-agent
node --test tests/premiere_lifecycle_test.mjs
```

The 17 integration cases exercise exact create/open dispatch, durable duplicate handling, occupied workspaces, unknown outcomes, stale/expired scope, changed manifests/files, active leases, symlink targets, in-host preconditions, deadline expiry and inspect-only authority. Eight Python session cases cover receipt/scope preservation, reopening, an already active target, unrelated workspaces, missing ownership, saved/unsaved changes and post-open mismatch. Publication tests verify both supported engines' frozen reopening metadata across a database restart and reject mismatched Premiere inspection/path/file/sequence pins.

These tests use simulated host responses and test-generated native bytes. The native project API and empty-workspace behavior still require a real isolated panel/project fixture. Human review and complete native editing/rendering acceptance remain separate release gates.
