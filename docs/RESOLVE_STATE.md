# Resolve state checks across reopening

The adapter now fingerprints a parsed Fusion graph rather than the raw `.comp` bytes. Native Studio 21.1.1 build 10 testing showed that reopening an unchanged project can reorder tools, increment the composition's `CurrentID` counter, and refresh the cached display label for the `Timeline Audio` metadata entry after timeline duplication. The former byte hash treated these serialization changes as editorial edits and stopped otherwise valid revisions.

`python/fusion_state.py` parses the exported declarative tables without executing Lua, evaluating expressions or loading graph scripts. Ordinary table keys are sorted; array indices and explicitly `ordered()` tables preserve their ordering. Constructor types, tool names, graph connections, source paths, input values, expressions, keyframes, ranges, preferences and unknown fields remain represented.

Only these qualified serialization/cache forms are omitted:

- The top-level composition `CurrentID` numeric allocation counter. Tool-local IDs remain represented.
- `MEDIA_AUDIO_TRACK_NAME` in a Loader/MediaIn's `CustomData.MediaProps.MEDIA_AUDIO_TRACKS_DESC` entry whose `MEDIA_AUDIO_TRACK_ID` is exactly `Timeline Audio`. The ID, audio properties and all source-track names remain represented. This cached label changes from the old timeline name to the duplicate's name when reopened.
- `__Queried = true` inside a Loader/MediaIn's `CustomData.MediaProps`. This successful media-query cache marker disappears on reopen. False, other values and identically named fields elsewhere remain represented.
- The exact plain empty `Prefs.Comp.SpellCheck = {}` placeholder. Nonempty settings and identically named tables elsewhere remain represented.
- The exact plain `Prefs.Comp.Views = { View1 = {} }` placeholder. Additional views, nonempty view contents and other constructors remain represented.

The parser rejects duplicate keys, executable expressions outside quoted strings, unsupported syntax, malformed strings and oversized/deeply nested exports. It never drops an unrecognized effect to make a fingerprint match. This initial parser supports the declarative exports observed in the toolkit fixtures; custom macros or long-string/script forms may require a specific parser extension and qualification. Existing expressions are retained as strings, not evaluated by the inspector.

Resolve snapshots also include item enabled state, media-pool source paths, native track enabled/locked state and timeline markers alongside the existing timing, source IDs, properties, fades, link IDs, settings and Fusion graphs. These checks are preconditions for revisions; they do not establish that every unexposed color/Fairlight effect or other native project property has been inspected. Broader native-state coverage remains a pilot gate.

## Before the first timeline

Inspecting the exact selected toolkit project with zero timelines returns a `resolve-project-without-timelines` state instead of an operation failure. It records the project identity/settings, media-pool folder and clip identities/properties, and render state. Imported media is reported even when no timeline exists; this state does not mean the whole project is empty. Inspection never creates a timeline, changes selection or switches projects.

If timelines exist but none is selected, inspection still refuses and asks for the intended timeline. It also refuses a timeline appearing during the read. Normal timeline snapshots, revision fingerprints and rendering preconditions remain unchanged. This removes the avoidable first-use reconciliation seen when agents inspected a newly prepared empty Resolve project before construction. Project opening remains explicit: build can create its named project when no project is open, but it does not close or switch an unrelated current project. The CLI `open` command restores review state, not the native host selection.

A live Studio 21.1.1 probe inspected a separate empty toolkit project, then imported one verified project-owned source and inspected it again. Both inspections succeeded without creating a timeline; the imported clip/path was reported and its addition changed the fingerprint. The prior synthetic review snapshot and render queue were restored unchanged. Three regression tests cover empty state, imported media and unselected/changing timeline refusal.

## Existing projects and receipts

New snapshots declare `fusionFingerprintSchema: acq-edit/fusion-state-v3`. Version 1 introduced parsed graphs and the additional native state fields; version 2 narrowly normalizes the three cache/empty-preference forms above. Version 3 additionally normalizes the qualified owned-expression caches below. Fingerprints from either an earlier schema or raw exports will differ. Do not rewrite historical inspection files or change a queued operation's expected fingerprint automatically. Inspect the current native timeline, compare it with the saved plan/version and reconcile any differences before preparing a new operation. Published versions and their review decisions remain unchanged.

Cache paths and other metadata are not broadly excluded. A duplicated timeline is a different native object with different IDs and may have different cache paths; its complete snapshot is expected to differ. Revision code still verifies that the allowed finishing change preserves source cut timing.

## Native evidence and limitations

On 2026-10-23, a dedicated synthetic paired-source project passed a real save, close and reopen with an identical complete new snapshot. Raw exports from before and after demonstrated the three serialization differences above. Twelve retained native Fusion exports parsed successfully; the regression suite separately checks changes to captions, source references, graph edges, expressions, keyframe curves and timing, plus malformed/unsupported exports.

On a separate duplicated test timeline, native caption text, expression and graph-connection changes each changed the Fusion fingerprint. A revision using the pre-edit fingerprint was rejected before further mutation. Native clip-disable, track-mute and track-lock changes also appeared in the expanded snapshot. The original test timeline was reselected and verified unchanged.

The unchanged original timeline then rendered through the updated adapter after reopening: 50 frames at 640×360/25 fps, with full decode passing. All decoded RGB video frames and decoded float PCM audio were byte-identical to the prior valid native render. This is same-timeline reopen evidence; it does not erase the separate picture-difference limitation observed when duplicating a timeline for a music revision.

A later motion fixture exposed additional cache drift. A fresh controlled build retained raw `.comp` exports before render, after render and after actual save/close/reopen. The before/after-render graphs were stable. On reopen, both caption graphs lost only `__Queried = true`, empty `SpellCheck`, and `Views = { View1 = {} }`. These were direct export-to-export comparisons; embedded DRP graph serialization was not treated as an equivalent format. Version 2 fingerprints made the complete pre/post native snapshots identical, and fresh native readback matched the reconciled snapshot.

That reopened motion timeline rendered through Resolve again: all 50 decoded RGB frames were byte-identical to its pre-reopen render. Decoded audio differed at −74.61 dB RMS relative to signal; the separate exact-audio qualification remains open. An intentional native caption mutation on a duplicated test timeline still changed the version 2 fingerprint, and a revision with its stale fingerprint was rejected before another timeline or edit was created. The existing review timeline was restored and verified against its original schema's snapshot. Regression tests preserve nonempty preferences, additional views, unknown values and fields outside the exact normalization locations. No historical receipt was rewritten.

Host page context mattered for the track mutation probe: `SetTrackEnable` and `SetTrackLock` returned success on the Deliver page without changing readback. The same API changes on the Edit page changed readback as expected. Read-only retrieval of those changed states subsequently worked on Deliver. The adapter does not add a track-mutation workflow on this evidence; any future writer must establish its context and verify native readback rather than trusting a boolean return.

This evidence qualifies the observed mechanical state checks on Studio 21.1.1 build 10. It does not grant human approval, establish speech quality, qualify arbitrary third-party Fusion tools, or complete the Resolve agent-driven acceptance loop.

## Version 3: owned caption expression caches

Studio 21.1.1 build 10 materialized numeric `Value` caches beneath unchanged caption expressions during the first render. Direct pre/post `.comp` exports isolated the differences to the owned Text+ `Center` and Merge `Blend` inputs. Version 3 omits only these exact forms:

- A TextPlus tool named `ACQ_Caption_<number>_<wide|tight|text>`, `Inputs.Center`, with an `Input` containing only a nonempty string `Expression` and a plain two-number point `Value` (array indices 1 and 2).
- A Merge tool named `ACQ_CaptionMerge_<number>_<wide|tight|text>`, `Inputs.Blend`, with an `Input` containing only a nonempty string `Expression` and numeric `Value`.

Only the cached `Value` is omitted. Expression strings, connections, additional fields, different node types/names, nonnumeric values and all other inputs remain protected. Unknown forms fail comparison rather than being removed. Regression tests cover both stable caches and these exclusions, including expression changes and Unicode captions.

A fresh caption-owner build and subsequent native wording/color revision then passed before/after-render snapshot checks. The original review timeline's entire v2 snapshot was first verified unchanged, then a separate v3 baseline was recorded for future operations; historical receipts were not rewritten. The revised parent timeline and checkpoint hash were independently checked unchanged, and the original review timeline was restored against its new baseline. This adds direct render stability evidence, not a claim that every native state is observable.

## Source clocks on duplicated timelines

The hook-removal fixture exposed a real source-timing change on Studio 21.1.1 build 10. The first native Timeline MediaIn reported `GlobalIn=0` and `GlobalOut=149` immediately after duplication/removal, but reopened with `GlobalIn=1` and `GlobalOut=150`. Its clip-local source range remained 0–149. The missing composition frame zero caused subsequent Fusion export failures. A later preview could show a frame while still being one source frame late. This drift must not be normalized out of a fingerprint.

`resolve_sources.py` now checks source path, native cut ranges, live Timeline MediaIn clocks, render coverage and absence of clock expressions/drivers before export. Fusion inspection reads live source clocks on both sides of graph export and refuses any change. Explicit MediaPool mappings used by camera panels remain the responsibility of their separate verifier.

New duplicate-based revisions explicitly store the already-verified static Timeline MediaIn values on the new copy. All source controls are validated before any write; parent and copy clocks must match, the native identities must differ, and readback must remain identical. The existing native protected-state comparisons still apply. The helper neither changes a shifted clock nor writes the parent. Resolve's Python `SetInput` can return `None` on success, so native readback establishes the result.

A controlled duplicate/removal probe retained its complete snapshot before and after explicit storage, then again after saving, closing and reopening. The source clocks remained 0–149, −50–99 and −100–49 on the three source cuts. Unmodified duplicate probes reopened with the first source shifted by one frame; merely reading controls around graph export did not prevent it. Earlier failed copies, packets and inspections remain preserved for reconciliation. No historical snapshot or receipt is migrated by this change.
