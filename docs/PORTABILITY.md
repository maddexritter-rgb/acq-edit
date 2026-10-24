# Portable procedures and explicit local inputs

Canonical source stays untouched. `distribution/SOURCE_MANIFEST.json` retains each
original source hash, the distributed hash and the transformations applied between
them. Reviewed replacements in `scripts/portable_overrides` are also hash-pinned;
the distribution audit checks those pins. A fresh full export reproduced all 681 source hashes, distributed hashes and
transformation records. The package generator applies the same transformations
when exporting a new canonical snapshot.

The installer resolves `__ACQ_TOOLKIT__`, `__ACQ_SKILLS__` and `__ACQ_ASSETS__` only
inside its new checkout-local runtime. The first two point to this toolkit and its
packaged procedures; the asset root is supplied explicitly during installation.
Existing runtimes and projects are preserved. Use a fresh checkout for this update.

## Intake and project paths

The packaged footage-fetch owner uses the toolkit intake contract. Its optional
shell entrypoint now takes `PROJECT_ID DRIVE_URL [RCLONE_REMOTE]` and delegates to
the existing `drive` or `drive-folder` command. It preserves arguments containing
spaces/query characters and rejects ambiguous bare IDs. This replaces the old
brand/slug signature, personal scaffold script, detached downloader and project
rename. Existing projects, transfer journals and exact source identities remain
owned by the toolkit; see [INTAKE.md](INTAKE.md).

The runbook's project setup uses the configured toolkit storage root and selected
backend. Example JSON paths refer to the current project, project-owned sources,
work products or configured assets. Substitute real paths before execution; examples
are not permission to run a legacy final renderer instead of the selected editor.

## Phrase lookup

The formerly project-specific `edit/scripts/cut_by_phrase.py` now accepts an explicit
source-word transcript, nearby source time, hook phrase and payoff phrase. It emits
all matching word-index pairs plus the transcript hash. It does not choose among
repeated phrases, append fixed padding, write files, run old project-local helpers
or render a clip. Its bounded lookup uses the former hook search window and a
150-second payoff search horizon; those are search bounds, not clip-length rules.

This is a locating aid within the existing editing owner. Assembly Design still
constructs the actual source-word selection, inspects speech boundaries, compiles
the plan and hands it to the project's native adapter. A phrase match does not prove
meaning, speaker identity, a complete payoff or an acceptable cut.

## Fonts, assets and precedents

The paid-ad graphics helper requires an explicit existing licensed font file. The
legacy renderer's config also requires `font`; neither falls back to a former user's
font directory. Both validate the font before creating output. Asset catalogs resolve
under the configured asset root, but fonts, music, stock media and templates are not
bundled or automatically licensed. Verify each selected asset and profile separately.

Precedent guidance points to restricted brain retrieval and explicitly supplied
calibration evidence. Historical private-study paths are not executable defaults.
Unavailable historical evidence cannot be labeled approved or acoustically verified.

## Verified scope and remaining work

Thirteen packaged files have reviewed portability or handoff changes while preserving
their canonical source hashes. Five added tests cover Drive delegation, missing-font
refusal, zero-time/repeated phrase handling, read-only transcript pinning and override
provenance. The full Python suite passes 178 tests. A fresh runtime in a directory
with spaces verified 681 files and 37 entrypoints. An actual graphics smoke test with
an explicitly supplied system font produced three transparent RGBA PNGs; that font
and those artifacts are not distributed.

The scanner now catches shell references such as `$HOME/Downloads/cluade` as well as
normalized private-path markers. One optional dependency remains explicitly flagged:
`live-clip/scripts/start_liveclip_autopilot.sh`, whose autonomous live-stream workflow
still depends on personal configuration and an unqualified execution route. Do not
run it as a toolkit workflow. Ordinary local/YouTube/Drive intake uses the supported
project commands. A clean marker report alone would not prove arbitrary helper,
asset, model, editor or clean-Mac compatibility; the pilot gates remain separate.

The hook distribution exposes its owner's already measured native text/shape coordinates without changing layout policy. The assembled-text gate's summary print is rewritten for the installer's Python 3.11 runtime; its prior multiline f-string required Python 3.12+. Both transformations retain canonical source hashes.
