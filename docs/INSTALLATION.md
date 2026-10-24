# Installation and portable runtime verification

Use a fresh checkout for a teammate installation or an upgrade. Keep existing projects and credentials in their configured external locations. The installer does not migrate project state or install global agent skills.

Resume saved review state with `acq-edit open PROJECT_ID`, then `acq-edit serve`. Resolve's explicit native reopening uses a prior inspection's identity/fingerprint packet; follow [RESOLVE_STATE.md](RESOLVE_STATE.md). Keep the existing native project database available. Review exports and DRP checkpoints alone do not silently replace a missing or manually changed native project.

The shared installer currently uses the `python3.11` executable. Install Node.js 24+, Python 3.11 and FFmpeg/ffprobe first, plus the selected agent CLI. YouTube and Drive intake additionally require `yt-dlp` and `rclone`; Drive authentication belongs to the teammate. Editor licenses, assets and agent authentication are separate setup steps.

Run the read-only prerequisite check for the selected engine before installation:

```sh
python3 scripts/install_engine.py resolve --check
# Or: premiere --check / filmcraft --check
```

Resolve checks for its bundled interpreter and shared executables. It does not require Cargo, Premiere or FilmCraft. Premiere adds npm. On macOS, FilmCraft adds Git, Cargo, Rust 1.95+ and Xcode Command Line Tools; preflight asks `xcrun` for a real compiler and macOS SDK. It does not require Linux's `pkg-config` prerequisite on a Mac. This follows [the pinned upstream build instructions](https://github.com/storytold/filmcraft/blob/71438c627b5cbcfb550526c3971f4d0037733c5c/docs/contributing.md). These checks do not prove all native libraries are linkable, that an editor is running/configured, or that an agent is authenticated. Continue with the README setup and `doctor`, then the acceptance workflow.

After a successful pinned FilmCraft build, the installer checks that tracked sources remain clean and that the executable can run `--help`. It creates a new immutable `.local/filmcraft-builds/<id>.json` receipt containing the source commit/origin, Cargo manifest/lockfile hashes, build command, Rust/Cargo versions, Apple tool paths, host architecture, selected build environment values, installer hash and executable size/hash. Repeat builds retain their earlier receipts. These are actual build inputs and outputs, not a claim of byte-identical reproducibility across hosts or native editing acceptance. System fonts and optional build inputs still require their own portable configuration.

## Verified materialization

Premiere installation also packages the four Python helpers used by native assembly, mixed-source master validation and camera coverage. The three compiler consumers resolve only the verified `.local/skills/edit/scripts` runtime. Their original and distribution hashes remain separate in the integration manifests. Setup checks these hashes, imports every helper and the actual compiler, then records helper hashes beside MCP discovery results. It never falls back to a global skill tree. Changed helpers or local skills are preserved and rejected. The source snapshot command retains reviewed dependency patches and refuses changed upstream inputs before writing.

The generated scoped profile now writes `lab/runtime/edit-project-authorization.json`, matching the Lab runtime and Python validators. Older profiles using `edit-authorization.json` are not repaired automatically; use a fresh installation. Setup excludes old `dist`, `node_modules` and bytecode directories before rebuilding.

The adapter now accepts only this checkout's `.local/premiere-profile.json`, with the exact installed command, working directory, fixture root, scope filename, connector and host version. It verifies the skill runtime before importing the bridge, then checks the Python helpers, compiled JavaScript/JSON files and prepared panel packages against installation receipts. Redirected paths, the production port, altered packages and old receipts are refused before launching a connector. Existing files remain untouched. Runtime receipts now use `acq-edit/premiere-runtime-v2`; use a fresh installation to adopt them.

Premiere `doctor` runs only the connection probe after those checks. It reports the installation counts, connection/version status and a specific panel repair step. It does not request or dump the current project's full timeline. `ready: true` means the isolated connector responded with the configured host version; `hostQualified` remains false and project scope is still required for edits. A missing panel reports `ready: false` without trying the production connector. These checks pin compiled code, helpers and prepared panel files; they do not attest to every transitive Node dependency or to a panel copy installed separately inside Adobe.

A fresh directory installation on the development Mac verified 683 skill files, five Python helper/bootstrap files, 183 compiled JavaScript/JSON files and 40 prepared panel files. Its real doctor probe reported `ready: false` when that isolated panel was not running; it did not inspect the production timeline or fall back to its connector. Nine added installation/doctor tests bring the Python suite to 253 passing tests. Native Premiere workflow and clean-Mac acceptance remain open.

`materialize.py` validates every distribution path and SHA-256 before writing any runtime files. It rejects duplicate/traversing paths and symlink entries. It substitutes the checkout and configured asset paths only in the private runtime copy.

All 681 packaged files are written to a new staging directory before the runtime is exposed at `.local/skills`. Every skill entrypoint receives a short routing reference immediately after its YAML metadata, before canonical execution instructions. It links to the toolkit's shared [native execution routing](AGENT_WORKFLOW.md#native-execution-routing), including for directly invoked stage skills. The materializer preserves metadata and procedure bodies. Six distribution descriptions have explicit, reproducible portability corrections for valid discovery metadata; their canonical source hashes remain in the source manifest.

The runtime contains `.acq-materialization.json` with schema `acq-edit/materialization-v2`, recording the distribution-manifest hash, resolved asset/runtime locations, all resulting file hashes, routed entrypoints, the shared execution contract's hash and unresolved legacy references. `.local/portability.json` retains the unresolved-reference report. `doctor` reports this as `skills`; `python3 scripts/materialize.py --verify` performs the same read-only check without editor access. A verified runtime is not proof that optional dependencies are present or the native workflow is qualified.

A repeat with the same source package, execution contract and assets verifies the existing receipt and every runtime file without overwriting them. Missing, edited or extra source files, an unreceipted runtime, or changed package/asset paths cause a specific refusal. Python bytecode caches are excluded from the source comparison. Older development runtimes, including v1 receipts that routed only the master skill, remain untouched; use a fresh checkout to adopt this installer. Changing the shared execution contract invalidates verification until a fresh runtime is prepared.

Cooperating installer processes serialize through exclusive checkout-local reservations. If a process is killed, inspect the PID in `.local/materialize.lock` or `.local/engine-install.lock` and confirm the original process has terminated before manually reconciling that exact reservation. Failed staging directories are retained. Do not delete a reservation merely because installation appears slow. There is no automatic stale-lock takeover or in-place upgrade.

The FilmCraft installer refuses dirty checkouts, an unexpected origin or an existing checkout at a different commit before materialization/build. A failed clone or partially prepared Premiere installation is retained for inspection; a fresh checkout is the supported retry location. Existing Premiere panels and profiles are never replaced automatically. The shared Python environment installer is still a separate pip/venv step; the skill-runtime transaction does not make pip installation atomic or fully lock transitive Python dependencies.

## Qualification recorded on 2026-10-23

A separate copy of the release-source files was installed under a path containing spaces, with an isolated `HOME`, on the development Mac. `npm ci --ignore-scripts`, TypeScript compilation, and the actual Python 3.11 shared-dependency installation succeeded. Resolve-only engine installation materialized all 681 skill files, and a second run preserved the exact receipt. No FilmCraft or Premiere runtime directories or global agent skill directories were created. Eleven files still report unresolved legacy references; those routes must not be treated as portable merely because materialization succeeded.

A second isolated checkout prepared and compiled the Premiere Agent Lab package and generated its local profile. It did not install the panel into Adobe or connect to the production host. The initial dependency audit reported seven advisories, including the newly updated [Zod resource-exhaustion advisory](https://github.com/advisories/GHSA-mrhx-c7xc-m3w5). The toolkit dependency lockfile was updated, Vitest/coverage were pinned to 4.1.12, and a fresh dependency install plus TypeScript compilation passed with zero npm audit findings. Original snapshot hashes and distribution override hashes are retained separately. This does not qualify a Premiere native workflow.

A subsequent fresh Premiere installation with isolated `HOME` exposed a missing runtime resource-copy step despite successful TypeScript compilation. The installer now validates and copies all 22 JSON resources, then initializes the actual packaged MCP transport and verifies required native tool registration. Fresh installation passed with 507 discovered tools. The generated ACQ Edit Agent CEP/UXP packages have distinct IDs, storage keys, mailbox and port; the production panel is not replaced. Three panel-isolation and four runtime-resource/startup failure-boundary regression tests pass. No panel was installed into Adobe and no host operation was executed by these installation checks.

On October 24, another fresh Premiere-only directory installation passed helper/compiler verification, npm installation, TypeScript compilation and actual MCP discovery. A synthetic 640×360/25 fps source with PCM tone audio exercised the original v2 selection → compiled → resolved → XML → independent exact-reproduction validator chain. It retained two 25-frame ranges and explicitly recorded no native host execution or editorial approval. Empty-HOME tests passed real helper/compiler imports; changed local compiler bytes and a one-frame change to the resolved selection were rejected while preserving previous XML. Missing-helper and changed-upstream snapshot tests also preserve the prior distribution. This is packaging and compiler evidence, not a Premiere render or clean-Mac qualification.

To reproduce that mechanical fixture after a fresh Premiere installation:

```sh
python3 scripts/premiere_assembly_fixture.py \
  --runtime "$PWD/.local/premiere-agent" \
  --output "$PWD/.local/premiere-agent/lab/runtime/fixtures/compiler-replay"
```

The output directory must be new. This fixture deliberately uses compiler replay mode with synthetic words and tone audio. It supplies no current-brain receipt, listening evidence or human approval and cannot satisfy the real-footage acceptance gate. It invokes no Premiere tool.

Nineteen installer regression tests cover corruption before writes, traversal/duplicates, local changes, incomplete/unreceipted runtimes, asset changes, symlinks, exclusive reservations, failed staging, engine-specific prerequisites and preserving a dirty FilmCraft checkout. The added cases cover direct-stage routing with preserved YAML/body, malformed or missing inputs, and read-only detection of changed runtime/contract bytes.

A fresh Resolve-only installation under another path with spaces verified all 681 runtime files, all 37 skill entrypoints, the contract hash and the actual CLI `doctor.skills` result. The skill validator passed all 37 metadata headers after the six portable-description corrections; their procedure bodies and canonical source hashes were unchanged. A repeat preserved every runtime file timestamp and its receipt, and no Premiere or FilmCraft runtime directories were installed. Four native-dispatch tests additionally verify rejection of wrong-engine, out-of-project and busy-project requests before adapter initialization, selected-only imports under the lock, and shared preparation without native adapter imports. These are routing and isolation checks, not a claim that a model cannot choose an incorrect tool or that all native workflows pass.

This is isolated-directory installation evidence on an existing Mac. It is **not** clean-Mac acceptance, an editor render test, a full shell-helper path-quoting audit, or an authenticated Codex/Claude workflow. The release gates in `ACCEPTANCE.md` remain open.

## Fresh FilmCraft source build

A fresh GitHub clone at toolkit commit `69c3e2c`, with the updated installer, installed shared Python dependencies and all 681 skill files. An isolated Rust 1.95.0 toolchain compiled the pinned FilmCraft source at `71438c627b5cbcfb550526c3971f4d0037733c5c` using the locked release build. No previous FilmCraft executable was copied, no Premiere integration was installed, and no Resolve integration was configured. macOS compiler/SDK preflight passed without `pkg-config`. The executable's SHA-256 was `e9d1255f873cd0feb72e8c184fecccc9f14f5a6ef8dada57da7dfcf1d93832ab`; the local receipt retained its actual source, toolchain and installer hashes. Doctor verified the executable and all 37 routed skills.

Four added installer tests cover macOS SDK requirements, missing SDK refusal, immutable build provenance and refusal after source drift. The full Python suite passes 173 tests. This is a fresh source/toolchain build on the development Mac; installed system tools and agent authentication were reused. Clean-Mac and both-agent installation acceptance remain open.

That newly built executable subsequently passed the real Codex build and browser caption-revision loop, including exact decoded audio, complete native caption-only comparison, immutable artifact hashes and late-feedback preservation. See `LIVE_AGENT_LOOP.md`. This adds native execution evidence without claiming clean-Mac or human acceptance.

## Portable procedure update

The later [portability update](PORTABILITY.md) replaces thirteen packaged workstation-specific paths or execution handoffs while retaining canonical hashes. A fresh runtime verifies 681 files and 37 entrypoints. The earlier eleven normalized-path warnings are resolved; improved shell-path detection now explicitly flags the optional live-stream launcher. This is a dependency warning, not a failed basic installation or proof that all optional workflows are qualified. Existing runtimes are preserved; install the update in a fresh checkout.

## Skill dependency verification

The later dependency update packages 38 owners and 683 files, including the required hook-copy cleanup skill. Installation verifies and pins the [explicit skill route inventory](SKILL_DEPENDENCIES.md) before exposing the runtime. Doctor reports scoped external routes separately from legacy path warnings. Unknown missing skills and stale inventory/policy records fail explicitly. Earlier 37-owner qualification results describe those historical snapshots; use a fresh checkout for the new package.

Agent dispatch and toolkit native commands now run this same read-only runtime verification before launching their agent/editor process. An unreceipted, changed or older runtime cannot silently run with a newer adapter. Failure retains the job/operation for reconciliation with no native child launched; it never overwrites the installed runtime. Use a fresh checkout with the matching distribution and rerun setup. This check does not install missing assets or establish native/editorial acceptance.

An actual hook-agent attempt exposed this gap: an older unreceipted development runtime rendered the base but lacked the helper's native hook geometry fields. The agent stopped without publishing, and the failed run was retained. The new preflight rejects that runtime. A fresh shared-dependency installation verified all 683 files and 38 entrypoints before another agent attempt; mock process tests separately cover invalid verifier output and refusal before native launch.

## Premiere lifecycle package

Fresh installations now register `lab_inspect_toolkit_workspace`, `lab_toolkit_project` and `lab_reconcile_toolkit_project` alongside the existing stage tools. The maintainer source manifest retains the original Lab server hash and its reviewed override; `premiere-distribution-additions.json` separately identifies the toolkit-owned lifecycle implementation. The distribution audit verifies its bytes, and future source snapshots refuse upstream name collisions rather than overwrite the addition. The compiled installation receipt also pins the resulting JavaScript. See [PREMIERE_STATE.md](PREMIERE_STATE.md) for scope, project preservation, current recovery limits and native qualification requirements.

The final lifecycle package was installed into another fresh directory on the development Mac. Verification passed for 683 skill files, five helper/bootstrap files, 184 compiled JavaScript/JSON files and 40 prepared panel files. Actual MCP discovery registered 509 tools, including both lifecycle endpoints. No panel was installed into Adobe and no native host operation was called by this check. Shared suites passed 261 Python and 79 service tests; the separately compiled lifecycle suite passed 17 simulated cases.

A subsequent fresh recovery-package installation verified the same 683 skill, five helper/bootstrap, 184 compiled and 40 panel files, and discovered 510 tools including `lab_reconcile_toolkit_project`. No Adobe installation or native host call occurred. The recovery checkpoint passes 267 Python, 88 service and 31 explicit lifecycle tests. The Python suite also corrected a test-only executable launcher so the suite itself works from a Python environment whose path contains spaces.
