# Filmcraft editable caption shadows

A native-inspected shadow override in the exact retrieved caption-stage policy
supersedes the default opacity only for that brand/production scope. Resolve it
with `filmcraft_shadow.scoped_shadow_profile`, then pass `shadow_profile` to
`shadow_layer_props`; default calls remain identical for every other production.
→ Follow [scoped shadow calibration](scoped-shadow-calibration.md).

Translate the reviewed caption cards with the project's pinned text adapter. For
all body-caption profiles, import `scripts/filmcraft_shadow.py` from this
canonical skill and call `shadow_layer_props(role, rendered_font_px, shadow_profile)` for every
card's `wide`, `tight`, and `text` layers, in that bottom-to-top order. Record
`PROFILE_ID`, any matched override ID, and the helper's hash in the caption receipt and backend config; use `None` when no scoped override applies.
Do not use the old project-local weak tuples or an optional `dark_shadows=False`
default. A cached project built with those settings must be rebuilt or revised
on its owned caption layers before it can satisfy this route.

At a rendered 75px font size the wide layer is black, 100% opacity, size 9,
blur 48, offset (2,2); the tight layer is black, 100%, size 4, blur 12,
offset (4,6). The helper scales spatial values with rendered font size, not
Filmcraft's font-size input units. Native blur equals Gaussian sigma times three;
copying a large Premiere slider or ASS blur into this field diffuses the shadow.

Keep fill enabled on the shadow duplicates with transparent fill and transparent
character-run colors. Filmcraft builds the shadow mask from enabled fill geometry;
disabling fill removes that mask. Clone exact text, fonts, weights, italic state,
line breaks, position and animation on both duplicates. The foreground retains
the reviewed voice colors, with shadow, strokes and background disabled. Apply
this recipe to every Filmcraft body-caption profile, including profiles whose
Premiere appearance is supplied by a preset. This is a Filmcraft-only shadow
override: preserve their exact typography, uniform weight/color rules, semantic
cards, placement, and reveal timing. Keep the Premiere preset assets and donor
appearance unchanged. Use the actual rendered glyph size for scaling; do not
assume that a native 48-point size equals 48 rendered pixels.

Before a batch export, render a representative white and colored caption over a
light background at delivery resolution. Check the visible dark halo just outside
the glyphs, crisp foreground, and matching animation on all three layers. Include
an actual bright-footage frame. Save/reopen and verify the three native layers;
record visual review separately from structural checks. A correct layer count or
100% opacity alone does not establish readable rendered shadows.

## Required caption handoff

Use `scripts/filmcraft_caption_contract.py` for reviewed Filmcraft cards before
creating native Graphics. `prepare_cards` applies the owning profile's punctuation,
quote styling and short-pause hold defaults. Every card requires explicit `quote`
true/false and the mapped `speech_end`; represented speech must be classified from
context, including quoted replies without transcript quotation marks. Split mixed
narration/quotation at the actual word boundary. Quote continuations retain their
own quotation marks and italic state; narration stays upright.

Bind display omissions to source-word IDs, not positional indices that shift after
an edit. Reconcile each omitted token against the current mapped words: remove only
incidental fillers/backchannels, never quantities, money, negations or qualifications.
`prepare_cards` rejects those meaning-bearing omissions unless an explicit replacement
is supplied (`purpose: replacement`, `replacement_text`); this does not infer permission
to redact. Render the affected numeric or replacement card before the final export.

Hold the outgoing card until the next onset within the profile's short-pause window;
never insert a one- or two-frame blank between continuous phrases. Preserve genuine
long pauses, omitted filler/backchannel intervals, and completed-speech picture-cut
boundaries. Never expose the next words early. Use identical text, style and timing
on foreground and both shadows. Run `verify_native_layers` against current native
items immediately before export; mismatches stop construction, not trigger an audit loop.
Hand-authored JSON and caption-only revisions are not exempt. Reopen and inspect a
quote, its upright neighbors and the frames on either side of a repaired gap.

## Position transport

→ Follow caption-clips’ composition-aware placement contract. Consume the reviewed
layout/card position rather than inserting a backend-wide Y percentage. Verify the
composed glyph position after graphic-layer placement plus clip Motion; these are
separate transforms. For standing Q&A, keep the chosen center band across full-screen
and split layouts. Apply identical placement to foreground and any shadow duplicates.
A position-only revision must preserve text, timing and all non-caption state.

For a requested exact center band, render an isolated foreground on black with
the real font and character styles, with arrival Motion disabled and scale 100,
then use `foreground_ink_bounds` and
`centered_text_position` from the canonical contract. Convert the measured extent
to local coordinates before computing the layer's Position. `graphics.list`
localBounds is the logical ascent/descent box, not visible ink. A point-text
Position of `[width/2,height/2]` is a baseline. Share the resulting position on
all three layers; never center on the shadow halo or an in-progress arrival frame.
Apply the entrance after measuring settled ink. Inspect the composed result.
Keep the settled band fixed through full/split layouts. Resolve arrival with
`profile_caption_motion` using the explicitly selected profile’s
`filmcraft_caption_motion`. `none` means full opacity and fixed clip Motion on
all three layers, with no arrival keys. Never impose another profile’s animation
because the rendering backend is shared. For a profile selecting
**measured fast settle** (`measured_fast_settle`), use a small
downward arrival, most movement on the first frames, then a gentle settle at the
measured center. Use `centered_caption_position` and `centered_caption_opacity`
from the canonical contract in the actual builder. They own the sampled curve
and 90→100% opacity arrival; do not reconstruct it with guessed Bezier handles,
reverse it into a rise, or add scale/pop motion. Keep scale 100 and Motion's
anchor at the canvas center, distinct from the graphic's ink-measured Position.
Pass `canvas_height` to scale travel at other resolutions.

Preserve the curve's real-time speed across frame rates. A short card consumes
the visible prefix; never compress the whole movement to its duration or extend
its caption hold to finish the animation. For a layout continuation, advance
`elapsed_frames` on both helpers and supply the item's native `source_in`; an
already elapsed entrance must not replay. Apply identical Motion and opacity
to foreground and both shadow duplicates. Keep the owning profile's fonts,
emphasis, speaker colors, capitalization, measured placement, and shadow recipe.
Other animation styles require an explicit per-job choice. Inspect a native
entrance and continuation before export. Premiere donor presets stay unchanged.

Run first-person capitalization after **every final** lowercase/normalization pass
with `caption_profiles.preserve_first_person`. Guest-turn italics come from
`guest_turn_italics`; `quote` classifies actual represented speech only. Never
derive quote punctuation from speaker identity, yellow color or italic state.

## Real font faces for emphasis

Honor an owning profile’s explicitly approved quote-only synthetic italic treatment
on its pinned face; this is distinct from synthetic bold or an arbitrary font fallback.
For other requested weight or italic changes, select an installed real family/style face
through `fontStyle` (or a verified explicit font family), with `fauxBold: false` and
`fauxItalic: false`. Do not simulate a heavier face by drawing duplicate foregrounds,
adding strokes, or expanding glyphs. Verify the requested face exists; Filmcraft can
silently synthesize a missing style. A variable font’s family name does not prove its
requested axis instance is available. Use a real static face if necessary, otherwise
report the missing face rather than silently substituting faux styling.
Apply the same Unicode character range and real face to foreground and both shadow
layers, retaining transparent run fill on shadow duplicates. Include brackets in the
range when the whole bracketed label is emphasized. Render that actual styled card
at delivery resolution during construction; confirm crisp glyphs and the requested
slant before the single final export. Preserve all other caption/audio/picture state.
