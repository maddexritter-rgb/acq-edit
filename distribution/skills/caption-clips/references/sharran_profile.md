# Sharran caption profile — approved V1

Sharran V1 uses the approved Leila V10 semantic-card, grouping, line-break, timing, placement, and
selective-reveal logic. The only typography change is the font family. Styling remains deliberately
uniform:

For Filmcraft, use [the shared Filmcraft shadow route](filmcraft_captions.md).
The preset-shadow preservation rules below apply to Premiere; preserve all other profile decisions in both backends.

- Inter SemiBold at 48 point for every word. The exact PostScript face is `Inter-SemiBold`; use the
  vendored `fonts/inter/Inter-SemiBold.otf` and fail closed on substitution.
- White fill, centered alignment, 69% Y placement, 80%-of-frame maximum width, and the approved
  Premiere preset's preserved native appearance/effects. Do not manually reconstruct the shadow.
- No automatic weight, size, or color variation. Represented speech and quotations are the sole italic
  exception and retain visible quotation marks. Italics use Premiere's synthetic-italic flag on the same
  `Inter-SemiBold` face; do not switch to Inter Italic or another family member.
- Sentence case with clean caption punctuation: no prose commas, periods, colons, or semicolons; retain
  apostrophes, quotation marks, question/exclamation marks, numeric punctuation, domains, and abbreviations.
- Usually use 4–10 words per semantic card, with 22–23 characters per line as a grouping guard. Prefer
  two lines and never shrink below the approved 48-point size merely to rescue a poor grouping decision.
- Show complete cards by default. When delivery cadence supports it, reveal the complete top line and
  then the complete bottom line at its reviewed onset. Word-by-word reveals remain exceptional and require
  explicit review.
- Production builds require the same reviewed semantic-card plan contract as Leila: exact `first`/`last`
  source ranges, explicit `lines`, `reveal`, and optional `quote`, covering every source word exactly once.

Use the supplied official Premiere preset as the donor appearance base, replace its Clash face with
`Inter-SemiBold` through the guarded native font-replacement contract, and preserve all other opaque style
and animation fields. Save, close, reopen, read back, and render before delivery.

Approval provenance: V1 was visually accepted by the user on 2026-09-22 using the same 23 semantic cards
and 30 timed states as the approved Leila V10 calibration clip. Future changes require a new visual review.
