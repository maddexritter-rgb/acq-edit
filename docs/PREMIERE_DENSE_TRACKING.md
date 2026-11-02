# Premiere tracking repair

Premiere now uses the same YuNet gap handling and X smoothing functions as
FilmCraft. The previous Premiere driver sampled at half-second intervals and
reduced the curve to sparse keys. Its instructions also encouraged that route.
The connector could inspect only 1,000 keys on one property.

## Changed behavior

- Decode and analyze every displayed source frame. Keep one editable native
  Anchor Point key per frame, with Linear interpolation requested.
- Smooth a continuous source/camera/layout run before slicing it into timeline
  items. Reset at removed source time, camera changes and layout changes.
- Preserve calibrated Y and Scale. Explicit posture transitions retain their
  authored duration when tracking changes from sparse to per-frame observations.
- Use exact integer frame ticks, including NTSC rates. Reject incomplete dense
  keys, unsupported frame mapping, retiming, and unresolved detection gaps.
- Remove sparse tracking guidance and prevent the legacy simplifier from reducing
  dense plans. Fixed crops require an explicit reviewed exception.
- Allow up to 10,000 keys per property while retaining the aggregate operation,
  snapshot-size, project-scope, ownership and protected-state checks.
- Connection recovery messages name ACQ Edit Agent, never the legacy MCP Bridge.

This changes tracking execution, not editorial selection. Existing keyed sequences
are preserved; rebuild from their pre-reframe source sequence when applying the new
tracking pass. Do not layer another animation over existing Motion keys.

## Verification on 2026-10-31

Automated regressions cover dense decoding, detection gaps, shared FilmCraft curve
parity, continuous subdivisions, camera/source/layout resets, 120-second key density,
fractional frame ticks, locked Y, bounded posture transitions, legacy simplification
rejection, and connector snapshot bounds. The connector VM fixture reads all 7,200
keys and rejects 10,001 without truncating them.

On Premiere 26.3.0, the isolated ACQ Edit Agent imported a source-linked mechanical
fixture, duplicated its timeline to 1080x1920, detected 1,080 of 1,080 source frames,
and wrote and independently read back all 1,080 native keys at 24000/1001 fps.
Source ranges, independent audio, other effects and protected timeline state matched
the baseline. The project saved successfully. Native application and verification
with save took 6.6 seconds; the Premiere export took 10.2 seconds.

The fixture deliberately loops 72 real source frames fifteen times to exceed the old
per-property limit. It is a mechanical stress test, not a new editorial clip or a
claim of acceptance on a complete Q&A. A longer source containing a camera change
correctly stopped on unresolved detector coverage rather than inventing tracking.

Nine native frame exports were visually inspected: the intended subject remains
centered and no source-edge black was observed. The source's already-clipped hat
edge remains present. The complete MP4 decodes to 1,080 frames at 1080x1920 with
48 kHz audio and a duration of 45.045 seconds. These observations are not human
approval or a listening assessment. Interpolation was requested but is not exposed
by the native readback API.

**Follow-up on 2026-11-02:** a full 111.903-second Q&A camera test now passes
native construction, export and UI save/close/reopen with all 15 sequence snapshots
unchanged. Independent panels and eight dense-keyed single-camera shots retain
original camera links. See [camera-stage evidence](NATIVE_PANELS.md#premiere-real-qa-camera-test--2026-11-02).
The dedicated empty-workspace lifecycle endpoint remains unqualified, as do full-job
completion, Premiere 26.5.2 native acceptance and human visual approval. Preview.18
ships the verified camera operations with these limits stated explicitly.

For an installed update, refresh the owned integration and skills in the existing
chat. Close and reopen the ACQ Edit Agent panel so it loads the new runtime; a
running cached panel can continue polling the old installation even when the files
on disk have been updated. Preserve existing projects and local customizations.
