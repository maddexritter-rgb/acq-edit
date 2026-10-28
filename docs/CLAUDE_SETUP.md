# Optional Claude background worker

Normal onboarding and editing run in the user's existing chat. They do not require
a second CLI, another login, folder-trust ceremony, saved “don't ask again” approvals,
or a paid agent smoke test. Use the session workflow in [AGENT_WORKFLOW.md](AGENT_WORKFLOW.md).
Do not open extra terminal agent sessions or wait for permission rules to appear.
Never change trust databases, install permission rules, or bypass managed restrictions.
A normal user approval for a specific command is sufficient for that command; it does
not need to become a permanent rule before the current chat can continue.

Only follow the steps below when the user explicitly requests **unattended background
editing**. Desktop authentication does not prove that the separate CLI is signed in.

1. Run `acq-edit --engine filmcraft agent-check PROJECT_ID` (or premiere).
   This checks the configured CLI version and authentication without a model request.
   The supported baseline is 2.1.251; it does not prove model access or generation credit.
2. If the CLI is unavailable or not authenticated, explain that this optional mode needs
   separate setup. Continue in the current chat unless the user wants to configure it.
   Guide an explicitly requested login through the installed CLI's supported auth flow.
3. If requested, run `agent-check PROJECT_ID --smoke`. This makes a small model request,
   executes two help commands and writes a random proof file. It cannot authorize future
   editing commands and is never a prerequisite for current-chat editing.
4. Submit `build PROJECT_ID --background REQUEST`, then use `serve --worker` or `worker`.
   Respect existing permissions. If a command is denied or the worker needs interactive
   input, report the exact blocker once and stop. Do not loop asking users to select
   “don't ask again,” approve broad Node/Python rules, or rerun equivalent shell variants.

Background jobs keep their original execution mode and frozen notes. Never silently
convert an active or historical worker job into a session job. After interruption, inspect
native state and reconcile using [NATIVE_RECOVERY.md](NATIVE_RECOVERY.md). Preserve receipts
and previous versions before starting a separate current-chat request.

Official CLI details: [Claude CLI reference](https://code.claude.com/docs/en/cli-reference).
