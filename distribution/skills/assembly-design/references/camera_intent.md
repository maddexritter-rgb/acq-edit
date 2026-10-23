# Editable picture coverage at assembly review

For multicamera assemblies, Assembly Design owns synchronized **coverage**, the spoken edit, and the proposed final shot/layout intervals. Preserve unused angles as editable coverage. Horizontal-to-vertical implements the plan; explicit editor picture decisions supersede it.
The editorial criteria, including the required Q&A opening split, live in [camera-decisions.md](camera-decisions.md).
Every new picture plan and construction packet must record `content_format` from the interaction route (`qa` for question/answer), so format requirements reach validation.

## Order and evidence

First design and resolve spoken content. For **each** kept source span, measure the
source-frame mapping for every camera recorded for that interaction. Place every
available synchronized angle over that span's full assembly-frame interval, including
angles not used in the visible review picture. Do this again after each dialogue
reorder or trim; an angle covering one source span does not prove coverage of another.
Keep the alternate angles on labeled, source-linked, independently editable picture
tracks or nests. They may be inactive behind the watchable composite. For editor
comparison, retain each available synchronized camera's embedded audio and each
separate recording as source-linked, individually identifiable audio coverage; mute
or disable the alternates so only one deliberate dialogue mix plays. Do not mix all
camera mics together or discard them before the editor can choose the best source.
A picture subdivision is not an audio cut.

Place the main review picture and its alternate camera tracks directly beside one
another in the timeline's video stack. Likewise, place the chosen dialogue audio
and alternate audio tracks together in the audio stack, rather than scattering them
among distant track numbers. Label tracks or items with camera/recorder identity;
where a track is reused for nonoverlapping source clips, the item labels must still
identify the source. Keep gaps honest when a camera or recorder does not cover a
selected span. Before handoff, inspect an early, middle, and late multicamera clip
in Premiere and confirm the coverage is visible by scrolling only within that
compact stack, each source remains independently editable, and alternate audio is
silent until deliberately enabled.

Record each camera's media identity, source-frame in/out, assembly-frame in/out, sync
evidence, and availability/quality for every kept span. If a source camera stopped,
was obstructed, or cannot be synchronized, mark that interval as a specific coverage
gap rather than claiming complete coverage or extending unrelated frames. Distinguish
physically present picture from editorially usable picture.

For each occurrence record a stable ID, clip ID, exact assembly-frame interval, layout
(`single` or `split`), independent panel source mappings, visible participants, speaker
role, observed visual evidence and editorial reason. Pin the resolved spoken revision.
If dialogue changes, remap/review picture intent. If only picture changes, preserve audio.
Unknown reaction evidence remains UNKNOWN, not a presumed nod because the guest is silent.

## 16:9 review representation

Keep one watchable picture presentation in `01_CUTS`. If it uses split screen, show
the actual intended review interval as **side-by-side picture** with independently
source-linked left/right panels, framed with native Motion/Crop. Do not merely scale
both uncropped 16:9 images to 50% and leave tiny pictures/large black areas. A
full-length split is optional, not a substitute for retaining every source angle.
The proposed picture plan is binding for downstream construction, but is not human approval.

Use separate editable picture tracks/items for each split occurrence. Align panel edges
to its precise entry/exit; name the occurrence so it is easy to locate. A reviewer must
be able to extend or shorten that split without rebuilding the spoken edit, baking a
composite video, or changing dialogue duration. Keep one deliberate dialogue mix; adding
a panel must not double its audio. Full-screen sections remain ordinary source-linked
items. A timeline marker alone is not a visible split-screen review. The inactive
coverage tracks remain complete even where a review panel or full-screen shot hides them.

Verify the first/middle/last visible frames, transitions, synchronization and a trial
boundary trim in an isolated review copy. Native numbers alone do not prove the layout.
No shadow, captions, decorative finishing or final 9:16 styling is needed at this stage.

## Finishing handoff

Read the actual current dialogue and coverage from the native sequence. Preserve explicit editor changes. Pass the revision-bound shot/panel plan to horizontal-to-vertical to translate geometry without reselecting camera or split timing. If no plan exists, return to Assembly Design for picture-only planning while preserving dialogue. Unusable coverage returns to the same owner before rendering. Keep original assemblies, independent sources and alternate audio.
