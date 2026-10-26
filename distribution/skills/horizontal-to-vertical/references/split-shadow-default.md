# Default split-screen finishing

Apply the soft seam-shadow treatment to every newly constructed split screen,
regardless of content format: Q&A, podcast, interview, reaction, or another layout.
This is the default finishing step, not an optional enhancement or a separate user
request. Omit it only when the user explicitly requests a clean seam/no shadow.
Record that opt-out in the framing handoff. Do not retroactively change existing
approved versions during unrelated revisions.

Use the repository profile `assets/profiles/native-split-shadow.json` as the
starting treatment. Keep the shadow linked to the relevant source-panel nest,
under the clean panel. Preserve independent panel motion, source clocks, captions,
and the single dialogue mix. Scope shadows to split intervals only. Full-screen
shots must remain unaffected. Never stack a second shadow on an existing one.

For equal-height top/bottom FilmCraft layouts, apply
`scripts/filmcraft_split_shadow.py` after native panel construction and before
final export. Use its guarded revision/export route from
`docs/NATIVE_SPLIT_SHADOW.md`, supplying the profile and exact current layout IDs.
The agent performs this step automatically as part of finishing; it must not ask
whether to add the default. Inspect existing native state before applying it.

For Premiere, follow [native-split-setup.md](native-split-setup.md): use the named
native preset on the linked shadow-only duplicate, beneath the clean image.
Missing packaged presets or unavailable native controls are explicit limitations,
never permission to load global skills or switch editing engines.

Side-by-side, unequal-height, inset, and multi-panel compositions inherit the same
soft separation intent. Orient and constrain the shadow to their actual shared
edges using a supported native route. The current FilmCraft helper supports equal
stacked panels only; do not force other geometries through it, apply a horizontal
seam blindly, or silently ship them without the requested treatment. Report the
unsupported geometry and repair its owning route before calling finishing complete.

Before final export, record each split interval's native shadow evidence or explicit
user opt-out. Inspect entry, midpoint, exit and adjacent full-screen frames. Reject
hard borders, darkened faces, doubled images, gaps, duplicate shadows, and shadows
persisting outside the split. Correct only the finishing layer; preserve the edit.
