# Premiere Agent: connection and stage routing

This is the default for every canonical skill that accesses Premiere. The local MCP
registration is `premiere-pro`; its implementation identifies as `premiere-agent-lab`.
The panel is still named **Premiere Agent Lab**. Those names describe the same new
connector. The old **MCP Bridge** panel and direct mailbox scripts are retired.
Do not reinstall the npm connector or start the old panel to recover a task.

## Start every native stage here

```bash
python3 __ACQ_SKILLS__/edit/scripts/premiere_agent.py doctor
python3 __ACQ_SKILLS__/edit/scripts/premiere_agent.py tools
python3 __ACQ_SKILLS__/edit/scripts/premiere_agent.py inspect ping
python3 __ACQ_SKILLS__/edit/scripts/premiere_agent.py inspect lab_snapshot
```

`doctor` reads local configuration; `tools` works without Premiere. The two inspections
check the running host and current exact project/sequence. Run them serially. A missing
MCP tool in an older chat is a discovery issue, not evidence that the bridge is broken:
use this CLI immediately. Future Codex/Claude MCP sessions use the same default profile.
The profile is `~/.config/premiere-agent/default.json`; explicit `--profile` or
`PREMIERE_AGENT_PROFILE` overrides it. Stage runners' `--bridge-profile` is optional.
The install lives behind `~/.local/share/premiere-agent/current`; do not guess an old
session folder. Preserve the configured Node executable and source path.

If tools works but ping/snapshot fails, inspect heartbeat age, panel and current project.
Premiere must be running with a project and the Lab panel running. A fresh heartbeat alone
does not prove requests work. Report the actual failure (missing profile, missing executable,
stale panel, no project, target mismatch, lease conflict, or unknown original job).
Never switch projects, restart Premiere with unsaved work, steal ownership or replay a
mutation as a connection test. Setup/recovery UI is subject to the task's authorization;
editing remains through the API. No private binary patching or headless-host promise.

## Discover the useful capability before editing

```bash
python3 __ACQ_SKILLS__/edit/scripts/premiere_agent.py search 'reframe'
python3 __ACQ_SKILLS__/edit/scripts/premiere_agent.py schema lab_apply_reframe_motion
```

`schema` is the installed tool schema; `search` reports backend, host eligibility and
recorded evidence. Use stage drivers below rather than inventing ad hoc scripts.
`references/premiere_capabilities.json` is an offline snapshot; a frozen count is never
proof that the currently selected connector has or accepts a tool. Inspect capability
limits before proposing the effect; UXP, arbitrary QE, masks/tracking, native subtitle
editing and SDK access are not generally accepted production routes.

| Stage owner | Use the advanced route for | Entry point |
| --- | --- | --- |
| assembly-design | Exact compiled source-word assembly, native AV link checks, independently planned sample-precise audio seams | `assembly-design/scripts/apply_native_assembly.py` and its `--audio-plan`; [audio precision](../../assembly-design/references/audio-precision.md) |
| horizontal-to-vertical | Camera-aware shot preparation, intended-face ROI, sparse item-local Motion, flat embedded panels and native frame QA | `horizontal-to-vertical/scripts/premiere_native_reframe.py`; [advanced reframe](../../horizontal-to-vertical/references/advanced-native-reframe.md) |
| caption-clips | Editable Graphics with semantic-card identity, exact reveals/layout boundaries and scoped revision as a separate sequence | `caption-clips/scripts/apply_native_captions.py`; [native transfer](../../caption-clips/references/native_bridge_transfer.md) |
| music | Auditioned source section, exact native placement, calibrated gain/envelope and full-mix audibility | `music/scripts/apply_native_music.py`; [native music](../../music/references/native_music_bridge.md) |
| edit export | Fresh target/range, exact ticks, preserved marks, decoded output QA | [exact native export](native-export.md) |

Other skills keep their own creative scope and delegate these stages. Inspection-only
skills do not gain editing authority from this table. Advanced tools execute editorial
choices; they do not substitute for hearing seams, reviewing framing, choosing semantic
cards or auditioning music. Record which tool was useful, or the specific reason it did
not fit the clip, in the existing stage ledger—no new editorial approval worksheet.

## Exact project scope for authorized editing

The default `scoped-edit` profile permits the listed stage tools only with a short-lived
exact-project lease. This is mechanical preparation within the user's editing request,
not another approval prompt. Coordinate the single writer first. For a read-only task,
do not create a scope. Research uses explicit `lab.json` and disposable fixtures.

Write `inputs.json` as an array of exact absolute input files: sources, prepared projects,
compiler XML/expected/resolved/compiled/design artifacts and referenced word transcripts.
Include every transitive assembly input. Use existing job paths; do not copy production
projects into fixtures or widen the fixture root. Create the job's work/output directory.

```bash
python3 __ACQ_SKILLS__/edit/scripts/premiere_agent.py scope \
  --project '<exact-open-project.prproj>' --owner '<current-chat-id>' \
  --inputs '<job>/10_WORK/inputs.json' --write-root '<job>/10_WORK' \
  --stages assembly reframe captions music export --hours 4 --ownership-confirmed
```

Select only stages authorized for this task. The command checks the current project,
refuses another live owner's lease or unresolved writer lock, and performs no host edit.
Never assert `--ownership-confirmed` without coordinating and confirming the retired
bridge stopped. A changed input set needs an updated same-owner scope; unsupported
operations need implementation/testing, never broader authority or raw-script fallback.
A stage scope allows execution; it is not blanket host acceptance of new arguments.

Mutations use the owning runner or `premiere_agent.py execute --plan <operation.json>
--receipt <new-receipt.json>` with the shared `edit.native-operation/v1` contract.
Long operations remain on the original job ID. Inspect original jobs with
`inspect lab_get_job --args <job-id-arguments.json>`. Never retry an uncertain command,
clear its lock, or switch backend based on a timeout. Read the
[execution contract](premiere_execution_contract.md) for evidence and recovery.

After the owned stage settles, run `premiere_agent.py release --owner '<current-chat-id>'`
and report the project/sequence left open. It expires only your lease/scope, refuses
an active or unresolved writer, and does not close or change the project.
