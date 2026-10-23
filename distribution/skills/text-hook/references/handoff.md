# Hook handoff v1

Store one JSON per clip/revision in the existing job's `10_WORK`. Text Hook records copy and evidence first, then resolves layout against the final canvas. Drafts may omit geometry until that stage. The renderer requires every field below.

```json
{
  "schema": "text-hook/v1",
  "clip_id": "C01",
  "source": "/absolute/job/00_SOURCE/clip.mp4",
  "source_sha256": "actual SHA-256 of this exact media file",
  "transcript": "/absolute/job/10_WORK/clip.transcript.txt",
  "transcript_sha256": "actual SHA-256 of that UTF-8 plain-text file",
  "transcript_revision": "current-cut-v1",
  "selected_text": "The cost of a second location",
  "copy_shape": "direct",
  "semantic_beats": 1,
  "supporting_passages": [{"quote": "exact passage from this transcript", "location": "clip seconds or transcript paragraph"}],
  "display_lines": ["The cost of a", "second location"],
  "font_path": "/absolute/path/to/Poppins-Bold.ttf",
  "existing_hook": "none",
  "delivery_platform": "instagram_reels",
  "caption_bottom_px": 1100,
  "safe_rect": [65, 269, 950, 979],
  "protected_rects": [[300, 150, 450, 700]],
  "geometry_evidence": "Path to measured caption geometry or inspected opening frame strip; note coverage and layout changes"
}
```

For changing captions, add `placement_intervals`. Each interval covers consecutive clip-local time and supplies measured **speech-caption** bounds including shadow/background, protected regions, and frame or native-geometry evidence. The renderer calculates `hook_bounds` and writes them back to every resolved interval. Static legacy handoffs remain valid and become one interval. The source observation must cover the full five-second display window; do not use approximate height percentages or ancillary labels as the caption anchor.

Set `caption_strategy` to `preserve` (default) or `replace` and record `caption_strategy_reason`. Preserve uses measured below/above placement. Replace is for an opening where captions would crowd the centered hook or force it outside the safe zone. It requires `clean_opening_source`, its SHA-256, and a visually measured `replacement_hook_top_px`; the clean file must be the same cut/framing without caption pixels. The helper uses its **video only** for the hook interval, keeps the finished source's audio, and restores the finished source's picture and captions afterward. Before using this route, compare opening frames outside the caption region and verify cut timing, picture, and dimensions. For native captions, hide or delay only the identified speech-caption layers for those frames and add an editable hook layer; keep all other layers and later captions intact. If no clean opening/native separation exists, do not obscure burned captions with a partially covering card.

```json
"placement_intervals": [
  {"start_seconds": 0, "end_seconds": 2.5,
   "caption_bounds": [130, 760, 820, 150],
   "protected_rects": [[360, 120, 360, 570]],
   "evidence": "opening strip frames 0-2.5s; speech-caption lower extent checked"},
  {"start_seconds": 2.5, "end_seconds": 5,
   "caption_bounds": [140, 810, 800, 100],
   "protected_rects": [[360, 120, 360, 600]],
   "evidence": "opening strip frames 2.5-5s; line count changed"}
]
```

All rectangles are `[x, y, width, height]` in final-canvas pixels. For a static handoff, `caption_bottom_px` is the measured visible speech-caption bottom, not a preset coordinate. In dynamic handoffs, each `caption_bounds` is authoritative for its interval. `protected_rects` cover relevant face/graphic regions. `safe_rect` comes from the delivery profile and may be stricter than the platform boundary. Inspect actual platform/canvas requirements before delivery.

For 9:16 input, absent `delivery_platform` defaults to `instagram_reels`. Its symmetric [safe-zone profile](instagram-reels-safe-zone.md) is a hard upper bound: top 14%, bottom 35%, and 6% at both sides. The renderer intersects this with `safe_rect` and records `effective_safe_rect`; it never shifts the hook horizontally. Use `delivery_platform: custom` only for a genuinely different destination with a separately measured `safe_rect`. A timed handoff may resolve `anchor_side: above` when below captions cannot fit without crossing the safe boundary. A static legacy handoff lacks a measured caption top and therefore cannot use the above-caption fallback. If neither position fits, return a placement conflict.

The Instagram Reels renderer finds the largest fitting size, then displays at 85% of it (50 px floor at 1080 width). The receipt records both `base_fit_font_size_px` and final `font_size_px`. A project may supply `font_size_multiplier` only for an explicit size treatment; the default is 0.85 for Reels and 1.0 for a custom destination. Recheck geometry after scaling rather than assuming smaller text preserves the same caption-side placement.

`existing_hook: none` is an observation, not an automatic default. The standalone helper refuses existing hooks. An authorized native hook replacement uses the editor route and identifies the exact target layer separately. Caption replacement is a distinct decision and does not authorize replacing an existing text hook.

The helper produces `plate.png`, `preview.jpg`, `source-frame.png`, `resolved.json`, and optionally `review.mp4`. Its resolved recipe contains exact bounds, actual font size/hash, canvas, frame rate, and clip-local display timing. It refuses stale hashes, missing support quotations, mismatched line text, unsafe/crowded bounds, and output reuse. These checks do not establish that the quote supports the headline logically or that supplied geometry was measured correctly.

Native adapters consume resolved text, line breaks, bounds, font, and time; translate pixels into backend units and add clip sequence start. Pixel font size is not automatically the same as native font points. Verify native rendered glyph dimensions and adjust to match. Never run a preview export back into the native timeline as a substitute for editable text.

## Optional approved style assignment

For library rotation, add `style_id` and the full approved `style` snapshot from the [style plan](style-library.md). Its `font_path` overrides the legacy top-level font path. The helper validates approval evidence, identity, casing, and opaque colors; unapproved candidates are refused. One or two semantic beats may use up to three physical display lines when a beat must wrap readably; use that exception sparingly. Per-line treatments require a matching `line_styles` entry for every physical line, or one entry shared by all. `box_mode: unified` fits one padded box around all lines of a single-color card; the default is fitted boxes per line. Resolved recipes record `rendered_display_lines`, `rendered_line_styles`, `box_mode`, foreground/background, and actual font identity/size for native and standalone consumers. Original `selected_text` and `display_lines` remain unchanged for source-fidelity checks.
