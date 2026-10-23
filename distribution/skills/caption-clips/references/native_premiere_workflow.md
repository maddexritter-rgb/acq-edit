# Editable native Premiere captions

Use this route for editable Premiere jobs. It is the same caption capability as
the burned route, with a different output backend. Do not edit every line by UI,
flatten text into a video, or substitute an SRT track when editable graphics were
requested. The approved implementation uses Premiere Graphic clips, not an AE
MOGRT importer. Variable styled text runs remove the four-slot template limit.

## What is established, and what is not

A full-length two-speaker review was user-approved for look, voice colors and
revised grouping/timing. Native shadow and entrance animation came from approved
graphic donors. Automated construction, saved/reopened text/style/frame readback
and a complete native export were verified. Use this supported route with those
checks on each new project; do not describe it as impossible because subtitle
tracks or a particular MOGRT API cannot do it.

This does not certify every transcript, camera-dependent height, optional gloss,
all font variations, a corpus-wide timing model, or pixel parity with the burned
backend. Preserve those boundaries instead of treating one review as universal
approval. Corpus project IDs, footage, fonts, preset files and approved template
projects belong in the brand/project folder, not hardcoded in this skill.

## 1. Recover the spoken content and non-speech events

- Transcribe the original full edit with word timestamps. Preserve a source hash,
  original word IDs, raw timing and source clock. Reuse cached transcripts only
  when their source identity matches. Enhanced audio cannot prove absent speech.
- Use a second independent transcript and bounded regional ASR for disputed or
  missing words. More identical retries are not independent evidence. Recognizer
  confidence/agreement is not frame-accurate hearing; retain unresolved cases.
- If using another export's transcript, align its audio to the supplied edit
  first. Even nearly identical exports can have a small fixed time offset. Do not
  copy its word times or caption boundaries unadjusted.
- Keep transcription and display normalization separate. A decimal in clear
  revenue context can need a currency sign and scale suffix; record the context
  decision rather than globally rewriting that number. Never infer millions from
  an isolated decimal. Use the existing `oliver_format.py` for normalization.
- Review numeric meaning after formatting: value, range endpoints, magnitude,
  currency, denominator and time unit. Colloquial ranges can be fused into one
  amount by ASR or incorrectly summed by normalization while retaining every
  source ID. Valid formatting and complete coverage do not certify the value.
  Compare disputed amounts with source context and independent evidence; retain
  reviewed range mappings with all source occurrences instead of globally
  replacing an ambiguous numeral or guessing an unspoken range connector.
- Preserve source IDs through money merges and repeat/stutter collapse. A
  displayed token can own multiple source IDs; omitted speech must not disappear
  from coverage accounting. Zero-duration ASR intervals remain timing warnings.
- Parentheses and brackets do not determine source-coverage roles. Distinguish
  spoken words with parenthetical styling, reviewed lexical substitutions,
  genuinely added explanations, and unresolved/redacted placeholders. Preserve
  spoken IDs for the first two; never invent spoken IDs for added explanations.
  A reference placeholder is not a verified transcription or glossary correction.
- When a name/term placeholder coincides with a silent edit, inspect the bound
  source audio before accepting ASR guesses. Multiple recognizers can complete
  the same missing phrase. Preserve the redacted/unresolved status; do not infer
  removed words, add them to a glossary, or count the silent interval as verified
  speech. Exact silence supports an edited interval, not its reason or contents.
- Inspect the complete rendered composition before diagnosing missing words or
  isolated connectives from extracted text. A separate logo/image may represent
  a word absent from text-layer extraction. Record that visual evidence separately;
  it does not automatically satisfy text alignment or accessible sidecar coverage.
  Do not fabricate a native text layer or silently waive a missing-word finding.
- Audit coverage after cleanup/grouping as well as normalization. A complete
  short word followed by an interruption dash can be misclassified as a fragment;
  a repeated phrase can survive normalization and then be deleted by cleanup.
  Recover only source-supported occurrences, with their original IDs and timing.
  Identical text is not proof of a stutter: repeated statements may deliberately
  receive stronger emphasis on their second occurrence.
- Review pauses for meaningful non-speech reactions. Verified reference examples
  include `crowd laugh`, `crowd laughing`, and `*audience laughing*`, with differing
  weight treatment. They are editorial sound labels, not verbatim speech. Do not
  automatically transcribe every laugh as `ha ha ha`, fill every blank, or assign
  a crowd laugh to a pictured individual. Use literal laughter syllables only
  when the audio and intended caption treatment support them.
- A sound-event card records `kind: sound_event`, event type, evidence, approximate
  audible onset/end and reviewed display interval. Give it separate event IDs;
  do not fabricate speech word IDs. Keep it off the next spoken sentence unless
  overlap is intentional and reviewed. A blank is valid when there is no useful
  speech or sound annotation to display.

## 2. Resolve one editorial card manifest

Start with the existing caption engine's normalization and grouping. Review the
whole clip and resolve semantic beats before either output backend renders.

- Prefer intact phrase units and useful reading beats over arbitrary character
  packing. Avoid splitting compounds such as `parent training` or `case studies`
  merely to fill a card. Do not combine a completed statement with the opening
  words of the next sentence across a pause.
- Consider an amount with its spoken qualifier (`a day`, `in revenue`, `per year`)
  as a cohesive phrase. A short setup may fit with it, or need its own card;
  do not always isolate the amount or always attach it to preceding words.
  Preserve source ownership through numeric normalization and check the resulting
  groups, not just formatted text. Added contextual labels remain separately
  reviewed annotations, never fabricated spoken-word occurrences.
- A later word appearing with its intact phrase is not automatically a timing
  error. Distinguish first-word onset error, normal within-phrase reveal, and
  premature reveal across a real pause or semantic boundary. Review the source
  and phrase grouping before applying a blanket per-word lead threshold.
- Speaker turns and camera cuts constrain reveals, but camera identity is not
  speaker identity. Keep physical speaker, represented voice, style and camera
  separate. A host reaction shot can still carry guest-yellow speech.
- Use frame-quantized source onsets, reviewed adjustments and explicit holds.
  Do not push a short function word toward its ASR end just because the recognizer
  gave it a long duration; this caused a negation to appear about 0.6s late.
- Before grouping around pauses/cuts, investigate stretched ASR labels using
  acoustic alignment and bounded source-region checks. A recognizer may attach
  over a second of preceding silence to `I`, `wanting`, or `your`. Quantizing that
  timestamp does not make it frame-accurate. Preserve raw times and record the
  evidence for corrected onsets; alignment scores alone are not certainty.
- Recompute grouping after timing correction. A false early onset can place a
  function word before a camera cut and wrongly isolate it from its phrase.
  Prefer `I felt like` over an accidental solo `I`; do not merge across a genuine
  speaker change, pause, or cut by exposing future words. A reviewed delay of a
  frame or two onto the incoming angle may preserve a phrase; record it explicitly.
- Run `scripts/native_graphics/caption_timing_review.py --manifest <resolved.json>
  --words <resolved-normalized-words.json>` before native construction. Review
  every reported early first word, internal pause and function-word orphan;
  resolve or document a source-supported exception. The supplied word timings
  must already have acoustic review: this checker cannot detect an equally wrong
  transcript and manifest. Its tolerances are triage settings, not corpus learning.
- A solo function word is not automatically an error. Preserve its original
  punctuation and inspect the neighboring cards/source rhythm: `I..`, `and..`,
  and quoted connectives may carry an intentional hesitation or transition.
  Punctuation suggests a review question, not proof of intent. Do not make a
  singleton bold/larger simply because it is isolated; grouping and emphasis
  are independent. Never normalize away punctuation merely to silence a flag.
- Separate sentence/phrase evidence from displayed punctuation. Removing a
  period for the visual style must not silently erase a meaningful boundary.
  Conversely, an ASR period is only a boundary candidate, not an unconditional
  instruction to strand the following word. Review changed seams, not just cue
  counts or token coverage, when adopting boundary metadata.
- A long onset-to-onset interval is not necessarily silence: a longer word can
  trigger a false phrase break even with zero gap before the next word. Inspect
  word duration, actual speech gap and semantic completion separately. Resolve
  reviewed phrase units through the existing manifest/grouping path, preserving
  camera/speaker constraints and avoiding future-word reveals across real pauses;
  do not create a word-specific exception list from isolated examples.
- For reviewed interruptions, preserve the source occurrence through cleanup,
  resolve its phrase boundary, then apply reviewed display punctuation. Adding a
  dash after the word has already been dropped cannot recover it. Bind decisions
  to the source hash, IDs and original text; reject stale or partially merged
  mappings. Update semantic-card words/text and all continuation words/text
  consistently, then recheck widths. Research preservation/boundary flags are
  not installed production options; do not assume the current burn CLI honors
  them or that serialization tests certify native or rendered parity.
- **Do not cap a card at a camera cut and leave its remaining hold blank.** Split
  it into render segments. The incoming segment may repeat text already revealed,
  but must not reveal words spoken after the cut on the outgoing angle. Track
  `semantic_card_id`, `animation_elapsed_frames`, `continuation`, and one
  `source_coverage_owner`. `native_graphics/caption_render_segments.py` supplies
  the no-hole partition once the semantic cards themselves are correct.
- Treat every verified full-screen/split-screen/PIP geometry change as the same
  kind of frame-exact render boundary. Resolve grouping before the split: a layout
  change partitions presentation, not language. Never assign a spanning card's Y
  from its midpoint or majority layout. The outgoing render segment uses the old
  layout position; the incoming continuation uses the new layout position, repeats
  only already-revealed text, preserves the semantic card's final end, and advances
  `animation_elapsed_frames` so its entrance does not replay. Deduplicate a layout
  transition that lands on a camera cut. Do not interpolate position between layouts.
- Build the layout track from the final reframed picture, at the delivery frame
  rate. Use a stable anchor once per contiguous layout region, not noisy per-frame
  face measurements. Reject or debounce one- or two-frame false layout flips. For
  each region, verify the actual caption bounding box clears both faces/chins,
  persistent graphics, and platform UI-safe areas; `split-screen` is not by itself
  proof that the nominal seam is safe.
- Native mixed-layout output requires a tested transport for segment-level position:
  layout-specific approved donors or an explicit position adapter with Premiere
  save/reopen/render/readback proof. `premiere_native_cards.py` currently rejects a
  card whose `y_pct` differs from the donor profile. That rejection is intentional.
  Do not work around it by flattening all captions to one Y or by manually dragging
  cards. If the current integration cannot transport position, stop and report the
  missing capability while preserving the resolved layout-aware manifest.
- Review every layout transition on three frames: immediately before, exactly at,
  and immediately after. Fail for any future-word reveal, replayed entrance,
  position tween, one-frame flash, hole/overlap, duplicate source coverage, or face
  collision. A saved-project structural check is not a substitute for this rendered
  transition review.
- Keep outgoing text through short beats when useful; allow deliberate long-pause
  blanks. A 0.75s gap threshold and 0.35s trailing hold worked as project-local
  review settings, **not** a universal learned rule. Do not flatten all pauses.
- Color follows represented voice, including money and numbers. Do not force a
  guest's money phrase white. Preserve approved voice assignments; correct exact
  turn boundaries when evidence shows one phrase was accidentally split by color.
- Weight, size, italic, punctuation and voice are independent decisions. Noun/
  number keyword emphasis is a starting heuristic, not a trained stress model.
  Keep quotes and parentheticals exact; don't add quote marks to all guest speech.
  Quoted inner thoughts can remain in the host's white voice with italic text;
  quotation marks alone do not establish a different represented speaker. Review
  the lead-in and meaning of the quoted span before assigning a voice color.
  Quotes around terminology can also remain upright in the current voice. When
  a spoken quotation marker is rendered as punctuation, retain its source ID in
  an explicit reviewed substitution; do not silently delete the spoken word or
  invent an unspoken closing marker. This is an editorial mapping, not evidence
  that the automatic normalizer already supports the conversion.
- Single-line is the default. Regroup awkward phrases first, then measure width
  with the exact installed faces. Resolve a uniform per-card fit size into the
  manifest; do not shrink only in Premiere and let the burned backend diverge.
  Word-count cadence is a preference, not a native card capacity: a cohesive
  five-word question can fit one line. Qualifiers need not become gloss lines;
  their emphasis is context-dependent, not automatically identical to the amount.
  The approved 2160x3840 template used a 1650px width budget and nominal 160px
  donor text, with selected 1.10 size tiers. These are template settings, not
  universal values for every resolution or camera angle. They are authored in the
  profile's own canvas (`frame_width_px` x `frame_height_px`): pass
  `resolve_cards.py --target-canvas <W>x<H>` and the grouper scales them (a
  1080x1920 sequence gets 80px and an 825px budget) and records `canvas_px`, which
  the native builder checks against the sequence. Never hand-scale them in a job
  config; with a target canvas that is refused.

The native transport consumes the resolved fields below. Existing research v2
manifests use these fields; do not convert through the older four-slot ASS parser
and silently lose timing, inherited font size, or variable runs.

```json
{
  "frame_rate": {"numerator": 24000, "denominator": 1001},
  "cards": [],
  "render_segments": [{
    "id": "card-01/segment-1", "semantic_card_id": "card-01",
    "start_frame": 24, "end_frame": 48, "animation_elapsed_frames": 0,
    "speaker": "host", "kind": "speech", "text": "example text",
    "y_pct": 50.0, "font_size_px": 160,
    "words": [{"text": "example", "weight": "base",
      "font_postscript": "ProximaNova-Medium", "color": "FFFFFF",
      "italic": false, "source_indices": [0]},
      {"text": "text", "weight": "strong",
      "font_postscript": "ProximaNova-Extrabld", "color": "FFFFFF",
      "italic": false, "source_indices": [1]}]
  }]
}
```

Do not invent missing style decisions to satisfy this shape. Optional glosses or
new Y positions need a supported donor/layout adapter and native verification;
the current batch CLI rejects a Y change from its declared donor profile.

## 3. Preserve the preset look with reusable native donors

### Required editorial style pass (before construction)

The builder transports supplied styling; it does not run the caption director or
invent emphasis. A correct transcript, speaker colors and inherited shadow do not
complete this pass. Use the existing director as a proposal, or make explicit
contextual decisions from the source; review weight, cue-level size and italic
independently. Retain approved words, grouping, onsets and ends during a style-only
revision. Do not introduce arbitrary variation just to satisfy a count.

Carry those decisions into each native word's `weight`, exact `font_postscript`
and `italic`, and each card's resolved `font_size_px`. Record intentional size in
`size_tier`; shrink-to-fit alone is not an emphasis decision. Re-measure width
after selecting faces and sizes. Copy decisions into all continuation segments.
Map director indices to the exact normalized source stream; never reuse stale
indices after normalization/regrouping. The historical director prompt can propose
different size/italic conventions; review proposals against the current approved
profile instead of blindly importing them.

When a caption-director `style.json` exists, resolve it into the native manifest
with the supported adapter rather than recreating flat word objects in a job
script:

```bash
# Grouping must see the director stream: represented voice (per-word `c`) is a
# card colour and therefore a grouping boundary.
python3 scripts/resolve_cards.py --words <normalized.json> --cuts <cuts.json> \
  --style <job.json> --caption-profile alex --target-canvas 1080x1920 \
  --director-style /path/to/director_stream.json --out /path/to/grouped-native-cards.json

python3 scripts/native_graphics/resolve_director_style.py \
  --manifest /path/to/grouped-native-cards.json \
  --director-style /path/to/director_stream.json \
  --out /path/to/resolved-native-cards.json
```

The base size defaults to the manifest's `nominal_font_size_px` (the profile size
already scaled to the target canvas); an explicit `--base-font-size-px` that
differs from it is refused. It is not a width-fit result. The director carries
represented voice only as per-word `c` (it empties `voice_spans`); the style pass
refuses a stream whose marked voice landed on host-coloured cards, because a
style-only pass cannot regroup. The resolver preserves text, source timing, grouping, speaker and color;
it resolves only word weight/italic and whole-card size. It rejects a
deterministic fallback stream because that stream is intentionally flat. A
pre-provenance legacy stream requires the explicit `--allow-legacy-stream` flag
only after its style decisions have been reviewed. Re-measure resolved size for
the template safe zone before building.

Supported native donor capabilities constrain transport, not editorial intent.
The current builder selects a donor by `speaker` and requires its exact face runs
and color contract. A donor profile may provide an upright/italic run map per
weight, for example `"runs":{"base":{"upright":12,"italic":18}}`; legacy
single-offset runs are valid only when their donor's one italic state matches the
word. If a reviewed italic span or weight is unsupported,
prepare/verify a compatible donor/profile or report that limitation. Do not erase
the style decision and silently ship base text. Do not change represented voice
just to access an italic donor. This gate does not add new donor capabilities.

Add `style_review` to the resolved manifest, covering all render-segment IDs:

```json
{
  "style_review": {
    "mode": "editorial", "reviewed": true,
    "segment_ids": ["card-01/segment-1"],
    "weight": {"status": "applied", "reason": "The contrast word carries the payoff",
      "targets": [{"segment_id": "card-01/segment-1", "word_index": 1,
        "text": "text", "value": "strong"}]},
    "size": {"status": "applied", "reason": "This payoff card gets a subtle whole-line bump",
      "targets": [{"segment_id": "card-01/segment-1", "tier": "emph", "font_size_px": 176}]},
    "italic": {"status": "not_applicable", "reason": "Reviewed literal host statement; no italic treatment warranted"}
  }
}
```

The example requires its actual card to have `size_tier: "emph"` and
`font_size_px: 176`; these numbers are illustrative, not universal. Italic targets
use `word_index`, exact `text`, and `value: true`. Targets are concrete audit
examples of actual editorial decisions, not quotas. An axis with no warranted
variation needs a genuine clip-specific `not_applicable` reason, never a stock
excuse for skipping review. Do not require italics or larger text where unsuitable.

For explicitly requested simple captions, use
`{"style_review":{"mode":"uniform_requested","user_request":"<actual request>"}}`.
Do not fabricate that request. Legacy manifests missing review must be reviewed,
not automatically backfilled with approval. Existing saved-file verification is
unchanged; new builds fail before writing if the review is missing or its targets
were flattened. Run the same preflight independently with:

```bash
python3 scripts/native_graphics/caption_style_review.py --manifest /path/to/resolved-cards.json
```

The build receipt records this structural check. It does not certify taste,
semantic emphasis or native rendering: inspect representative weight/size/italic
moments in the full native export as well as verifying saved styled runs.

Prepare a **copy** of the intended sequence with the correct picture/audio and a
dedicated graphics track. Store the approved host/guest graphic donors and their
profile in the project/brand workspace. They must be present in this prepared
project's object graph; the batch writer does not import another graph implicitly.
Find retained profiles with `rg --files <brand-project-root> -g '*native_style_profile.json'`.
Read their approval provenance and hash, rather than picking a random old scratch.
Never reuse the old clip's picture/audio as the new job's source: prepare a new
sequence copy and a fresh hash-bound profile for that job.

Apply the supplied text/animation presets once to reusable donor graphics when
preparing a style template. The proven batch route duplicates the resulting native
text/effect/keyframe graph, so every card inherits the same shadow and animation.
It does not approximate the shadow manually or apply presets through UI per card.
Preserve mixed base/emphasis donor runs and the real italic faces. A missing face
is not fixed by selecting a nearby dropdown variation: run the font preflight for
the exact embedded PostScript identities. Installing/replacing fonts requires the
user's authorization; a hidden Adobe cache entry alone does not prove availability.

External profile contract:

```json
{
  "project_sha256": "<prepared project hash>",
  "sequence_uid": "<exact sequence UID>", "track_index": 5,
  "expected_item_ids": ["<existing caption-track item IDs in order>"],
  "y_pct": 50.0,
  "donors": {
    "host": {"item_id": "<mixed-style donor item>",
      "runs": {"base": 0, "strong": 1}, "color": "FFFFFF", "italic": false},
    "guest": {"item_id": "<mixed-style donor item>",
      "runs": {"base": 0, "strong": 1}, "color": "FED90F", "italic": true}
  }
}
```

Inspect actual run indices; don't assume 0/1. Bind the profile to the prepared
project hash. Refresh it only after inspecting any user edits. Never use old object
IDs after Premiere saves; saved files can renumber them. Verify by guarded track
order plus text/ticks and properties, not stale item IDs alone.

### Canvas-matched donors

A donor's Source Text paragraph box (document fields 2/3) and its Graphic media
`VideoStream FrameRect` are absolute pixels of the canvas it was authored on;
only the text-layer Position is normalized. A donor from a 2160x3840 template in
a 1080x1920 sequence renders off-centre and its Program Monitor edit box lands
off the text (it cannot be clicked), while text/run/timing readback passes.
Build and verify refuse that geometry. Retarget the prepared copy first:

```bash
python3 scripts/retarget_native_donor.py --project PREP.prproj --profile style.json \
  --output PREP_1080x1920.prproj --out-profile style_1080x1920.json
```

It scales every paragraph box by schema, sets the donors' media and item frames
to the sequence canvas (recording any other items sharing that media), keeps the
authored Position (so the authored centre is preserved), re-runs the gate, and
writes `donor_canvas` into the new profile. Then build, Premiere save/reopen,
render, and click-test a caption in the Program Monitor.

## 4. Batch construction — no Bridge calls and no per-card UI

```bash
python3 scripts/premiere_native_cards.py build \
  --project /path/to/prepared-copy.prproj \
  --profile /path/to/native-style-profile.json \
  --manifest /path/to/resolved-cards.json \
  --output /path/to/new-native-review.prproj \
  --sequence-name 'Native caption review'
```

The command refuses an existing output, stale project hash, changed target track,
unsupported face/color/italic/Y, overlapping intervals, unresolved graph references,
and unshared-track violations. It retains unrelated objects and replaces only the
selected caption track's references in a new file. A fresh sequence UID prevents
Premiere selecting a same-UID sequence from a different open project copy.

Implementation details for maintenance:

1. Resolve shared Source Text payloads by `BinaryHash`; conflicting payloads fail.
2. Clone each caption's isolated object graph. Remap numeric IDs; explicitly retain
   source media and master-clip references at the declared shared boundaries.
3. Rebuild the ordered native styled-run vector by cloning validated donor payloads
   and updating relative pointers. Preserve opaque style fields instead of guessing
   a replacement serialization. This supports variable run counts (bounded at 256),
   with payload-size and exact roundtrip checks.
4. Set timeline Start/End in integer Premiere ticks (254016000000 ticks/second).
   Retain source-clock animation keys. `SourceIn = donor SourceIn + elapsed ticks`;
   `SourceOut = SourceIn + segment duration`. Do not stretch or restart an entrance
   at a continuation cut. An omitted saved Start means zero and is handled explicitly.
5. Apply the already-resolved uniform font size to each run; retain donor style,
   shadow and position/opacity animation. Emit a per-card receipt with expected runs
   and timeline/source clocks, then decode the written project independently.

## 5. Guarded Premiere opening, save/reopen and full review

Coordinate exclusive Bridge ownership with other active tasks. Check the current
project and preserve unsaved work. Open the new copy; guard **every** call by exact
project path and unique sequence UID. Never assume an active sequence stayed put.

If placing source media into a prepared scratch sequence, explicitly target/unlock
the intended video/audio tracks and call `sequence.videoTracks[index].overwriteClip`.
The sequence-level overwrite API previously ignored intended track arguments and
overwrote the caption lane. Assert picture, audio and caption counts before saving.

Through the Bridge, read every graphic's start/end, in/out source ticks and effects.
Save only the new project, close/reopen that copy, and compare readback before/after.
Then verify saved text and run properties with:

```bash
python3 scripts/premiere_native_cards.py verify \
  --project /path/to/new-native-review.prproj \
  --receipt /path/to/new-native-review.receipt.json
```

The saved-file verifier alone does not certify that Premiere opened or rendered it.
Require actual native readback and a complete export as separate gates. Use the
available Bridge/export integration (→ `edit` skill's guarded export helper), not
manual per-line editing. No-result/timeout is unverified: inspect the live process
and mailbox before retrying; do not duplicate a possibly-running export.

For a template-derived sequence, reconcile the actual picture/audio item extent
against the requested export range. Sequence end metadata may retain an older
donor's duration. Inspect all tracks for trailing items and set exact frame/tick
in/out points; do not export a stale duration or shorten genuine live content.

Generate the review/accessibility SRT from the resolved native segments, not a
stale ASR/ASS baseline. Use the existing exporter in native mode:

```bash
python3 scripts/export_premiere_srt.py --manifest /path/to/resolved-cards.json \
  --receipt /path/to/native.receipt.json --cuts /path/to/reviewed-cuts.json \
  --out /path/to/review.srt
```

The cuts file contains `hard_boundaries`, each camera boundary using
`{"kind":"camera_cut","reference_frame":24}` in the same sequence frame clock.
An explicitly reviewed single-shot clip may have an empty list. The exporter
checks native text/card-count/tick equality and rejects crossing supplied cuts.
It preserves explicit definition/gloss line breaks; it does not rewrap text.
Plain SRT cannot preserve the native look. Receipt equality is not a spell-check
or fresh Premiere readback: separately review omissions, names, money units and
contextual substitutions against the source, and disclose unresolved words.

Check every caption at a representative frame, long lines, short cards, all color
switches and continuation-cut pairs. Compare picture/audio against the source to
catch accidental edit changes. Check transcript coverage and sound events separately.
Inspect the actual rendered shadow and animation, not just effect names. Report
technical validation separately from user/editorial acceptance.

Standalone burns still use `generate_spice` and its locked shadow compositor. Both
backends should consume the same resolved decisions, but the old burn command does
not automatically ingest this native manifest. Do not advertise native/burn parity
until the manifest adapter and rendered outputs have actually been compared.

## Recovery

Keep the reviewed version unchanged. Build a new version for corrections. Retain
the source hash, raw/corrected transcript, style profile, resolved manifest, native
receipt, save/reopen evidence and full export together. Release Bridge ownership
explicitly. If a required style or schema is unsupported, stop that native mutation
and explain the missing capability; the transparent-video route remains an explicit
fallback, not a silent replacement for requested editable graphics.

## Maintainer validation

Run `python3 -m unittest discover -s scripts/native_graphics/tests`. To include the
real native-payload roundtrip cases, set `NATIVE_TEXT_STYLE_FIXTURE` to a licensed
`.prtextstyle` fixture; absent fixtures are reported as skips, not validated styles.
Also rebuild a complete approved manifest in a new offline file and compare its
decoded run properties with the known saved native result. The packaged builder's
offline checks complement, but do not replace, the actual Premiere gates above.
