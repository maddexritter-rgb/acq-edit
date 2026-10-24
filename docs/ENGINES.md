# Independent native backends

## FilmCraft

`install_engine.py filmcraft` checks out commit `71438c627b5cbcfb550526c3971f4d0037733c5c` and builds `filmcraft-cli` with Cargo's lockfile. The upstream workspace requires Rust 1.95 and its documented native build prerequisites. Only the CLI is used; no editing UI is required. The binary hash is included by doctor. The full upstream repository is not copied into Git here.

`python/filmcraft.py` performs native source import, frame-aligned linked AV cuts, text graphics, imported motion assets, inspection/reopen and export. Unequal speech/picture boundaries use the shared compiler and the canonical saved-project sample-geometry method, with native reopen, linked-pair and source-clock verification. See `NATIVE_ASSEMBLY.md`. Fixed crops and reviewed source-bound X curves use native Motion geometry through the shared framing contract; subject analysis/smoothing remain owned by the canonical framing helper. See `NATIVE_FRAMING.md`. Automatic orchestration of all finishing variants remains open; missing capabilities fail explicitly.

Source-linked music, dialogue/bed gain and fades are available through the explicit shared audio plan; see `NATIVE_AUDIO.md` for timing, measured behavior and limits. Music-gain revisions preserve existing automation and cuts.

Selected existing X curves can be revised through `tracking-framing` with a pinned previous plan and a protected native-data comparison. Caption-only revision operates on an inspected copy and changes explicit graphic properties. Native media/render checkpoints are always new files. Guarded source-word recuts build a new native project from freshly compiled cuts and dependent finishing plans; see `NATIVE_RECUTS.md`.

Assembly-bound camera panels construct independent native source sequences inside per-cut layout nests. The master retains one dialogue mix and separate captions/graphics. Fixed and source-bound tracked crops operate in each panel's coordinates. Native graph verification and caption-only preservation are implemented. `panel-framing` revisions use selected existing nests for crop/tracking/rectangle changes, with native save/reopen and full protected-project comparisons. Camera replacement/count/mode changes and Premiere implementation remain open. See `NATIVE_PANELS.md`.

Transparent Remotion assets use the shared media preflight and separate ordered video tracks with exact native placement readback. FilmCraft additionally supports guarded `graphic-replacement` for selected existing assets, preserving timeline effects/timing and other layers on a saved/reopened copy. Basic overlapping-asset construction and final native rendering were exercised in FilmCraft and Resolve; see `NATIVE_MOTION.md` for the format contract and Resolve reopen limitation.

Production FilmCraft body captions use the pinned caption-clips handoff and three native graphic layers, with owning-helper timing, shadows and motion. See `NATIVE_CAPTIONS.md` for preparation, explicit limitations and native revision evidence.

## Premiere Pro

`integrations/premiere-agent` snapshots the current Agent Lab implementation, CEP/UXP panels and source, with original MIT notice. `install_engine.py premiere` builds a separate ignored toolkit installation, generates a new local runtime/token, prepares the separately identified **ACQ Edit Agent** panel, and verifies actual MCP initialization/tool discovery. It does not overwrite an installed panel or global connector configuration.

For a clean Mac, copy `.local/premiere-agent/lab/packages/ACQEditAgentCEP` to the user's Adobe CEP extensions directory and open **ACQ Edit Agent** in Premiere. Configure the supported Adobe CEP debug setting if required by the host. The generated CEP ID is `com.acqedit.premiere.bridge`; the optional UXP package `ACQEditAgentUXP` uses `com.acqedit.premiere.uxp`. Both retain the original implementation and licenses. Only generated copies receive these identities; the source snapshot is unchanged.

The panel pins its mailbox to this checkout. UXP uses a new local token and port **17878**, separate from production Agent Lab's 17877. Choose another available dedicated port with `--premiere-port`; 17877 is refused. Port availability is checked during preparation, not reserved indefinitely. Browser storage keys are separate as well. If an ACQ Edit panel is already installed, coordinate its upgrade explicitly; the installer never replaces it or edits global MCP configuration. Preserve the prepared checkout at its installed path, since generated packages contain absolute runtime paths.

Preparation records package hashes in `.local/premiere-agent/lab/panel-preparation.json` and runtime resource hashes/tool discovery in `lab/runtime-preparation.json`. These receipts deliberately do not claim Adobe installation or host qualification. Startup discovery does not open or switch a project, dispatch an editor command, or authorize a mutation.

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

`python/resolve.py` directly imports source media, creates timelines, appends video/audio, checks exact source and record boundaries, links AV, sets native properties, creates native Fusion crop/resize and Text+ captions, imports motion graphics, saves DRP checkpoints and renders through Resolve. Native music uses an independent source track, read-back volume and fades. Music-gain revisions duplicate the timeline and preserve source cut ranges. See `NATIVE_AUDIO.md` for the measured fixture and picture-difference limitation. Fixed-framing revisions update owned static Fusion crop nodes on a duplicated timeline; see `NATIVE_FRAMING.md` for geometry and limits. Reviewed source-bound X tracking uses native Transform/XYPath/BezierSpline before the fixed crop, preserving subpixel movement with fixed Y/scale. `tracking-framing` revisions duplicate the timeline, update selected existing curves and verify all other inspected native data remains protected. Caption revisions duplicate the native timeline and change owned Fusion text nodes. Guarded source-word recuts build a separate native timeline and verify the published parent before and after construction; see `NATIVE_RECUTS.md`. Version-specific API changes are verified against the installed scripting documentation.

Native 21.1.1 testing established exclusive `endFrame` semantics for `AppendToTimeline`. The adapter checks actual durations and source offsets after each placement. Fractional source-audio trims use a version-gated native DRT construction/readback route on Studio 21.1.1 build 10; see `RESOLVE_PRECISION.md`. Variable/mixed frame rates, real multicamera synchronization and complex Fusion modifications still need qualification; do not label them supported because the frame-aligned fixture passes.

Assembly-bound camera panels use native Media Pool inputs, independent camera trims, fixed/tracked crops and Fusion Merge placement. The timeline retains its original dialogue and caption layers. Save/reopen and caption-only revision were exercised on synthetic moving-marker footage. Guarded `panel-framing` revisions update selected existing crops, curves and rectangles on a verified duplicate while protecting every other inspected field. Camera replacement/retiming, panel-count/mode changes and real-camera qualification remain open; see `NATIVE_PANELS.md`.

Production body captions use the same pinned caption-clips handoff as FilmCraft with an explicit Resolve typography/shadow/motion profile. Native Fusion nodes execute the cards, hold timing and arrival; no FilmCraft engine is installed or invoked. Planned revisions and exports verify graph inputs, clocks, exact fonts and cut geometry. See `NATIVE_CAPTIONS.md` for the supported fields, native build/revision evidence and open audio/real-footage qualifications.

The selected native project name is `ACQ_<project-id>`. The adapter refuses another open project. Create/open the dedicated project deliberately before execution. It never closes user work to make room for itself.

## Agent integrations

Codex uses the documented app-server protocol. Claude uses headless stream output and exact session resume. This build does not bypass interactive approvals. Configure permitted toolkit commands in each agent before unattended jobs. A request needing interactive permission is preserved with its exact job and log for reconciliation.
