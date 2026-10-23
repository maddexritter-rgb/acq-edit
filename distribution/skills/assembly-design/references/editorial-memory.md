# Assembly decision receipt

→ Use skill: `find-precedents` for retrieval. This reference only records how
the in-session editor used or rejected the returned assembly cards.

## Leave a tiny trace

The model decides the hook, reasoning/story, payoff and exact source-word playback.
Retrieval must change a *concrete* design choice to count as applied (for example,
retaining the question's condition, keeping a causal bridge, or selecting the later
source-supported result). Mention the applied card ID and decision in the clip's
`editorial_intent`. A card merely shown but not used is not an applied precedent.

For the batch, save `10_WORK/editorial_memory_receipt.v1.json` as a lightweight trace:

```json
{
  "schema": "edit.editorial-memory-receipt/v1",
  "project_id": "<confirmed Supabase project ref>",
  "preflight_context_paths": ["10_WORK/brain/q_and_a.preflight.v1.json"],
  "playbooks": [{"format": "universal", "version": 1, "body_sha256": "<live hash>"}, {"format": "q_and_a", "version": 1, "body_sha256": "<live hash>"}],
  "clips": [{
    "clip_id": "clip_01",
    "problems": ["question context"],
    "problem_context_paths": ["10_WORK/brain/clip_01.question-context.v1.json"],
    "retrieved_card_ids": ["workshop-question-hook"],
    "applied": [{"card_id": "workshop-question-hook", "decision": "Kept the source question's limiting condition before the answer."}],
    "unused_reason": null
  }]
}
```

If no card applies, use an empty `applied` list and one concise `unused_reason`;
if retrieval was unavailable, stop before new design rather than creating a receipt.
This is **not** an audit, approval
or prerequisite to Premiere placement. Do not write fabricated retrieval events or
feedback to Supabase. Only actual editor keep/change/delete decisions and exact
revisions may become feedback later.

Use the actual format's saved live responses, including their query, fetch time,
playbook and reading hashes, and returned card revisions. These files establish
what was retrieved; the exact-word decision explains what was used. They do not
prove the model read the bodies or the resulting clip is good. The compiler stays
deterministic and does not silently fetch newer guidance after the words are chosen.

## Preserve an approved iteration

When the editor asks to save progress, preserve the accepted sequence UID, project
path and saved-project hash, selected/compiled/resolved revision, final audio plan,
native readback, persistence and rendered-review receipts in the existing job.
Record the editor's actual quote and its revision scope in a new approval receipt;
do not rewrite earlier provisional or rejected reports as if they passed originally.
Keep project-specific names, timestamps and examples in that checkpoint, not in this
portable skill. Preserve required local bridge code/profile dependencies separately
from source footage, with hashes and restore locations; never include credentials.

Save stable procedures in their existing owning skill and evidence-backed cases
through `editorial-brain-ingest`. Human acceptance of one assembly is useful
calibration, not a verified captioned final, held-out result, or evidence of perfect
unattended editing. A local packet is not a published Supabase row: retain separate
publication/readback status. Keep the live preflight and bounded problem retrieval
above as the next job's actual knowledge path.
