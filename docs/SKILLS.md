# Use the whole editor or just one part

ACQ Edit includes individual agent skills. You can ask for only captions, only an assembly,
only reframing, or delivery of existing clips. The agent should do that job, not restart the
whole workflow. These are chat skills, not Bash aliases.

| What you want | Skill to select |
| --- | --- |
| Full editing workflow | `edit` |
| Choose a moment and design the cuts | `assembly-design` |
| Reframe an existing cut vertically | `horizontal-to-vertical` |
| Add or restyle captions | `caption-clips` |
| Choose and apply music | `music` |
| Send finished clips to Frame.io and Monday | `monday` |

Claude Code supports `/edit`, `/caption-clips`, and the other skill names. In Codex, use the
skill picker (search for the name) or explicitly mention `$edit`, `$caption-clips`, etc.;
the exact picker shortcut varies by client. Natural language also works, for example:
“Use caption-clips to caption this video. Keep the cuts and framing unchanged.”

## Agent setup instructions

Run these commands for the user; do not make them edit hidden folders or copy skill files.
Normal onboarding registers only the six public skills listed above. Claude Code defaults to
personal scope (`~/.claude/skills`) so they load when chats open in footage or project folders;
Codex defaults to the installed toolkit workspace. Explicit `--scope workspace` remains available. For a skills-only installation, no editor, Rust, Node build, API key or asset
download is required just to make the procedures selectable:

```sh
acq-edit skills install --agent codex
# Claude Code: replace codex with claude; both is supported.
acq-edit skills check --agent codex
acq-edit skills list
```

In a source checkout, use `python3 scripts/agent_skills.py` instead of `acq-edit skills`.
The command materializes and verifies the complete repository dependency chain, then links
only the six public owners (or a requested subset) into the selected discovery location:
workspace `.agents/skills` for Codex by default, personal `~/.claude/skills` for Claude Code. It does not copy
procedures into a second source of truth or use this machine's global editing helpers.
For workspace scope, open the toolkit folder. For Claude personal scope, use any local project.
Reopen the existing app session if the picker has not refreshed; never start another agent CLI.
Check the actual picker before claiming that discovery was accepted by the host.

For skills available in **all chats**, use the explicit personal scope:

```sh
acq-edit skills install --agent codex --scope user
# Or install only selected picker entries:
acq-edit skills install --agent claude --scope user --only caption-clips monday
```

Personal scope uses the agent's user skill folder. Existing user skills and symlink farms are
preserved. Conflicts are reported, never silently overwritten. On an upgrade, the agent may
run the same install with `--update-owned` to move only receipt-owned links to the new verified
release after verifying the old runtime has no changes. A changed/unverifiable runtime blocks
retargeting so local customizations are not silently bypassed. Old runtimes and their projects remain intact. Other public skills not selected remain
unchanged. Older toolkit-owned picker entries for
internal helpers are removed on registration, while their underlying runtime files stay intact.
User-modified or unowned entries are preserved and reported; they are never deleted.
If an old unreceipted link conflicts, report its path and resolve explicitly; do not delete it.

Only these six names are accepted by `--only`. Supporting owners such as watch, audits and
render remain internal dependencies loaded by the public workflow; they are not picker entries.

Registration is not proof of an editor, asset bundle, credentials, or rendered output. At first
use, resolve only the requested capability's missing dependencies from repository instructions:

- Captions → Use skill: caption-clips. Set up its selected native backend, fonts/profile and
  word timings as needed; preserve unrelated cuts, framing and music.
- Assembly → Use skill: assembly-design. Stop at the requested design/assembly, without
  adding captions, music or delivery unless requested.
- Reframing → Use skill: horizontal-to-vertical. Preserve the existing editorial selection.
- Music → Use skill: music. Load the approved asset bundle and the selected editor as needed.
- Delivery → Use skill: monday. Follow its own onboarding for Frame/Monday accounts and
  brand routes. Do not require FilmCraft/Premiere, AssemblyAI or Gemini to deliver existing files.

Keep the immutable project backend, source preservation, exact-project permissions, scoped
revisions, and explicit external-delivery authorization. Never resolve a missing capability by
calling a global/private helper or switching engines.

## Discovery references

- [Codex skill locations and symlink support](https://learn.chatgpt.com/docs/build-skills)
- [Claude Code skill locations and slash invocation](https://code.claude.com/docs/en/skills)

This is local Codex/Claude Code discovery. It does not install cloud/Cowork skills or bypass
organization policies that disable local skills.

## Claude picker troubleshooting

The agent runs `acq-edit skills check --agent claude --scope user` and confirms all six entries.
If registration is missing, install them with the same scope and `--update-owned`. Preserve
conflicting user skills; report their exact paths rather than replacing them. The user should
see `/edit`, `/assembly-design`, `/horizontal-to-vertical`, `/caption-clips`, `/music`, `/monday`.
Check the menu in the actual Claude Code session before claiming host discovery works.
If files pass but the menu is empty, inspect active Claude settings for hidden skills or managed
restrictions and confirm this is local Claude Code, not Cowork/cloud. Do not change policy or
hidden-skill preferences silently. Refresh/reopen the app session; no CLI login is needed.

Personal scope is local to that Mac; it does not install skills in cloud sessions.
