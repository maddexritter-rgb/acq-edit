# CAPTION TEARDOWN — IG reel DbzAXF5BqEw (2026-08-10)

Source: `00_SOURCE/DbzAXF5BqEw.mp4` — 1080×1920, **60 fps**, 21.13 s, 1268 frames.
Card: **979 × 909**, at x53–1032 / y505–1414, centred on **y = 960**. (Not square — 1.077:1.)
Method: every frame at 15 fps read in 18 contact sheets, then 60 fps micro-strips at three
entrances, then pixel measurement of colour, opacity and type size.

Spoken line (ASR): *"The only reason most people don't achieve it is because we think like the 95%,
not like the 5% who steps outside the norm, doesn't go on the freeway with every other car
following the same direction, believing the same stuff. You are the 5%. The ones gaining skills,
capabilities, something different. Stepping outside the norm, taking uncomfortable action."*

---

## 1. THE MECHANISM — WHITE TEXT ON **OVERLAY** BLEND (measured, not guessed)

Every caption is **white**, composited with the **overlay blend mode**. Nothing is hand-coloured.

    bd <= 0.5 : 2*bd*src          (dark plate -> text goes DARK)
    bd >  0.5 : 1-2*(1-bd)*(1-src) (bright plate -> text blows to WHITE)

Verified on three unrelated hues, comparing glyph pixels to the plate beside them:

| shot | plate | glyph measured | overlay(plate, white) | error |
|---|---|---|---|---|
| Mondrian yellow block | (0.64 0.54 0.01) | (0.99 0.98 0.11) | (1.00 1.00 0.02) | **0.038** |
| purple backdrop | (0.15 0.08 0.17) | (0.27 0.15 0.50) | ratio 2.21× | ✓ |
| car interior mid-tone | (0.39 0.31 0.25) | (0.78 0.63 0.56) | (0.77 0.62 0.50) | **0.02** |

For comparison, plain white / screen predicts (1,1,1) and is off by **0.31**. Overlay wins outright.

**The Mondrian shot is the proof frame.** The same word changes colour letter by letter as it
crosses the painting's blocks — `OU` white over grey wall, `TSID` bright yellow inside the yellow
rectangle. No hand-colouring can do that. Likewise `is because` on the woman: **`is` goes nearly
black over her dark hair while `because` glows orange over her lit cheek — one line, one layer.**

Consequences, which the editor accepts as the cost of the look:
- Orange sunset -> yellow text. Purple wall -> pink text. Underwater -> cyan text.
- **Bright sky -> the text goes DARK GREY** (`with every other car`). It reads as a deliberate
  dark-on-light caption; it is just the blend.
- **Dark plate -> the text goes dark and can nearly vanish** (`is` over her hair). Accepted.

## 2. 🛑 THERE IS NO FADE. THE "FADE" IS THE BLEND.

I twice read a caption as fading in — `achieve it` at 1.37 s and `the 5%.` at 12.60 s both look
ghosted for ~0.2–0.4 s, then snap solid. **Measurement says opacity never changes.**

| moment | look | plate | glyph | glyph/plate | overlay predicts |
|---|---|---|---|---|---|
| 1.500 s | "ghosted" | (0.39 0.31 0.25) | (0.78 0.63 0.56) | **2.10×** | (0.77 0.62 0.50) |
| 1.667 s | "solid" | (0.37 0.30 0.25) | (0.80 0.64 0.56) | **2.18×** | (0.75 0.60 0.50) |

Both are full-opacity overlay. What changed is the **plate**: over mid-tone lit skin, 2× lands
close to the skin value, so contrast collapses and the word looks translucent; when the subject
moves and the plate darkens, the same word reads solid. The apparent animation is the *subject
moving*, not the caption.

**Entrances are HARD CUT-INS at full opacity — no fade, no slide, no scale.** Confirmed at 60 fps
on `on` -> `on the` -> `freeway`: each word is simply present on the next frame. There is no
motion blur anywhere and no easing to model, because nothing moves.

**The one exception** is the `STEPPING / OUTSIDE / THE NORM.` hero card (17.0–18.1 s), where the
whole three-line block **translates right-to-left across the shot** over ~1 s.

## 3. POSITIONING — HAND-PLACED PER CUE, NOT A TEMPLATE

Measured against the card's centre lines. There is **no fixed alignment**:

| cue | horizontal | vertical | why |
|---|---|---|---|
| `The only reason` | centred | on centre line | face fills upper card |
| `on the / freeway` | **pushed right** (~0.75) | on centre | driver occupies the left |
| `the / outside` | centred | **raised to ~0.28** | his face sits low in frame |
| `believing` | centred | slightly below centre | nests under her eyeline |
| `the ones` | pushed right (~0.68) | below centre | swimmer on the left |
| `STEPPING…` | far right, then travels | full height | subject enters from the left |

The constant is **vertical centring on the card as the default**, broken whenever the subject
occupies that band — then the block moves up, down or sideways to the empty quadrant. Same
principle we already have measured (place the caption where the subject is narrow), executed by
hand per cue rather than by a rule.

## 4. THE TWO-LINE LOCKUP — SMALL LINE NESTED INTO THE BIG ONE

The signature structure. Two lines at very different sizes, **tucked tightly together**, the small
one overlapping the big one's x-range rather than sitting squarely above it:

    we think            <- small, sits above the TAIL of the line below
    is because          <- big

Measured on `on the / freeway`, which is clean of overlap:

| line | height | % of card |
|---|---|---|
| `freeway` (big) | 110 px | **12.1 %** |
| `on the` (small) | 49 px | **5.4 %** |
| **ratio** | | **2.24×** |

🛑 **Stacking direction is not fixed.** `on the` (spoken first) sits above `freeway`; but
`we think` (spoken *second*) also sits above `is because`, so that lockup literally reads
bottom-to-top. Same for `different.` above `something`. It is a designed lockup, not a reading
sequence — which is only possible because it is placed by hand.

## 5. FONTS — TWO, AND THE SECOND IS A FLAVOUR, NOT A ROLE

**Primary — a bold grotesque sans, very tight negative tracking** (letters nearly touching, word
spaces almost closed). Geometric-leaning: circular `o`, horizontal-barred `e`, flat-topped `t`
with an angled terminal. Consistent with **Helvetica Now Display Bold / Inter Display Bold /
SF Pro Display Bold**. Carries ~90 % of the captions. Always bold — there is no regular weight
anywhere in the clip, and **no weight contrast is used at all**; the hierarchy is entirely SIZE.

**Secondary — a high-contrast Didone italic** with hairline thins, thick stems, and a long swashed
descending `f`. Consistent with **Playfair Display Italic / Didot / Ogg Italic**. Used on exactly
three cues: `the` (above `outside`), `skills.`, `uncomfortable`.

🛑 It is **not** assigned to a grammatical role. `the` is a function word; `uncomfortable` is the
emotional payload. It is used where the editor wanted a softer, more expressive beat — decoration,
not system. (Our `/edit` weight logic assigns fonts by role; this creator does not.)

Case: sentence case throughout, with **two all-caps moments used as hero beats** — `CAPABILITIES`
and `STEPPING / OUTSIDE / THE NORM.`

**Punctuation: YES.** `the same stuff.` · `the 5%.` · `skills.` · `different.` · `action.` ·
`THE NORM.` Full stops are kept and are visibly part of the design.
🛑 This is the opposite of our standing rule ("No punctuation on these. Ever.") — noted, not adopted.

## 6. MATTING — ROUGHLY HALF THE CUES SIT BEHIND THE SUBJECT

`is because` (her hand), `believing` (her face), `the ones` / `gaining` (the swimmer),
`CAPABILITIES` (the drummer), `STEPPING…` (the walking man). The car-interior A-roll cues are
mostly *in front*. So matting is applied per shot where it buys depth, not as a blanket treatment.

## 7. WORD RHYTHM

~35 caption states across 19.7 s of speech ≈ **one change every 0.56 s**. Cues are **1–3 words**;
lines grow word-by-word (`most` -> `most people` -> `most people don't`) then the whole block
clears and the next begins. Holds run 0.13–1.0 s; the longest holds are the single big words
(`outside`, `believing`, `freeway`).

🛑 **Captions are SELECTIVE, not a transcript.** "who steps outside **the norm**" is spoken, but
`norm` is never captioned there — the phrase is saved and paid off later as the `THE NORM.` hero
card. The captions carry the argument, not the audio.

---

# THE SHOT LIST — EVERY CAPTION STATE

| t (s) | on screen | size role | font | notes |
|---|---|---|---|---|
| 0.00 | The only reason | one line | sans | white on car interior |
| 0.60 | most | one line | sans | |
| 1.00 | most people | grows | sans | |
| 1.20 | most people don't | grows | sans | |
| 1.37 | achieve it | one line | sans | washes out over lit skin (blend, not fade) |
| 1.80 | is because | big | sans | `is` black over hair, `because` orange over cheek |
| 2.40 | **we** + is because | small + big | sans | small line above the tail |
| 2.60 | **we think** + is because | small + big | sans | |
| 2.80 | like | one line | sans | orange sunset -> yellow |
| 3.00 | like the | grows | sans | |
| 3.20 | like the 95% | grows | sans | held ~0.9 s |
| 4.20 | not like | one line | sans | back to white on neutral plate |
| 4.40 | the 5% | one line | sans | held ~0.8 s |
| 5.40 | who | one line | sans | |
| 5.80 | steps | one line | sans | pushed to top of card |
| 6.20 | *the* + outside | small + big | **serif italic** + sans | raised; face is low |
| 7.00 | doesn't go | one line | sans | |
| 7.40 | on | one line | sans | |
| 7.48 | on the | grows | sans | hard cut-in, 60 fps verified |
| 7.62 | on the + **freeway** | small + big | sans | pushed right of the driver |
| 8.20 | with every | one line | sans | **dark grey** on bright sky |
| 8.60 | other | one line | sans | dark grey |
| 8.80 | other car | grows | sans | dark grey |
| 9.20 | following | one line | sans | white on dark plane |
| 9.60 | the | one line | sans | |
| 9.73 | the same | grows | sans | |
| 10.20 | the same + **direction** | small + big | sans | |
| 10.60 | believing | big | sans | pink on purple, matted behind her face |
| 11.20 | the same + believing | small + big | sans | |
| 11.40 | the same stuff. + believing | small + big | sans | **period** |
| 12.00 | You are | one line | sans | |
| 12.60 | the 5%. | one line | sans | **period**; washes out over skin then reads at the cut |
| 13.80 | the ones | one line | sans | cyan underwater, matted |
| 14.00 | gaining | big | sans | oversized — **clipped by the card's left edge** |
| 15.00 | gaining + *skills.* | big + small | sans + **serif italic** | **period** |
| 15.47 | CAPABILITIES | one line | sans | **ALL CAPS**, matted behind drummer |
| 16.27 | something | big | sans | |
| 16.60 | different. + something | small + big | sans | **period** |
| 17.00 | STEPPING / OUTSIDE / THE NORM. | 3 lines | sans | **ALL CAPS, huge, TRANSLATES across frame**, matted |
| 18.20 | taking | one line | sans | |
| 18.80 | uncomfortable | big | **serif italic** | |
| 19.40 | action. + uncomfortable | small + big | sans + serif italic | **period** |
| 19.73 | — | | | black card + logo |

---

# WHAT IS WORTH TAKING (and what is not)

**Take:**
1. **Overlay blend on ALL captions, full opacity, white source.** We currently restrict it to beat
   words after the V9 note. This creator shows the all-caption version working — but only because
   his plates are graded film with deep blacks. On our mid-tone talking-head plates the same
   setting is exactly what made V9 unreadable. **The blend is only safe where the plate is dark or
   saturated.** That is the rule to encode, not "always on" or "emphasis only".
2. **The 2.2× two-line lockup** — small line nested against the big line's tail. Cheap, and it is
   the single most recognisable thing about this style.
3. **Size-only hierarchy.** No weight contrast at all. Ours varies weight *and* size; his is
   simpler and reads harder.
4. **Selective captions.** Dropping a word so it can be paid off later as a hero card is a real
   editorial device we do not use.

**Do not take:**
- **Punctuation** — against the standing rule.
- **Per-cue hand placement** — it is the reason this looks bespoke, and it does not automate. The
  closest automatable version is what we already have: place the block where the subject is narrow.
- **Letting the blend eat a word** (`is` over dark hair) — acceptable in his register, not in ours.

---

# ✅ PORTED (2026-08-10, DreamsWillDie V13)

| finding | ported? | where |
|---|---|---|
| **Hard cut-in — no fade, no slide, no motion blur** | **YES** | `preview_matted.py`: `TRAVEL=0.0`, `OPACITY_FLOOR=1.0` |
| **2.24× two-line lockup** (small lead line, big payload) | **YES** | `caption_v2.py` `SIZES["lead"]`, `chunk_accumulate.py` |
| Overlay blend on ALL captions | **NO** | see below |
| Punctuation kept | **NO** | standing rule: "No punctuation on these. Ever." |
| Per-cue hand placement | **NO** | does not automate; we keep "place where the subject is narrow" |
| Size-only hierarchy (no weight contrast) | **PARTIAL** | house model is weight-per-word + size-per-cue and stays |

### 🛑 WHY THE ALL-CAPTION OVERLAY IS NOT ADOPTED
He runs overlay on every caption at full opacity and it works — but only because his plates are
**graded film with deep blacks and saturated colour**. Overlay is defined as `2*bd*src` below 0.5,
so on a MID-TONE plate it lands near the plate value and the word disappears. His own reel shows
the cost: `is` goes nearly black over the woman's dark hair.

Our A-roll is a mid-tone lit face — exactly the worst case. Running overlay on every caption is
precisely what made **V9 unreadable** and drew the editor's note. So the rule we encode is:

> **Overlay only where the plate is dark or saturated. On mid-tone skin, straight white.**

which is what the luma-weighted, emphasis-only blend in `preview_matted.py` already does.

### 🛑 THE MEASUREMENT LESSON (third time this session)
I read "fade-in" off the contact sheets twice and was wrong both times — it was the blend, not
opacity. **A caption that looks like it is fading may just be a blend meeting a brighter plate.
Measure glyph-vs-plate ratio across the supposed fade before modelling any animation:** constant
ratio = no animation, whatever your eye says.
