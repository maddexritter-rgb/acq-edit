# Installation and portable runtime verification

Use a fresh checkout for a teammate installation or an upgrade. Keep existing projects and credentials in their configured external locations. The installer does not migrate project state or install global agent skills.

The shared installer currently uses the `python3.11` executable. Install Node.js 24+, Python 3.11 and FFmpeg/ffprobe first, plus the selected agent CLI. YouTube and Drive intake additionally require `yt-dlp` and `rclone`; Drive authentication belongs to the teammate. Editor licenses, assets and agent authentication are separate setup steps.

Run the read-only prerequisite check for the selected engine before installation:

```sh
python3 scripts/install_engine.py resolve --check
# Or: premiere --check / filmcraft --check
```

Resolve checks for its bundled interpreter and shared executables. It does not require Cargo, Premiere or FilmCraft. Premiere adds npm; FilmCraft adds Git, Cargo, Rust 1.95+ and pkg-config. These checks do not prove all native libraries are linkable, that an editor is running/configured, or that an agent is authenticated. Continue with the README setup and `doctor`, then the acceptance workflow.

## Verified materialization

`materialize.py` validates every distribution path and SHA-256 before writing any runtime files. It rejects duplicate/traversing paths and symlink entries. It substitutes the checkout and configured asset paths only in the private runtime copy.

All 681 packaged files are written to a new staging directory before the runtime is exposed at `.local/skills`. The runtime contains `.acq-materialization.json`, recording the distribution-manifest hash, resolved asset/runtime locations, all resulting file hashes and unresolved legacy references. `.local/portability.json` retains the unresolved-reference report.

A repeat with the same source package and assets verifies the existing receipt and every runtime file without overwriting them. Missing, edited or extra source files, an unreceipted runtime, or changed package/asset paths cause a specific refusal. Python bytecode caches are excluded from the source comparison. An older development runtime without a receipt remains untouched; use a fresh checkout to adopt this installer.

Cooperating installer processes serialize through exclusive checkout-local reservations. If a process is killed, inspect the PID in `.local/materialize.lock` or `.local/engine-install.lock` and confirm the original process has terminated before manually reconciling that exact reservation. Failed staging directories are retained. Do not delete a reservation merely because installation appears slow. There is no automatic stale-lock takeover or in-place upgrade.

The FilmCraft installer refuses dirty checkouts, an unexpected origin or an existing checkout at a different commit before materialization/build. A failed clone or partially prepared Premiere installation is retained for inspection; a fresh checkout is the supported retry location. Existing Premiere panels and profiles are never replaced automatically. The shared Python environment installer is still a separate pip/venv step; the skill-runtime transaction does not make pip installation atomic or fully lock transitive Python dependencies.

## Qualification recorded on 2026-10-23

A separate copy of the release-source files was installed under a path containing spaces, with an isolated `HOME`, on the development Mac. `npm ci --ignore-scripts`, TypeScript compilation, and the actual Python 3.11 shared-dependency installation succeeded. Resolve-only engine installation materialized all 681 skill files, and a second run preserved the exact receipt. No FilmCraft or Premiere runtime directories or global agent skill directories were created. Eleven files still report unresolved legacy references; those routes must not be treated as portable merely because materialization succeeded.

A second isolated checkout prepared and compiled the Premiere Agent Lab package and generated its local profile. It did not install the panel into Adobe or connect to the production host. The initial dependency audit reported seven advisories, including the newly updated [Zod resource-exhaustion advisory](https://github.com/advisories/GHSA-mrhx-c7xc-m3w5). The toolkit dependency lockfile was updated, Vitest/coverage were pinned to 4.1.12, and a fresh dependency install plus TypeScript compilation passed with zero npm audit findings. Original snapshot hashes and distribution override hashes are retained separately. This does not qualify a Premiere native workflow.

A subsequent fresh Premiere installation with isolated `HOME` exposed a missing runtime resource-copy step despite successful TypeScript compilation. The installer now validates and copies all 22 JSON resources, then initializes the actual packaged MCP transport and verifies required native tool registration. Fresh installation passed with 507 discovered tools. The generated ACQ Edit Agent CEP/UXP packages have distinct IDs, storage keys, mailbox and port; the production panel is not replaced. Three panel-isolation and four runtime-resource/startup failure-boundary regression tests pass. No panel was installed into Adobe and no host operation was executed by these installation checks.

Twelve installer regression tests cover corruption before writes, traversal/duplicates, local changes, incomplete/unreceipted runtimes, asset changes, symlinks, exclusive reservations, failed staging, engine-specific prerequisites and preserving a dirty FilmCraft checkout.

This is isolated-directory installation evidence on an existing Mac. It is **not** clean-Mac acceptance, an editor render test, a full shell-helper path-quoting audit, or an authenticated Codex/Claude workflow. The release gates in `ACCEPTANCE.md` remain open.
