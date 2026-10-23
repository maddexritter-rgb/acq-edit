---
name: editorial-brain-ingest
description: Distill an editor’s method from full source footage plus finished clips into operational principles, cited examples, and decision cards in the shared editorial brain. Also ingest native cut studies, editor feedback, SOPs, and analytics. Use for “learn how these clips were made” or adding editing knowledge; assembly-design owns new cuts.
---

# Editorial brain ingest

## Scoped production guidance

For a user-directed brand production policy, preserve the original draft and publish stage bodies through the private `scoped_policy_bindings` lane.
→ Follow [scoped policy publication](references/scoped-policy-publishing.md); keep the generic skills neutral and don't promote unverified source examples into final evidence.

For any Premiere access, follow [Premiere Agent startup and advanced stage routing](../edit/references/premiere_start_here.md). Use the configured new bridge by default; if MCP tools are missing in this chat, use its CLI. Keep this skill’s existing creative scope and read-only limits.


This skill curates evidence for later retrieval. It does not edit footage or decide a new
clip. `assembly-design` owns the new edit; `find-precedents` owns retrieval. Store a
compact, evidenced decision in each card; general principles belong in active playbooks
and required reading with concrete actions and checks. Supabase is the operational
source of truth for active playbooks and cards; original files remain the evidence
authority. Preserve a versioned private source copy for each reviewed SOP/prompt.
An unreviewed document is never automatically an active instruction.

## Route the evidence

For **full source footage or podcast links + finished clips**, use
[source-to-clips editor study](references/source-to-clips-study.md). This owns
source-first case analysis, whole-batch synthesis, general principles with actions,
brain publication/retrieval checks, and paper-cut comparison tests. Keep the study
resumable; synthesize after the case analyses are frozen rather than making each
clip a new general rule. The user may supply any editor’s work.

For a repeatable project-by-project campaign, use
[Premiere cut-study mode](references/premiere-cut-study.md). Read the campaign's
master plan and current state first, including after compaction. The campaign owns
its paths, accepted reference authority, case queue and evaluation cadence. This
skill owns the reusable method; `assembly-design` owns any evaluation edits.

Read [evidence-and-packets.md](references/evidence-and-packets.md) for every ingest.
Choose the relevant section for: (a) raw footage + Premiere final, (b) human clip
feedback, (c) SOP/research commentary, or (d) analytics. One case may yield several
cards, but each card must describe one editorial choice or testable hypothesis with
an applicability condition and a counterexample/exception. Keep assembly, cuts,
picture, captions, and audio lessons in their owning stages.

For historical editor claims, start with the case inventory/handoff index. Resolve
project identity and source clocks rather than guessing from filenames or offsets.
An inspected fully edited captioned native sequence may be the reference final when
the campaign explicitly accepts native authority. A v2 assembly packet can then use
`NATIVE_FINAL_SELECTION_VERIFIED` for its evidenced spoken choices without claiming
a delivered export or reviewed acoustic seams. The delivered-final v1 route retains
its existing requirements. A project named FINAL, a rough cut, a model plan, or a
claimed match is not enough. Unresolved words or source occurrences block affected
choices; preserve them as development evidence rather than promoting by wording.
For spoken-selection or seam research, also read [cut-maps.md](references/cut-maps.md).
Build one ordered raw-to-final cut map per case before extracting small decision cards.
Keep `assembly` choice/order cards separate from `cuts`/`boundaries` acoustic cards. The
captioned finished sequence identifies the native reference; caption styling is
outside a cut-only pass. Keep native identity, spoken selection, delivered export,
and acoustic review as separate claims.

For feedback, attribute the actual human and exact clip revision. Never turn model
self-critique into human approval. For analytics, keep metric definition, denominator,
population, time window, comparison, and confounders with the observation. Performance
association is not causal proof or a universal editing rule.

## Prepare and publish

1. Read the source material and create a local [packet](references/evidence-and-packets.md)
   with exact evidence URIs, hashes where available, source/timeline locators, the
   observed choice or feedback, alternatives, limits, and verification gaps. Quote
   sparingly in cards; never upload footage, full transcripts, or credentials. A
   reviewed SOP/prompt may be copied verbatim into the private versioned source
   library; that copy is not itself an active instruction.
2. For a cut study, run `python3 scripts/validate_cut_map.py <cut-map.json>`, then pin
   its path and SHA-256 in each derived packet. Run
   `python3 scripts/validate_packet.py <packet.json>`. Fix factual/evidence errors;
   do not fill missing fields with invented proof. Both validators are structural only.
3. Check the existing `editorial_brain` source and card IDs for duplicates/conflicts.
   Read [supabase-publishing.md](references/supabase-publishing.md) before any write.
   For a new card, run `python3 scripts/prepare_sql.py <packet.json> --out <new.sql>`
   and inspect the exact transaction; revisions need a separately reviewed update.
   Publish only to the confirmed shared project and private schema through an
   authenticated, supported connection. If no connector is available, leave the
   validated local packet and report `NOT_PUBLISHED`; do not paste a secret into a
   command or route to an unconfirmed project.
4. Read back the stored row, evidence/status, and bounded retrieval result. A card
   that cannot be retrieved by its actual editorial problem has not completed ingest.
   A card that retrieves for the wrong stage/format needs correction, not more text.

Do not silently overwrite a prior conclusion. Preserve the previous packet, increment
the card revision when changing a card, and record what new evidence changed. Keep
held-out test cases out of precedent retrieval. Feedback changes the evidence record;
it does not automatically rewrite canonical skill rules. Promotion to a general rule
requires repeated support, counterexamples, held-out testing, and explicit editor
approval. New assembly design requires live active playbooks. If their read fails,
stop before choosing moments; do not call local guidance the Supabase brain.
Unrelated stages and already-approved cuts may continue.
