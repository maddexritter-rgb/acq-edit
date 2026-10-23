# Caption research: retained findings

Local knowledge package, consolidated 2026-09-17. Research is paused at the user's
request. Loading this file is not an instruction to resume research or change
accepted outputs. No external drive is needed to understand these findings.

Read [research_examples.md](research_examples.md) for concrete decisions and
[research_unresolved.md](research_unresolved.md) for candidate status and resumption.
The maintained production procedure remains
[native_premiere_workflow.md](native_premiere_workflow.md); this package does not
replace it or install experimental flags in the CLI.

## Acceptance standard

The user accepted the full native side-by-side as shippable while explicitly
not identical to the human reference. Learn sound editorial decisions, not
pixel-perfect imitation of every individual choice. Neither reference
inconsistency nor perfect reconstruction of the editor's reasoning was proved.

Separate these outcomes:

- **Actual error:** incorrect/omitted speech, changed numeric meaning, wrong
  represented voice, future-sentence reveal across a real pause, unsafe layout,
  camera/speaker-boundary violation, or failure to preserve editable native data.
- **Valid alternative:** readable phrase partition, emphasis choice or hold
  differing from the reference without violating meaning, timing or coverage.
- **Uncertain:** disputed acoustic onset, ambiguous amount, unknown final-export
  identity or unreviewed omission. Do not turn uncertainty into a pass or a fix.

One-frame reference differences alone do not prove a timing error. Do not spend
another full render solely to match an acceptable weight or hold choice.

## Timing and grouping findings

Word-level ASR is evidence, not frame-accurate truth. It can attach preceding
silence to a short word, stretch a token over a pause, omit quiet speech, or
produce zero-duration words. Quantizing bad timestamps preserves the error.
Correct source-supported timing before regrouping and splitting at cuts.

Distinguish first-word onset, ordinary within-phrase reveal, and next-phrase
pre-reveal across a genuine pause. A long onset-to-onset interval may simply
contain a long spoken word; inspect end-to-next-start gap separately.

Preserve meaningful restarts and repeated complete statements through cleanup.
Duplicate text does not establish a stutter. An interruption dash must not cause
the complete word preceding it to be deleted. Keep semantic-boundary metadata
separate from visible punctuation; ASR punctuation is only a candidate boundary.

Short pronouns/connectives deserve review, not automatic merging, bolding or
deletion. A solo `I` caused by faulty onset/grouping should become `I felt like`
when source rhythm allows; deliberate `I..` or `and..` can be appropriate.
Already-revealed prefixes can persist into a later reveal without advancing the
incoming words. Update text, styled runs, inherited IDs and animation consistently.

Camera cuts split render segments, not necessarily semantic ownership. Continue
already-seen text when needed, keep one source-coverage owner, and advance source
animation time instead of replaying the entrance. Do not truncate and leave holes.
Do not use reference cut times from a different edit without clock alignment.

Five- and six-word cards occur; cadence preferences are not a four-slot native
capacity. Keep phrases/amount qualifiers intact when they fit, then measure actual
font width. Long lines and short holds still require rendered review.

## Voice, emphasis and placement findings

Physical speaker, represented voice, camera view and style are independent.
Guest speech stays guest-colored over a host reaction shot. Numbers do not
override voice color. Quotes do not automatically imply another speaker:
internal thoughts can retain host color with italic; quoted terminology can
remain upright in the current voice. Inspect meaning and lead-in context.

Weight and size are independent: a face may change at unchanged size; a repeated
statement may be stronger the second time. Contrastive function words can be
emphasized. Noun/number keyword rules are only heuristics. Exclamation marks and
singleton cards do not automatically justify a peak tier. Punctuation itself can
have independent styled runs. Font suffix alone may not expose synthetic italic.

Use exact installed PostScript faces and approved donor graphics. Font
substitution invalidates typography/width/position training. Presets can be
applied once to donors; batch cloning retains real shadow and animation without
per-card UI work. Native Graphic runs, not the old four-slot MOGRT probe, are
the proven editable transport.

Height is camera/layout-dependent, but an observed delayed height change may
occur after a deliberate blank rather than during a visible caption. Match
caption visibility and camera timing before concluding the placement is late.
Raw stored size/position is not automatically rendered screen geometry.

## Text meaning and annotations

Audit normalization's meaning as well as its spelling: amounts, ranges, magnitude,
currency, denominator and units. Complete source-ID coverage can coexist with an
incorrect value. Never sum adjacent alternatives or infer millions from a lone
decimal. Contextual ranges and compact prices require explicit evidence.

Distinguish spoken parentheticals, substitutions, added glosses, sound events and
redactions. Spoken words and reviewed substitutions retain source IDs. Added
explanations and laughter annotations do not acquire fictitious spoken IDs.
Silent edits can provoke plausible ASR completions; do not reconstruct a redacted
name from model agreement. A logo can visually represent a word missing from text
extraction, but that does not automatically supply accessible SRT coverage.

Reference laughter treatments include `crowd laugh`, `crowd laughing`, and
`*audience laughing*`. They support optional verified sound labels, not automatic
`ha ha ha` in every gap. Some gaps are deliberate and valid.

## Evidence discipline and efficient review

Keep source word IDs, raw timing, source hashes and review decisions separate from
display text. Inspect coverage after normalization AND cleanup/grouping. Preserve
unknowns; a note approving a look is not a blanket source-omission waiver.

The project library had 122 projects and 120 automatically nominated final
sequences, not 120 visually certified finals. A later 128-row partition included
reference-package entries, not 128 unique library projects. Session provenance,
final selection, local availability and actual shipped status are separate facts.

Cache extraction/transcription and review meaningful exceptions. Reuse bounded
regional evidence before new ASR calls. Freeze candidate code before evaluation;
record prior exposure by capability. Tests, saved-file readback, native reopening,
full export and user editorial acceptance are different gates. Do not turn long
research logs or passing synthetic tests into claims of autonomous readiness.

Original videos/projects and large frame collections remain external job assets.
They are needed to reproduce a visual experiment, not to load this local knowledge.
