# Claude worker setup

Desktop sign-in does not prove CLI sign-in. The toolkit checks the configured CLI
with `--version` and `auth status` before a build and again before worker dispatch.
Account output is discarded; reports never include email or tokens. The current
baseline is 2.1.251 because the teammate's selected model explicitly refused
2.1.195. Passing this baseline does not qualify every model or confirm generation credit.
See the [official CLI reference](https://code.claude.com/docs/en/cli-reference).

1. Run `acq-edit --engine filmcraft agent-check PROJECT_ID` (or premiere).
   If login is missing, guide the user through `claude auth login` using the actual
   configured executable. If an update is needed, use its supported update route
   and rerun the check. Preserve managed installation policy.
2. Open Claude interactively in the exact project root shown by `acq-edit projects`.
   The user accepts the folder-trust prompt. Trusting the installation folder alone
   does not trust newly created project folders. Never edit Claude's trust database.
3. In that interactive session, review `/permissions` for the commands this workflow
   needs. Use the exact toolkit Node and Python paths from configuration and simple
   commands. A narrow initial template is `Bash("<node>" "<toolkit>/dist/cli.js" help)`
   and `Bash("<python>" "<toolkit>/scripts/sample_render.py" --help)`; replace placeholders
   with actual paths and review the rule syntax in the installed Claude version.
   These are examples to review, not a silently installed allowlist. The smoke test
   prints its exact command strings in its result. Allow actual editing commands
   as needed through the normal user permission flow. Do not permit unrestricted
   Bash/Python, change managed settings, or use bypass-permissions.
4. Run `acq-edit --engine filmcraft agent-check PROJECT_ID --smoke`.
   This explicitly makes a small model request. It runs two help commands and writes
   one random proof file under `10_WORK/agent-checks/`. It uses the same project,
   configured CLI, and permission mode as the worker. No editor, footage, credentials
   or permissions are changed. A receipt records the result without raw account data.
   Both command evidence and the proof file must pass; an agent saying “success” is
   insufficient. It is a basic smoke check, not authorization for every future command.
5. Start the editing job. If a later command is denied, report that exact command
   and stop retrying variants. Let the user review it interactively, then resume
   through documented recovery. Do not fabricate an alternate profile or permissions.

Worker commands should use absolute paths, toolkit Python and one operation per
command. Avoid `cd &&`, shell variables, compound redirection and repeated attempts
at equivalent blocked commands. Prefer the `acq-edit helper` entry point; in a source
checkout use its configured Python directly. Register the clip UUID before designing
its selection, and preserve it through every plan and handoff.

An authentication/version preflight failure happens before agent dispatch and ends
as a failed job. Failures after an agent starts still require inspection/reconciliation,
including interrupted model sessions, since tool calls may have changed native state.
