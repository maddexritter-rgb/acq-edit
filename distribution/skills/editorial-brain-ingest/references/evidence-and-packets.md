# Evidence packet contract

One packet captures one reusable editorial decision or hypothesis. Save it beside the
case's research, with stable `packet_id` and version; never edit the raw/final assets.
Decision cards are a compact search index, so `source_uri` should point
to this packet (or an equally accessible immutable evidence document), not merely a
project folder. Use a shared URI when other machines must retrieve the evidence.

## Minimal JSON shape

```json
{
  "schema": "editorial-brain.packet/v1",
  "packet_id": "case-001-question-context-v1",
  "card_id": "case-001-question-context",
  "revision": 1,
  "stage": "assembly",
  "status": "development",
  "evidence_kind": "raw_native_study",
  "evidence_class": "RAW_NATIVE_PARTIAL_NOT_FINAL_VERIFIED",
  "source": {
    "case_id": "case-001",
    "project_uri": "/absolute/or/shared/project/path",
    "project_sha256": null,
    "raw_media_uri": "/absolute/or/shared/source/path",
    "raw_media_sha256": null,
    "transcript_uri": null,
    "final_asset_uri": null,
    "final_asset_sha256": null,
    "cut_map_uri": null,
    "cut_map_sha256": null,
    "premiere_sequence": null,
    "source_locator": "source time or word IDs",
    "timeline_locator": null
  },
  "decision": {
    "title": "Retain the question when it supplies the premise",
    "problem": "The answer begins with an unresolved referent.",
    "observed_choice": "The research packet proposes retaining the owner's question.",
    "alternatives": ["Answer-only opening"],
    "transferable_lesson": "Check whether the answer itself establishes the stakes before removing the question.",
    "exception_note": "A self-contained answer may not need the question.",
    "applicable_formats": ["q_and_a", "podcast"]
  },
  "verification": {
    "native_source_mapping": false,
    "visible_final_match": false,
    "captions_checked": false,
    "audio_checked": false,
    "method": "Research handoff only; no final match claimed.",
    "gaps": ["Exact captioned final and acoustic match unavailable"]
  },
  "provenance": {
    "author_type": "researcher",
    "source_uri": "/absolute/or/shared/research/path",
    "source_sha256": null,
    "created_at": "2026-09-24",
    "prior_packet_uri": null
  }
}
```

## Public finished-clip and paper-cut research (v1 development)

For source footage + public/rendered finished clips without a verified native map,
follow [source-to-clips-study.md](source-to-clips-study.md). Use the existing
`editorial-brain.packet/v1`, `evidence_kind: research_commentary`, and
`status: development`. Use `RAW_PUBLIC_FINAL_TRANSCRIPT_MATCH` only for the named
spoken selections whose source occurrences and reference transcript were reconciled;
keep uncertain choices explicitly unresolved. This class establishes neither visible
caption inspection, native timeline mapping, nor acoustic boundary verification.

Pin the public source mapping and frozen case analysis as supplementary evidence
URIs/hashes (for example, `source.public_mapping_uri` and
`source.public_mapping_sha256`). Keep `source.cut_map_uri` null unless an actual map
satisfying the native cut-map contract exists. Do not invent native item IDs, ticks,
sequence UIDs or reviewed frame boundaries to fit the native validator. Packet
validation remains structural; there is no native certification through this route.

An agent-authored paper cut and its comparison are `research_commentary`, with an
evidence class explicitly identifying paper-only/model-authored evidence. Human
comments about a paper cut may be retained with exact quote, revision and review
scope in that source packet; they do not become timeline approval, a pairwise
preference, or `verified_final`. Use the timeline-feedback interface only when its
actual review requirements are met. Agent preference remains attributed to the agent.

## Historical delivered-final route (v1, unchanged)

No generic `verified: true` flag. In v1, `status=verified_final` requires nonempty raw
media, final asset and hashes, native project/sequence and source/timeline locators,
all four verification booleans true, and a method describing how the visible-caption
final was matched to the native sequence and raw source. Those fields still require
actual inspection; passing the validator alone is not proof.
For `assembly`, `cuts`, or `boundaries` raw-to-final claims, additionally use
[cut-maps.md](cut-maps.md). A `verified_final` packet requires a pinned,
`frame_reviewed` cut map whose case, project, and final hashes agree with the packet.
The validator checks the referenced bytes and structure, not the truth of the
listening receipts. An unreviewed or partially mapped case remains `development`.

## Native spoken-selection route (v2)

When a campaign accepts an inspected fully edited captioned native sequence as
authority, use `editorial-brain.packet/v2`, `reference_authority: native_final`,
`stage: assembly`, and `evidence_class: NATIVE_FINAL_SELECTION_VERIFIED` for supported
`verified_final` choices. This route does not certify delivery, acoustic boundaries
or human approval. Keep v1 historical records unchanged.

Add `source.sequence_uid`; pin a v2 `selection_reviewed` cut map as specified in
[cut-maps.md](cut-maps.md). Copy its exact `verification_scope` and `unresolved_ranges`
into the packet. Verification is confined to named claim IDs, not the whole case.
`verification.native_source_mapping` must be true; describe actual evidence in
`method`, and disclose remaining gaps. The map's pinned receipts must bind the
project, sequence, source identities, exact words and complete interaction.

Add `decision.observed_format` and `decision.transfer_rationale`, an object mapping
every applicable format to its concrete reason for transfer. Separate the observed
choice from the inferred benefit. Do not label all cases universally applicable.

Unresolved delivery or acoustic ranges may remain. An unresolved native identity,
word occurrence, audibility or selection that affects a named claim blocks that
claim. Narrow the scope or keep it development; never remove the uncertainty record.

## What each evidence kind means

- `raw_native_study`: Compare raw source, exact Premiere sequence/items, and visible
  captioned final. Describe specific kept/omitted/reordered passages and viable
  alternatives. Record source and timeline clocks, not just a topic or sequence name.
  A delivered-final claim uses v1 proof; accepted native-final spoken choices may use
  the scoped v2 route. Uninspected drafts and guessed native mappings stay development.
- `editor_feedback`: Quote or precisely locate a human keep/change/delete judgment;
  identify the clip revision and before/after source-word selection. A complaint about
  a cold open is evidence for *that* failed opening, not automatic proof of a universal
  question-first formula. Store the unresolved reason if no revised clip exists.
- `sop` or `research_commentary`: Attribute the author, version/date, section, and exact claim.
  Distinguish directive, example, speculation, and observed edit. Note conflicts with
  other SOPs. A worked example is not a verified historical final by default.
- `analytics`: Record metric name/formula, unit, numerator/denominator, platform,
  population, timeframe, sample size, baseline/comparator, selection bias, and known
  confounders in `analysis_context`. Link exact clip revisions and data extract. Make
  the card a conditional hypothesis until a comparison supports it; never infer a
  raw-to-final edit decision from views or retention alone.

## Normalization before writing

Use one card per problem → observed choice → transferable lesson → exception. Keep
the original wording and the curator's inference distinguishable. Cite precise page,
row, timecode, word IDs, or Premiere item; save multiple source URIs in the packet if
needed. Separate contradictory cases rather than blending them into a vague rule.
Tag format by the *content unit*, not the recording type. Do not propagate a Q&A
choice to monologues unless the causal editorial problem also occurs there. A broad
SOP can be `calibration`; a research observation without final proof is `development`.
Neither may be described in retrieval as an editor's verified final choice.

For a reviewed SOP or prompt, store an immutable private source copy with its exact
text, hash and revision before publishing derived claims. The copy preserves the
original; its existence alone does not make any passage normative. Promote only a
reviewed, cited decision to an active playbook or conditional card.

For a multi-project research library, begin at its handoff/inventory index, not at
the project folder. Numeric labels locate evidence; resolve full project title,
hash, raw source and native/source clock through each case packet. A project count
is not a count of verified raw-to-final decisions.
