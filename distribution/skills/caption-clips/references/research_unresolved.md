# Research status and safe resumption

Consolidated2026-09-17. Research paused by user; do not resume automatically.
This local record preserves findings, not a claim that all experiments shipped.

## Established versus experimental

**Established:** native Graphic batch construction with editable variable styled
runs; approved donor look, shadow and animation; exact font checks; separate native
save/reopen/readback/export gates; receipt-matched sidecar generation. A full
comparison was user-accepted as shippable, not an exact imitation of the reference.
See native_premiere_workflow.md for commands and limitations.

**Experimental, not enabled by this package:** adjacent-number collection guard,
spoken-decimal preprocessing, reviewed multi-record numeric range merging,
reviewed restart preservation and cleanup-only sentence metadata, inherited-prefix
refinement, and adjacent-quantity ambiguity detection. Research tests used
in-memory changes to existing engines; their flags are not supported live CLI
options merely because they appear in research notes.

## What the combined experiments actually showed

- Five development transcripts:2,078 source words,11 changed numeric spans;
  seven decimal changes, one option-label correction, three still-ambiguous ranges.
  No newly missing source IDs or cross-speaker normalization merges. This does
  not prove every numeric interpretation or unchanged word is correct.
- Two explicit reviewed ranges survived full-clip grouping exactly once.
  One other range remained rejected for a zero-duration source word.
- One full development clip initially lost eight normalized records. Preserving
  a complete repeated statement reduced this to four; preserving an interrupted
  pronoun reduced it to three `uh` records. Those are tracked omissions, not a
  blanket approval to omit source words.
- A second development clip still lost five records including repeated articles.
  The reference itself can omit a restart; there is no installed general reviewed
  omission contract. Removing expected IDs is not a valid coverage fix.
- Without a voice style stream, the diagnostic groupings mixed speakers in five
  cards across the two clips. Supplying source-linked voice decisions to the
  existing engine eliminated mixed-speaker cards in the follow-up. This is not
  camera-cut, diarization, role-play, or full native-render certification.
- Six reserved transcripts were evaluated with code hashes frozen before the run.
  A price phrase became `4 97`, demonstrating remaining contextual-number work.
  Another changed ownership `fifty fifty` from100 to separate values. Four had
  unchanged numeric output; one retained a pre-existing missing-source flag.
  Preserve this failed/incomplete evaluation, not just successful cases.

## Remaining work, if the user resumes

1. **Contextual quantities:** amounts, shorthand prices, ratios, ranges, conjunction
   forms and years. Do not infer the connector, currency or magnitude from adjacent
   numbers alone. Ambiguity detection flags work; it does not resolve them.
2. **Source timing:** independently review stretched/zero-duration labels, including
   both sides of a speaker boundary. Keep raw transcripts immutable and corrections
   explicitly source-bound. Acoustic emissions and recognizer agreement are not
   certified word edges.
3. **Semantic cleanup:** preserve complete interruptions/repetitions with evidence;
   distinguish stutter editing from actual missing speech. Keep omissions visible.
4. **Placement and style prediction:** camera/face/layout-dependent height, semantic
   stress, quote roles, glosses and independent italic/size/weight axes. Transport
   capacity is not an accurate predictive model.
5. **Shared output decisions:** native and burn paths should use one resolved
   manifest. The legacy burn CLI does not automatically consume the native schema;
   no universal native/burn visual parity was established.
6. **Validation:** final/export sequence selection across the original library,
   shipped-export pairing, independent sessions and nuance coverage remain
   incomplete. Do not label120 automatically nominated sequences as verified finals.

The reserved set had eight clips in an old session partition. Six had cached review
audio/transcripts, not confirmed shipped video. Two lacked local media. A later
sequence-level provenance audit changed some recording dates; one reserved clip
already had an emphasis evaluation. Thus these were not globally untouched
shipped-final validation examples. A live bounded delivery-folder check did not
locate the missing finals; it did not prove they do not exist elsewhere.

## Resume efficiently, without repeating this investigation

- Ask which concrete defect or new clip the user wants improved. Preserve accepted
  outputs; avoid another broad token-heavy research loop without a bounded result.
- Load research_findings.md and only the relevant worked examples. They contain
  the usable knowledge locally; external media are not required to read them.
- Inspect the current engine before implementing: historical experimental results
  are not proof of current code behavior. Extend the existing capability only.
- Create contrastive fixtures: valid compound versus adjacent alternatives, real
  pause versus long word, intentional restart versus accidental duplication.
- Freeze code before independent evaluation. Record exposure and provenance;
  improvements after seeing failures are development, not a fresh blind pass.
- Run a whole requested clip with actual voice/camera inputs. Check source coverage,
  numeric meaning, timing and visual readability; then perform native verification.
- Promote a narrow verified change after backup and approval. Do not install all
  experimental patches together because isolated tests passed.

## What is and is not local

This package contains the distilled findings, examples, evidence limits and
resumption decisions. It intentionally does not duplicate raw video, all frame
grabs, licensed project/font assets or machine-specific experimental scripts.
Those job assets may be needed to reproduce an old experiment, but no local
learning here depends on opening them. Existing skill scripts remain the live
implementation. This packaging operation changes documentation only.
