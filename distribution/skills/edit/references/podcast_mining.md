# Podcast mining — design the conversation before cutting it

## Scope and precedence

Use for ordinary podcast interviews, cohost conversations, and free-form solo passages
inside a podcast. An interview question does not make an exchange a business-owner
diagnostic. Livestream Q&A, hotline, workshop/L1 diagnosis, selected drafts, and standalone
monologue/listicle jobs retain their existing routes; classify mixed footage per content unit.

This is the podcast editorial procedure within `/edit`, not another skill or finishing
pipeline. Read [editorial_design.md](editorial_design.md) for the shared source-value and
restart contract; it owns evidence/coverage schemas and repair limits. This reference
overrides conflicting generic editorial preferences for podcasts only:

- No caller-revenue/seven-beat skeleton, host-interjection limit, one-clip-per-question rule,
  fixed word floor, or inherited monologue duration cap. Explicit user limits still bind.
- Question openings, necessary multi-sentence context, internal edits, and an interviewer
  ending are allowed when they make the complete clip stronger. Do not enforce an arbitrary
  hook deadline at the expense of understanding.
- Do not apply blanket rules to remove the abstract why, dialogue middles, all backchannels,
  or every connective. Distinguish redundant speech from reasoning and meaningful response.
- Empirical podcast lift tables are discovery priors, not mandatory structures or proof
  of quality. No selector score or boundary PASS can choose the idea for the editor.

Shared acoustic gates, source fidelity, native editability, independent review, human
approval, and delivery permissions remain in force. If a shared validator enforces an
incompatible generic editorial limit, report the conflict and resolve it in its owner;
do not falsify the format, truncate the idea, or claim a bypass is a PASS.

## 1. Understand the episode before ranking moments

Read the full transcript chronologically with speaker identity and source locations.
Use overlapping windows for long sources and reconcile the joins and tail. An index or
summary helps navigation but does not substitute for the read. Reuse verified transcripts;
a rejected batch's candidate pool is not the starting shortlist for a clean-room restart.

Map topics and the useful ideas within them in the shared coverage record. Include later
clarifications, callbacks, examples and changes of direction. Do not limit discovery to
the first N candidates, the loudest quote, a keyword search, or one pick per interviewer turn.
One answer may contain several distinct clips; several turns may be needed for one clip.

Direct in-session mining is a supported primary method. `clip_select.py --rules
config/clip_lift_podcast.json` is optional assistance. A missing API key does not require a
different editorial standard: use the same source-grounded procedure in-session and state
the backend used. Never silently substitute unreviewed heuristic picks.

## 2. Find the complete value, then choose its opening

Read the surrounding conversation through its actual completion. Identify what a cold
viewer gains: a usable explanation, decision rule, worked example, changed belief, resolved
tension, or satisfying story. A catchy sentence alone is not necessarily a clip. Find the
passage that earns the payoff before settling on the hook.

Consider plausible openings within that idea: a direct claim, concrete problem, revealing
example, or concise question. Choose the strongest truthful entry that the body delivers.
Do not force a quote to the front merely because it sounds punchy. Preserve chronological
dialogue by default; any relocation must preserve referents, qualifications and what each
person is answering. Never fabricate agreement, causation or a response.

Length follows substance within the brief. Tighten the path, not the useful idea. Do not
pad a thin claim or hollow out an explanation to hit a generic duration. Separate neighboring
ideas when they have distinct promises/payoffs.

## 3. Write the actual edit, not a synopsis

Before assembly, write speaker-labeled **verbatim kept dialogue in playback order**.
Record the intended viewer, promise/opening, necessary context, mechanism or story development,
concrete example when relevant, and exact payoff. These are questions to answer, not a fixed
beat count that every story must satisfy.

Use the existing `design_evidence.json` contract to anchor minimal essential source phrases,
not whole paragraphs of optional speech. Resolve actual phrases/word indices to source;
model-proposed approximate timestamps are not final cut boundaries.

A founder-plateau explanation might need comfort → owner capacity → hiring need →
revenue/margin/reserve math → size of the hiring bet. Keeping only “growth requires risk”
retains the thesis but deletes the lesson. Protect the dependency chain, not this particular
topic or a mandatory financial example.

## 4. Tighten inside the design before human review

Read the full assembled dialogue and remove repeated setup, redundant restatements,
abandoned starts, tangents and weaker examples where removal improves it. Preserve the
reasoning bridge, qualifications, distinctive specifics and explanatory/emotional payoff.
Do not flatten a back-and-forth into isolated quotes just to increase pace.

Keep a question if it supplies missing context; shorten its preamble. Keep a challenge,
clarification, revealing reaction or real-time application when it adds value. A quiet
“mhm” is not automatically verbal junk. Pure repetition can go. Either speaker may deliver
the ending when that is where this idea lands.

Then → Use skill: `assembly-design` for verbal cleanup, pause assessment and acoustic boundary resolution.
Transcript labels are coordinates, not proof of intact phonemes. Unsafe microsplices require
another edit or retained continuity; do not make a choppy clip to satisfy a filler/cut-count
target. Log specific retained imperfections rather than a blanket “clean” claim.

After each span change, reread the actual kept words. Check references, transitions,
question/answer relationships and the final sentence. Evidence receipts prove declared
words survived, not that the chosen words make a compelling clip.

## 5. Review what was kept AND what was left out

Perform two distinct checks before assembly handoff:

**Clip check:** Does the dialogue work without the episode? Does the body earn its opening
and payoff? Compare with surrounding source: did tightening delete the useful explanation,
qualification, best example or stronger ending? Repair the specific defect; preserve a
strong body when only the opening needs work.

**Missed-opportunity check:** Revisit rejected, merged and unused topic ranges after the first
design pass. Look for distinct sub-ideas, alternate openings, later completions and useful
callbacks. Revisit “weaker than another clip” decisions: when asked for all quality clips,
lower relative rank alone is not rejection. Distinguish duplicate value from different
lessons about the same subject. Apply the shared overlap/distinctness check.

Record results in `10_WORK/mining/podcast_review.md`, linked from the run ledger:
- Topic/source range and candidate IDs; selected, rejected, merged or withheld outcome.
- Rejected ideas: concrete editorial reason, not just “weak” or a score.
- Withheld ideas: remaining defect, attempted repair and whether it is editorial or technical.
  A good idea with an unsafe seam is not a bad idea.
- What the second pass recovered, or why no additional distinct clip met the brief.

Honor the shared bounded repair rule. Stop when coverage and the second pass are accounted
for and included clips meet the bar—not when a quota is filled. Report unresolved promising
ideas separately; never pad the batch or claim objective exhaustiveness.

## 6. Continue the shared workflow and learn from review

Mark meaningful handoffs, challenges and reactions as editorial camera opportunities; do
not select content just to create angle changes. → Use skill: `horizontal-to-vertical` for
layout/tracking after approval. This reference does not own visual or audio recipes.

Continue RUNBOOK boundary resolution, native `01_CUTS` assembly and live readback.
→ Use skill: `audit-script`, assembly review mode, via RUNBOOK Step 8A. Its fresh cold-viewer
review complements the source-aware check; a cut-only reviewer cannot detect all valuable
omitted source. Do not invent a parallel audit rubric or replace the existing handoff gate.

After human review, compare native kept/deleted source ranges with the handed-off designs
and record the stated reasons. Success means strong distinct ideas, preserved substance,
natural pacing and low human correction—not raw clip count, cut density or N/N machine passes.
One successful batch is a useful qualitative precedent, not a validated universal template
or proof that the episode yielded every possible good clip.
