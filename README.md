# ACQ Edit

Edits use source-word storytelling, body captions, framing, music and requested graphics. Opening text headlines are not included.

A Mac-based editing toolkit for Codex and Claude Code. Give your agent footage and a brief. Review the resulting clips in a local browser, add timecoded feedback, and apply revisions without managing a timeline yourself.

**New-Mac preview.** FilmCraft and Premiere have produced real native caption proofs; clean-Mac installation and full team acceptance still require the new-machine test. Resolve work is paused. See [evidence and remaining work](docs/STATUS.md).

**Premiere uses ACQ Edit Agent MCP only.** An older installed Premiere bridge is not a
fallback. If the toolkit connection is unavailable, repair its setup and open the ACQ Edit
Agent panel. Do not use global Premiere MCP tools or another bridge for this workflow.

## Individual skills

Use the whole `edit` workflow or just `assembly-design`, `horizontal-to-vertical`,
`caption-clips`, `music`, or `monday`. Normal onboarding registers skills in the toolkit
project. Ask your agent to make them available in all chats, or install only selected skills.
[Skill picker setup and standalone workflows](docs/SKILLS.md) explain both options.

## Start here

Open this repo in Codex or Claude Code and say **“Help me get set up.”** Your agent will guide
you one step at a time, give you the account links, explain where to enter keys privately and
help troubleshoot through your first clip. For a Homebrew/Workbrew package, run
`acq-edit onboard guide` to find the installed folder to open. The agent instructions are in
[AGENTS.md](AGENTS.md), with a [Claude Code entrypoint](CLAUDE.md) and one shared
[onboarding guide](docs/ONBOARDING.md).

Use the [guided new-Mac onboarding](docs/ONBOARDING.md) for Homebrew or Workbrew, bundled
assets, personal credentials, editor setup and Frame/Monday delivery setup.

```sh
brew tap maddexritter-rgb/acq https://github.com/maddexritter-rgb/homebrew-acq.git
brew install maddexritter-rgb/acq/acq-edit
acq-edit onboard guide  # Open the shown folder in your agent and ask for setup
```

Use Workbrew's existing `brew` command when installed. No GitHub account is required for the public repository or release downloads.
No Anthropic/OpenAI API key or separate editorial-brain signup is required. The installer
fetches the versioned team assets and asks privately for AssemblyAI and Gemini keys.

See [installation verification and recovery](docs/INSTALLATION.md) for selected-engine prerequisite checks, repeat installs and retained partial installations.

Rerunning `setup` keeps existing values when you press Enter. It offers the selected integration's conventional install path, preserves advanced settings and retains a private copy of the previous configuration when changes are saved. Backend and agent choices are defaults for new projects; existing projects keep their identities. Stop the review service and finish or reconcile active work before changing setup.

`doctor` returns a JSON report with `readiness.ready`, blocking repair steps and optional intake dependencies. It exits 1 when a required prerequisite is missing, including before setup. It checks local brain configuration without retrieving guidance or printing keys. A ready result does not verify agent login/credit, API key validity or native editing quality.

Setup stores configuration and API keys under `~/.config/acq-edit`, outside the checkout. API key entry is hidden. Supply your own AssemblyAI and Gemini keys. The team asset release supplies the restricted editorial-brain reader configuration automatically. No database service-role key belongs on a teammate's machine.

```sh
node dist/cli.js project "Workshop short clips"
node dist/cli.js source PROJECT_ID /absolute/path/recording.mp4
# Alternatives:
node dist/cli.js youtube PROJECT_ID https://www.youtube.com/watch?v=VIDEO_ID
node dist/cli.js drive PROJECT_ID https://drive.google.com/file/d/FILE_ID/view drive
node dist/cli.js drive-folder PROJECT_ID https://drive.google.com/drive/folders/FOLDER_ID drive
node dist/cli.js build PROJECT_ID "Design three complete, useful short clips."
node dist/cli.js serve
```

Open the authenticated loopback URL printed by `serve`. The worker runs the project's selected agent. Missing permissions or uncertain native outcomes stop the job with recoverable evidence. Do not treat an agent's completion message as a successful render.

Use `serve --no-worker` to review without dispatching jobs. `projects` lists persisted projects; `open PROJECT_ID` re-exports its state. The next `serve` session reopens the same projects, versions, and feedback.

## What stays constant

- One backend per project: FilmCraft, Premiere, or Resolve. No hidden conversion or fallback to another editor.
- Assembly Design owns word selection and story construction; native adapters execute the design. [Compile exact source-word and paired-audio plans](docs/NATIVE_ASSEMBLY.md) before native construction.
- FilmCraft body captions use the [pinned caption-clips handoff](docs/NATIVE_CAPTIONS.md), with native text, two shadow layers, profile-selected motion and saved-project verification.
- `00_SOURCE` contains verified, project-owned copies. Work goes into `10_WORK`; published immutable renders go into `20_DELIVER`.
- Feedback is bound to an exact version. Applying revisions captures that version and its notes. Later notes stay separate. Changed clips return unreviewed.
- The [shared brain](docs/EDITORIAL_BRAIN.md) is read-only here. New design fetches current guidance with `brain PROJECT_ID REQUEST.json` and records its versions; approved edits do not change when guidance changes.
- [Source intake and recovery](docs/INTAKE.md) retains verified footage and tracks interrupted transfers.
- Remotion produces graphic assets. Final composition and export happen in the chosen editor.

## Development

```sh
npm test
npm run audit:distribution
python3 -m unittest discover -s tests -p '*_test.py'
```

[Architecture](docs/ARCHITECTURE.md) · [Agent workflow](docs/AGENT_WORKFLOW.md) · [Engine setup](docs/ENGINES.md) · [Acceptance matrix](docs/ACCEPTANCE.md) · [Third-party notices](THIRD_PARTY_NOTICES.md)

`distribution/SOURCE_MANIFEST.json` records canonical source hashes, distribution hashes, and explicit portability transformations. `PORTABILITY_REPORT.json` records excluded assets and unresolved optional references. Canonical source and older repositories are never modified by this toolkit.

[The dependency inventory](docs/SKILL_DEPENDENCIES.md) covers 38 packaged owners and explicitly classified external routes. Installation and distribution audits reject unknown missing skill dependencies or stale inventory records.
