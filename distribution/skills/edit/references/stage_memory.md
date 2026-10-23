# Stage memory handoff

Before each high-judgment stage, query only that stage from `find-precedents` and pass the cited briefing to the owning capability. Use stages in this order: `assembly`, `cuts`, `boundaries`, `camera_reformatting`, `captions`, `audio`, `qa`.

Historical editor evidence is **final-only**. The retrieved decision must be certified against a captioned export or captioned final timeline. Never inspect or learn from drafts, rough cuts, working sequences, intermediates, or model trials. A name containing `FINAL` is insufficient without visible-caption proof. If final identity is uncertain, retrieval must return nothing. Raw footage is valid as replay input, but historical choices are learned only from raw-to-verified-final comparison.

Research one case end to end in this order: synced raw cameras/mics and frame-accurate transcript → cuts/order → camera, split-screen, reframing, and keyframes → captions, grouping, emphasis, size, font variation, and definitions → audio/QA. All stages share the same word/frame map. A final-only observation that skipped the raw-to-final chain is a hypothesis and must not retrieve.

Completion does not mean every stage automatically becomes precedent. The certification stores `eligible_stages`, and each capability can retrieve only if its own stage cleared review. Failed or unresolved stages remain counterexamples/unresolved evidence while independently cleared stages can still teach their owning capability.

```bash
python3 __ACQ_SKILLS__/find-precedents/scripts/find_precedents.py \
  --memory-db "$EDIT_MEMORY_DB" --stage <stage> --case-id <case-id> \
  --exclude-case <case-id> --topic "<the decision being made>"
```

The active replay/holdout case must remain excluded until both baseline and memory manifests are locked. Retrieval is advisory: cite decision IDs/evidence paths in the manifest, inspect exceptions, and let source fidelity override precedent. Baseline manifests receive no retrieved evidence. Memory manifests record every retrieval event and which decisions changed.

Never promote or rewrite a canonical skill from a retrieval result. Promotion follows the tracker decision-memory gate.
