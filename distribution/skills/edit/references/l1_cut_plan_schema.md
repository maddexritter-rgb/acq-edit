# L1 selection plan and structural compiler

Use `edit.l1-cut-plan/v6` to make a model's editorial choices inspectable and executable
without embedding a particular model provider. This compiles a selection guide; it does
not select moments itself, trim audio, or modify Premiere.

Version 6 keeps v5's boundary checks and also forces ranked promise selection plus an
explicit comparison between owner-specific Q&A value and a host-only alternative. This
prevents “smallest complete” from silently becoming “smallest isolated host anecdote.”
Version 5 forces the plan to record full-interaction coverage, its exact promise,
opening/ending reasoning, retained word-range evidence for those claims, and a grounded
inventory of substantive answer branches, and explicit review of mid-sentence source
boundaries. The compiler still accepts v1-v4 for historical
plans and accepts v5 with a legacy warning; do not start new work in an older version.

`source_words` points to JSON containing a `words` array with `word`, `start`, `end`, and
optional `spk`/`speaker`. Times are seconds in a documented source clock. Paths resolve
relative to the plan file; the SHA256 must match the entire transcript file. If ASR or
timing is corrected, regenerate/review the indices and plan against the new hash.

All ranges below are **zero-based inclusive word indices**, not seconds. `segments` are
in desired playback order. Every word in `interaction_words` must appear exactly once
in a kept segment or a removal. Do not narrow the interaction to avoid explaining a
removal; its bounds must correspond to the full exchange recorded in source coverage.

```json
{
  "schema": "edit.l1-cut-plan/v6",
  "clip_id": "clip_001",
  "source_words": "source.words.json",
  "source_sha256": "REPLACE_WITH_TRANSCRIPT_SHA256",
  "interaction_words": [0, 19],
  "source_coverage": {
    "interaction_start_basis": "Owner begins the question after the prior handoff",
    "interaction_end_basis": "Owner thanks the host before the next owner begins",
    "handoff_checked": true
  },
  "viewer": "An owner deciding whether to delegate",
  "intent": "Explain the tradeoff and make its cost concrete",
  "promise_ranking": [
    {
      "rank": 1,
      "promise": "Owner-specific decision rule",
      "disposition": "selected",
      "why": "It resolves the retained owner dilemma with a usable payoff"
    },
    {
      "rank": 2,
      "promise": "Host-only illustrative story",
      "disposition": "not_selected",
      "why": "It is self-contained but loses the stronger owner-specific Q&A value"
    }
  ],
  "promise": {
    "kind": "sub_answer",
    "question": "Which cost should determine the delegation choice?",
    "payoff": "A decision rule grounded in the retained costs",
    "scope_boundary": "This answers the retained delegation tradeoff, not every branch of the consultation"
  },
  "format_review": {
    "owner_specific_value": "The owner supplies the dilemma and stakes that the payoff resolves",
    "host_only_alternative": "A host anecdote is available but would remove the Q&A-specific application",
    "selection_basis": "Keep the owner-specific sub-answer because it is the stronger useful promise"
  },
  "opening_review": {
    "identity": "The viewer knows what kind of owner is deciding",
    "tension": "The retained question states the tradeoff",
    "uncertainty_or_condition": "The relevant costs remain conditional rather than guaranteed"
  },
  "ending_review": {
    "completion": "The final line supplies the promised decision rule",
    "raw_continuation": "The remaining source contains no correction that reverses this sub-answer",
    "moved_reaction_or_thanks": "No reaction or thanks is moved"
  },
  "semantic_evidence": {
    "promise_question": [[10, 14]],
    "promise_payoff": [[15, 19]],
    "opening_identity": [[10, 10]],
    "opening_tension": [[10, 14]],
    "opening_condition": [[0, 4]],
    "ending_completion": [[15, 19]]
  },
  "branch_review": [
    {
      "label": "Selected decision rule",
      "source_ranges": [[10, 19]],
      "relationship": "selected_promise",
      "disposition": "kept",
      "scope_action": "not_needed",
      "scope_effect": "This is the complete selected sub-answer",
      "retained_evidence": [[10, 19]]
    },
    {
      "label": "Repeated setup",
      "source_ranges": [[5, 9]],
      "relationship": "separate_promise",
      "disposition": "removed",
      "scope_action": "claim_narrowed",
      "scope_effect": "The cut does not claim to answer that separate setup",
      "retained_evidence": []
    }
  ],
  "target_seconds": 90,
  "cleanup_review": "Removed repeated setup; preserved the condition attached to the recommendation",
  "segments": [
    {"words": [10, 14], "role": "context", "why": "The later question states the dilemma concisely"},
    {"words": [0, 4], "role": "reasoning", "why": "Explains the same dilemma",
     "reorder": {"why": "Bring the question before its explanation",
       "original_relationship": "The owner elaborated before restating the question",
       "edited_relationship": "The question introduces that unchanged explanation"}},
    {"words": [15, 19], "role": "reward", "why": "Delivers the decision rule"}
  ],
  "removals": [
    {"words": [5, 9], "reason": "redundant", "why": "Repeats the setup without adding a constraint"}
  ],
  "essential": [
    {"words": [10, 14], "role": "context", "why": "The dilemma must remain understandable"},
    {"words": [15, 19], "role": "reward", "why": "The usable decision rule"}
  ]
}
```

This illustrates schema only; do not copy its indices or judgments to actual footage.
Segment/anchor roles: `context`, `reasoning`, `example`, `reward`. At least one reward
anchor is required. Select minimal essential phrases before cleanup, including any
qualifications required to preserve meaning. The compiler cannot decide their quality.
Removal categories: `off_arc`, `redundant`, `setup_detail`, `restart`, `filler`,
`conversational_tail`, `replaced_by_clearer_statement`; each needs a specific explanation.
Each backward move requires `why`, `original_relationship`, and `edited_relationship`.

For v2-v4, `promise.kind` must be `consultation`, `sub_answer`, `standalone_story`, or
`human_exchange`. The three review objects require specific prose; use an explicit
source-grounded “none” explanation when a category is absent rather than leaving it blank.
`source_coverage.handoff_checked` must be true. V3 also requires one or more inclusive
word ranges for every `semantic_evidence` field. Every cited range must be retained. Cite
the actual words that support the claim; do not cite a nearby passage or describe context
that the cut removed. This blocks unsupported review prose but does not prove that the
interpretation is correct. The assembled transcript and raw source still require
independent editorial review.

V4 `branch_review` inventories each substantive answer branch that could change what the
short promises. `relationship` is `selected_promise`, `separate_promise`,
`qualifies_selected`, or `reverses_selected`; exactly one entry must be the selected
promise. `disposition` must agree with the plan's actual kept/removed words. A partial
branch must include both. When a qualification or reversal is not fully kept, use
`claim_narrowed` or cite where the qualification survives with
`qualification_retained_elsewhere`; unresolved risk must use `blocked`, which stops
compilation. The compiler cannot prove that every real branch was listed, so compare the
ledger with the full raw interaction during editorial review.

`consultation` means the cut resolves the governing interaction through its material
answer branches; it is not a synonym for “advice from a consultation.” If the ledger
narrows the claim around an omitted branch or removes a separate substantive promise,
use `sub_answer`, `standalone_story`, or `human_exchange`. V4 blocks the contradictory
combination.

V5 inspects every selected segment edge. When a noncontiguous segment begins after a
source word without sentence-ending punctuation, add `start_boundary_review` **inside that
segment object**; when it ends without sentence-ending punctuation, add
`end_boundary_review` inside that segment object. Top-level boundary-review fields are not
read by the compiler. Each review records
`original_phrase`, the exact `edited_phrase`, and `why_complete`. This does not certify an
acoustic seam, but it blocks accidental starts such as a verb whose subject was deleted.
The first lexical token of a start review and the last lexical token of an end review must
match the actual selected range. A review cannot claim cleanup that the word indices do
not perform, even when the source edge already has sentence-ending punctuation.
Prefer moving the boundary to a complete source phrase over explaining a fragile splice.

Run from the active `edit` directory, with project-owned output paths:

```bash
python3 scripts/l1_cut_plan.py --plan /path/to/job/10_WORK/clip/plan.json --out /path/to/job/10_WORK/clip/compiled
```

Exit 0 means `STRUCTURE_VALID`; exit 2 means `BLOCK`. Inspect `l1_receipt.json` and
`assembled_transcript.txt`. The compiler also writes `selection_guide.json`,
`rough_design_evidence.json`, and `rough_design_receipt.json`. The latter's source-word
PASS is structural only. Rough durations exclude acoustic handles and finishing.
The receipt records both plan and source hashes. Consumers must require a current matching
receipt; a failed attempt can leave earlier files in the directory, which are not usable.
Do not rename rough evidence into resolved evidence: the `cut` workflow must determine
actual safe source boundaries, followed by the shared source-value and native checks.
