# TikTok / Reels / YouTube Shorts UI Safe-Zone Spec

Canvas: **1080 × 1920** vertical 9:16.

Captions must stay inside the white area below. The red zones show where the host platform UI (username/follow chip, action buttons, description area) will overlay or crop the video. Anything you render in red is at risk of being obscured.

## Pixel coordinates (1080×1920 canvas)

| Zone | Box (x0, y0 → x1, y1) | Purpose |
|---|---|---|
| **Usable caption box** (middle vertical) | 60, 220 → 860, 1500 | Text stays here. Right side capped at 860 because actions column starts there. |
| Top UI chip | 350, 0 → 730, 200 | Username / follow badge (varies by platform) |
| Right action-button column | 860, 900 → 1020, 1500 | Like / comment / share / bookmark buttons — **most common culprit** for caption clipping |
| Bottom description / caption text | 0, 1530 → 1080, 1920 | Platform's own caption/description — don't render video-caption text here |

## Margins to use in CSS

For lower-third captions (CY ≈ 1200 — below face, above description):

```css
/* caption line container */
position: absolute;
top: <CY - blockHeight/2>;
left: 60;       /* safe from left edge */
right: 220;     /* CLEARS the right action-button column */
text-align: center;
white-space: nowrap;  /* prevent wrap that would blow past the safe box */
```

Effective text-box width: `1080 - 60 - 220 = 800px`. At 72px Inter Black, that's roughly **5 average words** or **3 wide words**. Cap phrase length at 7 words (split into 2 lines) so each line stays under 5 words.

## Vertical placement rules

- **CY 1200** is the sweet spot for lower-third captions: below the speaker's face, above the platform's description zone (1530+), and below the top chip (<200).
- Do NOT place captions in y=[0, 200] (top chip) or y=[1530, 1920] (description zone).
- The right action column starts around y=900 and ends around y=1500 — this intersects typical caption y-range, which is why we squeeze horizontally (right: 220) rather than move vertically.

## Platform variations (2026 snapshot — check if platforms change)

- **TikTok**: action buttons right, vertical username+follow bottom-right above captions. Description bottom.
- **Instagram Reels**: similar right-side action column, username top-left, description bottom.
- **YouTube Shorts**: username top-left, action column right-aligned but narrower.

The 800×1280 usable box at [60, 220 → 860, 1500] is the conservative intersection — captions that fit here are safe across all three.

## Implementation reference

See `__ACQ_ASSETS__/content-skill-system/remotion-captions/src/CinematicCaptions.tsx` — the `PhraseOverlay` component uses `left: 60, right: 220` on each line div.
