# Leila caption profile — approved V10

Evidence source: the supplied production text-style preset, editing deck, recorded editor workflow, and
the visually approved V10 Premiere test. Body captions—not opening hook plates—are the authority.

For Filmcraft, use [the shared Filmcraft shadow route](filmcraft_captions.md).
The preset-shadow preservation rules below apply to Premiere; preserve all other profile decisions in both backends.

For an explicitly scoped shadow correction, follow [scoped shadow calibration](scoped-shadow-calibration.md); a verified backend-specific override changes only the job-owned shadow state.

- Use the vendored official Premiere text style at
  `presets/leila_captions_official.prtextstyle`. Its native Source Text payload is
  `ClashGroteskVariable-Regular`, Regular, 48 point, centered, white. Do not substitute Avenir, Inter,
  another Clash face, or a manually reconstructed shadow.
- The exact variable face and license are vendored under `fonts/clash-grotesk/`. Run exact PostScript
  preflight before construction; fail closed rather than allowing Premiere font substitution.
- Use the composition-aware placement contract in [caption-clips](../SKILL.md). The calibrated
  69% Y position is only a close talking-head reference, not a standing-stage default.
  For standing Q&A, use a stable screen-center band across full-screen and split layouts,
  normally in one or two lines. Preserve the reviewed top-line alignment when a card
  changes line count; do not recenter each continuation independently.
- Sentence case with clean caption punctuation: remove prose commas, periods, colons, and semicolons;
  retain apostrophes, quotation marks, question/exclamation marks, numeric punctuation, domains, and
  standard abbreviations.
- Build a complete semantic phrase card before wrapping. Usually use 4–10 words per card and treat
  22–23 characters per line as a grouping guard, not a reason to shrink the official 48-point style.
  Prefer two lines, preserve a stable reviewed line break, and show the complete card at once by default.
- Use staged reveals only as an exception when delivery is visibly slow enough that showing the full
  card would read conspicuously early. Prefer a two-state line reveal: show the complete top line,
  then add the complete bottom line at its reviewed onset. Word-by-word reveal is rarer and requires
  genuinely slow, separated delivery or an explicit reviewed override.
- A staged continuation must retain the card, placement, final hold, and animation clock; it must not
  replay an entrance.
- Keep one uniform upright body weight. Do not add bold emphasis for vocal stress. Use the true italic face
  only for represented speech, explicit quotations, and internal speech. Every displayed quote card keeps
  its own visible opening and closing quotation marks, including continuations of a longer quotation.
- Preserve every opaque appearance field from the official `.prtextstyle` donor—including its shadow
  state—instead of estimating the look. Do not add a second shadow, stroke, box, or weight variation.
- Keep the rendered caption block within 80% of frame width (minimum 10% side margins) and the platform
  safe region. Regroup before shrinking. `max_chars_per_line` is a guard, not proof of visual fit.
- The approved V10 test established full-card presentation as the dominant prior. Selective line reveals
  are cadence decisions, not decoration. Word-by-word reveals remain exceptional and require explicit
  review.

## Repeatable native build

1. Copy the official preset into the job workspace; do not edit the canonical asset.
2. Apply it once to an upright donor Graphic in the prepared sequence. Duplicate that donor for quotes
   and enable synthetic italic without changing its PostScript face, size, fill, alignment, or effects.
3. Write a reviewed semantic-card plan (`first`, `last`, explicit `lines`, `reveal`, optional `quote`) and
   pass it to `build_profile_manifest.py --plan`. The automatic grouper is a draft aid, not the production
   editorial decision. The plan must cover every reviewed source word exactly once.
4. Bind both inspected donors to a fresh project hash/profile. Never reuse object IDs from another saved
   project.
5. Generate the manifest with `--caption-profile leila`, review semantic cards and reveal choices, then
   construct with `premiere_native_cards.py`.
6. Save, close, reopen, read back the exact face/48-point size/italic flags/line breaks/timing, and inspect
   the rendered frame before, at, and after every reveal boundary.

Approval provenance: V10 was visually accepted by the user on 2026-09-22. Future changes to font, size,
placement, shadow/effects, wrapping, or reveal policy require a new visual calibration; they are not
silent cleanup.
