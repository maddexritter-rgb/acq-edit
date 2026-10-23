# TEARDOWN — a bought short-form "workflow" pack (2026-08-09)

What a $100 creator pack actually contained, what was worth taking, and what to ignore.
Kept because the **animation constants** in it corrected a measurement error of ours. The
verdict generalises: buy these for their *asset payloads*, never for their teaching.

## What was in the box

| | |
|---|---|
| video "course" | **~10 min total, all install guides** + one Photoshop-carousel walkthrough. No teaching content. |
| preset pack | `.prfpset`, **663 named entries** — the real value |
| LUTs | 11 `.cube` (incl. a SLOG3→REC709 conversion) |
| SFX | 3 in the pack + 4 more from its linked drive (riser, clicks, reverse bell) |
| transitions | 4 film-burn `.mp4`, already **1080×1920**, 0.17–0.29s |
| templates | 6 `.prproj`, a `.zxp` panel plugin, card-overlay PNGs, a carousel PSD |
| fonts | a list, not files: Akira Expanded (display), Open Sauce Sans, Helvetica, Neue Haas Grotesk Display Pro, DM Serif Display |
| clip decks | 2 `.cdk` (Clip Deck app) — 80 slots of Premiere clipboard captures |

## The one thing that changed our build

Their slide presets state travel and duration explicitly, so they are **ground truth we could
not get by measuring pixels**:

| preset | travel | duration | fade-in |
|---|---|---|---|
| Slide In · **subtle** | **161 px** | 1627 ms | **200 ms** |
| Slide In Up | 295 px | 1468 ms | 200 ms |
| Slide In Left | 465 px | 1793 ms | 200 ms |
| Slide In Up · **Big** | 1056 px | 1168 ms | 200 ms |

Ours was **64 px / 375 ms** — under half their *most restrained* tier.

🛑 **Why our own number was wrong, and the rule it produces.** We had measured 36 px median
travel off the reference reels by tracking the caption centroid across entrance frames. But
**captions fade in while they slide** — a brightness-thresholded tracker cannot see the word
until it is already bright, by which point most of the travel is done. The instrument
systematically under-measured, exactly like the earlier zero-fades probe.

> **When a reference does two things at once, do not measure one of them with a detector that
> the other one blinds.** Prefer a source that *states* the value (a preset, a spec) over a
> pixel measurement of a composite. Same family as the existing rule about generalising from a
> distribution rather than one frame — this one is about the *instrument*, not the sample size.

Applied: `TRAVEL = 150px`, slide = **55% of the word's own hold** (clamped ≥10 frames),
fade-in a flat **200 ms**, smoothstep. Verified safe: of 121 words only 1 has less edge
runway than 150 px, and it carries no text.

## Card geometry — theirs is NOT ours

Their overlay hole is **1031×1031, 25 px margin, ~78 px corner radius**. Our measured
reference is **980×980, 50 px margin, ~48 px radius**, verified at 27 timestamps.
**Keep ours.** The pack is a neighbouring style, not the same one. Don't let a bought template
overwrite a measured number.

## Font question, settled

IoU against our clean 8-sample caption specimen:

| face | IoU |
|---|---|
| **Helvetica Neue Bold** | **0.788** |
| Open Sauce Sans Black | 0.763 (wins on one reel: 0.84 / 0.88 / 0.86) |
| Helvetica Bold | 0.751 |
| Inter Bold | 0.740 |
| Akira Expanded | 0.312 |

Akira scoring 0.31 **confirms it is a display/hook face, never a caption face** — which is how
the pack itself uses it. Our HelveticaNeue Bold (ttc index 1) stays.

## Their usage distribution (from `useCount` in the clip decks)

Real evidence of what a working editor reaches for, not what a tutorial claims:
Continuous Scale-In **12** · 3D Scatter Text Hook **8** · Horizontal Wipe **7** ·
Flicker Text Hook **7** · Zoom Out (Hook Pull) **6** · Weekly Vlog Title Card **6**.

Note what that says: a **slow continuous scale on the hook** is the single most-used move.

## Taken into the vault

- `assets/sfx/` — 5 unique SFX (riser, 2 clicks, focus click, reverse bell)
- `assets/transitions/` — 4 film burns, native 1080×1920
- `assets/caption_anims/` — their free preset pack alongside ours
- `content-skill-system/(1) Tik Tok/(3) ViralREELS/` — 74 tracks, vibe-tagged, indexed

## Ignored, and why

- **LUTs** — grading is the editor's job, not this skill's.
- **`.prproj` templates / `.zxp` panel** — hand-editing tools; our timeline is generated.
- **`.cdk` clip decks** — payloads are opaque Premiere clipboard blobs, and they point at the
  author's own machine. Only the slot names and `useCount` were readable, and those were the
  useful part anyway.
- **The videos** — install guides for a workflow we don't use.

## Verdict

**Worth it for the preset pack alone, and for one reason: it stated animation numbers we had
measured wrong.** As a *course* it is close to empty — ten minutes of install screencasts. As an
*asset drop* (four numbers, five SFX, four native-vertical film burns, a settled font question,
and a usage distribution) it paid for itself. Do not expect a second one to teach anything;
buy the next one for its `.prfpset` and open it with a parser, not a video player.
