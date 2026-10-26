---
name: saas-animation-video
description: "Create a short vertical SaaS animation using Remotion text, glass-reveal and dashboard scenes. Use for a product demo, animated app introduction or a reusable SaaS motion asset."
---

# SaaS Animation Video Orchestrator

End-to-end: brand + bullets → finished vertical MP4 in the SaaS animation style.

Based on the technique breakdown in [`editing-styles/saas-animation-style.md`](../editing-styles/saas-animation-style.md) — Ported to Remotion via the 3 components in [`promo/templates/saas/`](../promo/templates/saas/).

---

## When to use

- ✅ The brand is a SaaS / tech / app brand and needs a scroll-stopping promo
- ✅ You want a 15-20s trailer-style intro for a feature launch, course, or product page
- ✅ The brand already has brand colors + a logo + 3 "why us" bullets + a dashboard screenshot (or a list of dashboard sections)
- ❌ The brand is a talking-head creator and the promo should feel personal — use `shortform` or `client-viral-scripter` instead
- ❌ You want a static title card before a talking-head clip — opening headline generation is not included in this toolkit

---

## Inputs

```yaml
brand:
  name: "ACME"                      # appears in the text pop-up intro
  suffix: "2.0"                     # optional version string
  primary_color: "#8b5cf6"          # the main brand color — picks up gradients
  accent_color: "#ec4899"           # secondary — used for highlights
  logo_path: "public/acme-logo.svg" # optional; if missing, ★ glyph is used

headline: "Three ways to win"       # glass-reveal scene heading

features:                           # 3 glass-UI feature cards
  - icon: "⚡"
    label: "fastest"
  - icon: "✨"
    label: "easiest"
  - icon: "🎯"
    label: "smartest"

dashboard:
  title: "Your dashboard"           # dashboard-tour scene title
  tiles:                            # 4-6 tiles; each becomes a 3D card
    - {title: "Analytics",   color: "#8b5cf6"}
    - {title: "Reports",     color: "#ec4899"}
    - {title: "Settings",    color: "#f59e0b"}
    - {title: "Team",        color: "#10b981"}
    - {title: "Integrations", color: "#3b82f6"}
    - {title: "Billing",     color: "#ef4444"}

cta:                                # optional final card
  title: "Get started"
  subtitle: "acme.com/start"

client: "alex"              # tracker integration — matches vault/clients/<slug>.md (default brand: alex)
duration_sec: 18                    # default: auto-calc from scenes (18s)
output: "~/Downloads/promos/acme-saas-promo.mp4"
```

If any required field is missing, the skill should ASK — don't guess brand colors or feature names.

---

## Phase 1 — Scaffold Remotion project

On first run for a new brand, create `~/Downloads/promos/<client>-<brand-slug>/`:

```bash
cd ~/Downloads/promos
npx create-video@latest <client>-<brand-slug> --template=blank
cd <client>-<brand-slug>
npm install @remotion/google-fonts
```

Copy the SaaS templates into `src/`:

```bash
cp __ACQ_SKILLS__/promo/templates/saas/*.tsx src/
```

If the brand project already exists (subsequent runs for the same brand), SKIP scaffolding and just update `Root.tsx`.

---

## Phase 2 — Write `Root.tsx` with the chained compositions

```tsx
import {Composition} from "remotion";
import {SaasTextPopup} from "./SaasTextPopup";
import {SaasGlassReveal} from "./SaasGlassReveal";
import {SaasDashboardTour} from "./SaasDashboardTour";
import {loadFont} from "@remotion/google-fonts/Inter";

loadFont();

const fps = 30;
const width = 1080;
const height = 1920;

export const RemotionRoot: React.FC = () => (
  <>
    <Composition
      id="intro"
      component={SaasTextPopup}
      durationInFrames={4 * fps}
      fps={fps}
      width={width}
      height={height}
      defaultProps={{
        title: "This is",
        accent: "<BRAND_NAME>",
        suffix: "<SUFFIX>",
        brand: {primary: "<PRIMARY>", accent: "<ACCENT>"},
        logoPath: "<LOGO_PATH>",
      }}
    />
    <Composition
      id="features"
      component={SaasGlassReveal}
      durationInFrames={6 * fps}
      fps={fps}
      width={width}
      height={height}
      defaultProps={{
        heading: "<HEADLINE>",
        cards: [/* 3 features */],
        brand: {primary: "<PRIMARY>", accent: "<ACCENT>"},
      }}
    />
    <Composition
      id="dashboard"
      component={SaasDashboardTour}
      durationInFrames={8 * fps}
      fps={fps}
      width={width}
      height={height}
      defaultProps={{
        title: "<DASHBOARD_TITLE>",
        tiles: [/* 4-6 tiles */],
        brand: {primary: "<PRIMARY>", accent: "<ACCENT>"},
      }}
    />
    {/* Optional: wrap all 3 in a <Series> composition for one continuous render */}
  </>
);
```

For ONE continuous MP4 (recommended), also create a `<Series>`-wrapped composition:

```tsx
import {Series} from "remotion";

const FullPromo = () => (
  <Series>
    <Series.Sequence durationInFrames={4 * fps}>
      <SaasTextPopup {...introProps} />
    </Series.Sequence>
    <Series.Sequence durationInFrames={6 * fps}>
      <SaasGlassReveal {...featureProps} />
    </Series.Sequence>
    <Series.Sequence durationInFrames={8 * fps}>
      <SaasDashboardTour {...dashboardProps} />
    </Series.Sequence>
  </Series>
);
```

Register `FullPromo` as a composition with `id="full-promo"` and `durationInFrames={18 * fps}`.

---

## Phase 3 — Render

```bash
npx remotion render full-promo <output_path>
# defaults: H.264, fps 30, 1080x1920, CRF 18
```

For better quality add `--crf=16 --color-space=bt709`.

---

## Phase 4 — Tracker + audit integration

Register the output in the clip tracker:

```bash
python3 __ACQ_SKILLS__/clip-review-tracker/scripts/tracker.py create \
  --client <client> \
  --clip-slug <brand-slug>-saas-promo \
  --clip <output_path>
```

Then auto-audit via `mozi-sf-audit`:

```bash
python3 __ACQ_SKILLS__/mozi-sf-audit/scripts/audit.py \
  --clip <output_path> \
  --platform instagram \
  --out ~/Downloads/audits/<brand-slug>-saas-promo.audit.md
```

Transition tracker to `audited-v1-pass` or `audited-v1-fail` based on exit code.

Note: the mozi audit's face-centering check will likely be `skip` (no face in an animated promo) — that's correct behavior.

---

## Phase 5 — Report

```
SAAS ANIMATION VIDEO — <brand> — <date>

Scenes:      3 (intro 4s → features 6s → dashboard 8s) = 18s
Brand:       <primary> / <accent>
Output:      <output_path>
Audit:       <pass|fail>
Tracker:     <client>/<brand-slug>-saas-promo — audited-v1-pass

Next:
  → preview in <output_path>
  → if ACQ approves, deliver
  → if revisions, attach feedback with tracker.py feedback, then revision-planner
```

---

## Sensible defaults when user is vague

If user says just "make a saas animation video" with no brand specified:

- **Brand name:** prompt user for it
- **Colors:** default tech-purple palette (`primary: "#8b5cf6", accent: "#ec4899"`)
- **Features:** prompt for 3 bullets; if user says "whatever", use "fastest / easiest / smartest" as placeholders + flag for them to replace
- **Dashboard tiles:** prompt for 4-6; if user doesn't have a product yet, use generic ("Dashboard / Analytics / Team / Settings / Integrations / Billing")
- **Output path:** `~/Downloads/promos/<brand-slug>-saas-promo.mp4`

---

## Customizations that don't require code changes

- **Swap emoji icons for SVG icons** in features: change the `card.icon` string to an inline SVG or image-URL
- **Longer/shorter scenes:** adjust `durationInFrames` in each Composition
- **Different brand palette:** just change `primary` / `accent` hex codes
- **Darker theme:** change the gradient backdrops in the TSX templates (background props) — trivial CSS tweak

---

## Deps required

```bash
# Per machine (one-time)
brew install node
npm install -g create-video
```

Every new brand project runs `npm install` internally — fresh `node_modules` per project. Each project folder is ~300MB on disk; delete unused ones periodically.

---

## Quick reference card

```
TRIGGER   "make a saas animation video" / "saas promo for <brand>"
INPUT     brand (name, colors, logo?) + headline + 3 features + 6 tiles + cta
PHASE 1   scaffold Remotion project (new brand) or update existing
PHASE 2   write Root.tsx with 3 chained compositions + FullPromo Series
PHASE 3   render via `npx remotion render full-promo`
PHASE 4   tracker.py create + mozi-sf-audit → audited-v1-{pass|fail}
PHASE 5   report: output path + audit verdict + next steps

NEVER: guess brand colors / skip audit / render without tracker registration
ALWAYS: ask for missing brand info / default to 18s total / register in tracker
```
