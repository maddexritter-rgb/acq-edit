# CINEMATIC CARD STYLE — spec (reverse-engineered 2026-08-08)

Source refs (in `00_SOURCE/`): `DbyOnB1O16q` 33.4s · `Dbqg5BTulbG` 34.9s · `Dbi5QOgOYPk` 39.0s
Watched at 15 fps, full coverage (24 contact sheets in `10_WORK/sheets/`).

---

## 1. CANVAS — this is the thing that makes it look different

Delivery is 1080×1920, but **nothing is full-bleed.** Everything lives in a rounded card
floating on pure black.

| element | measured value |
|---|---|
| canvas | 1080 × 1920, `#000000` |
| card | **980 × 980 (1:1 square)** |
| card x | 50 → 1029 (50 px side margin) |
| card y | 470 → 1449 (**vertically centered**, 470 px black above and below) |
| corner radius | **≈ 48 px** (measured: straight edge begins 48 px in from each corner) |
| card content | source scaled to FILL the square (center-crop), never letterboxed inside it |

**Split-screen variant** (used once, on a paired-idea line):
two cards, each **980 × 696**, stacked with a **29 px gap**, whole stack vertically
centered (y 258 → 1678). Same 48 px radius. Top card enters first, bottom joins ~0.45 s
later behind a 1-frame white flash.

**Interstitial card variant:** the same 980×980 rounded rect filled flat **white** or flat
**black**, with one small line of type centered in it. Nothing else.

> This is the whole visual signature. Square card, black surround, rounded corners.
> Get this wrong and no amount of caption work will read as "that style."

## 2. CUT RHYTHM

| | ref 1 | ref 2 | ref 3 |
|---|---|---|---|
| shots | 28 | 35 | 28 |
| median shot | 1.02 s | 0.77 s | 1.20 s |
| cuts / 10 s | 8.4 | 10.0 | 7.2 |
| shortest | 0.07 s | 0.13 s | 0.40 s |
| longest | 3.27 s | 4.23 s | 4.60 s |

Rules that hold across all three:

- **Open long.** First shot is the longest or near-longest in the piece (3.3–4.2 s) — the
  hook is allowed to breathe, everything after it is fast.
- **Body = 0.7–1.3 s per shot.** A new image on nearly every phrase.
- **Close long.** Final shot holds 1.6–1.8 s on the payoff line, then hard cut to black.
- **Flicker beats.** 1–2 frame shots (0.07 s) exist and are deliberate — ref 2 cuts through
  six different macro eyes in 0.4 s on the word "see you."
- **Black tail.** Every reel ends with **1.6–1.9 s of pure black with the music still
  playing.** Picture out before sound out.

## 3. FOOTAGE MIX

Roughly **50/50 A-roll to B-roll**, and the A-roll itself is multi-source.

- **A-roll:** the interview, but pulled from **several different episodes/setups** in one
  reel — different backgrounds, wardrobe, and grades intercut freely. Continuity is not a
  concern; the voice is the through-line.
- **B-roll, two flavors:**
  - **Film clips** (refs 1 & 2) — Good Will Hunting, Wolf of Wall Street, American Psycho,
    Whiplash, Pursuit of Happyness, Catch Me If You Can. Chosen for *emotional* rhyme, not
    literal: "afraid of what people say" → Will Hunting alone in a room.
  - **Literal/stock illustration** (ref 3) — buffet spread, banquet hall, shrimp platter,
    burger stack, typewriter, hand crossing something out with a red pen. Chosen for
    *literal* rhyme with the spoken metaphor.
- **Word-image sync is exact.** The pen finishes crossing out on the frame the word
  "loaded" lands. This is cut to the word, not to the sentence.

## 4. TYPE SYSTEM

Two voices, always.

**Voice A — bold neo-grotesque sans.** Helvetica Now / Neue Haas Grotesk Display Bold.
(Proxima Nova Bold, already in our pipeline, is the closest in-house substitute.)
Lowercase for ordinary words, ALL CAPS for the heavy ones.

**Voice B — high-contrast Didone italic.** Didot Italic / Bodoni Moda Italic / Playfair
Display Italic. Ball terminals, deep swash `f`. Used for the soft, poetic, or structural
words: *influencing*, *against*, *achieve it*, *fit it*, *work*, *first rule*.

The two mix **inside a single caption block** — e.g. `stomachs` (sans bold) with *work*
(Didone italic) tucked under and to the right, overlapping.

**Size hierarchy within one block.** The key word is 2–3× the others:

```
your          ← small, orange
behavior      ← 2.5× larger, cream
```
```
HARD          ← largest
THINGS        ← medium
DECISIVELY.   ← medium
```

**Color rule — CORRECTED 2026-08-08. The first version of this section was WRONG.**

Type is **FLAT PURE WHITE**. Measured over 65 caption samples spanning all three reels:
mean glyph RGB **(252.7, 251.8, 251.1)**, R−B spread **1.6**, **97% neutral white**.

There is **no gradient, no glow, and no drop shadow.** Shadow test on 'RELENTLESS' (white type
over movie b-roll): ring luminance 3–9px = 149.8 (glyph antialiasing), 9–17px = 88.7, far
background = 84.1 — no darkening anywhere.

> ⚠️ An earlier version of this spec claimed a cream→gold gradient with a warm glow on A-roll.
> That was generalised from ONE payoff frame where warm background light bled into the
> compression around the letters, and it produced a genuinely bad result. **Generalise a style
> rule from a distribution across all three reels, never from a single frame.**
> Legibility on a bright plate comes from flipping the type dark (the reference does this on its
> white interstitial cards), never from adding colour or glow.

**Placement is dynamic, never a fixed lower third.** The block goes into whatever negative
space the shot has: left of a right-facing profile, right of a left-facing one, dead center
on a wide. Roughly vertically centered in the card, but it moves shot to shot.

**Build behavior.** Words accumulate into the block rather than replacing it —
`BUT` → `CAN'T` → `DO` → `HARD` → `HARD THINGS` → `HARD THINGS DECISIVELY.` — then the
finished block holds through the last shot.

## 5. INTERSTITIAL CARDS — the structural punctuation

At a hard structural beat (a rule being stated, the thesis landing), picture drops out
entirely and the card goes **flat white or flat black**, with one small line of type
centered in ~980 px of empty space. Type is *tiny* relative to the card — cap height
around 6 % of card height. Maximum white space.

Observed:
- ref 3, 18.0–18.9 s — white card, ***first rule*** in black Didone italic
- ref 1, 23.2–24.4 s — black card `NOT`, inverting to white card `NOT ALLOWING`
- ref 2, 28.0–28.8 s — white card `against`, inverting to black card `against you.`

The invert (black → white or white → black on consecutive beats) is part of the device.

## 6. TRANSITIONS

- **Hard cut** is the default — no dissolves anywhere in 91 shots.
- **White flash**, 1–2 frames of blown-out white, used maybe 3× per reel at the biggest
  turns. Not decorative — it marks a gear change.

## 7. AUDIO

- Integrated loudness **−14.1 / −14.2 / −14.3 LUFS** across the three. Tight, and hotter
  than our current −16 LUFS vertical standard.
- Continuous cinematic music bed under the entire piece, still audible over the black tail
  (tail mean −19 to −22 dB vs −15 to −18 dB mid-reel). The score resolves after picture.
- No SFX whooshes, no risers on cuts. The music does all of it.

## 8. STRUCTURE (all three, same shape)

1. **Cold open on the thesis**, longest shot of the reel, A-roll, caption already running.
2. **Illustrate**, fast — a new image per phrase, alternating A-roll / B-roll.
3. **Structural break** — interstitial card at the hinge line.
4. **Escalate** — fastest cutting of the reel, split-screen or flicker montage if there's a
   paired or plural idea.
5. **Payoff** — back to A-roll, caption block builds to the full line, holds 1.6–1.8 s.
6. **Hard cut to black**, music resolves over ~1.7 s of nothing.

Total runtime 33–39 s. Word count 116–146.

---

## PROVENANCE
Measured 2026-08-08/09 from three reference reels (33.4s / 34.9s / 39.0s, all 1080×1920 30fps),
1,609 full-resolution frames extracted at 15fps and analysed per-frame. Card geometry verified at
27 timestamps. Caption colour verified over 1,473 text-bearing frames. Caption size verified over
1,882 measured line heights.

⚠️ Rules NOT verified across a distribution are marked as such. Anything unmarked was measured
across the whole reel. See `CASEBOOK.md` for what happened when a rule was taken from one frame.


---

## SECOND REFERENCE SET — 3 more reels, 2026-08-09
`DbV7ABLOKR1` 58.5s · `DbTWtQbu87q` 20.3s · `DbQyEwbu2Kx` 28.5s (all 1080×1920 30fps).
Durations are far more varied than the first set (20–59s vs 33–39s), so **runtime is not a constant**.

| | DbV7ABLOKR1 | DbTWtQbu87q | DbQyEwbu2Kx |
|---|---|---|---|
| cuts / 10s | 7.0 | 6.9 | **9.1** |
| median shot | 1.10s | 1.27s | **0.63s** |
| black tail | 2.53s | 1.87s | 1.33s |
| text on screen | 94% | 82% | 87% |

### THREE INVARIANTS across all SIX reference reels
1. **CAPTIONS ARE CENTRED** — measured centre x 0.49–0.52, y 0.50–0.56 of the card. Not
   left-aligned in negative space (that was my earlier misread).
2. **LOWERCASE.** Not one ALL-CAPS word in any reel — `lazy · people · don't · know · start. ·
   when · they · finish. · neither · than finding £5`. **Emphasis comes from SIZE, never from case.**
3. **1–3 WORDS at a time.** Some reels replace one word at a time (`lazy`→`people`→`don't`),
   others accumulate a short phrase (`than finding` → `than finding £5`). Both are in-style; long
   lines are not.

### THE SECONDARY FACE IS A BOLD ENGRAVER'S SCRIPT — NOT A DIDONE
Measured on "2nd" (white card): **ink coverage 0.263, aspect 2.76**.
**Snell Roundhand Black = 0.252 / 2.69** ✅ · Snell Bold 0.204/2.53 · Snell Regular 0.141/2.30 ·
Great Vibes 0.202/2.13 · Didot Italic is a seriffed italic and visibly wrong.
→ `SnellRoundhand.ttc` **index 2**, ships with macOS.

### OTHER
- A caption **persists across a shot cut** and fades on its own schedule — caption timing is
  independent of picture cuts.
- ⚠️ `finish.` appears two-tone in a downscaled contact sheet. It is NOT — glyph pixels measure
  254–255 uniformly. That is the dark background behind "fi" showing through the thumbnail.
  **Do not invent a treatment from a downscale** (see CASEBOOK §1).


## 🛑 CORRECTION — THE BLACK TAIL IS ~0.15s, NOT 1.6–1.9s (SHIPPED TAIL, 2026-08-12)
The 1.6–1.9s tail recorded above was measured off the ORIGINAL reference reels. **No delivered
ACQ build uses it.** Measured across all five shipped clips (SacrificeOrdinary, AfraidOfEverything,
DieTrying, LonelyByDesign, ThatBoyDied) the black tail is **0.00–0.20s** — two of them end on a
live frame with no black at all.

A 1.70s tail shipped once and the editor caught it immediately: *"it kind of cuts to black
abruptly and then has like a second of black."* Use **TAIL = 0.15**.

Two things travel with it: the final cue must **hold to picture-out** (it was the only cue
clipped to its own last word, so the payoff word vanished before the picture did), and the
music fade must be **derived from TAIL** (a hardcoded 1.5s fade was fine inside a 1.7s black
tail but ducks the bed across the whole payoff line once the tail is short).

> **A number measured off the reference is not automatically the number we ship.** Check the
> delivered builds the editor already approved before trusting a spec row.
