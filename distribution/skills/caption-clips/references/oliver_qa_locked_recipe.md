# Oliver Q&A Caption Recipe — LOCKED 2026-06-10

THE single caption look for Alex Q&A Workshop clips, reverse-engineered from Oliver's actual
Premiere preset (the `Q&A FONT` .prtextstyle + the EGP shadow sliders) and signed off by Maddex
on a real clip. Engine: `scripts/generate_spice.py` + `presets/spice.json`. This is the ONE caption
skill — `caption-clips`. (`glow` is a separate, explicit-only viral style; `clip-miner/presets/oliver_caption.json`
is SUPERSEDED — captions are always burned by generate_spice, run qa_assembly with `--no-captions`.)

## The hard-won lessons (why this took so long — don't repeat the mistakes)
1. **Render the CAPTIONS at 4K.** The biggest early failure was captioning a downscaled 1080 export
   and upscaling — soft footage never matches Oliver's true 4K. Rebuild the cut at 4K from the raw
   cameras (`ACQ_QA_RES=2160` in qa_assembly.py, reusing the approved EDL) THEN caption natively at 4K.
2. **font_size_px = 150 @ 4K.** 250 (the preset's authoring size) is WAY too big on screen. 150 is right.
   Don't size off a single Oliver frame — one clip looked bigger and sent us to 250 (wrong).
3. **Base weight = Proxima Nova MEDIUM**, never Regular/Light. A thin Regular base made the shadow
   read wrong. Emphasis ladder: Medium(base) → Bold → Extrabold → Black. Italics for reflective pivots.
4. **The shadow is the Premiere drop shadow, decoded from the preset's FIVE sliders per layer**
   (Opacity, Angle, Distance, Size, Blur) — see below. The trap: the BLUR values are HUGE (110/250).
   A low-blur shadow looks like a hard "stroke"; the big blur is what makes it a soft Premiere shadow.
5. **Don't pixel-measure Oliver's footage for the shadow** — his arm/body sits under the text and
   contaminates the reading. Use the PRESET values; verify the LOOK against his clip in motion (video_watch).
6. **Always compare in MOTION at ~12–20fps + full-frame side-by-side**, not single stills. The
   position/size differences only became obvious watching it move next to Oliver.

## LOCKED shadow (in spice.json `shadow`, mode "premiere", TWO layers)
Decoded from Oliver's EGP sliders, then scaled from the preset's font 250 → our font 150 (×0.6).
Premiere "Size" → the shadow blob `border`; Premiere "Blur" → ffmpeg gblur `sigma ≈ blur×0.3`;
"Distance@Angle" → a DOWN-RIGHT (x,y) overlay offset; "Opacity" → curves intensity.

| Preset slider | Layer 1 (directional) | Layer 2 (ambient) |
|---|---|---|
| Opacity | 100% | 70% |
| Angle | 130° (down, slight right) | 135° (down-right) |
| Distance | 20 | 7 |
| Size | 15 | 33.9 |
| Blur | 110 | 250 |

Mapped @ font 150 (FONT-RELATIVE, FS_REF=150 — scales to any res via generate_spice):
- **Layer 1 (directional, drawn OVER):** `sigma 33`, `border 9`, `intensity 1.0`, offset **(7,11)** down-right
- **Layer 2 (ambient, drawn UNDER):** `sigma 75`, `border 20`, `intensity 0.70`, offset (3,4) down-right
- `premiere_layer2: true`, `premiere_stroke_px: 0` (NO hard outline — the shadow does all separation)

Pipeline (generate_spice premiere path): one white blob per layer at its Size/border →
`gblur(sigma) → curves(0/0 1/intensity) → alphamerge(solid black) → overlay(dx,dy)` ×2 → crisp text on top.
Two separate blob ASS files (one per border). **border MUST drive Size; offset MUST be down-right** —
a centered/borderless blur reads as a halo or a stroke, which Maddex rejected repeatedly.

## LOCKED type + layout
- Font: Proxima Nova (full weight family in `fonts/proxima_full/`). Base = **Medium**, 150px @4K.
- Weights: mute/base/soft = Medium · strong = Bold · emphasis = Extrabold · payoff = Black.
- Color = voice: white = Alex/host; **yellow #FED90F = guest/second speaker** (was #FECB00 pre-v2) (per-word `c:"guest"`, no italic/quotes).
- Chunking: ≤18 chars / ≤3 words, sentence/clause boundaries. lowercase except proper nouns + I-forms.
- Money/symbols: `$55M`, `$100M`, `$1B`, `40%` (spice_normalize).
- Animation: "Text Down Small" — `\move` down 16px over 500ms + opacity 90→100% over 83ms (from Oliver's preset).
- Position: layout-driven per camera angle — see `segment_aware_captions.md`. (Oliver runs fullscreen
  captions ~mid-chest; tune `safe_y_pct` per segment. NOTE: position was still being dialed at lock time.)

## Verify-before-ship
- video/audio same length, **0 data streams** (strip bin_data), opens clean, no face coverage on splits.
- Watch a 10s window at fps next to an Oliver clip on a LIGHT background (shadow only shows on light bg).

---

## Oliver caption-style NUANCES (from watching his Q&A clips @ fps, 2026-06-10)
Observed across ShouldISellMyCompany, HowDoIRaisePrices, BuyTheFrontEnd + others:

- **Position is MID-FRAME (~50–58% from top), NOT lower-third.** Fullscreen single-speaker: caption
  sits around mid-chest. Split-screen: caption rides the SEAM between the two panels. Wide/room shot:
  a bit lower. Drive this per camera angle (see segment_aware_captions.md). My default 60% was too low.
- **Color = voice (white = Alex/host, yellow = guest)** AND **yellow also highlights the KEY word**
  inside a caption. e.g. Alex's WHITE line "I still have **prices**" renders "prices" in YELLOW+bold;
  "a **higher price**", "the **new** price". The recurring TOPIC noun gets the yellow highlight even
  in a white (Alex) caption. ⚠️ This partially conflicts with the current locked rule "yellow = voice
  only, numbers NOT yellow" (set 2026-06-04). NEEDS A MADDEX DECISION: revive yellow-as-key-word-highlight
  (Oliver's actual look) or keep yellow=voice-only. Until decided, keep current rule; flag this.
- **Reported/quoted speech: yellow + ITALIC + real quote marks** on EVERY cue of the span —
  e.g. `"just so you know"`, `"to reward you"`, `"the new price"`. Confirms the yellow_quotes_rules.md path.
- **2–3 words per cue**, lowercase, appears-and-holds (the Text-Down drop-in), zero-gap between cues.
- **Emphasis = key/topic word per line** (bold weight + sometimes the yellow highlight), not every other word.
- Base text is a clean MEDIUM weight; emphasis words jump to Bold/Extrabold/Black.

---

## ⚠️ MONEY/NUMBERS = YELLOW (confirmed by surgical frame-reads, 2026-06-10) — CONTRADICTS current rule
Method that works (NOT tesseract OCR — too noisy; NOT 30fps — redundant): use the Groq transcript to
find where money/numbers/quotes are SPOKEN, extract the caption frame at that exact timestamp, read it.
Verified on IMake600KAsAStayAtHomeMom:
- spoken "600k in revenue" → on-screen **`$600K`** (YELLOW+bold) + "in revenue" (white)
- spoken "5 million"       → **`$5M?`** (YELLOW, `?` kept)
- spoken "$200 a day"      → "more than **`$200`** a day?" (`$200` YELLOW inside a white line)
Also HowDoIRaisePrices: the topic noun "prices" rendered YELLOW inside Alex's white line.

**Implication:** Oliver's actual style highlights MONEY + NUMBERS (and the key topic word) in **yellow+bold**,
independent of speaker. The current locked rule (`number_color: null`, "numbers NOT yellow, yellow=voice only",
2026-06-04) is WRONG vs Oliver. PENDING MADDEX DECISION to flip: numbers/money → yellow highlight, AND keep
yellow for the guest voice. Formatting: `$`+capital K/M, keep `?`. Until Maddex confirms, rule is unchanged.
