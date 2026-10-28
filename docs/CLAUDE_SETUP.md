# Use the existing Claude Code chat

ACQ Edit does not require another Claude CLI, another agent login, or terminal setup.
Stay in the signed-in chat the user already has open. Read [ONBOARDING.md](ONBOARDING.md)
and follow [AGENT_WORKFLOW.md](AGENT_WORKFLOW.md). The agent executes internal toolkit
commands; the user describes edits, chooses the editor, connects services in the browser,
and reviews the results. Do not ask the user to type commands or save broad permission rules.
Normal permission prompts from the host still apply; do not bypass them.

The former separate-agent background mode is removed, including its auth checks and
model smoke tests. Do not offer it as an optional setup or work around the disabled entrypoints.
FilmCraft review requests return to the existing chat; the room does not launch another agent.

Historical jobs, notes and evidence remain intact. Inspect and reconcile interrupted work
using [NATIVE_RECOVERY.md](NATIVE_RECOVERY.md); do not silently convert or replay old jobs.
