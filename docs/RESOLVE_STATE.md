# Resolve state checks across reopening

The adapter now fingerprints a parsed Fusion graph rather than the raw `.comp` bytes. Native Studio 21.1.1 build 10 testing showed that reopening an unchanged project can reorder tools, increment the composition's `CurrentID` counter, and refresh the cached display label for the `Timeline Audio` metadata entry after timeline duplication. The former byte hash treated these serialization changes as editorial edits and stopped otherwise valid revisions.

`python/fusion_state.py` parses the exported declarative tables without executing Lua, evaluating expressions or loading graph scripts. Ordinary table keys are sorted; array indices and explicitly `ordered()` tables preserve their ordering. Constructor types, tool names, graph connections, source paths, input values, expressions, keyframes, ranges, preferences and unknown fields remain represented.

Only two fields are omitted:

- The top-level composition `CurrentID` numeric allocation counter. Tool-local IDs remain represented.
- `MEDIA_AUDIO_TRACK_NAME` in a Loader/MediaIn's `CustomData.MediaProps.MEDIA_AUDIO_TRACKS_DESC` entry whose `MEDIA_AUDIO_TRACK_ID` is exactly `Timeline Audio`. The ID, audio properties and all source-track names remain represented. This cached label changes from the old timeline name to the duplicate's name when reopened.

The parser rejects duplicate keys, executable expressions outside quoted strings, unsupported syntax, malformed strings and oversized/deeply nested exports. It never drops an unrecognized effect to make a fingerprint match. This initial parser supports the declarative exports observed in the toolkit fixtures; custom macros or long-string/script forms may require a specific parser extension and qualification. Existing expressions are retained as strings, not evaluated by the inspector.

Resolve snapshots also include item enabled state, media-pool source paths, native track enabled/locked state and timeline markers alongside the existing timing, source IDs, properties, fades, link IDs, settings and Fusion graphs. These checks are preconditions for revisions; they do not establish that every unexposed color/Fairlight effect or other native project property has been inspected. Broader native-state coverage remains a pilot gate.

## Existing projects and receipts

New snapshots declare `fusionFingerprintSchema: acq-edit/fusion-state-v1` and include the additional state fields. Old fingerprints will differ. Do not rewrite historical inspection files or change a queued operation's expected fingerprint automatically. Inspect the current native timeline, compare it with the saved plan/version and reconcile any differences before preparing a new operation. Published versions and their review decisions remain unchanged.

Cache paths and other metadata are not broadly excluded. A duplicated timeline is a different native object with different IDs and may have different cache paths; its complete snapshot is expected to differ. Revision code still verifies that the allowed finishing change preserves source cut timing.

## Native evidence and limitations

On 2026-10-23, a dedicated synthetic paired-source project passed a real save, close and reopen with an identical complete new snapshot. Raw exports from before and after demonstrated the three serialization differences above. Twelve retained native Fusion exports parsed successfully; the regression suite separately checks changes to captions, source references, graph edges, expressions, keyframe curves and timing, plus malformed/unsupported exports.

On a separate duplicated test timeline, native caption text, expression and graph-connection changes each changed the Fusion fingerprint. A revision using the pre-edit fingerprint was rejected before further mutation. Native clip-disable, track-mute and track-lock changes also appeared in the expanded snapshot. The original test timeline was reselected and verified unchanged.

The unchanged original timeline then rendered through the updated adapter after reopening: 50 frames at 640×360/25 fps, with full decode passing. All decoded RGB video frames and decoded float PCM audio were byte-identical to the prior valid native render. This is same-timeline reopen evidence; it does not erase the separate picture-difference limitation observed when duplicating a timeline for a music revision.

Host page context mattered for the track mutation probe: `SetTrackEnable` and `SetTrackLock` returned success on the Deliver page without changing readback. The same API changes on the Edit page changed readback as expected. Read-only retrieval of those changed states subsequently worked on Deliver. The adapter does not add a track-mutation workflow on this evidence; any future writer must establish its context and verify native readback rather than trusting a boolean return.

This evidence qualifies the observed mechanical state checks on Studio 21.1.1 build 10. It does not grant human approval, establish speech quality, qualify arbitrary third-party Fusion tools, or complete the Resolve agent-driven acceptance loop.
