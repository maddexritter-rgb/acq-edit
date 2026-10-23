# L1 Q&A: finish an editor-selected draft

Use this route for a recurring multicamera Q&A format when a human has already selected the content and wants camera/audio finishing in an editable Premiere project. This is a scoped entry into /edit, not a separate editing pipeline. Raw-footage mining remains on the normal /edit route.

## Input and scope

Read the supplied project and identify the exact input sequence and, when needed, its selected timeline range. Sequence names are clues, not proof: a sequence called FINAL DRAFT may already contain the target camera switches and fades, while RAW CUT can hold raw footage and several alternate selections. Do not process the whole scratch timeline or silently use the finished reference as the test input.

Treat the Premiere bridge as a single-writer resource across concurrent editing tasks. Before opening, relinking, mutating, saving, or exporting, coordinate the exact project path and sequence with every active task using the bridge and wait for an explicit release. Re-read the active project path immediately before each mutation and fail closed on a mismatch. Use an isolated project copy for analysis or automation; never let a shared active-project window become implicit authorization to change that project.

Preserve selected content, order, native source links, synchronization, and human decisions. Preserve disabled content and gaps as supplied. A disabled alternate camera is not a deleted story segment. Do not trim, compact gaps, change dialogue in/out points, or remove content. Picture-only subdivisions for camera switching are allowed when they preserve the underlying source-time mapping and dialogue timing. Audio fades must use the existing clip spans without extending into another word. Cutting and pacing remain human work unless separately requested.

This pass changes only camera choices, split screens, and audio fades. First-frame centering is optional. Continuous tracking, captions, grading, drawing cutaways, and decorative finishing are outside this narrow pass unless requested. Record those scoped exclusions in the run ledger; do not activate the full-finish defaults or their unrelated checkpoints.

## Reuse the existing owners

- Acoustic word-integrity inspection: → Use Assembly Design's boundary procedure for verification only. Do not invoke trimming, alignment-driven boundary replacement, or gap removal on the human assembly.
- Framing, split-panel geometry, and keyframe simplification: → Use skill: horizontal-to-vertical. Lock the camera/content subdivisions first, then generate sparse native Motion keys separately on each resulting source-linked item. Never place one tracking curve over the finished sequence.
- Audio and visual verification: → Use skills: audit-audio and audit-visual for the layers actually produced.
- Native project work and saved-timeline verification: → RUNBOOK.md, editability invariant and native readback. Reuse the working project; preserve the human input and reference sequences.

Existing qa_assembly.py is useful implementation evidence for camera roles, synchronized sources, split geometry, and speaker microphones. Its baked render output does not satisfy an editable Premiere handoff.

## Learn from paired examples

Learn style only from verified final exports and their contributing native timelines, not standalone drafts or heuristic FINAL labels. A selected draft is an implementation input only when the user has requested finishing it; it is not style evidence. For final-only research, exclude draft comparisons and unused nested material. Store brand/shoot parameters outside the skill and pass them by path.

Extract transition type, duration in frames, curve where available, alternating speaker audio tracks, enabled states, source/timeline spans, framing, animated Motion property, key times in source-media space, interpolation metadata, and key count per edited item. Do not reduce variable native fades or keyframe paths to a single constant based on one example. A camera switch can leave the dialogue uninterrupted; do not equate picture boundaries with audio edits. Dense detector samples are evidence for the intended path, not the native-key count to write into Premiere.

Keep example-derived observations distinct from tested automation rules. A project relink or copied finished timeline is preparation, not an automated finishing result.

Camera-choice reasoning and aligned reference comparison: → Use skill: horizontal-to-vertical, `references/native-camera-decisions.md`.

## Test and handoff

Use a working copy with separate human input, automated result, and verified-final reference sequences. Read back the saved project; verify media links, selected-content preservation, synchronization, editable camera/audio items, and the actual seams/frames. Require zero changes to dialogue source in/out, timing, gaps, and order. Native picture subdivisions must cover exactly the original intervals. Keep all camera assets and audio items editable, with item-local native Motion/keyframes and native audio transitions; no baked composites or flattened dialogue. For key placement, retained trim handles, camera resets, and rendered seam verification, follow the owning horizontal-to-vertical skill rather than duplicating its rules here.

Prepare the existing /edit skill and its necessary sibling dependencies for the receiving editor only after a local pilot passes. Resolve machine-specific paths and required Premiere bridge setup; exclude credentials, personal data, and unrelated skills. A reusable handoff must run on the recipient's draft rather than depend on the author's project paths. Mark recipient-side execution as unverified until the editor has run it successfully.
