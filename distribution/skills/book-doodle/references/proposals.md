# Batch recommendation and decision record

Use the final assembly's clip-relative clock. Show seconds/timecode to the user; persist exact integer frames and a rational FPS. Include source-span mapping or the locked-cut artifact/revision so a later edit cannot quietly reuse stale placements.

A compact proposal can look like this (examples, not a required count):

| ID | Clip / moment | Drawing | Why it helps |
|---|---|---|---|
| C04-D1 | One bottleneck · 00:12–00:15 · “one thing slows everything down” | A queue stops at one narrow gate; circle the gate. | Makes the limiting step clear in one glance. |
| C09-D1 | Three paths · 00:22–00:27 · “all three lead to the same outcome” | Three arrows appear in spoken order and meet at one destination. | Shows the relationship more clearly than three text labels. |

Then ask: “Want these doodle moments? Approve all, pick IDs, or say no.” Exact wording can stay conversational. Add a short call/credit estimate if the provider exposes it; clearly label unknown billed cost. Do not ask about technical settings that the existing batch context resolves.

A reply such as “yes to C04, no to C09” approves only C04's displayed moments. An unambiguous “yes” to a single displayed proposal can approve all of it. A requested concept change updates that case; do not infer approval for another clip. A “no doodles this batch” bypasses the checkpoint for that batch. With no strong candidates, say that briefly and continue without a question.

## plan.json shape

```json
{
  "schema_version": 1,
  "locked_edit": "10_WORK/locked-cut-readback.json",
  "locked_edit_sha256": "<hash of the approved edit snapshot>",
  "fps": "30/1",
  "style_refs": ["<resolved ref paths and hashes>"],
  "clips": [
    {
      "clip_id": "C04",
      "title": "One bottleneck",
      "duration_frames": 1350,
      "screening": "recommended",
      "reason": "The bottleneck is an abstract relationship with enough time for a simple visual.",
      "moments": [
        {
          "id": "C04-D1",
          "start_frame": 360,
          "end_frame": 450,
          "spoken_cue": "one thing slows everything down",
          "concept": "A queue stops at one narrow gate; circle the gate.",
          "draw_order": ["queue", "narrow gate", "green circle"],
          "labels": [],
          "decision": "pending",
          "decision_evidence": null,
          "accepted_still": null,
          "accepted_animation": null,
          "plate": null
        }
      ]
    },
    {
      "clip_id": "C05",
      "title": "Personal lesson",
      "duration_frames": 1100,
      "screening": "no_use_case",
      "reason": "The speaker's expression carries the point; a cutaway would interrupt it.",
      "moments": []
    }
  ]
}
```

`end_frame` is exclusive. `decision` is `pending`, `approved` or `declined`; only the user's explicit response changes it. Keep the response text and available message/time reference in `decision_evidence` when resolving a proposal. All intervals must be within the locked clip, non-overlapping, and mapped to the spoken cue. No approved moment may be generated from an earlier cut revision without remapping it first.

Before generating and again before final export, reconcile the record: each integrated plate belongs to an approved moment; declined moments have no inserted media; pending moments remain unresolved; each included asset is the accepted version; removed clips contribute nothing. Preserve the decisions in the project's run ledger as well.
