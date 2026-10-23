---
name: text-hook
description: Write and place a transcript-supported opening headline as an editable or rendered five-second card. Own copy, style selection, measured caption-aware placement, and batch rotation. Use for /text-hook, text hook, opening headline, or hook text during /edit.
---

# Text Hook

Own the complete opening-card decision: the words, matching style, safe placement, and render. Read the finished clip and write a clear reason to watch: a direct takeaway, useful question, or concrete promise that the clip pays off. This is the sole canonical skill for text hooks; `/edit` routes here directly.

## Inputs and scope

- Accept a finished clip, an exact current assembly with its playback transcript, or a supplied transcript. Read the entire cut, including the payoff. A title, first sentence, source-recording summary, or transcript of removed speech is insufficient.
- Reuse the matching transcript; verify media identity and opening, supporting passage, and ending. Inspect the source for disputed words, numbers, or context. If the transcript is absent, use the existing transcription workflow. Do not invent missing dialogue or imply listening from ASR alone.
- For a transcript alone or a writing-only request, return copy without rendering. For a clip or an authorized end-to-end `/edit` run, choose automatically and place the hook after framing and captions settle. Do not add a hook to an assembly-only request, publish anything, or change the spoken cut.
- A user-supplied exact hook bypasses generation. Preserve it and route to placement; flag a material mismatch without silently rewriting it.

## Choose one idea before writing

Use the **rule of one**: one central idea that is easy to understand, believable, and interesting. Source rationale and its limits: [copy reference](references/copy-reference.md).

The headline should be useful or interesting when read alone. It may give the lesson away (“Get one ad channel working first”), ask the viewer's real decision (“When to replace yourself”), name a felt problem, or promise a useful method (“How to buy back your time”). Do not substitute a specific detail from a story for its takeaway: an amount of time, money, or effort can be accurate and still tell the viewer nothing useful. A generic topic label, cryptic teaser, or sentence that only makes sense after watching fails.

Do not force an imperative, question, or story angle. Keep the scope and uncertainty the source earns. Use familiar, concrete vocabulary from the speaker and clip; an abstract “clever” rephrasing is usually worse. If the cut is too weak to support a useful angle, skip it rather than manufacture one.

1. Privately state what the viewer can learn or do differently from this exact clip and which passage supports it. For a story, write the supported lesson or decision, not a recap of the incident. For a list, identify a useful principle across the items rather than announcing that a list exists.
2. Generate several different angles internally. Each candidate must carry one idea; do not stack benefits or merely swap synonyms. A list clip can still have one unifying promise.
3. Prefer concrete subjects and actions over broad topics. Resolve ambiguous pronouns and missing context. A viewer should understand the subject in a glance without knowing the recording, guest, or previous clip.
4. Read each candidate alone. Does a viewer immediately understand the action, decision, or useful subject? Would the clip actually deliver what the line promises? Keep a strong source phrase when it works; novelty is not a requirement.
5. Reject unsupported, cryptic, and vague candidates before ranking. Select by clarity, useful framing, source fit, voice, and reading effort. Prefer direct phrasing over strained abstractions or unnecessary specificity. Do not force a contrarian claim, numbered formula, or artificial curiosity gap.

For a configured opening-card reference corpus, inspect the user's **selected** examples for both copy and visual treatment. Classify the selected idea as a direct position, real viewer question, meaningful contrast, specific method, or concrete stake. This is a choice of emphasis, not a template to fill. Decide whether the wording naturally has one beat or two; a second treatment may emphasize the useful action as well as answer a question or correct an assumption. Use `copy_shape` and semantic display lines to choose a compatible style from the [style library](references/style-library.md). Do not pick a dramatic style first and bend the claim to fit it.

After seeing the measured card, revise line breaks or shorten the same supported thought if the treatment feels crowded. Recheck the revised wording against the transcript. This copy/layout loop can improve the hook; it must not turn a weak source into a stronger invented claim.

Source fidelity is a hard constraint: preserve conditions, uncertainty, attribution, units, and the difference between someone's experience and a universal claim. Do not turn a hypothetical into a result, a possibility into a guarantee, or one example into a rule. Do not merge a numerical claim about a general tactic with one person's separate outcome. Do not invent numbers, stakes, authority, emotions, or direct quotes. Paraphrases are not quotations. A user's Yes on a historical visual reference does not waive this check for new copy.

## Required writing pass

→ Use skill: [slop-detector](../slop-detector/SKILL.md) on every generated candidate that will be shown or used. Apply its canonical cleanup internally; do not duplicate its pattern list here or treat its default response format as a reason to discard this skill's handoff.

Compare cleaned copy to the supporting passage again. If cleanup weakens the interesting detail, repair the wording while preserving the meaning. If shortening removes a necessary qualification, choose a narrower angle.

Aim for one or two readily readable lines. Use natural case and punctuation. There is no fixed character limit; measure the real font and canvas. A two-beat thought may need a third physical line to preserve readable size. Rewrite to fit instead of clipping characters, adding an ellipsis, or making the text tiny.

Do not put a period glyph anywhere in the displayed hook: no sentence-ending periods, ellipses, or decimal points. Write a clean line break or rephrase the thought instead. Question marks and quotation marks are allowed when the copy calls for them. Preserve the meaning of any number when rewriting a decimal; never silently drop its fractional part.

## Match copy to a visual treatment

Read the selected reference study in `<vault>/clients/<brand>/` when one exists. Learn the *decision*: one clear idea before the viewer has context, concrete creator vocabulary, and a second block or accent only when the thought turns. The user's historical Yes selections teach the desired look; a replica still needs visual review. Do not claim a hook caused a post's performance from the card alone. Keep source examples and fonts in brand configuration, not this reusable skill.

Use the current brand's [approved style library](references/style-library.md). A one-beat thought can remain one padded card. A question/answer, correction, contrast, or action emphasis can use two treatments when the wording supports it. For two fitted boxes, bring the shorter line close to the longer line without making them equal: start with visible lettering about 90% as wide, with each box fitted independently. Judge the stagger on the actual frame, not by the number alone. Keep the boxes connected without a footage gap, but give the upper glyphs breathing room before the next color by adding internal bottom padding, not by separating the boxes. Inspect that seam at full size. Use `box_mode: unified` for one padded multi-line card. Recheck copy and source fidelity after changing line breaks. If an approved style cannot fit, rewrite faithfully or report the conflict rather than making the text tiny.

## Place and render

- Display from frame zero through the first frame at or after **five seconds**, capped at clip duration, then disappear. Preserve the spoken cut and audio. After the hook ends, the original picture and captions return unchanged.
- Keep the painted hook horizontally centered on the canvas. Constrain every font glyph, box, padding, and accent to the symmetric [Instagram Reels safe zone](references/instagram-reels-safe-zone.md) or a stricter delivery profile. Never move left to dodge right-side controls.
- Measure actual visible *speech-caption* bounds, including shadows/backgrounds, over the entire opening. Choose the caption treatment for this clip, not by a fixed percentage: **preserve** when the captions and card can both read clearly (usually below central captions with a 24 px gap at 1080 width); **replace during the hook** when lower-third captions would push it out of the safe zone or a larger card would crowd central captions. An above-caption preserve fallback may sit higher than 24 px from the captions to respect the safe-zone edge; keep that full separation and check the face. Judge the opening as a whole, including scene cuts. Ancillary labels do not become caption anchors.
- Replacement requires an exact, caption-free version of the same finished picture for the opening or editable native captions that can be hidden for those frames. Verify framing and cuts match, keep the finished clip's audio, and restore its original picture/captions after five seconds. Never paint a card over burned words while leaving caption fragments visible. If a clean opening is unavailable, use a readable preserve placement or report a conflict.
- Make stable placement intervals when captions change position or line count, or a scene cuts; do not jitter with every word. Carry measured caption bounds, protected regions, hook bounds, treatment decision, and frame/native evidence in the [recipe](references/handoff.md). If the chosen treatment cannot fit safely and readably, report the conflict rather than covering the interface.
- Preserve any existing hook. Replace only an identified native hook layer when asked; a burned hook needs a clean source or explicit revision instruction.

For a standalone downloaded clip, copy media into the existing project's `00_SOURCE`, work in `10_WORK`, and keep the original. The canonical `scripts/render_hook.py` validates source/transcript hashes, supplied support quotations, style approval, measured geometry, and timing; it does not discover captions/faces or judge editorial claims. Run it with the recipe and a fresh output directory, adding `--render` for a separate review video with copied audio:

```bash
python3 __ACQ_SKILLS__/text-hook/scripts/render_hook.py \
  --manifest '<job>/10_WORK/text-hook.json' --output-dir '<job>/10_WORK/text-hook-preview' --render
```

For `/edit` in a native project, add a separate **editable** hook layer to the existing sequence after framing and captions are settled. Use the existing backend's native text workflow (e.g. [Premiere Graphics](../caption-clips/references/native_premiere_workflow.md) or [Filmcraft text](../caption-clips/references/filmcraft_captions.md)); apply this recipe's exact text, line treatments, bounds, and timing. Save, reopen, and read back the hook layer, then inspect the native render. A standalone preview is not proof of native editability. Keep writing quality, geometry, rendered playback, native editability, and user approval as distinct verification results.

## Output and integration

- Default: one selected hook. Keep alternatives and reasoning internal unless requested. Do not pause `/edit` for a hook choice.
- Persist the recipe in the current project's `10_WORK`, using the [hook contract](references/handoff.md): clip/media identity, current transcript and revision, selected text, exact supporting passages, `copy_shape`, semantic beats and their display lines, and timing. A long beat may wrap to a third physical line only if it stays readable. Resolve measured placement after framing/captions are settled.
- After a spoken edit, re-read the changed cut and reselect if necessary. After a framing/caption change, recalculate placement. Explicit hook revisions take precedence over an old recipe.
- For batches, use [style rotation](references/style-library.md). Choose each clip's words first, then assign a compatible approved style; save assignments so retries do not reshuffle.
- For brand voice, read the current project's brand configuration, including `<vault>/clients/<brand>/text-hook-voice.md` and its linked selected opening-card study when present, **before drafting**. Treat user-selected historical hooks as calibration for plain wording, useful framing, emphasis, and the creator's familiar vocabulary. Keep identity-specific presets and real examples outside this reusable skill. The brand profile teaches diction and presentation, but the finished transcript supplies every new claim.
- When a user approves a batch, save the exact approved lines, clip identities, and review evidence in that brand profile. Distinguish explicit Yes decisions from unreviewed clips and distinguish overall approval from a separate copy or placement judgment unless the feedback does so. Use the examples as editorial guidance, never as a formula or permission to reuse a claim in another clip.

Judge writing through actual examples and user feedback. Mechanical validation establishes file and placement correctness, not editorial quality or predicted performance.
