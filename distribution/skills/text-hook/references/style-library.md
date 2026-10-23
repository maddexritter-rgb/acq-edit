# Approved style library and batch rotation

Use the current brand's `hook-styles.json` next to its other visual presets, or the explicit library supplied by the user. Keep real selections and brand colors outside this reusable skill. Each style ID identifies a treatment; a handoff stores the complete recipe snapshot used for that render.

A library has `schema: hook-style-library/v1`, a stable `library_id`, and a `styles` array. Each style stores `id`, `status` (`candidate`, `approved`, or `inactive`), `approval_evidence`, `font_path`, `case` (`preserve` or `upper`), `foreground`, `background`, and a preview reference. Colors are six-digit opaque hex values. Approval evidence records the user's selection and review context; model recommendations and unobserved browser favorites do not qualify. A color exploration is not proof of an official brand swatch. A user selecting an Instagram source look establishes the desired reference corpus; a newly built replica still needs its own review before entering approved rotation.

An approved style may specify `collection`, `copy_shapes`, and `semantic_beats` (one or two). Optional `line_styles` assigns different opaque colors, case, font, and `font_index` to each physical display line; one entry applies to every line. `size_multiplier` gives a line initial emphasis. For two fitted lines, `short_line_width_ratio` adjusts the shorter line toward a target fraction of the longer line's visible lettering; start near `.90` and leave the fitted backgrounds independent. Keep a small, noticeable stagger, not exact equality. If the target cannot fit readably between .8 and 1.6 times the base size, rewrite the copy or choose another treatment. `transition_clearance_px` adds bottom padding before the next fitted box while `line_gap_px` keeps their backgrounds overlapping; do not create a transparent seam to gain text spacing. Two or three entries may express a genuine two-beat hook, including a wrapped beat. `padding_x_px`, `padding_y_px`, `corner_radius_px`, and `line_gap_px` set the base geometry. `box_mode: unified` draws one padded background around a single-color thought; otherwise `fitted_lines` draws fitted boxes. Recheck safe-zone fit after changing emphasis or clearance. A font collection index applies to installed TTC fonts; keep the installed path and index in the handoff snapshot.

If the brand library lists `reference_studies`, read the relevant source-linked study when developing new style candidates. A study or approved source *look* is not an immutable render recipe: confirm fonts, colors, safe-zone fit, and a preview before adding a style to automatic rotation.

When asked for more variations, preview candidates using approved copy on the same frame, number them, and let the user select. Give a distinct new treatment a new ID. When review exposes a flaw in an existing treatment, correct its active recipe in place and record the feedback; old handoffs retain their exact snapshots. Do not keep a flawed active recipe merely to preserve its old version or promote unselected candidates.

## Plan a batch

Write the ordered stable clip IDs as a JSON array in the project's `10_WORK`. Run:

```bash
python3 __ACQ_SKILLS__/text-hook/scripts/style_library.py \
  --library '<brand-config>/hook-styles.json' \
  --clips '<job>/10_WORK/clip-ids.json' \
  --collection '<approved-collection>' \
  --shapes '<job>/10_WORK/hook-shapes.json' \
  --output '<job>/10_WORK/hook-style-plan.json'
```

The optional shapes file maps each stable clip ID to `{"shape":"question","beats":2}` (or another supported shape). `text-hook` decides this from the finished cut before style allocation. Omit `--collection` to use the library's `default_collection` and omit `--shapes` when all hooks are one-beat. A requested collection is never silently mixed with another to fill a batch.

Use `--previous-plan '<prior-job>/10_WORK/hook-style-plan.json'` to continue the same library's rotation. The next batch starts after the last assigned style. Without a prior plan, start at the first approved style. Reserve assignments by saving the plan before rendering. On retry, reuse that exact plan; do not reshuffle styles because a render failed. One operator should allocate a library's batches sequentially.

Use every compatible approved style before repeating where the written shapes permit it; if there are at least twenty compatible approved styles, twenty clips receive twenty different styles. If the batch is larger than the compatible library, cycle evenly and report the actual distinct count. Never force a question/answer style onto a direct statement just to avoid a repeat, and never invent approvals to meet the batch size. An explicit user style request overrides rotation for that job.

Copy each assignment's `style_id` and full `style` snapshot into the clip's text-hook handoff. Keep `selected_text` and input `display_lines` in their original spelling/case. The renderer applies the approved case transform only to display text and records `rendered_display_lines`. Native adapters use those rendered lines and the same font/colors; the source-supported wording remains intact in the handoff.

Each clip still needs its own measured placement and full opening review. Font size and line wrapping adapt to the actual headline and frame; color, font family, and casing stay with the assigned style. The helper first fits between 116 and 60 px at 1080 width, then Instagram Reels displays that fitted size at 85%, with a 50 px final floor. This is a sizing treatment, not an excuse to use unreadably tiny text. Prefer a better line break or faithful shorter copy over smaller type. If a style cannot fit safely/readably, mark that assignment as a placement conflict and resolve it explicitly. Caption replacement is an editorial choice made from opening geometry and clean-layer availability, never a way to force style rotation.
