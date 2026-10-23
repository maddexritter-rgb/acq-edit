---
name: caption-clips
description: Create accurate short-form captions as editable native Premiere Graphics or burned video using Alex, Leila, or Sharran profiles. Use for captioning, caption revisions, subtitles, grouping, timing, speaker styling, and Premiere caption builds.
---

# caption-clips

## Scoped production guidance

→ Load [scoped production policy](../edit/references/scoped-brand-policy.md), including on direct invocation; consume the `captions` stage without changing unrelated profiles.
For a scoped shadow correction, follow [shadow calibration](references/scoped-shadow-calibration.md); preserve the official donor asset and separate candidate/native/human status.

For any Premiere access, follow [Premiere Agent startup and advanced stage routing](../edit/references/premiere_start_here.md). Use the configured new bridge by default; if MCP tools are missing in this chat, use its CLI. Keep this skill’s existing creative scope and read-only limits.


One caption engine, three selectable presentation profiles. The canonical implementation is this
folder. Do not hand-roll captions or copy this skill into another live skill tree.


## Filmcraft execution

For Filmcraft editable captions, follow [Filmcraft captions](references/filmcraft_captions.md).
Its required executable handoff enforces display punctuation, represented-speech
quotation/italics, and profile-based caption holds on all native layers.
Use the canonical shadow helper there for every Filmcraft body-caption profile;
project-local weak-shadow defaults and opt-in dark-shadow switches are no longer accepted.
A native-inspected override from the exact scoped caption policy takes precedence only in that production family.
This backend-specific shadow overrides preset shadow transport only in Filmcraft;
Premiere continues to preserve each profile's donor appearance.

## Native bridge execution

Before native handoff or revision, follow the [shared execution contract](../edit/references/premiere_execution_contract.md); keep the donor-graph builder, semantic card IDs and reveal/layout rules owned here.
Bind source/prepared project hashes, target sequence and card manifest to any accepted transfer route; map revised cards to native Graphics and protect picture, Motion and audio.
Native builds must pass complete binary-dependency checks and an explicitly visible owned caption lane; see [visibility and combined dependency integrity](references/native_bridge_transfer.md#visibility-and-combined-dependency-integrity).

Use `scripts/apply_native_captions.py` with the default Premiere Agent profile and [native bridge transfer](references/native_bridge_transfer.md). Transfer the validated donor-built Graphics sequence; for revisions, rebuild the affected semantic cards and transfer a separately identified revised sequence while checking unaffected cards. In-place replacement and subtitle-track editing are not equivalent accepted routes. Inspect rendered glyphs, shadow, emphasis, animation and layout seams, not only the card manifest.

## Choose the profile

Use an explicitly stated brand/profile. If it is absent, ask exactly:

> Which caption style: Alex, Leila, or Sharran?

Automation must pass `--caption-profile`. Direct CLI calls default to `alex` only for backward
compatibility.

| Profile | Body-caption behavior |
|---|---|
| `alex` | Approved Oliver/SPICE profile: Proxima Nova, single-line cadence cards, voice color, emphasis ladder, two-layer shadow, drop-in animation, Oliver v2 normalization. |
| `leila` | Approved V10: official Clash Grotesk Premiere preset at 48 pt; compact centered phrase cards, normally complete; selective slow-delivery line reveals and quote-only synthetic italics. |
| `sharran` | Approved V1: Leila V10 grouping/timing/reveal logic with uniform Inter SemiBold at 48 pt and synthetic quote italics. |

Opening hook plates are not body captions. Route those to `text-hook`.

Read the relevant profile only:

- Alex: [references/alex_profile.md](references/alex_profile.md)
- Leila: [references/leila_profile.md](references/leila_profile.md)
- Sharran: [references/sharran_profile.md](references/sharran_profile.md)

## Composition- and face-height-aware caption placement

Choose caption position dynamically from the face's height and the clear space in
the final reframed picture before building cards. Use the rendered crop, not face
coordinates from the uncropped source. Inspect representative start/middle/end
frames and meaningful leaning positions; compare the face/chin bounds with the
full visible caption block, including shadows. Keep breathing room below the face
and keep text near the visual focus. A profile percentage is a starting point,
not a placement decision; even screen-center placement must move if it overlaps
the face. Adapt the chosen band between materially different compositions, then
hold it stable within a consistent composition instead of chasing every head movement.
For a below-face band, place the top of the rendered caption ink below the lowest
representative chin/beard edge with visible breathing room. A face detector's
rectangle may exclude the beard; verify the composed frame. Size the clearance
to the rendered lettering and composition rather than copying a fixed pixel
offset or Y percentage. Re-evaluate placement after a crop, punch-in, tracking,
or layout revision; check the tallest/multiline card and its entrance at the
closest head positions.
For standing stage/Q&A footage, default to a stable screen-center caption band across
full-screen and host/guest split layouts. Do not blindly apply a profile's lower
percentage: on a standing/wide shot it can put text below the subject's waist.
A lower caption band is a composition-specific option for close talking-head footage,
not a universal profile default. A seated shot showing the torso, hands or lap is a
medium shot even when only one speaker is visible. When the face occupies the upper
half, start near screen center (`composition: "seated_medium"`) and resolve the
actual `y_pct` from chin clearance; do not inherit a low preset that strands text on the
lap or knees. Judge the actual crop, not the recording type or a "closeup" label.
Explicit user placement takes precedence. Inspect
actual rendered glyph bounds against faces, torso, panel seams and delivery safe areas.
Preserve stable card/line alignment and reveal clocks; do not bounce captions with
face tracking or move them automatically on every camera cut. Record the composed
chin/beard-bottom and caption ink-top in canvas pixels, the resulting clearance,
placement reason, and chosen
position and composition in each reviewed card (`composition: "standing_qa"` resolves
to `y_pct: 50`; write an explicit resolved `y_pct` for face-aware placement) and require the backend adapter
to implement that position for every card, including continuations and shadow layers.
For a position-only revision, preserve words, timing, typography, audio and picture.
For two-line split captions, center the visible inter-line gap on the panel divider;
use `split_caption_gap_shift` in `scripts/caption_profiles.py` with rendered glyph bounds,
then apply the same translation to foreground and shadow layers.

## Reviewed display substitutions

For user-requested anonymization, consume Assembly Design’s source-word-linked
redaction handoff; display its approved bracketed role without rewriting the raw
transcript or inventing missing speech. Preserve timing and apply any requested
emphasis to the brackets too. Filmcraft uses the real-face contract in
[Filmcraft captions](references/filmcraft_captions.md).

## Nonessential fillers and listener acknowledgments

Omit nonessential hesitation sounds (`um`, `uh`) and listener backchannels
(`mm-hmm`, `uh-huh`, incidental `yeah`) from displayed captions, even when retained
in the audio. Classify by conversational function, not a blanket token blacklist:
keep a meaningful yes/no answer, consequential agreement, negation, quoted wording,
or a sound needed to understand the exchange. Keep the raw transcript intact and
record each display-only omission with source word IDs/times and its reason in the
caption plan. Reviewed plan entries use `action: "omit"`, `first`, `last`, and
`reason: "nonessential_filler"` or `"listener_backchannel"`; the builder emits an
explicit `caption_omissions` ledger without changing the raw transcript or audio.
Coverage checks must distinguish these intentional omissions from
lost speech. Do not extend neighboring captions across the resulting pause just to
fill the screen. Foreground and every shadow layer must share the omission.

## Shared accuracy contract

- Apply letter-name corrections through `caption_profiles.capitalize_letter_names`,
  with whole-token boundaries. Never replace a suffix substring: `t's` inside
  `it's`, `that's`, `what's`, or `let's` is not a standalone letter name.
  Run `validate_display_casing` on final cards and native readback before export.
- Always capitalize the first-person pronoun `I` and its contractions after the final
  display-casing pass. Live guest style does not imply quotation marks; follow the
  owning profile's speaker treatment separately from represented-speech classification.
- Transcribe the actual source with word timestamps and preserve source IDs/times.
- Never trust ASR alone for names, money, missing spans, rhetorical tags, or disputed words.
- `one` remains the word unless a verified money, adjacent-number, or listicle signal applies.
- Use pinned `--words` and per-project `--corrections` for reviewed fixes; do not re-roll accepted
  transcripts during caption-only revisions.
- Run the transcript coverage gate. Enhanced audio cannot prove that missing speech is absent.
- Inspect rendered text or native readback, not only transcript JSON. Record an accuracy review for
  exact words, omissions/inventions, names/acronyms, punctuation/quotes, and speaker changes.
- Camera cuts and layout transitions are hard presentation boundaries. Never expose incoming words on
  the outgoing shot or replay an entrance on continuations. A natural speech pause may remain caption-free.
- Resolve caption lifetime against the actual spoken interval before splitting at picture boundaries.
  → Follow [segment-aware captions](references/segment_aware_captions.md#speech-lifetime-before-layout-segmentation).

## Generate

Alex burned-video route remains unchanged:

```bash
python3 scripts/spice_caption.py input.mp4 output.mp4 \
  --caption-profile alex [--speaker-mode auto|monologue|qa|read-aloud] [--context "..."]
```

Leila/Sharran editable-native route:

```bash
python3 scripts/spice_caption.py input.mp4 \
  --caption-profile leila --gen-only --work 10_WORK/leila_gen \
  --caption-plan 10_WORK/leila_reviewed_plan.json \
  --native-manifest-out 10_WORK/leila_native_manifest.json

python3 scripts/spice_caption.py input.mp4 \
  --caption-profile sharran --gen-only --work 10_WORK/sharran_gen \
  --caption-plan 10_WORK/sharran_reviewed_plan.json \
  --native-manifest-out 10_WORK/sharran_native_manifest.json
```

`build_profile_manifest.py` is the deterministic manifest entry point when a reviewed word JSON already
exists. For production Leila and Sharran builds, pass a reviewed `--plan` containing exact source ranges,
line breaks, and reveal choices; automatic grouping is draft-only. Every staged continuation retains the
semantic-card ID and advances `animation_elapsed_frames`.

## Editable Premiere Graphics

Read [references/native_premiere_workflow.md](references/native_premiere_workflow.md) before native work.
Use `scripts/premiere_native_cards.py`; do not substitute SRT tracks, flattened overlays, or per-line UI
editing when editable text was requested.

Before construction:

1. Review transcript, phrase grouping, explicit line breaks, reveal onsets, and style decisions.
2. Run `caption_font_preflight.py --native-graphics <manifest-or-readback>` for exact PostScript faces.
3. Use a profile-specific approved donor/profile bound to the prepared project hash.
4. **Match the canvas.** Group with `resolve_cards.py --target-canvas <W>x<H>` (the sequence size,
   e.g. `1080x1920`); never hand-scale `font_size_px`/`max_text_width_px` in a job config. Pass the
   director stream to grouping too (`--director-style`) so represented voice is grouped and coloured.
   If the donor was authored on another canvas (e.g. a 2160x3840 template), run
   `retarget_native_donor.py` on the prepared copy first — see "Canvas contract" below.
5. Build the duplicate sequence offline with `premiere_native_cards.py build`.
6. Open in Premiere, save, reopen, read back text/runs/timing, and render the whole sequence.
7. Inspect the frame before, at, and after every reveal/layout boundary.
8. **Click-test**: select a caption in the Program Monitor. The edit box must sit on the text, inside
   the frame. A centred render does not prove this.

### Canvas contract

A Graphic donor stores its canvas in absolute pixels in two places; only the text-layer Position is
normalized: (1) the Source Text paragraph box (document fields 2/3) and (2) the Graphic's synthetic
media `VideoStream FrameRect` (plus the donor item's FrameRect). Cloned onto a different-size sequence,
(1) renders the text off-centre and (2) puts the Program Monitor edit box off the text so it cannot be
clicked — while every text/run/timing readback still passes.

- `premiere_native_cards.py build` and `verify` now fail closed on this: donor media frame must equal
  the sequence FrameRect, a paragraph box must fit the frame, and its centre must land on the profile
  intent (x = 0.5, y = `y_pct`) computed from the canvas — never from the donor's own position.
- Fix a mismatched donor with
  `python3 scripts/retarget_native_donor.py --project PREP.prproj --profile style.json --output PREP_<W>x<H>.prproj --out-profile style_<W>x<H>.json`.
  It scales every paragraph box by schema, sets the media/item frames, keeps the authored Position,
  re-runs the gate, and records `donor_canvas`. Do **not** "fix" it by moving the anchor (centred render,
  box hangs off-frame) or by scaling only the box (centred render, edit box offset by half a frame).
- Never-used caption tracks are valid targets (`expected_item_ids: []`); no placeholder clip is needed.

Native manifests preserve `caption_profile`, explicit `lines`/`line_breaks`, `semantic_card_id`,
`reveal_index`, `source_coverage_owner`, font PostScript face, weight, italic state, shadow profile,
position, and animation source clock. Each semantic card has exactly one coverage owner even though
earlier reveal states repeat already-spoken text.

## Profile invariants

- Alex continues through `oliver_format.py`, `caption_director.py`, and `generate_spice.py`; changes to
  Leila/Sharran must not alter Alex output.
- Leila/Sharran use sentence case with Alex-style clean display punctuation: remove routine prose commas,
  periods, colons, and semicolons while retaining quotation marks, apostrophes, question/exclamation marks,
  numeric punctuation, domains, and abbreviations.
- Two-line wrapping is explicit and stable in the manifest. Regroup before shrinking.
- Leila uses the approved supplied Premiere text-style preset: `ClashGroteskVariable-Regular`, Regular,
  48 point, white, centered, with the preset's native appearance fields preserved. Its 80%-of-frame width
  limit and 22–23-character line guard are Leila-only and must not alter Alex or Sharran.
- Leila defaults to complete cards. Slow delivery may trigger a complete-top-line then complete-bottom-line
  reveal; word reveals require exceptionally slow spacing or an explicit reviewed override.
- Sharran inherits Leila's approved grouping, timing, line-break, placement, and selective line-reveal
  rules. It changes only the type family: every word remains `Inter-SemiBold` at 48 point with no automatic
  weight/size/color variation; represented speech and quotations use synthetic italic on that same face.
- Sharran clones the approved Premiere preset donor and replaces only its Clash font identifier with
  `Inter-SemiBold`; preserve its native alignment, appearance/effects, position, and animation fields.
- Leila uses one upright body weight with no bold emphasis. Synthetic italic on the same approved Clash
  variable face is reserved for represented speech, explicit quotations, or internal speech, with visible
  quote marks. Never approximate or add shadow; clone the official preset donor so its exact effect state
  survives.
- Font preflight fails closed. Approved font assets and licenses are vendored under `fonts/clash-grotesk/`
  for Leila and `fonts/inter/` for Sharran.

## Gates

Run the profile and Alex regression tests, manifest validation, timing review, font preflight, native
save/reopen/readback, full render review, and caption-accuracy review. Structural checks do not constitute
visual approval.

Detailed shared contracts:

- [references/native_premiere_workflow.md](references/native_premiere_workflow.md)
- [references/caption_card_manifest.md](references/caption_card_manifest.md)
- [references/segment_aware_captions.md](references/segment_aware_captions.md)
- [references/research_findings.md](references/research_findings.md)
- [references/oliver_caption_formatting_spec.md](references/oliver_caption_formatting_spec.md)
