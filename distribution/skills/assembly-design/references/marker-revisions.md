# Revise a reviewed batch without losing the good work

Capture the live project/sequence identity, every marker's exact text and time, native
source/timeline ticks, routing and link groups before making changes. Preserve the
marked project and compare it with the handoff snapshot. A saved file can lag an
unsaved live timeline; do not diagnose a save/reopen defect from that mismatch.

Account for every note, including empty markers, duplicates, praise, deletions and
later comments that supersede earlier ones. Bind notes to source-word spans and
nearby native joins; a marker time is a locator, not proof of which phoneme failed.
Keep the exact user wording beside the model's interpretation, planned action,
source evidence and eventual result. Ask only about ambiguity that affects the edit.

Separate three kinds of evidence:

- **Editorial:** source words establish missing context, an incomplete explanation,
  an unearned ending or the wrong speaker. Read the full relevant source exchange.
- **Acoustic:** compare the intact phrase, the rendered reviewed join and proposed
  repair on the verified played channel. → Use [audio-precision.md](audio-precision.md).
- **Execution:** compare delivered and reviewed source/timeline geometry. If the
  user moved items, or another operation intervened, retain that confound. Frame-grid
  edges alone do not identify which operation changed them or prove audible damage.

Protect explicitly accepted clips at the reviewed geometry. Leave unnoted work
unchanged unless a demonstrated defect requires a documented repair; absence of a
note is not explicit approval. Do not globally restore an older timing plan because
some reviewed edges changed. A later preference for a complete duplicate can
supersede a request to repair its shorter version.

Preserved is not exempt from mechanical validation. Report picture gaps, off-grid
picture boundaries and unintended AV offsets even when they match the reviewed
baseline. With authorization to repair these while keeping the cuts, start from a
fresh current snapshot, protect audio/markers/effects and limit the repair to picture
coverage and source-clock alignment. Never regenerate over the editor's current work.

Fix the smallest unit that resolves the note: a join, context line, opening, ending
or scoped proposition. Preserve praised body material. If a tiny omission breaks
a fluent phrase, compare retaining the source-native phrase instead of repeatedly
shaving it. A requested merge needs a new coherent spoken arc, not concatenation.
Use the existing compiled revision comparison for changed words; never silently
change a selection as part of an acoustic repair.

After rearranging or ranking the revised clips, verify their source ticks, relative
timing, sync and native link membership again, then save/reopen/read back. A pure
timeline translation changes start/end by the same amount while preserving source
in/out and duration. Anything else requires explanation. Approved source boundaries
must survive the actual move/import path, not merely the initial placement test.

`scripts/compare_native_timing.py` compares matching track-item snapshots exactly,
allowing only a declared common translation per clip group. Use explicit index maps
after deletions/reordering; never infer identity from rank alone. A clean report is
mechanical evidence only. Re-audition changed joins and distinguish local inspection,
model observations and the user's actual acceptance in the final handoff.

Generalize confirmed failure mechanisms into the owning procedure. Put exact notes,
speaker identities, source examples and accepted/rejected revisions in the project
and → Use skill: `editorial-brain-ingest` for their Supabase records. Do not promote
an untested explanation or one repaired timestamp into a universal editing rule.
