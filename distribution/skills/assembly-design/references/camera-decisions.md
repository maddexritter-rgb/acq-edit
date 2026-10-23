# Editable multicamera picture decisions

For scoped production guidance, → Load [the shared policy procedure](../../edit/references/scoped-brand-policy.md).
Keep `production_policy`, source-session camera exclusions, `mirror_intent`, and
selective `graphics_intent` in the existing revision-bound picture handoff.

For a mirror decision, record inspected inherited flip state, intended final state,
composed eyeline evidence and any readable-text conflict. The implementation owner
applies the difference once and reviews the final panel/full-frame picture. No flip
is implied merely by a guest camera label. `scoped_policy.camera_exclusion_matches` tests exact session/camera/media and half-open source overlap when the source map is available. An exclusion identifies source session,
camera/media, whole-source or exact half-open source tick intervals, and the actual
review reason. Map exclusions through source clocks after trims/reordering; preserve
inactive alternatives and original media. Resolve ambiguous identity from evidence.

Use after the dialogue assembly is fixed. Keep the source-linked audio continuous while making picture-only decisions. Preserve the input cut and store the camera plan separately so revisions can change picture without rebuilding dialogue.

## Coverage-first assembly handoff

For a multicamera assembly, expect **every available synchronized angle over every
selected spoken span**, not merely the camera visible in the 16:9 review picture.
Read the per-span camera media/source-frame/assembly-frame map and verify it against
native items. Missing or unsynchronized intervals are explicit coverage gaps, not
permission to fabricate frames. Assembly Design owns the proposed picture timing; explicit editor picture decisions supersede it.

Within Assembly Design, compare all usable angles at each spoken and visual
beat, then select the full-screen shots, reactions, and split intervals using the
criteria below. Keep unselected sources as inactive editable alternatives; preserve
the original sequence and the dialogue/audio tracks exactly. Build the selected
full-frame sequence and independent panel source sequences **before** invoking
the native reframing driver, which cannot interpret an overlapping camera stack.
If picture was explicitly approved, preserve the approved shot and panel intervals
instead of selecting anew. Read back every chosen camera's source/timeline frames,
split entries/exits, inactive coverage, and unchanged dialogue before reframing.

## Beat-led camera rhythm

Assembly Design authors the complete paper cut, spoken-cut decisions, and a separate
revision-bound camera/layout plan. Horizontal-to-vertical executes that plan; it does
not choose new switch moments. Apply this ownership in both execution backends.

For conversational multicamera clips, aim for varied **4–9 second visible shot holds**
where usable coverage and the exchange support it. Treat about four seconds as the
normal minimum, not a timer that triggers a cut. Switch on a completed thought,
contrast, example, useful reaction, or payoff. Consider every usable host angle and
later synchronized splits; actively seek meaningful variety rather than leaving a
long answer on one angle by default. Hold longer when an uninterrupted explanation
or payoff benefits; a short necessary speaker turn or explicit editor instruction
can justify a shorter hold. Record the reason for an exception in the picture plan.

For single-speaker explanations, plan subtle framing emphasis at meaningful words,
contrasts and the payoff. Prefer a small relative scale change with a smooth arrival
and hold; do not punch in on every card or reset zoom merely because an interval ends.
Specify the source-linked keyframe times and intent for horizontal-to-vertical to execute.

Measure holds by the visible camera/layout occurrence, not by underlying audio-cut
items: adjacent same-angle items can form one hold. Panel-only switches count as
visible changes too. Inspect proposed entry/exit frames for usable faces, sync and
continuity before rendering. Never fabricate reactions or use bad coverage to meet
a duration target. Preserve approved dialogue and caption clocks on picture-only
revisions; no recurring audit loop.

Bind each switch to exact resolved timeline frames. When it is meant to accompany
a source cut, use that cut's frame rather than an independently rounded timestamp;
reject accidental one-to-three-frame fragments of the old or next shot. Preserve
intentional short exchanges. A dialogue splice alone does not request a camera move:
do not author a pan into each new cut or reset a zoom at every paper-plan interval.

## Evidence and judgment

Use verified final exports and their contributing native controls as style references. Sequence names alone are insufficient. Exclude standalone drafts, superseded versions, unused alternatives, and analyst-created pilot decisions from evidence of the reference editor's style. If a final nests a draft-named sequence, inspect only its actual contribution to the final picture and visible motion.

When explicitly studying draft-to-final changes, use the draft as the **before-state**, not the style target. A RAW timeline may contain early stacked-camera assemblies and later finished copies; an animated item somewhere in RAW does not disqualify every earlier range. Conversely, an unkeyed item can already belong to a camera-switched assembly. Match retained source intervals and inspect the candidate's surrounding tracks, disabled states, framing, and edits. Exact camera-stack boundaries are useful structural evidence, but do not alone prove synchronization or editing chronology. Record unresolved ancestry rather than choosing the candidate that produces the most impressive delta.

Trace the full contributing chain: source assembly → inner picture cut → outer finishing sequence → verified export interval. Outer finishing can add a source-linked shot or substitute another cut version with additional framing. Do not stop at the first FINAL-named sequence, pool separate alternate assemblies, or use inner times as export times without mapping trims and offsets.

For an unswitched, unkeyed stack claim, inspect every aligned camera peer's explicit chain, not only the final's matching source or peers already filtered as unkeyed. Compare against that identified stack; a later exact finished-chain copy in RAW is not the before-state. Where no single before item contains a final source interval, check the union of retained same-media ranges. A genuine gap may be a source-handle extension or newly selected material, not missing physical footage or a reason to shift every camera's clock.

Inspect disabled camera items separately before claiming a source was absent from the draft. A disabled, unkeyed camera can already occupy the initial aligned stack and later supply final shots; record its enablement/selection change without pretending it was visible in the before-state. Keep active-stack coverage, stored source availability (including disabled alternatives), and source synchronization as separate findings. Scope effect inventories to the reconciled delivered interval, preserving source-time keys outside that interval as handles rather than counting unused alternate versions as final moves.

Treat the active speaker as a baseline candidate. A listener can be the correct picture during a joke, pointed prediction, question, or payoff if the listener's visible response adds information. Review the actual reaction around the proposed interval. A transcript or loud microphone alone cannot prove a useful reaction.

Separate coverage constraints from creative preference. A reference may use a wide shot because the close camera stopped recording, lost focus, or became obstructed. Record the observed defect or stated limitation and its evidence; do not infer a technical cause from the cut alone. Check usable synchronized coverage before proposing a reaction or split. Do not imitate a fallback's soft focus or treat its shot frequency as a style target when a cleaner appropriate angle is available.

Reference review has shown listener shots while the host continues a sentence, host reactions during a guest's joke, and brief answers delivered while picture stays on the questioner. Do not force every turn into a camera cut. Record `speaker_role` separately from `camera_role`; a reaction shot is not a diarization failure.

Record the actual `visible_participant` independently of the camera label. A guest camera may reframe onto a partner or audience addressee; its label does not establish whose reaction is visible. Review introductions, direct addresses, and responses from those additional participants. Silent gestures or repeated physical beats can motivate an angle change even when the word transcript has no event; confirm the action in footage rather than inventing a reaction from a pause.

A panel may intentionally contain multiple participants. When the exchange needs both, plan a group composition and preserve their shared framing; do not let a single-face tracker select the largest or highest-confidence face and silently crop out the other. A speaking-role change within that group does not automatically require a camera cut or reframe.

The framing target can also be an explanatory object: a whiteboard, pointing hand, phone, or demonstration. Preserve what makes the explanation legible rather than automatically recentering a face. Record `framing_target` separately from `visible_participant`; judge an object shot by its intended subject, not a face-centering score.

Classify the selected content unit, not the recording label. A self-contained host
explanation taken from a Q&A recording is answer-led when the guest's retained words
or visible reactions add no context or value. Keep that unit on the speaker rather
than adding an inert listener to satisfy the recording's format. Record the unit's
format and rationale; genuine retained question-and-answer exchanges keep the rule below.

For Q&A clips, start on synchronized split screen from frame zero: host above
guest in portrait, with both actual participants visible. Establish the question
before moving to a single. This is the opening standard, not an optional split
opportunity. A later split does not satisfy it. Set `content_format: "qa"` in the
picture plan and construction packet. Only an explicit user opening-layout override
may waive it; record that instruction in `opening_layout_override`.

If opening coverage is missing, out of focus or obstructed, search the retained
synchronized angles and report the exact coverage gap before rendering. Do not
silently replace the opening with a single, borrow later guest frames, freeze a
reaction, or alter approved dialogue to manufacture coverage. A coverage problem
remains unresolved until real usable picture or an explicit user choice resolves it.

Beyond the opening, choose split screen when sustained simultaneous visibility helps
the exchange: a consequential explanation directed at the guest or useful listening
behavior. End a split when the focus belongs to one participant. Later split timing
remains an editorial choice grounded in the footage.

Plan each panel independently. A speaker addressing the room may justify changing only the listener panel from guest to audience, then returning it when the exchange resumes. Verify the addressee and useful response in footage; do not treat every split as a permanently fixed pair. Keep panel source selection, crop, and item-local motion separately editable. A panel's framing curve is not automatically suitable for that source's full-frame shot.

Do not activate split screen because a segment exceeds a fixed duration. Do not alternate host angles at every source seam by default. For each switch, ask whether it reveals a speaker or reaction, follows a meaningful beat, improves framing, or conceals a visible same-camera edit. Holding the current angle is valid when none applies.

Protect purposeful short exchanges from blanket minimum-shot cleanup. A brief clarification, its answer, and a follow-up can justify successive sub-second shots, while the developed explanation immediately afterward may call for one sustained split. Verify each short shot against the visible exchange; this is not permission to retain low-confidence microphone-driven chatter. Judge rhythm within the conversational passage, not by a single duration threshold for the whole clip.

## Reviewable camera plan

For each interval record exact frame bounds, source mapping, visible camera/panel roles, spoken role where known, the editorial reason, and confidence/evidence. Protect deliberate reactions and human decisions from duration cleanup. Unknown decisions remain review candidates; unverified reactions must not be described as reference-matched.

Separate `observed_picture`, `inferred_editorial_reason`, and `coverage_constraint` in the decision evidence. A same-speaker angle change at an analogy, new premise, or concluding challenge can support the thought structure; it is not a mandatory switch at every rhetorical marker. A developed explanation may benefit from a sustained shot. Review the surrounding exchange before adding a cut.

Classify source-item subdivision, same-camera content seam, camera/participant change, and layout change separately. Identical camera labels—and even the same media file—can show different participants. An item boundary can also preserve continuous source action without any visible cut. Use boundary pictures plus source mapping; do not learn switching cadence from raw item counts or caption changes.

Keep opening, reaction, split, same-speaker angle change, and closing decisions individually adjustable. Build native panels from source-linked clips/nests with editable crop and Motion. Apply item-local framing only after the final picture subdivisions exist. Preserve a comparison sequence and the frozen pre-review plan so correction effort can be measured.

## Comparison and acceptance

If the draft and reference differ in length or order, compare matching speech/source moments. Validate local audio-match candidates visually; do not apply one global offset across dialogue edits or reordered passages. Distinguish missing content from unresolved alignment.

Inspect speaker/listener choice, split entry/exit, shot size, headroom, audience intrusion, movement timing, and seam stability independently. Passing keyframe numerics does not establish camera judgment. Report corrections per decision and the kinds of changes required, then test the updated reasoning on material whose camera reference has not been used to design its plan.

These are evidence-informed editorial prompts. Reference-level autonomous camera selection remains unproven until rendered comparisons and held-out correction review pass.

## Deliberate motion versus corrective tracking

Decide the shot's motion before fitting keys. A stable composition can hold; do not turn every detected body sway into a camera move. For a needed move, record the visual reason, the first/last **visible** frame, the hold before it, its destination, and how it settles. Examples of reasons are following real travel, retaining a gesture, restoring headroom, or a deliberate shot-size change. Keep tracking correction distinct from an authored zoom or pan so a revision can change either decision.

Plan hold, movement and settle independently for each participating control. Scale and Anchor Point can begin together yet finish at different times; a later correction need not span the whole shot. Preserve those differences rather than stretching all curves between one shared start/end pair. Likewise, a panel's source-selection change and the other panel's later framing correction are separate decisions, not automatically one coordinated animation.

Reference curves can be linear, slow-starting, slow-settling, or multi-stage; do not apply one easing preset to every item. Two endpoint values do not describe the path. Evaluate native values at intermediate times and inspect rendered movement. A middle key need not be a local maximum/minimum: tangent continuity can carry a curve beyond it before returning. Reject **unplanned** overshoot against the intended path, not every overshoot found in a reference. Treat preservation of an authored curve separately from recreating a measured linear tracking curve.

Equal-valued keys do not by themselves prove a hold: their tangents can still produce intervening movement. Preserve complete serialized key/interpolation data when carrying an approved curve, then verify native samples between keys. When reusing measurements from an isolated copy, reconcile exact source/timeline spans, parameter keys and the surrounding effect chain to the original; report the measurement's scope. Intrinsic Scale samples do not evaluate a separate animated Transform or establish the net visible crop.

Distinguish digital framing from source motion: a subject turning, leaning, or moving toward the camera changes the face box without a native zoom. Compare Motion values and stable scene features as well as the face. Express relative zoom as `end_scale / start_scale - 1`; a change in Scale percentage points is not the same relative magnification.

When studying a final, trace through finishing nests to the source-item Motion, exclude adjustment layers from picture selection, and keep unknown source labels explicit. Compare key timing with actual visibility: source-item handles can extend beneath another angle, so keys before an item's visible entry do not prove a visible lead-in hold. Preserve native temporal/spatial interpolation when carrying an approved move into a working copy; changing the key times/values alone is not a faithful copy.

Motion is not the whole framing system. Inspect explicit Transform effects as well as intrinsic Motion, in their native order, on source clips and contributing nests. Multiple enabled Transform instances can animate Anchor Point alongside an intrinsic Scale move. Preserve their separate controls, instance identities, bypass states, parameter values and interpolation; do not collapse them into a guessed Position curve or apply the same preset twice merely because a nested item has two timeline occurrences. Verify the composed picture before attributing a visible move to one component.

An intrinsic-Motion-only test cannot certify an unkeyed before-state. Check other component parameters, opacity, stabilization, static flips/crops and parent processing. Explicit default Motion/Opacity flags explain omitted intrinsic parameter blocks but do not establish numerical values or absence of added effects. Missing bypass metadata is unknown, not proof of an enabled effect. A single serialized key or a time-varying flag alone is not evidence of changing visible framing. Label partial audits by their scope and retain unresolved effects for native inspection.

Record underlying item bounds, visible bounds, and key times independently. A short reframe may begin exactly when a covering split ends; a final key may lie just after another camera becomes visible. Preserve necessary handles rather than moving the cut to reach the endpoint. Opening panels can deliberately zoom out while reframing laterally; neither motion direction nor key density is a universal emphasis rule. Count reused nested occurrences separately from distinct authored curves when reporting evidence.

The reconstruction check is both visual and editable: test a trim and a framing revision in an isolated sequence, confirm media-time keys remain attached to the intended source frames, and verify that no global tracking curve or flattened render replaces those per-item controls. Keep the untouched reference and a before/after comparison.

## Required ownership and eligibility

Assembly Design owns the shot and layout choices alongside the resolved spoken edit.
The finishing skill implements these decisions; it must return an unusable interval
to Assembly Design rather than silently substitute a camera or layout. This applies
to both Filmcraft and Premiere Agent Lab. Explicit human choices take precedence.

For each spoken beat, consider speaker full-frame, listener full-frame and a
synchronized split. Record whether simultaneous visibility adds information; do not
require splits or extra camera angles merely for variety. In portrait two-person
Q&A, default an intended split to host above guest unless the user or format specifies
otherwise. A camera facing the speaker's back is not eligible as a dialogue shot
merely because it is synchronized. Reject wrong participants, obscured faces, lost
focus and missing panel coverage; an explicit demonstration/object shot needs its
own visible purpose. Retain rejected angles as inactive source coverage. A sliver of profile is not enough
when the face and expression read worse than the front angle in the intended crop.
Treat an editor-rejected angle as ineligible for that interaction unless newly inspected
coverage or an explicit request changes the decision; vary usable framing and split
layouts instead of forcing a side shot to satisfy cadence.

Pin the spoken-selection revision. Each occurrence carries stable ID, exact timeline
frames, layout (single/split), panel roles and independent source mappings, visible
participant, observed picture, editorial reason, and usability evidence. Record split
opportunities and the reason for using or declining them. Dialogue revisions require
remapping picture and captions; picture-only revisions preserve audio samples.

Before export verify complete plan coverage, both split sources at the same session
clock, no duplicate dialogue audio, and rendered first/middle/last frames and layout
boundaries. This is construction checking, not a recurring audit or human approval.

Resolve nearby source-edit and layout boundaries together on the actual frame grid.
Do not leave a source change visible for one or two frames immediately before a
layout change, or a new layout visible for one frame before another source jump.
Choose one intentional picture boundary, bind the updated plan to the unchanged
spoken edit, and preserve audio samples. Source-continuous subdivisions keep their
crop and zoom progression; a paper-plan beat alone must not reset the composition.
