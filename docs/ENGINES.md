# Independent native backends

## FilmCraft

`install_engine.py filmcraft` checks out commit `71438c627b5cbcfb550526c3971f4d0037733c5c` and builds `filmcraft-cli` with Cargo's lockfile. The upstream workspace requires Rust 1.95 and its documented native build prerequisites. Only the CLI is used; no editing UI is required. The binary hash is included by doctor. The full upstream repository is not copied into Git here.

`python/filmcraft.py` performs native source import, frame-aligned linked AV cuts, text graphics, imported motion assets, inspection/reopen and export. Unequal speech/picture boundaries use the shared compiler and the canonical saved-project sample-geometry method, with native reopen, linked-pair and source-clock verification. See `NATIVE_ASSEMBLY.md`. Fixed-crop plans use native Motion geometry through the shared framing contract; tracking continues to use the canonical FilmCraft helper. See `NATIVE_FRAMING.md`. Automatic orchestration of all finishing variants remains open; missing capabilities fail explicitly.

Source-linked music, dialogue/bed gain and fades are available through the explicit shared audio plan; see `NATIVE_AUDIO.md` for timing, measured behavior and limits. Music-gain revisions preserve existing automation and cuts.

Caption-only revision operates on an inspected copy and changes explicit graphic properties. Native media/render checkpoints are always new files.

Transparent Remotion assets use the shared media preflight and separate ordered video tracks with exact native placement readback. Basic overlapping-asset construction and final native rendering were exercised in FilmCraft and Resolve; see `NATIVE_MOTION.md` for the format contract and Resolve reopen limitation.

## Premiere Pro

`integrations/premiere-agent` snapshots the current Agent Lab implementation, CEP/UXP panels and source, with original MIT notice. `install_engine.py premiere` builds a separate ignored toolkit installation, generates a new local runtime/token, and prepares the panel. It does not overwrite an installed panel or global connector configuration.

For a clean Mac, copy the generated `PremiereAgentLabCEP` directory to the user's Adobe CEP extensions directory and open **Premiere Agent Lab** in Premiere. Configure the supported Adobe CEP debug setting if required by the host. If the same panel ID is already installed, coordinate a deliberate installation change first; never replace a working production panel implicitly.

The generated toolkit profile uses canonical `precision_bridge.mjs` and the packaged Lab. Add that profile's command/arguments to the selected agent's MCP configuration if desired. The CLI fallback always works through the same profile:

```sh
python3 .local/skills/edit/scripts/premiere_agent.py --profile .local/premiere-profile.json doctor
python3 .local/skills/edit/scripts/premiere_agent.py --profile .local/premiere-profile.json tools
python3 .local/skills/edit/scripts/premiere_agent.py --profile .local/premiere-profile.json inspect ping
```

Before mutation, use the canonical exact-project scope command with explicit inputs, write root, owner and stages. Verify the open project and coordinate the exclusive lease. Stage runners remain the owners of native assembly, reframe, Graphics captions, music and exact-range export. `python/premiere.py` executes only scoped stage packets; it cannot widen privileges or switch projects.

The native `render` action now accepts a guarded save plus typed exact-range export, checks restored marks and unchanged native state, verifies the actual rendered file and emits the shared publication receipt. See `PREMIERE_RENDER.md` for the packet and current full-clip sequence contract. Adapter failure-boundary tests pass; live toolkit export qualification remains pending.

A live production project was open during development. Read-only connectivity was checked; no toolkit mutation was submitted to it. A dedicated new-toolkit Premiere native fixture remains required.

## DaVinci Resolve Studio

Install Studio 21.1 and enable **Preferences → System → General → External scripting: Local**. The bundled `ResolvePython` interpreter is used; no Premiere, FilmCraft, XML conversion or foreign project is required.

`python/resolve.py` directly imports source media, creates timelines, appends video/audio, checks exact source and record boundaries, links AV, sets native properties, creates native Fusion crop/resize and Text+ captions, imports motion graphics, saves DRP checkpoints and renders through Resolve. Native music uses an independent source track, read-back volume and fades. Music-gain revisions duplicate the timeline and preserve source cut ranges. See `NATIVE_AUDIO.md` for the measured fixture and picture-difference limitation. Fixed-framing revisions update owned static Fusion crop nodes on a duplicated timeline; see `NATIVE_FRAMING.md` for geometry and limits. Caption revisions duplicate the native timeline and change owned Fusion text nodes. Version-specific API changes are verified against the installed scripting documentation.

Native 21.1.1 testing established exclusive `endFrame` semantics for `AppendToTimeline`. The adapter checks actual durations and source offsets after each placement. Fractional source-audio trims use a version-gated native DRT construction/readback route on Studio 21.1.1 build 10; see `RESOLVE_PRECISION.md`. Variable/mixed frame rates, multicamera layouts and complex Fusion modifications still need qualification; do not label them supported because the frame-aligned fixture passes.

The selected native project name is `ACQ_<project-id>`. The adapter refuses another open project. Create/open the dedicated project deliberately before execution. It never closes user work to make room for itself.

## Agent integrations

Codex uses the documented app-server protocol. Claude uses headless stream output and exact session resume. This build does not bypass interactive approvals. Configure permitted toolkit commands in each agent before unattended jobs. A request needing interactive permission is preserved with its exact job and log for reconciliation.
