# Moment-level editorial profiles

Apply all relevant profiles to each candidate, regardless of the source's container.

## Development before tightening

Choose the strongest worthwhile developed arc the source supports before removing
words. Apply the development guidance in the full live **Actionable takeaways and
the noisy-bar test** required reading. The one-sentence takeaway describes what
the viewer leaves with; it is not a short script or a limit on development.
Hook/reasoning/payoff ranges locate landmarks, not all the beats a clip may keep.

When a selection becomes an isolated tip or assertion, compare it with a genuinely
fuller source-supported arc in the existing editorial intent. Read both literal
versions and state what the fuller version adds to understanding, interest,
specificity, credibility or emotional investment. Supporting reasons, applications,
examples and reactions can develop one promise; do not classify each as another
topic merely because the central claim remains true without it. Choose the version
that delivers the stronger experience, then tighten redundant meaning and empty
delivery inside it. A defensible deletion reason alone does not establish that the
remaining clip is the best selection.

If the source only supports a thin soundbite for the ordinary developed-clip brief,
choose a stronger moment rather than padding it or lowering the selection standard
to fill the batch. An explicitly requested microtip or a compelling standalone
short moment can use a different scale. No sentence count, minimum runtime, extra
worksheet, reviewer or approval gate is added.

## Two tightening passes for the default paper cut

**Choose the promise before polishing the opening.** Compare viable literal source
hooks for cold-viewer clarity, relevant audience, curiosity, the development they
set up, and attention. Explain the meaningful tradeoff in `editorial_intent`; a
numeric hook score is not a quality gate. Remove competing introductions that
restart the same clip. A striking quote loses when its promised payoff is absent.

**Meaning first.** Construct the developed hook → reasoning/story → earned payoff from
the complete interaction. Then challenge every retained sentence or clause: if it
disappears, what specific understanding, proof, emotion, condition, or payoff is lost?
If nothing changes, delete it. A sentence being true or on-topic is not a reason to
keep it. Compare repeated introductions, explanatory restatements, same-point
examples, rhetorical transitions (such as asking what a just-stated phrase means),
and recaps after the landing. Prefer the strongest concrete example when others do
the same job. Do not strip the mechanism and leave an empty slogan.

**Performance second.** Inspect the retained spans themselves, not only their outer
edges. Use the existing candidate performance map to locate false starts, duplicated
words, fillers, breathing gaps, pauses hidden inside stretched ASR labels, and dead
space while writing or thinking. Decide each event against source performance.
Remove empty delay; preserve meaningful suspense, grief, humor, emphasis, turn-taking,
and enough breath for natural speech. Splitting adjacent KEEP word ranges can tighten
a pause without deleting a word. Never use a global silence threshold to decide
every pause, speed up all dialogue, or mute phonemes to hide an unsafe splice.

Keep these passes with the main editing session by default. Make the second pass
against the compiled words and actual retained performance, not the quality of the
written pitch. Return from acoustic inspection to the smallest affected phrase when
necessary; a slightly fuller source-native phrase can deliver better than a tighter
but damaged splice. After that revision, cold-read the whole clip again and record
the intentional word changes before resolving its new boundaries.

Cold-read the literal recompiled dialogue after both passes. Check the question
actually gets answered, quoted speech has an owner, pronouns have referents, and
negations, numbers, counts, qualifications and causal bridges still hold. A moved
ending can become the hook only if the new ending still pays off; do not repeat it
automatically or spoil a story's only reveal. If the hook and payoff concern different
ideas, rescope instead of adding a second hook in the middle. Split broad material
only where each resulting clip stands alone.

In the existing `editorial_intent`, record concrete second-pass changes by source
word range and why the hardest-to-cut remaining example or condition is essential.
Record meaningful pause KEEP/TRIM choices by source time in the boundary receipt.
These are the active editor's decisions, not a new worksheet, score or approval gate.
Duration and cut count are descriptive outcomes, never targets or evidence of quality.
Do not pad a concise clip or amputate a complete one to approach 45 seconds.

**Check the hard counterexample.** Before accepting a major compression, identify
the retained condition, proof, reaction, or causal bridge most tempting to remove.
Compare its literal absence: if the advice changes, the mechanism disappears, or
the ending stops feeling earned, keep it and trim within the beat instead. A true,
on-topic quote can still create a false endorsement when moved before a reply;
compare what that reply originally answered with what it now appears to answer.
Same topic and exact words alone do not establish source fidelity.

Source SOPs are evidence with scope and exceptions. Preserve their older guidance
in the brain, but do not inherit hard duration bands, mandatory hook formulas,
fixed cut cadences, universal fades, or finishing instructions from them.

## Monologue / explanation

**Find the unit boundary first.** This profile has no structural delimiter — no question
opens a unit and no answer closes it, so a continuous talk will silently be treated as one
interaction unless a boundary is established deliberately. Delimit by *proposition*: a unit
starts where a distinct claim is introduced and ends where that claim's payoff lands. The
usual lecture shape may include multiple useful examples. Decide whether they repeat value
or jointly earn one payoff. Set `interaction_words` to complete relevant context, including
omitted branches. This may be the whole file for one clean scripted take.

Find the most compelling claim, contradiction or concrete result the source actually
supports. Rebuild the necessary reasoning and useful examples around it. Avoid thesis-only
clips with the mechanism removed, and avoid repetition that adds no explanatory value.
For monologues, actively reconstruct the interior: retaining a paragraph unchanged
requires examining its clauses and pauses, not merely finding a punchy opening.
A late hook can precede earlier explanation when referents, conditions and chronology still
make sense. End where the promise is delivered, not automatically at the source selection's
original endpoint.

## Q&A

Distinguish a genuine question-answer exchange from a business diagnosis. Preserve enough
of the question or a self-contained answer to establish the viewer's problem; neither
the full interviewer setup nor its automatic removal is required. A cold-open answer
can work if it supplies its own referents. Preserve any condition in the question that
limits the answer. This applies equally to livestreams, interviews and podcasts.

When compressing a long question, distinguish the fact that makes the answer apply
from a second phrasing of the same request. Compare the shorter question with the
answer it introduces: retain a unique condition, dependency or follow-up problem;
remove the restatement when the answer already supplies that distinction. Record
the necessary retained fact in the existing `editorial_intent`, not a new checklist.

## L1 diagnosis

Read the existing `/edit/references/l1_qa_cuts.md` for diagnosis-specific context,
promise ranking and owner-value review. Distinguish a whole consultation from a
self-contained sub-answer. Keep the facts needed to understand why this advice fits
this owner and preserve diagnostic reversals. Do not turn a conditional recommendation
into generic advice or remove the owner merely to make a monologue. Retain useful
owner/host exchanges while cutting repeated discovery that adds no information.
A 60–90 second diagnosis can earn its length through necessary context and reasoning;
that is neither a required range nor a maximum. Apply the same deletion test without
collapsing the exchange into an unexplained answer.
Legacy L1 plans remain supported by their existing compiler.
New assembly plans with this profile use the `diagnosis` extension in the shared
contract; its existing v6 validator checks branch dispositions, retained evidence,
promise scope, ranked alternatives and sentence-edge reviews.

## Conversation / story

Read `/edit/references/podcast_mining.md` for source coverage and conversational value.
Preserve what each speaker is responding to, stakes, the event or mechanism, and the
earned payoff. Questions, reactions and either speaker's final line can carry value.
Reordering is available when it improves the story without manufacturing a response,
changing event order or making someone know something they did not yet know. Preserve
reveals intentionally; a later summary may work as a hook but may also spoil the story.
For a story, retain the beats that cause a change or create an obstacle; cut incidental
"and then" chronology without inventing causal links. Test ending at the performed
resolution before retaining an explanatory moral. For a personality moment, the
resolution may be humor, surprise, or a reaction rather than advice. It still needs
enough source context to stand alone.

The shared assembly contract owns the construction procedure. Existing format references
supply domain checks, not global duration, endpoint, chronology or retention quotas.
