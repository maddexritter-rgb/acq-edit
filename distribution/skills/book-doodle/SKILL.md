---
name: book-doodle
description: Recommend and create selective animated marker-drawing cutaways for approved clip edits. Use for doodles, draw-on illustrations, or the /edit checkpoint before final 9:16 finishing; propose exact useful moments and generate only those the user approves.
---

# Book doodle

For any Premiere access, follow [Premiere Agent startup and advanced stage routing](../edit/references/premiere_start_here.md). Use the configured new bridge by default; if MCP tools are missing in this chat, use its CLI. Keep this skill’s existing creative scope and read-only limits.


Turn a spoken idea into a clear drawing that reveals itself on white paper. The default treatment is a **full-screen 9:16 cutaway** with continuous original speech, then a return to the speaker. This skill owns the drawing treatment; the existing edit, captions and delivery workflows still own their respective layers.

## When /edit calls this skill

Run the recommendation checkpoint **after assembly cuts are approved and read back**, before final 9:16 finishing. Use the locked edit and its timeline-relative transcript, not an earlier candidate list. Do not change the assembly, speech, cut order, or approved framing to make a drawing fit.

1. Screen the whole retained batch for moments where a drawing makes the idea easier to understand. Strong fits: a concrete metaphor, a bottleneck, a process, a comparison, a relationship between things, or distinct steps the speaker actually explains. Identify the specific explanatory benefit, not merely a word that can be illustrated.
2. Review the picture as well as the transcript. Prefer the speaker when expression, demonstration, an existing visual, evidence, or an emotional beat already communicates more. Skip decoration, redundant diagrams, crowded labels, and ideas too brief to read. There is **no quota**: zero, one, three, or more recommendations may be right. Do not force a fixed percentage of drawing coverage.
3. Show one compact batch proposal using [the proposal format](references/proposals.md). Each suggested moment needs a clip title/ID, exact spoken cue and interval, the proposed drawing/action, and one sentence explaining its value. List only the worthwhile recommendations in the user-facing table; record all screened clips in the project plan.
4. Ask once for approval of the proposed cases: “Want these doodle moments? You can approve all, pick IDs, or say no.” Keep any prior explicit decisions. Generate **only approved moments**. A recommendation, silence, or “finish the batch” alone is not a doodle approval. Do useful work on unaffected clips while waiting.
5. A yes to the proposed moments authorizes their stills, animation and integration. Inspect stills internally before animation; **do not add a second mandatory still-approval stop**. Ask again only if the concept/placement changes materially, the user requested still review, or a required account/budget constraint is unresolved. No/skip means finish those clips normally. An unresolved proposal is not permission to silently add or silently discard the drawing.

An explicit direct request to add a specified doodle already authorizes that specified treatment; do not re-ask the same question. If the user authorizes broader creative discretion, record that scope and operate within it.

## Persist the decision

Save `10_WORK/doodles/plan.json` following [proposals.md](references/proposals.md), with clip IDs, locked-cut revision, timeline-relative frame ranges, spoken cues, concepts, user decisions and their evidence. Save a compact proposal alongside it. Resume from this record instead of proposing approved/declined cases again.

If the edit changes, remap the approved cue to the new locked timeline. A pure timing shift preserving the same cue/concept can retain approval after verification; a changed meaning, new moment or materially different drawing needs a new decision. Removed clips must never leave orphaned drawing assets in the final edit.

## Create approved drawings

Read [generation-and-finishing.md](references/generation-and-finishing.md) when building approved moments. It contains the reusable style prompts, blank-first/end-still animation method, timing, optional alpha, integration and QC details.

- Keep the supplied three images in `refs/` together as the default style reference set. Copy their linework, lettering and accent treatment, **not their words, logos or subject identity**. A supplied brand style pack can override the reference set/accent consistently for the whole batch; keep brand-specific configuration in the brand project, not this skill.
- Prefer one readable metaphor per beat. For lists, use separate simple scenes timed to the actual named steps when each helps; avoid one overloaded diagram.
- Preserve the original audio. Generated clips are silent picture assets; discard any provider audio.
- The proven model pairing is an OpenAI image model for stills followed by MiniMax H3 with a blank first frame and the accepted still as end frame. Verify currently available tool/model schemas instead of assuming provider field names. Do not submit video generation for pending/declined cases.
- Store prompts, reference hashes, provider/model/settings, job IDs, returned media, accepted revision and QC in the project's `10_WORK/doodles/`. Never store API keys, tokens or signed upload URLs in the skill.

`python3 scripts/make_plate.py --help` exposes the reusable plate conformer. It preserves diagram proportions, matches destination FPS and exact frame count, holds the finished drawing, and can create a ProRes 4444 alpha companion from the same accepted animation. It does not generate images, change the spoken edit, assemble a whole clip, or upload anything.

## Finish and verify

Use the project's selected finishing route. **/edit remains Premiere-native by default.** Generated plates are removable/retimable picture-layer media above source footage and beneath captions; they do not replace editable source cuts with a flattened final. Explicit headless requests stay headless; see the finishing reference for the current renderer integration boundary.

Check the drawings in motion, their final hold, every entry/exit boundary, caption readability, exact duration and uninterrupted source audio. Give the normal visual auditor the exact approved drawing/hold intervals so intentional illustration holds are evaluated correctly rather than reported as missing faces; this is not a blanket audit waiver. Reject hands/pens, text drift, extra objects, unreadable diagrams, black seams or unexplained freezes outside those intervals. Reuse accepted assets on routine rerenders; reroll only the failed beat, not the whole batch.

Keep generation time, editing/export time, retries and provider-reported usage separate. Report unavailable actual cost/token counts as unavailable; estimates and a few examples are not a cost or consistency guarantee. If two consecutive corrective attempts fail on a beat, stop that beat and propose a simpler treatment; continue independent work on the rest.

Deliver locally through the normal edit workflow. Approval to add drawings does not authorize Frame uploads, Monday changes, posting or messages.
