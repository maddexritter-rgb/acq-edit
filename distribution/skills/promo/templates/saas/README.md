# SaaS Animation Templates

Three ready-to-use Remotion compositions that port the "SaaS animation style" dominating Instagram/TikTok for tech brands in 2026. Spec-level source: [`editing-styles/saas-animation-style.md`](../../../editing-styles/saas-animation-style.md).

## The three templates

| File | Scene | Duration | Use case |
|---|---|---|---|
| `SaasTextPopup.tsx` | Minimal text pop-up with logo reveal | 4s (120f @ 30fps) | Opener / brand hook / "This is [PRODUCT] 2.0" |
| `SaasGlassReveal.tsx` | Glass UI cards with backdrop-blur | 6s (180f @ 30fps) | Feature callouts / value props / "3 reasons to..." |
| `SaasDashboardTour.tsx` | 3D dashboard tour with cursor | 8s (240f @ 30fps) | Product demo / dashboard showcase / "here's your app" |

## Chain them together

The orchestrator skill `saas-animation-video` sequences all three into a ~20s SaaS promo:

```
[0-4s]   SaasTextPopup   — "This is ACME 2.0" branded intro
[4-10s]  SaasGlassReveal — 3 feature highlights with glass UI cards
[10-18s] SaasDashboardTour — show the actual product dashboard
[18-20s] CTA card (reuses SaasTextPopup with CTA text)
```

## Dropping into a new Remotion project

```bash
# Assuming you already have a Remotion project (see remotion-captions/ for reference)
cp promo/templates/saas/*.tsx your-project/src/
```

Then in your `Root.tsx`:

```tsx
import {SaasTextPopup} from "./SaasTextPopup";
import {SaasGlassReveal} from "./SaasGlassReveal";
import {SaasDashboardTour} from "./SaasDashboardTour";

<Composition
  id="saas-intro"
  component={SaasTextPopup}
  durationInFrames={120}
  fps={30}
  width={1080}
  height={1920}
  defaultProps={{
    title: "This is",
    accent: "ACME",
    suffix: "2.0",
    brand: {primary: "#8b5cf6", accent: "#ec4899"}
  }}
/>
```

## Brand customization

Every template takes a `brand: {primary, accent}` prop. Typical SaaS palettes that work:
- **Tech purple:** `primary: "#8b5cf6", accent: "#ec4899"` (default)
- **Finance blue:** `primary: "#3b82f6", accent: "#06b6d4"`
- **Startup orange:** `primary: "#f97316", accent: "#facc15"`
- **Healthcare green:** `primary: "#10b981", accent: "#3b82f6"`

If you want a specific brand's palette, scrape its homepage + extract the 2 dominant brand colors.

## Font setup

Templates use Inter by default (loaded from system). For a more polished look, add Inter via Google Fonts or use Remotion's `@remotion/google-fonts`:

```tsx
import {loadFont} from "@remotion/google-fonts/Inter";
loadFont();
```

## What's NOT ported from AE

- **Real turbulent displace** — SVG approximation is close but not identical. If you need "liquid" motion, use `<feTurbulence>` + `<feDisplacementMap>` in an SVG filter.
- **Deep glow on icons** — CSS `filter: drop-shadow()` approximates but AE's Deep Glow is more luminous. For Deep Glow specifically, chain multiple drop-shadows with different colors/blurs.
- **Exact AE Bounce It curve** — Remotion's spring with `damping: 8-12, mass: 0.5-0.8, stiffness: 80-120` is visually equivalent for most cases. If you need exact AE parity, pre-render in AE for those shots only.

For everything else, Remotion can match or exceed AE for SaaS-style motion graphics.

## Rendering

```bash
# Inside your Remotion project
npx remotion render saas-intro out/saas-intro.mp4
# Or the full 20s promo chain
npx remotion render saas-full-promo out/saas-promo.mp4
```

Default output: 1080×1920 (9:16 vertical for IG/TikTok). Change `width`/`height` in Composition for horizontal.
