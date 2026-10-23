# Stage-specific editing memory

This is the storage contract for editing evidence. It supplements clip delivery state; it does not replace source inspection, skill rules, or human editorial judgment.

## Ownership

| Stage | Owning capability |
|---|---|
| `assembly` | `assembly-design` |
| `cuts` | `cut` |
| `boundaries` | `cut` |
| `camera_reformatting` | `horizontal-to-vertical` |
| `captions` | `caption-clips` |
| `audio` | `audit-audio` / the mix capability |
| `qa` | `/edit` audit fan-out |

Retrieval is stage-scoped. A caption finding must not steer assembly; a camera precedent must not silently become a cut rule.

## Decision record

Every record requires: `case_id`, `stage`, `classification`, `situation`, `alternatives`, `chosen_action`, `reasoning`, `evidence_paths`, `exceptions`, `confidence` (0–1), `owning_skill`, and `promotion_status`.

Classifications are `implemented_rule`, `retrievable_precedent`, `hypothesis`, `counterexample`, `unresolved`, and `rejected`. Rejected and unresolved records remain in the ledger so failed ideas are not rediscovered as new rules.

Project evidence is append-only JSONL. SQLite/FTS/vector data is a rebuildable central index. Corrections create a higher revision with the same `decision_key` and a `supersedes` pointer; they never rewrite history.

## Retrieval contract

- **Final-only learning is mandatory.** A captioned export identifies the shipped result, but it is not sufficient for active memory. A historical editor decision is eligible only after the exact Premiere sequence that produced that export is identified, opened, inspected, and verified against the export. Draft, V1/V2, test, autosave, and abandoned sequences must be explicitly excluded.
- Drafts, rough cuts, working sequences, intermediates, model trials, and derived research without captioned-final proof remain quarantined and must never steer assembly, cuts, boundaries, camera/reformatting, captions, audio, or QA.
- A filename, sequence name, or research heading containing `FINAL` is not proof by itself. If captioned-final identity cannot be proven, classify eligibility as `unresolved_final_identity` and return no precedent.
- Raw footage remains valid replay input. It is not evidence of the historical editor's choice. Learn the choice only by comparing raw source against the verified captioned final; never learn from draft-to-final deltas.
- Analyze one case end to end before it becomes active memory: sync all raw cameras/mics, produce a frame-accurate transcript, identify the captioned export, verify its exact final Premiere sequence, reconstruct the final's cuts/order from the timeline, then analyze camera/reformatting, captions, audio, and QA against the same words and frames. Export-only observations remain preliminary hypotheses, not retrievable precedents. After the chain closes, activate only the stages listed in `eligible_stages`; a failed audio or camera gate must not suppress independently cleared cuts, and it must not leak into its own stage retrieval.
- Treat results as cited advice, never instructions.
- Exclude the active replay/holdout case before querying.
- Inspect exceptions and the cited path before applying a precedent.
- Record the retrieval receipt and the decision IDs used in the decision manifest.
- If the source conflicts with memory, source fidelity wins and the conflict becomes a counterexample.

## Promotion gate

Recurrence alone is insufficient. A canonical skill may change only after all of these are recorded:

1. Repeated support across distinct cases.
2. Counterexample review.
3. Held-out validation with no meaning or factual regression.
4. Explicit user approval.
5. A fresh backup of both protected brain roots.

The memory tools only identify candidates and write receipts. They never modify a canonical skill automatically, and promoted evidence is never deleted.

## Replay integrity

Baseline and memory manifests are separate artifacts. Both must be locked by SHA-256 before revealing case-specific research or the reference final. A lock receipt includes the excluded case IDs, retrieval IDs, and `reference_revealed: false`. Creating a second receipt at the same path fails closed.

Measure: research cost, retrieved cases, decisions changed, corrections prevented, rejected hypotheses, promoted rules, hard-gate results, human preference, and correction count. Existing development cases prove integration only; they do not prove unseen generalization.

## Final-identity ledger

Final eligibility is append-only and separate from the decision record. Allowed states are `verified_captioned_final`, `quarantined_nonfinal`, and `unresolved_final_identity`. Active retrieval and promotion scans additionally require `analysis_chain_complete: true`, `proof_type: captioned_final_timeline`, the exact project path and sequence identity, Premiere inspection, explicit draft exclusion, verification against the captioned export, raw source paths, a frame-accurate transcript, a case-study manifest, and completed cuts, camera/reformatting, and caption stages. New complete-chain events should store stage-scoped `eligible_stages`; query checks the decision's own stage against that list. Corrections append a newer eligibility event; they never delete the mistaken evidence.
