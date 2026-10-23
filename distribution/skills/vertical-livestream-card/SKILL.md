---
name: vertical-livestream-card
description: THE look for raw footage that is ALREADY 9:16 (a phone livestream, e.g. Alex poolside/couch streams) — floating card over a blurred duplicate of itself, physical elevation shadow, headroom-anchored face crop. NOT a 16:9→9:16 reframe (that's horizontal-to-vertical's job — this skill starts from footage that's already vertical and has nothing to reframe). Use whenever raw source is natively 9:16 phone-shot livestream footage and the deliverable is a stylized vertical short. Trigger keywords: livestream card, vertical livestream, phone stream footage, floating card look, card over blur, already vertical footage, native 9:16 source.
---

# Vertical Livestream Card — the floating-card-over-blur look

## When this applies (the actual decision point)
Check the SOURCE aspect ratio before picking a skill:
- **Source is 16:9 (or any horizontal) → `horizontal-to-vertical`.** That skill's whole job is
  the reframe/crop-to-vertical decision. Do not use this skill for that.
- **Source is ALREADY 9:16 (a phone livestream, most vertical-cam raw footage) → THIS skill.**
  There's no reframe to do; the job is turning the flat vertical frame into a designed card
  composite. `ffprobe -show_entries stream=width,height` the source first if unsure — never
  guess from the filename.

## The look (locked 2026-08-20, reference-reel-calibrated)
A card (default 4:5, full canvas width, hard corners) sits over a blurred, darkened duplicate
of the same source frame — same footage twice, cropped differently. The card reads as a
**physically elevated object**, not a pasted rectangle:
- **Ambient shadow** — tight, low-opacity blur directly under the card silhouette (a whisper of
  contact shadow, no offset).
- **Key shadow** — the card's own silhouette offset ~30px DOWNWARD and blurred wide. This is
  the component that actually sells "floating, lit from above" — almost nothing shows above the
  card; nearly all the visible shadow weight sits below it.
- **Background** — the source scaled down hard then blurred back up (near-tonal, no readable
  detail) and pushed slightly darker so the card reads forward of it.
- **Card crop** — headroom-anchored on the speaker's face, not a naive center-crop. A crop that
  puts the face too close to the top edge reads "too zoomed in" even at the correct scale — this
  was the single biggest miss across bake-off rounds 1–2. Anchor at `face_top - headroom*card_h`
  (default headroom 0.22), clamped to the canvas.
- **Per-item face tracking, not per-clip.** A livestreamer drifts across frame over a long
  broadcast — probe each CUT ITEM's own footage (median face-top over ~5 frames), not one fixed
  crop for the whole assembled clip.
- **No screen-edge gradients.** Earlier attempts added top/bottom vignette fades to the whole
  frame — wrong; the reference reel has none. The only darkening is the shadow model above.

## Why the card aspect is 4:5, not 1:1 or full-height
Bake-off ran three card heights on a real clip (1:1 square, 4:5, and ~1.15:1 short) — 4:5 won
because it shows more of the surrounding scene (reads less cropped) while still being closer to
the reference reel's proportions than a full square. **Don't assume 4:5 is universal** — if a
different reference or a different editor's taste calls for another ratio, that's a one-line
`--card-h` change (see below), not a re-architecture.

## Getting the shadow right — expect 2-3 rounds, don't guess past round 1
The shadow was the hardest part to nail and went through visibly wrong attempts before landing:
1. **First attempt (rejected):** a flat vignette-style band painted at each screen edge. Read as
   "distance between the overlay and the background" being ADDED as a filter, not as a natural
   physical object — the editor's exact words: "You're adding a shadow... not natural. You can
   tell it's [pasted] up, if that makes sense." That's the tell this is wrong: if a shadow reads
   as a filter effect rather than a physical relationship, it's the wrong model, not the wrong
   opacity.
2. **Second attempt (rejected, "too puny"):** a stronger symmetric band, still painted rather
   than modeled. Making a wrong model bigger doesn't fix it.
3. **Third attempt (approved, "that's it"):** switched to the ambient+key elevation model above
   — an actual light-and-distance simulation, not a decorative band. This is what's implemented
   in `scripts/render_card.py::ensure_shadow`.

**When calibrating a new reference look:** measure the reference's ACTUAL pixels before
guessing parameters — pull a still, crop to the seam region, read the luminance profile above
and below the card edge (a tight band above vs a long exponential falloff below is the tell for
this same elevation family). Don't iterate blind on opacity/blur sliders; measure first.

## Running it
```bash
python3 __ACQ_SKILLS__/vertical-livestream-card/scripts/render_card.py \
    --source <9:16_source.mp4> \
    --spans '[[12.3,45.6],[50.0,80.2]]' \
    --out clip.mp4
```
`--spans` is a JSON list of `[start,end]` SOURCE-time seconds per cut item (contiguous items from
one design span, e.g. multiple razor cuts inside one clip, are just consecutive entries — the
concat is seamless since it's the same underlying source). Or pass `--cuts <cuts.json>` pointing
at a file shaped `{"spans": [[a,b], ...]}` or a bare list.

Tunables: `--card-h` (canvas-relative card height, default 1350 of a 1920 canvas = 4:5),
`--headroom` (fraction of card height above the face top, default 0.22), `--canvas-h`/`--canvas-w`.
Requires `yunet.onnx` (shared with `horizontal-to-vertical`) for face detection.

## Downstream — this owns the COMPOSITE only
Captions, music, and delivery are separate stages owned by their own skills
(`caption-clips`, the music-matching chain, `/monday`) — run this skill first to produce the
card-composited base, then hand that file into the normal `/edit` finishing pipeline. Don't
duplicate captioning/music logic here.

## Provenance
Calibrated 2026-08-20 against a real Instagram reference reel (measured pixel luminance at the
seam, not guessed) across two Alex poolside livestreams (BirthdayStream, Top1SalesMasterclass).
Editor-approved after 3 shadow rounds + 3 card-height options. If Alex's livestream setup changes
(different framing, different phone orientation habits), re-calibrate the face-anchor headroom
against a fresh sample before assuming the same 0.22 still holds.
