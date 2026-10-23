# Paid-ad house style — measured spec

Reverse-engineered from four shipped ads by the team's ad editor (industry callout ads,
9:16, 1080×1920, 24fps). Every number below was sampled off the actual pixels, not eyeballed.
Reference set used: an orthodontist callout (32s), a physical-therapy callout (32s),

Two documented caption systems, both reverse-engineered from real shipped ads (9:16,
1080×1920, 24fps) — pick by which the reference calls for, don't blend them:

| System | `caption_mode` | Reference set | Use for |
|---|---|---|---|
| **CHIP** (default) | `"chip"` | One ad, Hunter, 2026-08-21 (f.io/G4BFDgKa, "Leads Problem / Offer Problem", 41s) | Simple single-cam talking-head closes — the common case |
| **Headline+pill** (legacy) | `"hybrid"` / `"headline"` | Four ads, 2026-08-11 (orthodontist/PT/HVAC/recovery-wellness callouts, 32-49s) | Multi-cam industry-callout ads with a subject matte — a heavier, more produced look |

Both are measured, not guessed — this file documents CHIP first (§2-4, the current
default), then the legacy headline+pill system (§2b-4b) for when that specific look is
wanted. Section 1 (base scripts), 5 (safe zones), 6 (palette), 7 (open items) apply to both.

---

## 1. The two base scripts

Callout ads are **one base VO with the industry name swapped at the front**:

| Base | Opening | Length |
|---|---|---|
| **Gift** | *"[Industry] business owners. The best gift I could possibly give you is something I could charge for and just make it absolutely free…"* | ~49s |
| **Mortality** | *"Most [industry]s don't change. They live the same six months of their lives a hundred times in a row, and then they die…"* | ~32s |

Everything after the callout is identical across industries. **This is what makes the format
scale** — one master edit, N industry heads.

---

## 2. CHIP timeline structure (default)

| Beat | When | What |
|---|---|---|
| **Whole ad** | 0 → end | Small black CHIP caption, same style throughout. **No separate hook headline —** this is the single biggest difference from the legacy system, and the most common way this style gets botched by defaulting back to a big headline. |
| **Proof / cutaway** | wherever the VO names a proof point or names the offer | A labeled full-bleed cutaway (blurred backdrop + video card + purple badge naming the segment) OR a brief screen-recording proof card composited straight over the talking head. |
| **CTA** | last beat | Purple/glass CTA pill slides up. **The CHIP caption keeps running underneath it — it never stops for the close.** |

---

## 3. CHIP caption (primary track, runs the whole ad)

Measured off a real frame, 1080×1920:

- Solid rounded rect, fill `rgba(13,13,17,0.92)`, radius ≈14px — plain black, not a
  colored/gradient pill
- White ALL-CAPS text, ~32px
- Box measured **419 × 116** for a 2-line caption (auto-sizes to text, capped ~520px wide)
- **Centered on X** (x-center = 540 = canvas center — NOT left-of-center)
- **y 1322–1438** (68.9%–74.9% of frame height)
- Same box, same position, from the first frame to the last — including under the CTA pill
  (see §4b below): there is no moment where this box disappears before the ad ends

### Text rules (shared with the legacy system, from the org's subtitle spec)
- `dollars`/`bucks` → `$`; `percent` → `%`
- `≥ $100,000` → `K` / `M` / `B` (`$250,000` → `$250K`, `$1,200,000` → `$1.2M`)
- ≤3 words and ≤18 chars per line; max 2 lines
- Drop trailing stub words (`and`, `but`, `so`, `or`, `the`, `a`, `of`, `to`)
- The org's organic-clip standard is **lowercase**; ads use **ALL CAPS**. Keep them distinct —
  lowercase reads editorial, caps reads promotional.

---

## 4. Labeled cutaway (`type: "cutaway"` in `render_ad.py`)

The real ad's B-roll moment isn't a small inset next to the speaker — it fully replaces the
frame for the beat:

- **Backdrop**: the live talking-head frame at that moment, blurred (σ≈30) and darkened
  (~-22% brightness) — not a cut to black. Fills the whole 1080×1920 canvas.
- **Card**: the B-roll clip in a rounded-rect card, ~918px wide (85% of frame width), height
  by the clip's own aspect ratio, centered horizontally, top ≈690px. Thin dark border
  (`rgba(60,60,66,0.9)`, 3px) — no purple glow on this one (that's the *other*, smaller inset
  style below).
- **Badge**: a small glass-purple label — same visual family as the CTA pill (icon circle +
  text, `#5919CB` fill, `#887AB3` border) — sitting just above the card, naming the segment
  in 1-2 lines ALL CAPS (e.g. "OFFERS WORKSHOP").
- The CHIP caption keeps running underneath, unchanged.

A **screen-recording proof card** (e.g. a real Amazon book-listing screenshot) is a
different, simpler beat: composited directly over the talking head as a `seq` overlay,
generally as a slide/wipe-in animation — catch it mid-reveal (top of the frame still shows
the live speaker) rather than letting the whole animation play out to full opacity, or it
reads as a jarring full-screen freeze instead of a proof cutaway. Keep the overlay `dur`
short enough that it doesn't finish its own reveal.

The **small purple-glow inset** (`type: "broll"`, no `full`) — a smaller card *next to* the
still-visible speaker rather than replacing the frame — is a legitimate third pattern, just
not the one in this specific reference; see §4b's B-roll row for its original measurements.

---

## 2b. Legacy headline+pill timeline structure (`caption_mode: "hybrid"`/`"headline"`)

Reverse-engineered from four shipped ads (industry callout ads). Every number below was
sampled off the actual pixels, not eyeballed.

Reference set used: an orthodontist callout (32s), a physical-therapy callout (32s),
an HVAC callout (49s), a recovery-and-wellness callout (49s).

| Beat | When | What |
|---|---|---|
| **Hook** | 0 → ~5–6s | Big two-line ALL-CAPS headline at top **+** pill caption. Wide/front angle. |
| **Turn** | ~7s | Cut to a second angle (profile / tighter). **Headline stops here — never returns.** |
| **Product** | ~9–10s | Product shot: device mockup or UI card on a dark purple gradient. 1–2s. |
| **Body** | ~11–30s | Talking head, angle changes every 4–8s. Pill caption only. |
| **Proof** | ~31–35s | Semi-transparent UI/screen-recording cards over the talking head. |
| **B-roll** | ~38–41s | Event/workshop footage inside a purple-glowing rounded frame, inset from edges. |
| **CTA** | last ~8s | Gold/white CTA pill slides up. Pill captions stop — **this IS correct for this system** (unlike CHIP mode, which keeps captioning through the close). |

**The single biggest mistake in this system** is running the big headline for the whole ad.
It is a hook device only — roughly the first 12% of the runtime. (In CHIP mode there is no
big headline at all, ever — don't reintroduce one by defaulting back to this system's habits.)

---

## 3b. Legacy caption system — two tracks

### Framing prerequisite (do this FIRST)

The headline only works if the subject's head actually reaches it. In the reference the
**subject's top edge sits at 4–6% of frame height**. If your reframe leaves the head at 20%+,
the headline floats over empty background and the whole treatment reads as a sticker.

Measure it before rendering:
```python
rows = (np.asarray(Image.open(frame).convert("L")) > 28).mean(axis=1)
top  = next(y for y in range(1920) if rows[y] > 0.012)   # want ~80-120
```
Push in until `top` lands in that range while still keeping chest/hands in frame — that
usually means cropping from a y-offset, not just narrowing the width.

### Graphic placement — never cover the face

Every overlay that isn't a caption (B-roll card, stat card, product card, chips) starts
**below the chin**. Covering the face kills the only thing carrying a talking-head ad.

Find the chin the same way you find the head top — it's the narrow neck band between the
head and the shoulders:

```python
w = [(np.asarray(Image.open(frame).convert("L")) > 28)[y].sum() for y in range(1920)]
# head ~200-450px wide, neck pinches to ~90-120px, shoulders jump to 500+
```
On the worked example: head top **343**, neck pinch **880–950**, shoulders from **1000**.
So graphics start at **y ≥ 930**.

Sizing: a 16:9 B-roll insert at **800×450** clears the chin at y=930 and still bottoms out
at 1380 — comfortably above the 1500 platform line. Full-height B-roll frames (Hunter's
938×1667) only work when the B-roll is itself vertical; a 16:9 clip in one leaves dead bands.

### Track A — hook headline (first ~5s only)
- ALL CAPS, ≤3 words per line, two lines stacked
- Line 1 `#F7F7FD` cool white, soft white bloom
- Line 2 vertical gradient `#A86EFF` (top) → `#7E30FE` (bottom), purple bloom
- Cap height ~110px → ~130px font, auto-shrunk to fit `W − 96`
- Line 1 cap-top y≈96, line 2 y≈244
- Sits **behind** the subject in the reference (person matte). Without a matte, keep it in the
  upper region where the background is dark.

### Track B — pill caption (runs the whole ad, primary track)
- Rounded rect r=18, fill `#5641B0` @ ~84% alpha
- White ALL-CAPS text, ~46px
- Box measured **651 × 111** (two lines)
- **Centre x = 483, centre y = 1443** (72–78% of frame height)
- Deliberately **left of frame centre** — clears the right-hand action-button column

### Text rules (from the org's subtitle spec)
- `dollars`/`bucks` → `$`; `percent` → `%`
- `≥ $100,000` → `K` / `M` / `B` (`$250,000` → `$250K`, `$1,200,000` → `$1.2M`)
- ≤3 words and ≤18 chars per line; max 2 lines
- Drop trailing stub words (`and`, `but`, `so`, `or`, `the`, `a`, `of`, `to`)
- Emphasis words (numbers, money, payoff nouns) promote a weight step
- The org's organic-clip standard is **lowercase**; ads use **ALL CAPS**. Keep them distinct —
  lowercase reads editorial, caps reads promotional.

---

## 4b. CTA pill (end card) — shared by both systems, re-confirmed 2026-08-21

This is the one piece that measured the same in both reference sets — the built-in
`cta_pill()` already matches the real ad closely:

- Rounded rect r≈38, ~900 × 128, fill `#5919CB` @ ~88% alpha
- Border 3px `#887AB3`, plus an outer purple glow
- Circular badge left (white @ 18%) containing the brand mark
- Line 1 **gold `#D69B23`**, ~42px, ALL CAPS — the offer
- Line 2 **white**, ~38px, ALL CAPS — the instruction (e.g. "CLICK THE LINK BELOW")
- Slides up over ~0.45s, eased
- Measured 2026-08-21: visual top ≈ y=1078 (56.1% of H) — set `cta_y` (the pill's padded
  top, ≈30px above the visual top) to **1048** to land there. **Long offer text must
  shrink-to-fit inside the pill** (floor ~22px) — a fixed font size clipped past x=860 on
  a real render before this was caught; never let CTA copy just run off the right edge.
- **In CHIP mode the caption chip keeps running underneath this pill** (§3) — do not gate
  the chip off when `t >= cta_at` the way the legacy hybrid pill does.

---

## 5. Safe zones (1080×1920)

| Zone | Box | Rule |
|---|---|---|
| Usable caption box | 60, 220 → 860, 1500 | all text lives here |
| Top UI chip | 350, 0 → 730, 200 | avoid |
| Right action column | 860, 900 → 1020, 1500 | **never cross x=860** |
| Bottom description | 0, 1530 → 1080, 1920 | **never place the CTA pill below y=1500.** The disclaimer is the one deliberate exception — it's *designed* to sit in this zone (measured y≈1540-1650) since it's non-critical, semi-transparent text; default `disclaimer_y` is **1630** (below the CHIP band at 1322-1438, not overlapping it — the old 1496 default did overlap once CHIP mode became the default). |

---

## 6. Palette

| Token | Hex |
|---|---|
| headline white | `#F7F7FD` |
| headline purple top | `#A86EFF` |
| headline purple bottom | `#7E30FE` |
| pill caption fill | `#5641B0` |
| CTA pill fill | `#5919CB` |
| CTA border | `#887AB3` |
| CTA gold | `#D69B23` |
| brand primary (web) | `#6D20E0` |

---

## 7. What still needs a human

- **Angle changes.** The reference cuts between camera angles from a multi-cam shoot. With a
  single-angle source, substitute punch-ins — but they are not as good.
- **B-roll selection.** Which event footage goes in the glowing frame is an editorial call.
- ~~Subject matte~~ — **solved, two ways.**

  **A. MatAnyone** (what the team's ad editor uses) — best quality, real hair edges,
  temporally stable:
  ```bash
  scripts/make_matte.sh reframed_9x16.mp4 ./matte_out
  # then in config:  "matte": true, "matte_video": "matte_out/..._pha.mp4"
  ```
  Install notes that cost an hour to find: `cchardet` won't build on py3.12 (install with
  `--no-deps`, then add torch/torchvision/opencv/hydra-core/einops/imageio/requests by hand),
  and `torchvision >= 0.28` removed `io.read_video` — so feed it a **frame folder**, not an
  mp4. The frame-folder path defaults to 24fps, which matches.
  **Licensing:** S-Lab License 1.0 = non-commercial only. Whether that's acceptable on paid
  creative is a call for whoever owns licensing — not a default. Commercially-clean options:
  Apple Vision person segmentation (native macOS), BiRefNet (MIT), SAM 2 (Apache-2.0).

  **B. Built-in luma key** — `"matte": true` with no `matte_video`. Zero dependencies, no
  licence question, and genuinely good **on a dark set** because the background is already
  near-black. Fails on a lit set. Tune `matte_threshold` (24) / `matte_feather` (1.6).

  Either way the matte only runs on the top 520px band, so torso holes don't matter.
