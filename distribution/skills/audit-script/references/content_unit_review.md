# Content-unit assembly review

## Context and scope

Use the creator's editorial perspective through this supplied framework: hook, retain, reward; callout plus promise; goodwill through repeated useful giving; value per time; audience growth. This is an editorial simulation, not the creator's personal judgment or endorsement. Load brand-specific vocabulary and overrides from a supplied brand path; keep this rubric reusable.

Provenance: the editor explicitly adopted the conversation's summary of the content chapters and hooks material as the review context on 2026-09-09. The original linked excerpts were not accessible in that session. Treat the principles below as the editor-approved working rubric, not a verified transcription of those excerpts or invented quotations from their author.

This mode audits words, structure and time allocation in the assembly. It does not certify visual hooks, caption quality, acoustic integrity or predicted performance from a transcript. Those remain with their existing owning audits. Do not require finished graphics or captions at the assembly stage.

## Fresh-agent inputs

The orchestrator supplies: this file and the owning SKILL.md; the applicable cutting playbook and format SOP paths; brand context by path if available; clip ID; saved project/sequence identity; timeline range and duration; a timeline snapshot identifier or hash; a hash of the line-numbered, clip-relative timed transcript reconciled to the native readback and machine-ear evidence. Actual visible hook text may be supplied only if already present and verified in the assembly. Never credit a planned title/graphic as delivered value.

Review the clip without the full source narrative, mining ranks, builder explanations, or prior verdicts. The edit orchestrator must separately complete its source-value design check; this blind review cannot discover valuable source material that was deleted. The builder, not the reviewer, checks proposed repairs against source footage. Missing/unreconciled transcript or identity evidence = UNKNOWN. Source footage is never rewritten to fabricate a stronger promise or reward.

## Review criteria — cite kept lines and clip-relative times

1. **Content unit:** identify the intended viewer, the hook, the retention mechanism and the reward. They may overlap or recur; do not demand three artificial sections. A longer clip can link several units within one coherent arc. Does a cold viewer understand it without the source conversation?
2. **Hook / callout / promise:** state who should care and what the opening leads them to expect. The callout or promise can be implicit if understandable. Does the first substantive line earn attention? Flag generic preamble, insider context, or an exaggerated promise. An unsupported hook or no discernible reason to watch requires revision; subjective wording preferences alone do not.
   Quote the actual opening from its first kept word. Do not skip over retained setup or
   credit a hook later in the clip. Judge any pre-hook material explicitly; a marker,
   title or builder description cannot supply an opening the viewer does not hear.
3. **Retain:** identify what makes the viewer want the next line: a useful step, unresolved problem, list progression or story. Locate repetitions, tangents and missing reasoning bridges. Retention does not mean withholding the answer until the end; intermediate rewards help earn continued attention.
4. **Reward / promise match:** identify the exact delivered answer, useful action, insight or emotional/story payoff. Does it satisfy the opening's specific promise for that audience? A tease, generic maxim in place of the promised mechanism, missing step, or truncated explanation requires revision. Entertainment can be a valid reward when it is what the clip promises. For a business-mechanism brief, a general claim is not interchangeable with a usable explanation or action. Identify what the viewer can now understand or do beyond repeating the thesis; do not infer a missing example or tactic. A concise insight can still pass when that is the actual intended reward.
5. **Goodwill / giving:** would the viewer receive something worthwhile even if they never buy or follow? Check honest expectations, useful completeness and whether an ask interrupts or replaces the value. Repeated giving builds trust; it does not require an offer or CTA in every clip, nor does it ban an explicitly requested CTA that fits the brief.
6. **Value compression / earned length:** assess what each section contributes relative to its time. Cut redundancy, not the context, example or reasoning that makes the lesson usable. Neither a short duration nor a long duration proves quality. Cut count is never a scoring criterion. Filler and pause cleanup counts as editing; do not demand multiple substantive omissions. Format bands are planning guidance for this editorial criterion; an explicit user/platform delivery limit remains binding. If a legacy mechanical duration gate conflicts, report it to the orchestrator rather than falsely claiming it passed. Never recommend padding, rushing speech or amputating the middle just to reach a generic band.
7. **Audience growth rationale:** explain why this viewer might stop and why they might want more from the creator or share the clip. Views/impressions and followers gained are the supplied audience-growth goals, not proof of usefulness or guaranteed outcomes. Do not predict counts, demand unpublished metrics, or pass misleading clickbait because it might get views. Once published data exists, it can inform future reviews; it is not a pre-handoff requirement.

## V4 final editorial review

New `edit.assembly-job/v4` strict jobs run one independent review after Assembly Design's frame resolution and
word reconciliation. The neutral `final_editorial` packet contains the exact executable
selected dialogue, resolved spans, reconciled words and the complete source interaction.
In one fresh execution, first judge the seven cold-viewer criteria using only selected
words, then judge the five source-fidelity criteria below against the complete interaction.
Return all twelve checks in one `edit.editorial-review/v1` response with perspective
`final_editorial`. This replaces two preliminary reviews plus a repeated native editorial
review; it does not replace native structural readback or human viewing.

## Source-fidelity companion (historical v1-v3 pre-native assembly)

This is a separate fresh execution, not the cold-viewer review. Read the complete supplied
interaction and selected dialogue without builder rationale or earlier verdicts. Assess:
`context` (referents, owner condition and scope), `question` (necessary guest setup retained
or genuinely supplied by a self-contained answer), `qualifications` (negations, limits and
exceptions), `causality` (chronology, reasoning and speaker knowledge), and `omitted_value`
(whether a deleted step/example is needed to earn the reward). Cite exact source words,
including omitted words where relevant. Brand identity never implies guest exclusion.
Multiple examples and continuous scripted takes may be appropriate; count/ratio is not
quality. Missing source context produces UNKNOWN, not assumed fidelity.

For job-controlled pre-native reviews, use `edit/references/assembly_job.md`'s response
contract. Native assembly handoff below retains its existing timeline-based contract.

## Native agent task template

> Read the supplied audit-script skill and content-unit reference, plus applicable cutting/SOP files. Act as an independent editorial reviewer using this framework from the creator's perspective. Review this one native assembly's actual kept words, not an imagined improved version. Identify its viewer, promise and delivered reward, then assess every criterion with exact evidence. Return the report below. Do not edit the project. Do not claim to be the creator or to know their private opinion. Recommend only changes that the builder can verify against source; never invent dialogue. A subjective alternative is not automatically a defect.

## Required Markdown report — one per clip and reviewed revision

Save to `10_WORK/assembly_review/<clip-id>_<revision>.md`:

- **Identity:** clip ID, revision, project/sequence, timeline range, duration, snapshot identifier/hash and transcript hash.
- **Verdict:** PASS, REVISE or UNKNOWN. PASS requires all seven criteria assessed, no unresolved material editorial defect, and complete evidence. UNKNOWN means the review could not be completed, never a pass.
- **Viewer / promise / reward:** one concrete sentence each, with supporting lines/times.
- **Criteria table:** all seven criteria, finding (PASS/REVISE/UNKNOWN), line/time evidence, explanation. For the growth criterion the finding assesses the rationale, not future results.
- **Fixes:** exact offending line/time, viewer consequence and proposed edit (move, remove, restore missing context/reasoning, extend to complete payoff, or withhold). Distinguish required fixes from optional suggestions. The builder must verify source availability, boundaries and original meaning before applying them.
- **Handoff note:** one sentence explaining why it earns review, needs revision, or lacks evidence. State the transcript-only scope; do not imply a complete audiovisual pass.

The orchestrator checks coverage, report completeness and evidence identity before accepting PASS. Do not accept an agent's bare “looks good,” a verdict on stale spans, or a batch score in place of an individual review. After editorial changes, regenerate evidence from the saved native assembly and review that clip again in fresh context. Existing mechanical gates and the editor's final decision remain separate requirements.

## Executable evidence contract

The owning validator is `scripts/assembly_handoff.py` in this skill. Its `validate_report` function defines and validates the `assembly-review/v1` JSON contract before accepting any verdict. Supply a JSON receipt alongside each Markdown review; prose alone no longer clears the gate.

1. Save and read back the intended assembly through Premiere. Group V1 items by gaps greater than five seconds in timeline order, matching the existing native workflow. Name the reconciled transcripts `clip_001.txt`, `clip_002.txt`, etc. The IDs refer to this snapshot's order, not old markers. Every native V1 group is required; media outside those groups blocks preparation. Do not silently omit a clip. Reconcile disabled items or stray tracks before review.
2. From this skill folder run:
   ```bash
   python3 scripts/assembly_handoff.py --prepare \
     --require-project <exact-project-name.prproj> --require-sequence <exact-sequence-name> \
     --transcripts <10_WORK/assembly_review/transcripts> \
     --builder-id <actual-orchestrator-agent-id> --packet <10_WORK/assembly_review/packet.json>
   ```
   The packet contains schema `assembly-packet/v1`, the native project/sequence, source/time/track evidence and each full transcript with an `evidence_sha256`. Preparation is NOT a pass. The orchestrator must still reconcile transcripts to audible kept words; a checksum cannot establish transcription accuracy.
3. Spawn one new agent per clip, supplying that clip's packet entry and the rubric. Have the agent return the Markdown report and a JSON receipt with schema `assembly-review/v1`, copied `clip_id` and `evidence_sha256`, its actual `agent_id`, `verdict`, `viewer`, `promise`, `reward`, `handoff_note`, `checks` and `fixes`. Preserve its returned verdict; do not author PASS receipts on the agent's behalf or invent agent IDs. Retain the tool result in the run ledger for provenance.
4. `checks` must contain exactly `content_unit`, `hook`, `retain`, `reward`, `goodwill`, `value_compression`, `audience_growth`. Each value is an object with `verdict` (PASS/REVISE/UNKNOWN), nonempty `evidence` (kept lines/times), and `reason`. `fixes` is a list of objects with Boolean `required`, `evidence` and `edit`; use an empty list when there are none. A PASS with any non-PASS criterion or required fix is rejected. Other requested textual fields must be nonempty. Save receipts as `reports/clip_001.json`, etc.
5. The `/edit` Step 8A handoff command re-reads the live native sequence, validates complete clip coverage and checks these receipts. Each clip must have a different fresh reviewer ID, distinct from the builder. Missing or malformed evidence, a bridge error, a changed transcript or changed native state fails closed. The whole sequence is bound to the evidence: any timeline change requires a new packet and fresh reviews for all included clips. This conservative rule supersedes per-clip reuse for this executable gate.

The checker verifies recorded independence, content coverage and freshness; it cannot authenticate a fabricated report or judge prose quality. The orchestrator must actually spawn the reviewers and preserve their outputs. Native readback is read-only and covers source, timing, track placement/mute, item enable state and playback speed; this remains an editorial assembly gate, not an effects/audio-quality audit. The human handoff must show the actual N/N result, not merely state that a workflow was followed.

Nested/multicam sequence items and unresolved non-file media block this gate because their inner edits cannot be verified from the outer timeline. Use the workflow's source-linked native items. Fixture regression checks: `python3 tests/test_assembly_handoff.py` from this skill folder; these tests do not substitute for a live Premiere handoff check.
