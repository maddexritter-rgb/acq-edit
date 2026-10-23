# Editorial worksheet contract

Author this before `assembly_plan.json`. It is the reasoning record that turns a
complete interaction into one designed content unit; the plan is the execution receipt.

Use schema `assembly-design.editorial-worksheet/v1` with:

- `source_words:{path,sha256}` and `interaction_words:[first,last]`.
- `interaction_text`: exact complete source dialogue for that range.
- `source_read`: what was read before/after the interaction and whether any gap remains.
- `question_and_revealed_problem`: exact question, problem ultimately revealed, and how
  they differ. Use `not_applicable` only when there is genuinely no exchange.
- `branch_ledger`: every substantive diagnosis, example, objection, correction,
  qualification, reaction and coda with source ranges and disposition.
- `ranked_promises`: at least every viable promise, strongest first, with viewer,
  promise, reward, supporting ranges, and clip-specific acceptance/rejection reason.
- `selected_promise`: the chosen promise and why it beats the alternatives.
- `question_policy`: `retain`, `self_contained`, or `not_applicable`, with exact evidence.
- `reasoning_ladder`: playback-ordered context, mechanism, story/example and conclusion
  dependencies required to earn the reward.
- `payoff`: exact source range, quote, and the opening promise it completes.
- `omissions`: substantive omitted ranges, their function, why the viewer can still
  understand the selected promise, and the strongest omitted counterexample.
- `reorder_checks`: every backward source move, including original relationship, new
  adjacency, referent, chronology, certainty and speaker-response effect.
- `proposed_assembly`: exact ranges and exact dialogue in playback order.
- `cold_read`: literal opening, first-15-to-20-second retention judgment, final line,
  cold-viewer comprehension, and unresolved weakness.
- `meaningful_alternative`: exact competing arrangement when one exists, otherwise a
  source-specific explanation of why a second arrangement would be ceremonial.

The worksheet is written from actual dialogue, not programmatically generated prose.
Code may quote source ranges and validate identities; it may not rank promises or author
the reasoning. A worksheet with generic repeated explanations fails even when structurally
complete.

## Decision order

1. Read through the real resolution and handoff.
2. Inventory branches and late facts before choosing a hook.
3. Rank the viable promises by usefulness and completeness.
4. Choose the strongest complete promise, not the shortest defensible excerpt.
5. Choose the payoff, then work backward through what earns it.
6. Choose the literal source opening and required question context.
7. Write exact playback dialogue and compare the meaningful alternative.
8. Read it cold. Only then author the assembly plan and design comparison.

Duration, cut count and retention percentage do not rank promises. A candidate whose
topic is strong but whose source contains no satisfying reward is rejected.
