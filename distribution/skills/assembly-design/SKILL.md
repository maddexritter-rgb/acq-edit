---
name: assembly-design
description: Design exact source-word clips and place source-linked 16:9 assembly cuts in Premiere or Filmcraft for editor review. Own moment selection, interior edits, frame-boundary resolution, camera/layout decisions, and timeline construction; use directly or through edit for new or explicitly recut assemblies.
---

# Assembly design

## Scoped production guidance

→ Load [scoped production policy](../edit/references/scoped-brand-policy.md), including on direct invocation; apply the `assembly` stage while choosing words and picture.
Preserve its production identity on answer-only units and pin the applicable policy in the existing selection/picture handoff.

For any Premiere access, follow [Premiere Agent startup and advanced stage routing](../edit/references/premiere_start_here.md). Use the configured new bridge by default; if MCP tools are missing in this chat, use its CLI. Keep this skill’s existing creative scope and read-only limits.


Own the complete first assembly pass, from editorial construction to a playable
source-linked 16:9 timeline in the selected backend. Use the active editing agent;
no provider-specific model calls. Curating or promoting memory is outside this
capability, but retrieving relevant decision precedents is part of design.

**Default creative ownership:** the main session owns moment selection, competing
hooks, exact source-word restructuring, both tightening passes and the final joined
dialogue review. Do not delegate these decisions unless the user explicitly requests
it. Delegated proposals still require this source-grounded design pass; a plausible
summary or successful compiler run is not an accepted clip.

When asked to improve or benchmark this capability, use
[evaluation.md](references/evaluation.md) for source-held-out editorial comparisons.
→ Use skill: `editorial-brain-ingest` for publishing sources, decisions, and actual
editor feedback to Supabase; do not create a second knowledge store in this skill.

When revising a reviewed batch, read [marker-driven revisions](references/marker-revisions.md).
It owns complete note accounting, review-state comparison and preservation of accepted work.


## Default construction and timing

Follow [pre-render construction](references/pre-render-construction.md) before final
export. Inspect source evidence and fix decisions while constructing the clip; do not
render first and run a chain of model audits. This default supersedes older blanket
audition/ASR mandates in the references below. Independent reviewers, scorecards and
whole-batch listening loops are optional strict evaluation only when requested.
Retain targeted inspection for genuinely ambiguous or user-rejected edges.
For direct invocation as well as `/edit`, initialize the [run clock](../edit/references/timed-execution.md)
before further skill reading or setup; reuse an existing parent run clock.

## Waveform-first cutting — default for every spoken assembly

→ Follow [audio-precision.md](references/audio-precision.md) before construction.
AssemblyAI locates the words; inspect locally decoded waveform/spectrogram evidence
for every selected edge and suspicious interior pause, then resolve both sides of
each join together. This is the normal path for new cuts, not a repair-only option.
Use the same resolved decisions in Premiere and Filmcraft; never fall back to
ASR-only cuts because a backend differs or a remote listener is unavailable.
For source-fused speech, preserve the smallest complete spoken phrase rather than
forcing an isolated-word edit; follow [assembly boundaries](references/assembly-boundaries.md).

**Evidence stack, read before cutting.** Each source answers a different question:
AssemblyAI says *what* was said and by whom; MFA + the waveform say *where* each sound is
(the only authority for cut points and word endings); Gemini says *how* it sounds;
local Whisper is a second transcript. Once per source, build the per-word table
(`scripts/word_evidence.py build --words ... --audio ... --delivery-map ... --out ...`).
Before each paper cut, read `scripts/word_evidence.py view <table> <first> <last>`: it
marks clean (`‖`) and tight (`¦`) cut points and lists Gemini's stumbles, real fillers,
crosstalk, emphasis and swallowed words. Use it to choose words (skip the stumbled take,
never build a join on crosstalk or a phantom word, keep the emphasized line).
Draft the join windows with `scripts/seam_windows.py decide ... --out ... --bounds-out ...`
(MFA edges, quietest 5 ms points; `peek` shows a flagged edge's waveform) and pass the
bounds to `pair_audio_seams.py --phonemes` so squeezed ASR labels defer to MFA.

After `pair_audio_seams.py`, before building, run the **measured join check**
(`scripts/join_check.py --paired ... --selection ... --clip-id ... --words ... --audio
... --cache-dir ... --out ...`). It aligns every edge word with MFA on the intact phrase
and refuses a cut inside a kept word (start or end) or one that leaks an audible slice of
a removed word. Repair each blocking edge with the paired-seam method or a word revision,
or accept it with `--accept EDGE:reason` when the editor wants it. Listener models miss
clipped word endings (2026-10-15 controls), so endings are judged only here. In stutters
and crosstalk ("it's, uh, it's", "what, and what's") both ASR and MFA can point at the
wrong occurrence, and either one can be the wrong one: such edges block as
`LOCATORS_DISAGREE` until resolved from the waveform or a third transcript (find the actual
silence before the kept onset) and accepted with that evidence. Where the
words run together with no silence, keep the source phrase whole instead of cutting it.

Then, optionally, `scripts/gemini_seams.py` once per clip: one call on at most five risky
joins rendered as they will play. Act on every positive finding (leaked syllable,
clipped word, duplicate, breath/click): re-inspect that join's waveform, fix it, rebuild
and re-check once. On a 2026-10-15 hotline these flags caught a leaked "and", a clipped
"two" and a fused "now|you're" that measurement alone passed. A "clean" answer is
recorded as not flagged and is never proof. Before
captions, `scripts/word_evidence.py check-kept <table> --selection ... --clip-id ...`
lists every kept word where AssemblyAI and Whisper disagree, with Gemini's A/B vote. These
are words to verify by ear; votes never rewrite caption text (Gemini's choice flipped
between runs on the same words). Gemini runs a fallback chain (`gemini-4-argon`, then
`gemini-3.8-flash`, then `gemini-3.1-pro-preview`), moving on only when a model is busy;
none is a qualified acceptance listener. If Gemini is `UNAVAILABLE`, record it and
continue on the local evidence; never rerun unchanged evidence for a different answer.

## Requested anonymization

When the editor requests a name or identifying phrase be concealed, preserve the
source transcript and define one source-word-linked redaction in the assembly plan:
source occurrence, resolved output sample interval, supported role label, and the
editor’s request. Keep the role context intelligible; do not invent a relationship.
→ Follow [audio redaction](references/audio-redaction.md) for execution and the
caption handoff. Do not anonymize every name by default.

## Native bridge execution

Select the backend through [execution backends](../edit/references/execution-backends.md).
For Filmcraft, follow [Filmcraft execution](../edit/references/filmcraft.md) and use
`scripts/apply_filmcraft_assembly.py`; the Premiere-specific instructions below apply
only to Premiere. Backend choice changes execution, not selected words or acoustic
review. Direct assembly-design use ends at the review assembly; `/edit` may continue
an explicitly authorized end-to-end run through the other owning skills.


Before native construction, follow the [shared execution contract](../edit/references/premiere_execution_contract.md) using the compiled source-word packet already owned here.
Verify exact source/timeline ticks, playback order, intentional gaps and paired audio/video; report native link-group membership separately from matching ranges, and retain the existing seam audition.
Plan equality alone is insufficient: run the final picture-continuity audit described in
[audio-precision.md](references/audio-precision.md) on every clip, including preserved
clips. It checks sequence-frame alignment, picture coverage and linked source clocks.
Use `scripts/apply_native_assembly.py` on the default Premiere Agent profile. It consumes the original resolved v2 compiler chain and XML receipt, verifies native linked pairs, and records a creation handoff. Prepare the exact assembly input scope from the startup guide; do not substitute a generic import or raw mailbox script. Bounded fixture acceptance does not certify the current source/channel layout: inspect native linkage and audition the joined dialogue on each actual assembly.

Run the cached local pre-build triage in [audio-precision.md](references/audio-precision.md#fast-local-pre-build-triage) before construction; resolve ambiguous contexts through its paired-seam method. Timestamp proposals alone are not finished cuts.

For new spoken assemblies as well as precision repairs, follow
[audio-precision.md](references/audio-precision.md) by default:
prepare matched-rate PCM, resolve audio independently of picture frames, and pass
`--audio-plan` through the native importer for exact sample/tick execution.
Pin the actual played channel before analysis. The same reference owns seam repair,
deliberate picture/audio pause compression, and full-assembly audition; successful
native placement alone does not complete those steps.
Establish the correct source occurrence before refining timestamps: inspect the
intact phrase and unchanged neighboring words, and validate any local timing patch
using the occurrence procedure in that reference. Forced alignment can fit the
right text to the wrong sound; it is not listening proof.
For dialogue cleanup, use its **paired-seam construction method**: inspect full local
phonemes including excluded neighbors, choose both sides of each join together,
then compile continuous audio with `scripts/pair_audio_seams.py`. Do not independently
trim each audio item inward from rounded picture cuts and leave accidental gaps.
Inspect every selected head/tail and suspicious interior pause, not only edges a
timestamp heuristic flags. Its inspection helper prepares waveform/phoneme evidence;
the editor must examine it and choose the acoustic windows. If the verified channel,
supported sample grid or native precision route is unavailable, preserve a clearly
provisional review assembly rather than silently reverting to timestamp-only cuts.
Only claim acoustic completion when actual listening evidence exists. The executable
[seam audition loop](references/seam-audition.md) is available for explicitly requested
strict listening evaluation, not an automatic normal-run stage. A successful import or missing listening service
does not waive this completion requirement. Keep review timelines flat and directly
editable; ranking clips does not justify nesting their underlying cuts.
That reference also owns the Gemini audio-review runner, preferred evaluation
model, local paid/fallback credentials, and early reporting of quality blockers.

## Default: construct clips for the editor's 16:9 timeline

**Mandatory editorial-brain preflight.** Before selecting moments or designing new
spoken cuts, → Use skill: `find-precedents` in its live preflight mode.
Execute its [live CLI commands](../find-precedents/references/assembly-cards.md)
with a new `--out` path **for each clip** and set that clip's `brain_preflight` to it.
The compiler refuses a new v2 clip without its own receipt, one fetched more than six
hours earlier, or one already used to design a different clip. Merely reading
this instruction or naming the tool does not establish a live connection. Read
the active universal and moment-format playbooks **and every full source body in the
required universal, format, and applicable overlay packs**. Classify the content
unit, not the recording; add the L1 overlay for owner-diagnosis Q&A and the Workshop
overlay for Workshop-style clips. **Re-run the preflight and re-read every pack in full
immediately before designing each clip**, whether it is a single clip or one of a
batch, and whether or not context was compacted. Never rely on an earlier read or a
summary of one. A missing connection, wrong project, missing
playbook or required document, or body-hash mismatch is `EDITORIAL_BRAIN_UNAVAILABLE`: stop new
assembly design and report the exact problem. Do not substitute cached/local guidance
or call a thin-context cut complete. This is a knowledge-availability guard, **not** an
editorial audit or approval gate. Existing approved timelines are unaffected.

**Required payoff construction.** Read the full live **Payoff construction** guide
and **Payoff source reader** in every clip's universal required-reading pack before
choosing words. Apply their source-word payoff pass within the existing
`editorial_intent`; they own the detailed method, not a separate audit or approval gate.

Read [assembly-boundaries.md](references/assembly-boundaries.md) and the retained
[Clip Cutting Playbook](references/CLIP_CUTTING_PLAYBOOK.md) before constructing
cuts. The boundary reference identifies which parts of the historical playbook
govern this assembly route. Before word selection, inspect the complete source
interaction with its disfluencies, neighboring excluded words, pauses, and
targeted performance evidence from `scripts/candidate_performance.py`; verify
uncertain acoustic or picture events against the relevant source region. Do not
frame-resolve the entire recording or hash a large stable media copy per clip.
Pass ingest's validated `media_identity.vN.json` to the probe with
`--media-identity` when available; it reuses that copy's digest after path/size
validation. Never claim this targeted map certifies frame-accurate word edges.

Read each promising interaction through its actual conclusion. Then design a *new spoken
playback*: choose the source-word hook (or necessary question), the reasoning/story that
keeps the viewer engaged, and the earned payoff. Work backward from the payoff. Remove
false starts, repetition, detours, redundant examples and wind-downs while preserving
context and truth. Write the exact kept source-word spans in playback order and read
their joined dialogue as a clip before resolving frames. A complete source exchange
is not automatically a complete edited clip. A candidate row, topic label, start/end
window, or outer-edge-only cut is not a design.

**Full-source coverage and independence.** Identify every distinct complete content
unit in each authorized recording and disposition each as selected, source-incomplete,
out of the requested topic scope, or editorially weak, with a concrete source-based
reason. Evaluate each interaction on its own merits: a clip from another recording
teaching a similar lesson is not a reason to reject a complete interaction here.
Distinct useful arcs within one interaction may become separate clips. Do not impose
a clip-count or duration quota. If a long passage needs few internal edits, explain
which exact interior material was examined and why it all earns the payoff. A
publication fact-check concern does not exclude an otherwise source-faithful assembly:
mark the claim `FACT_CHECK_BEFORE_PUBLICATION` for the editor, without presenting it
as verified advice. Withhold only when the source itself cannot support a truthful
clip or the user's content scope excludes it.

**Develop before tightening.** Follow [development before tightening](references/profiles.md#development-before-tightening) in the normal design pass. Hook, development and payoff are functions, not one sentence each; the noisy-bar sentence summarizes the takeaway, not the amount of dialogue to retain.

**Default paper cut for every new assembly.** Work on one complete interaction at a
time, not a batch of topic windows. Display its source word IDs, literal words,
speaker IDs/roles, and word times; inspect gaps and targeted performance evidence.
Mark the entire interaction in source order as `KEEP` and `CUT` word ranges. Split
decisions where the speaker or editorial function changes, including the question,
answer, examples, corrections, and coda. Every `CUT` range needs a concrete reason;
do not fabricate reasons after choosing broad in/out points. The model owns these
marks. Code only reconstructs them. Map local diarization IDs to roles (for
example, questioner and answerer) before choosing the opening and payoff; chunk
speaker letters are not globally stable identities. A questioner restating the
answer is not the answerer's earned payoff by default.
Map identities within each source interaction using actual conversational or audiovisual
evidence; never assign one recording-wide A/B dictionary to every selected unit. When
the brief requires a particular speaker, verify that speaker supplies the intended
substance. Necessary interviewer context remains available.

Use `edit.assembly-selection/v2` for the new paper-cut artifact. Each clip keeps
the existing source, interaction, hook/reasoning/payoff and intent fields, and adds
`paper_cut: [{"word_range":[first,last],"action":"KEEP"|"CUT",
"reason":"..."}]` covering every source word in the complete interaction without
gaps or overlap. `kept_word_ranges` may specify playback order when rearranging;
otherwise the compiler derives source-order KEEP spans. Add `speaker_roles` keyed
by the exact source speaker IDs and `payoff_speaker` equal to the last selected
word's speaker ID. A questioner ending needs `questioner_payoff_reason`; if it is
merely an echo or new tangent, cut it and end on the actual payoff. List every
unavoidable retained `um`, `uh`, `ah`, `erm`, or `hmm` as
`retained_fillers: [{"word_index":N,"reason":"..."}]`; an opening on one of
those words is never a designed hook. An opening `so`, `well`, `and`, or `but`
requires `opening_connective_reason` explaining why that exact connective is
part of the hook, not merely a leftover lead-in. Do not keep an unhelpful filler just because
its boundary is fused: choose another grammatical phrase, or leave the local edge
unresolved for editor review. Existing v1 designs remain readable for historical
replay, but do not use v1 for a newly designed clip.

For a clean-room rebuild, treat only explicitly allowlisted original media and
neutral ingest artifacts as input. Prior selections, design scripts, coverage
dispositions, compiled/resolved cuts, and timeline handoffs are not source
evidence. If one enters the new design context, invalidate that design and restart
it from a clean context; compare old and new only after the new selections freeze.

Before each design pass, read [profiles.md](references/profiles.md) for the interaction's
actual format, including its two tightening passes. Record the meaningful second-pass
deletions and retained essentials in `editorial_intent`; do not just restate that the
clip is concise. The live playbook governs conflicts in preserved source SOPs; these
local references are supporting context, not a fallback for a missing live pack.
For L1/Q&A, use [editorial-precedents.md](references/editorial-precedents.md) to open
matching evidence cases when relevant; preserve their confidence levels. For other
formats, load only relevant precedents, not the entire corpus.

**Required Q&A editorial reading.** The live Q&A pack includes the full canonical
CLIPPER prompt, Q&A master SOP, and worked examples; the L1 overlay adds its own
guidance only for owner diagnosis. Apply the payoff-backward method to the complete
interaction: compare viable promises, preserve necessary question/diagnosis context,
make exact KEEP/REMOVE/TRIM decisions through the interior, then cold-read and tighten
the joined playback. Do not copy a worked example's hook or treat it as a verified
historical final. Old fixed duration, money-hook, host-entry, scoring, audit, and
finishing instructions inside source SOPs do not override this editor-first route.
If a Q&A answer seems self-contained, compare its literal first sentence with the
speaker's actual question. Keep the shortest source-faithful question that supplies
the viewer's problem, condition, or stakes; answer-first is a deliberate exception,
not a default way to remove the guest. Honor the editor's feedback on a specific
interaction before reusing an answer-first design.
In `editorial_intent`, record the live policy versions and source-body hashes and a
concrete source-word choice each relevant reading changed or failed to change.

After reading the complete interaction, use the same live context interface with the
actual editorial problem. Read up to five relevant, cited decisions and their exceptions;
zero honest matches is valid. Apply or reject each against this source. Record the live
playbook versions/hashes and any concrete card influence in the selection's
`editorial_intent` and [decision receipt](references/editorial-memory.md). Retrieval
is not a cut generator and adds no independent review gate.

Record the selected arc and paper cut in `edit.assembly-selection/v2` as above.
Compile it with `edit/scripts/compile_assembly.py`.
That code reconstructs the literal playback and beat text from the pinned source words.
Read the *actual joined dialogue* **and the first/last speaker receipt** before
resolving frames. Confirm the opening starts on the intended first spoken word,
the answer develops the promise, and the ending belongs to that arc. At each reordered
beat, use only information already heard in the clip: identify who each pronoun refers
to, what each number measures, and which process or question is being discussed.
An explanation later in the clip cannot repair an unintelligible first mention.
For the proposed ending, name the question it answers and compare the next source
clause: a grammatically complete sentence can still be the introduction to the payoff.
Keep a strong body when only its opening or ending fails. Compare
the claimed editorial intent with the literal kept words; if an intended aside
or filler is still present, fix the paper cut. Revise the selection when its
opening, transition or ending is weak. Read the compiler's
`omitted_source_continuation` through the interaction handoff before accepting
any ending; name the best later payoff or condition and why it is kept or
excluded. This is a design choice, not a new audit or approval gate. Do not
author a separate topic-window
manifest for timeline placement. If one uncut span genuinely works, explain why its interior has no removable
setup, repetition, detour or tail. One-span clips are possible, not the batch default;
if most selections are broad continuous excerpts, stop and redesign before building
more. Resolve the compiled selection and every intended internal edit against
the **played dialogue source**, following
[assembly-boundaries.md](references/assembly-boundaries.md). Reuse or make one
AssemblyAI map of that exact audio clock; align the selected words to it, then
use `scripts/played_audio_edges.py` for initial source-frame proposals. These are
locators, not final cuts. Follow the default paired-seam method in
[audio-precision.md](references/audio-precision.md) to inspect all selected edges,
adjacent excluded words and retained-span pauses against the played audio; use a
local independent alignment when useful. Keep all
selected speech; mark unresolved fused edges `PROVISIONAL_SEAM`. The older
`scripts/resolve_review_edges.py` speech-map/RMS route remains available for
strict or fallback diagnostics, but its 45/60 ms clearances are **not** the
default boundary decision for a new review assembly. Never delete a selected
explanation, example, question, or payoff merely to obtain a tool exit 0;
never run a batch-wide `reduce_fused`-style rewrite. If the literal playback
itself is weak, deliberately redesign from the full interaction, recompile,
and compare revisions. A local seam can also be moved to a better source-native
phrase or merged through connective speech, but changed words belong to the
model's design pass.
One unresolved seam does not stall the batch, but it is not a completed precision
cut. Attempt a bounded local repair and supply its exact source frames and playable
seam evidence; keep unresolved edits visibly provisional in the handoff. Never
describe a batch as audio-verified because its word map or native readback passed.
The XML builder takes only the
resolved selection, never a raw window. Use
`../edit/RUNBOOK.md` to build, save, reopen, and read back the source-linked
V1/A1 timeline. Assembly Design owns this handoff even when invoked directly.
For every **new** clip handed to a separate Premiere writer, deliver the exact
`edit.assembly-selection/v2` file and its pinned source, compiled literal playback
and omitted continuation receipt, and resolved frame file. The writer must verify
that chain before placement and reject custom span-only, v1, or raw in/out packets;
it must not infer an edit from a topic description or historical timeline. The
writer's check is technical provenance, not an independent editorial review.
No worksheet, design comparison, audit,
independent review, scoring gate, or final editorial PASS is required for this default
route. AssemblyAI word times are locators, not certified edit frames.

When a selection is recompiled after a boundary conflict or editorial change, save
the changed design at a new revision path and run
`scripts/compare_assembly_revisions.py <prior-compiled.json> <new-compiled.json> --out <revision-diff.json>`
before native placement. A flagged opening, hook, payoff, removed selected words,
or in-place source change
requires reading both literal playbacks and recording why the new source-word choice
is intentional; a boundary-only repair cannot silently drop the prior question,
reasoning, example, or promise. If the sole reason for removal is a refused seam,
keep the original paper cut and place a marked provisional edit instead. The diff
is a mechanical regression notice, not an editorial verdict or another approval gate.

The evidence-heavy workflow below is optional strict mode, used only when specifically
requested. It must not delay or block the default 16:9 assembly timeline.

**Strict-mode rollout only.** Human editorial acceptance
remains a separate gate, and a saved native timeline is not approval. Do not retrofit
approved timelines or migrate historical plans.

Read [contract.md](references/contract.md) and
[the editorial worksheet contract](references/editorial-worksheet.md) before authoring
or compiling a plan. The worksheet is the editorial thinking; the plan is its execution
receipt. Read
[`audit-script`'s content-unit rubric](../audit-script/references/content_unit_review.md)
before designing: its seven hook-retain-reward criteria are the shared editorial lens,
not merely a downstream audit. For a
batch, mixed workshop/event source, or a retry after weak clip construction, also read
[editorial-calibration.md](references/editorial-calibration.md) before designing.
For workshop/event calibration or L1 diagnosis, read
[editorial-precedents.md](references/editorial-precedents.md) and load only the relevant
evidence cases. Precedents inform a decision; they do not dictate a beat pattern.

Design from the verified complete interaction and targeted performance map. Use
source listening during design when wording, attribution, a pause, reaction or
performed ending changes the editorial decision. Run the one independent v4 review on the
resolved, reconciled words. AssemblyAI word times locate selected
phrases; they are not certified frame boundaries. See the contract for the staged handoff.

## The editorial pass comes before the plan

For every candidate, author `editorial_worksheet.json` from the complete interaction.
Inventory all branches and late facts, rank every viable promise, choose the strongest
complete viewer promise, choose its source-supported payoff, then work backward through
the reasoning/story that earns it. Only after reading the exact proposed playback dialogue
cold may you author `assembly_plan.json` and `design_comparison.json`.

Do not begin with a candidate window, title or hook and search for enough adjacent words
to make it look complete. A surprising datum is setup until the viewer learns what it
means or what to do. A clean answer is not automatically the most valuable answer. The
smallest complete unit means the smallest version of the strongest useful promise.

## Editorial judgment is not batch generation

Design from dialogue, not timestamps. An in/out window, topic label, or candidate row is
only a search lead. Before selecting boundaries, write the unedited candidate dialogue,
identify the exact spoken hook and payoff, then work backward through the reasoning,
story or exchange that earns the payoff. Only after that may words be mapped to time.

Do not programmatically generate plan prose, diagnosis fields, design comparisons or
editorial reviews. Code may retrieve source words, calculate omissions, pin hashes and
validate evidence; it may not decide what the hook, retention path, payoff or best
arrangement is. Work in bounded editorial passes of at most five candidates so each
complete interaction is actually read and compared. Mechanical compile/cut work may be
batched after those individual decisions exist.

Internal cuts are an outcome, not a quota. A clean source passage may remain contiguous,
but a one-span assembly must prove that the source already delivers the strongest clean
hook -> retention -> payoff and that no filler, restart, repetition, detour, weak setup or
trailing tail should be removed. Across a large batch, a sudden collapse into mostly
single in/out ranges is a regression signal requiring redesign, not evidence that dozens
of raw passages all happened to be clean.

## Scope one clip before constructing it

Choose one coherent viewer promise and preserve what earns it. Several examples may be
necessary to explain a distinction, establish a pattern or resolve a diagnosis; remove
an example when it repeats value, not merely because it is a second example. Independent
complete propositions can become additional candidates, not incomplete fragments.

Keep complete interaction context separate from the selected output unit. Never narrow
`interaction_words` to hide omitted qualifications or make a ratio look better. A clean
scripted take can use the entire source and remain contiguous. A long conversation may
need extensive restructuring. Neither retention ratio, duration nor cut count establishes
whether the design works. Inspect actual dialogue and performance.

Duration is a **symptom of scope, never a constraint on it.** Do not adopt a target length
or trim words to reach one. A clip running far past what its format normally needs is a
prompt to re-examine scope — usually several illustrations packed into one unit — not a
reason to cut the reasoning that earns its payoff. Correctly scoped units land where they
land: some formats resolve in well under a minute, and a diagnosis or a layered story
legitimately runs longer.

## Construct the idea

1. Read the complete source transcript, in bounded windows if necessary. Record actual
   read ranges and all useful ideas in the existing `/edit` coverage ledger. Mark gaps
   honestly. Candidate discovery is not assembly design. Read beyond each proposed end
   through the answer's completion and any correction/retraction.
2. Classify **moments**, not files. A podcast can contain Q&A, monologue, diagnosis and
   story. Combine applicable principles; camera count and delivery format are metadata.
   Read [profiles.md](references/profiles.md) for the relevant interactions.
   Brand identity is not a speaker-exclusion instruction. Recover all necessary guest
   dialogue across synchronized sources before designing shots. An unavailable guest
   angle is a picture-coverage issue, not permission to remove the spoken question.
3. Define the viewer, specific promise and source-supported payoff. Find the best spoken
   hook for that promise, then construct the explanation, mechanism or story that earns
   it. Preserve what makes the idea useful, including qualifications and counterexamples.
   A hook is a spoken promise, not an overlay compensating for a weak opening. Explicitly
   judge all seven shared content-unit criteria: content unit, hook/promise, retain,
   reward/promise match, goodwill, value compression, and audience-growth rationale.
   A clip with a strong topic but no usable reward, or a complete answer with no reason
   for a cold viewer to continue, is not a designed clip.
4. Write exact source-indexed selections in **playback order**. Internally remove genuine
   repetition, false starts, tangents and unhelpful hesitation. Keep meaningful contrast,
   emotion, deliberate pauses and connective words where they carry meaning. Do not
   rewrite speech, manufacture agreement, or join different claims into a stronger one.
5. Compare a faithful arrangement with a more aggressive rearrangement when they offer
   a meaningful choice. Both may contain many internal cuts. If no useful alternative
   exists, explain why; do not create a ceremonial duplicate. Judge the actual assembled
   dialogue, not the idea's title. No forced first/last source selection, keep percentage,
   duration floor, minimum span size or cut-count target. These ban *quotas imposed on a
   unit* — they do not say the unit itself is unbounded. Scope still governs: see "Scope one
   clip before constructing it" above.
6. Audit every jump for referents, speaker identity, chronology, conditions, causal links
   and changing knowledge. Inventory substantive omitted branches. Retain qualifications
   or explicitly narrow the spoken claim using actual source words. A compelling but
   misleading edit is rejected. Read the proposed assembly cold, then against source.

End at the earliest complete source-supported payoff after preserving consequential qualifications. Remove a later restatement or wind-down when it adds no new value; do not append a second conclusion simply because it sounds like an ending.

## Opening and cleanup acceptance

Check the opening for repeated **meaning**, not only duplicated words. Read the
question/setup as a cold viewer: retain each problem, condition and necessary fact
once; remove paraphrases that restate the same premise without changing the answer.
A fluent hook can still be repetitive. Name what each retained setup sentence adds
before handing off the selected words. A difficult acoustic boundary is not a reason
to retain redundant setup silently: resolve it in the played audio, or return the
specific unresolved join for review while preserving the tighter editorial intent.


The quoted hook must begin at the actual first selected word and follow playback order.
Do not credit a strong sentence later in the clip while retaining housekeeping, lesson
numbering or a restart ahead of it. Necessary question context may itself be the hook;
the independent reviewer judges the literal opening, not a title or the builder's summary.

Review the whole audible assembly for removable hesitation, repeated setup, misstarts,
redundant diagnostic loops and wind-downs, not only the seams. Apply the
selected-word and boundary method in [assembly-boundaries.md](references/assembly-boundaries.md).
Edge safety does not certify interior pacing. Keep meaningful performance,
but explicitly justify it from audio instead of calling an unpolished passage complete.
If a shorter design fails acoustically, compare the changed spoken edit against its
original promise and removals. Restored junk means redesign or hold—not a broad-span PASS.

### Ambiguous word releases

ASR end timestamps are locators, not phonetic release boundaries. If a proposed
out-point intersects a voiced envelope or the following word is fused, inspect the
intact source phrase and resolve that particular edge before committing it. A fixed
padding amount, a low-energy sample, or a successful waveform export does not prove
a complete word. If targeted listening is unavailable, retain a known-clean source
boundary or present a clearly labeled short boundary comparison; do not silently
ship the uncertain tight cut as fixed. A user-rejected join stays unresolved until
new acoustic evidence or user listening resolves it. Keep this local to the affected
join; no recurring audit loop and no restoration of redundant setup without review.

## Picture intent before native review

For multicamera assemblies, read [camera_intent.md](references/camera_intent.md).
For Q&A, apply the required opening split in [camera-decisions.md](references/camera-decisions.md); carry `content_format: "qa"` into the plan and construction packet.
Keep **every available, synchronized source angle across every selected spoken span**
as source-linked, independently editable picture coverage in the 16:9 project, even
when that angle is not visible in the review composite. Record actual coverage gaps;
do not invent missing frames, duplicate camera audio, or alter the spoken edit to
make an angle fit. Assembly Design chooses source-bound camera and split intervals using
[camera-decisions.md](references/camera-decisions.md), pins them to the spoken revision,
and hands that plan to `horizontal-to-vertical` for native framing. Explicit editor
picture choices supersede the proposal; unusable coverage returns here before export.
Keep the available synchronized camera and audio sources on compact, adjacent,
source-labeled tracks for editor comparison; only the selected dialogue mix plays.

For every candidate, save `editorial_worksheet.json` and `design_comparison.json` beside
`assembly_plan.json`. The worksheet must pin the same source and complete interaction,
show the branch ledger and ranked promise comparison, and reproduce the exact proposed
assembly. `design_comparison.json` must
pin the plan, contain the full unedited interaction dialogue and exact selected dialogue,
quote source-indexed hook/retention/payoff evidence, record separate opening/body/ending
decisions, compare the meaningful alternative (or explain why none exists), and explicitly
justify a single-span result. It must also state the viewer, promise, reward, goodwill,
value-compression judgment, cold-viewer comprehension, and audience-growth rationale.
The schema is in the contract. Then run:

```bash
python3 scripts/design_quality_gate.py --clips-root CLIPS_DIR --out DESIGN_GATE.json
```

This structural evidence gate must pass before compilation or acoustic execution. It
rejects missing comparisons, mismatched dialogue/ranges and exact duplicated rationale.
It cannot detect every generic explanation or decide whether a hook/payoff is good.
Independent editorial judgment remains required; it does not reward extra cuts.

For a selected nonverbal payoff, record the reviewed `performance` interval in the
contract. Word retention alone cannot protect a gesture or reaction after speech ends.

Before acoustic execution, apply `audit-script`'s seven criteria in the designer's
self-check of the actual proposed dialogue. The independent v4 review happens once,
after frame resolution and retained-word reconciliation. It may reject every option. Never invent
missing speech to repair an incomplete promise; redesign, narrow or reject it.

## Final editorial gate

The first independent review is not a receipt; it is a decision. If it says `REVISE`,
the reviewed plan is rejected. Apply the exact source-backed changes to a new plan
revision, recompile it, and rerun boundary resolution. V4 spends one independent review on the final
reconciled dialogue, not separate cold-viewer and fidelity reviews on preliminary drafts.
Before frame resolution, the designer itself must cold-read the opening, every transition and the
last complete sentence; remove dangling referents, broken grammar, repeated payoffs and
promises whose reasoning is absent. This self-check is design work, not an audit receipt.
Only a final `PASS` tied by SHA256 to the resolved/reconciled revision may enter the clean
approval sequence. Preserve rejected reviews and never reroll unchanged work merely to
obtain a different verdict.

New jobs use [the job-control contract](../edit/references/assembly_job.md). The compiler
requires `--job`; that record pins sources, skill versions and authorized plan revisions.
For v4 use its neutral `final_editorial` packet after frame resolution; it combines the cold-viewer
and source-fidelity criteria in one fresh execution. Preserve the original returned JSON
and actual invocation evidence. Mechanical validation
cannot authenticate a fabricated report or prove that the reviewer made a good judgment.

For batches, quality determines the count. “As many as possible” means every distinct,
complete arc that passes; it never means one clip per candidate, coverage-ledger row or
subtopic. Combine overlapping fragments when that earns one stronger payoff. Reject
teasers, mechanisms without outcomes, outcomes without reasoning, and generic advice
that depends on removed owner context.

The single final review must quote the exact opening, retention path and payoff word ranges and
explain why a cold viewer continues through each transition. Boilerplate such as “the
opening states the tension” or “the ending completes the mechanism” is not editorial
evidence. For Q&A and L1 diagnosis, preserve the audience question as the hook unless the
answer is independently self-contained and the reviewer explicitly proves that removing
the question improves the clip without losing the applicable condition.

Before native construction, run:

```bash
python3 scripts/final_editorial_gate.py --job JOB.json --out FINAL_GATE.json
```

Every clean-approval clip must pass. A coherent playable candidate with subjective seam or
pacing uncertainty belongs in a media-bearing review sequence with its status marked,
not an empty marker-only holding timeline. If the user wants one review timeline, keep
clean and provisional clips there with distinct markers. Truly incomplete or misleading
candidates are withheld.

Acoustic repair may move a boundary without changing selected words. `FUSED` describes one
boundary, not the whole candidate. Merge adjacent spans when the selected speech is truly
continuous; otherwise return an explicit `RESTORE_MINIMUM`, `MOVE_BOUNDARY`, `DROP_SEGMENT`,
or `HUMAN_LISTEN` action. If repair changes words, return once to design, create a new
plan/comparison, then resolve and run the one final review. Never restore arbitrary filler,
repetition or a tangent merely to obtain an `OK` seam.

## Verify and execute

→ Use skill: `long-form-ingest` for AssemblyAI-first transcription, speaker turns and
complete interaction indexing. Verify the entire candidate region
against audio, including excluded branches and suspicious gaps. Preserve raw ASR and a
separate corrected word file with an evidence log. A plausible contextual substitution
is a hypothesis, not an evidenced correction. Unresolved names, numbers, negation or
speaker attribution block affected claims. See the contract's verification package.

Compile with `scripts/assembly_plan.py compile`. This reuses `/edit`'s L1 source compiler
and design-evidence implementation; it does not certify semantics or acoustic timing.

Use `_shared/speech_map_cut.py` after the exact spoken assembly passes the
designer's self-check, for selection-preserving acoustic boundary resolution.
Supply compiled `cut_request` as the spec, `selection_guide` for inspection, and pinned
words; use selection-preserving execution. Return
lexical changes to the designer. After **every** boundary adjustment run
`scripts/assembly_plan.py reconcile`. Added words, missing words, overlapping source
spans or partial edge words require redesign or corrected timing—not silent acceptance.
Do not sort spans chronologically, restore material to meet a retention ratio, or
swallow a FUSED boundary by expanding the edit without a new design revision and self-check.

→ Use `/edit` RUNBOOK Steps 6–8A for native source-linked construction and technical
readback. Reconcile the final source ranges read back from the saved timeline,
after combining adjacent camera-only subdivisions. Render/listen to actual seams.
Caption consumers receive the reconciled assembly-clock words, never raw source times.
The handoff must retain every approved boundary word whose acoustic interval overlaps the
kept picture/audio range, then clamp that word to the assembly clock. Never select caption
words by ASR-box midpoint: a recognizer can start an intact opening word before the verified
cut and midpoint filtering will silently drop it even though the viewer hears it.
At handoff, pin the compiled/reconciled dialogue revision in the existing receipt
and quote its literal opening and final complete thought. If later spoken edits
change either or restore omitted interior material, return that change to the
existing revision comparison; a finishing-only handoff cannot certify new dialogue.
Preserve existing finishing and delivery gates.

Separate the claims: `STRUCTURE_VALID`, `WORDS_RECONCILED`, acoustic review, independent
editorial review and **human acceptance**. Never turn one into another. If listening,
source coverage or native access is unavailable, preserve a checkpoint and state the
missing gate; do not label the pilot ready.
