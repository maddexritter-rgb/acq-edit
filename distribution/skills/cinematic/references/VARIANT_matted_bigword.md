# VARIANT — "matted big-word" (@elitevision-style), measured 2026-08-09

A **second, distinct** cinematic-card style the editor flagged as *"ghosted editing… I love his
caption logic, the look and the b-roll logic."* Same structural family as our house style — rounded
square card floating on black, film b-roll, white-card interstitials — but the caption system and
the cut rhythm are near-opposites. Do not blend the two by accident; pick one per clip.

Measured on 3 reels: `DaAy4kch2E9` (25.1s) · `DZ2wJtxBBkh` (13.5s) · `DZ0OdqTBCrb` (30.0s),
all 1080×1920 **@60fps** (ours is 23.976). Sources in `2026-08-08_EditStyleStudy/00_SOURCE/`.

## The card — same family, slightly smaller
| | his | ours |
|---|---|---|
| card | **932 × 932** at x75, y495 | 980 × 980 at x50, y470 |
| margin | 75px | 50px |
| centre | y = **960** | y = 960 |

Identical across all three reels, so it is a template, not a per-clip choice. Both are square and
both centre on y=960 — the difference is a 75px vs 50px side margin.

## 🛑 THE SIGNATURE: THE SUBJECT IS COMPOSITED **IN FRONT OF** THE TEXT
The caption sits **behind** the person. Verified by zooming to pixel level: the letterforms are
interrupted by a hard-edged shape with a light rim — an overlay could never do that. This is a
**matte** (roto/AI segmentation, e.g. MatAnyone), not a blend mode and not opacity.

It is what makes the look read as depth rather than as a title card, and it is the single thing we
do not currently do. **This is the build if the editor wants this variant.**

## Captions — 2–3 words, continuous (⚠️ CORRECTED)

🛑 **I first recorded this as "ONE huge word per cue". That was WRONG** — generalised from frames
that happened to be single-word cues. Reading the full sequence off a 2fps sheet shows a normal
continuous word-by-word read:

> *everyone is · jealous · of what · you've got · no one · is jealous · of how · you got it ·
> people · trophies · but not · THE TRAINING · THE TRAINING GROUND · everybody · the view ·
> but no one · climb.*

**Mostly 2–3 words, with single words used for beats.** Structurally this is OUR system. The real
differences are narrower: matting, bigger type, slower cuts, colour on some beats, and he keeps
punctuation (we do not — editor ruling).

**He also ACCUMULATES on a beat phrase**: `THE TRAINING` → `THE TRAINING GROUND` — the cue grows
rather than replacing. We always replace. Worth trying.

*(The lesson, again: count the cues by READING a 2fps sheet. A state-counter is useless here — the
matted subject makes the visible ink area fluctuate every frame and the counter fires constantly.)*

| | his | ours |
|---|---|---|
| words per cue | **2–3**, single words for beats | 2–4 |
| ink height | **8.8 – 13.9%** of card | 6.8% median, 10.0% max |
| case | **lowercase** for single words; CAPS for phrases | sentence case, CAPS for rare beats |

Measured: `sacrifice` 130px tall (13.9%), `20x` 130px (13.9%), `stupid` 82px (8.8%) on a 932 card.
Roughly **2× our size at the emphasis end** — because it is carrying the frame alone rather than
sitting beside other words.

**Colour tracks the scene**: cyan/teal on a blue-lit shot, warm cream on a warm shot, pure white on
neutral. Seen across multiple frames and multiple reels, so it is a real device and not a one-frame
artefact — but I have NOT determined the mechanism (gradient fill vs blend mode vs RGB-split
fringing; the preset pack does ship a "Cinematic Edge Blur + RGB Split"). **Measure before
building it.**

## 🛑 WATCHED AT 15fps, EVERY FRAME — what sampling missed (2026-08-10)
Editor: *"you have to go a little bit more granular… I see twelve frames. Watch them at 15 frames
a second for the entire thing."* Doing that on 245 consecutive frames found three structural
things that 12 sampled frames did not show. **The 12-frame sheet is for structure only; caption
FORMATTING and ANIMATION require every frame.**

1. **ROLLING MULTI-LINE STACK — the phrase ACCUMULATES, it does not replace.**
   `until…` / `YOU GUARANTEED` / `YOU GUARANTEED LOSE` are on screen together — each state stays
   stacked below the previous. We replace every cue. This is probably the biggest formatting gap.
2. **ENTRIES ARE HARD CUT-INS, NOT SLIDES.** Eight consecutive 15fps frames of `if you don't /
   try it` are pixel-identical. A 200ms slide would show ~3 intermediate frames at 15fps; there
   are none. Our motion-blurred 36px slide is our invention, not his.
3. **ITALIC AND CASE CARRY MEANING.** `lose` renders italic; emphasis pairs go full-caps and wide
   (`YOU'RE DEFINITELY / GONNA LOSE`); body stays lowercase.

⚠️ **Still unresolved: the glassy word.** `risk` is visibly translucent, but scanline correlation
on that busy plate swung −0.96 to +0.17 across frames — no clean mechanism. **Do not build it on a
guess** (that is how the fabricated gold gradient shipped). Measure on a clean plate first.

## 🛑 PLACE THE CAPTION WHERE THE SUBJECT IS NARROWEST
Not at the card centre. Measured silhouette width by height on an Alex medium shot:

| caption height | subject covers |
|---|---|
| y 0.14 | **33%** |
| y 0.21 | 37% |
| **y 0.50 (card centre)** | **64%** |

At mid-card his torso + arm + mic blocked two thirds of the line and ate the words. At head level
he is a narrow vertical slice and the caption reads. **Re-measure per source — it is framing-
dependent** (u2net matte, mean column coverage per row band).

## 🛑 MASK PARTIALLY, NOT FULLY
Editor: *"tone down the masking."* A 100% knock-out reads as a blunt cut-out and deletes words.
`CINEMATIC_MATTE_STRENGTH = 0.70` leaves the letters visible THROUGH the subject — softer, and
closer to the glassy read than a hard cut-out.

## 🛑 CUT RHYTHM — 2–4× SLOWER THAN OURS
| reel | duration | shots | cuts/10s | median shot |
|---|---|---|---|---|
| DaAy4kch2E9 | 25.1s | 11 | **4.4** | 2.28s |
| DZ2wJtxBBkh | 13.5s | 3 | **2.2** | 4.50s |
| DZ0OdqTBCrb | 30.0s | 5 | **1.7** | 6.01s |
| **ours** | 23.9s | 18 | **7.5** | 1.18s |

*(ffmpeg scene detection at 0.35; it can under-count slow dissolves between similar film clips, so
treat these as a floor. Even so, 3 shots in 13.5s is unambiguous.)*

The two choices are coupled: **long held shots + one big word behind a matted subject** is a
coherent system. Our **fast cutting + small multi-word cues on top** is a different coherent system.
Porting the captions without the cut rate — or vice versa — gets neither.

## B-roll — themed by IDEA, not locked to ONE film
He mixes films within a single clip (Wolf of Wall Street, a Will Smith drama, MMA/boxing, suited
office) unified by *theme* (ambition / struggle / defiance). Our house rule locks one film per clip
(Matrix, Whiplash). **His is the looser rule and it still reads coherent** because the emotional
register is constant. Worth trying, but the one-film lock is what made BlackDotRoom's b-roll land,
so treat this as an option, not a replacement.

## Also present
- White-card interstitials — same device as ours.
- Small watermark bottom-centre (his handle). We do not do this.

## If adopting this variant, build order
1. **Matting** — the signature; everything else is cosmetic without it.
2. Caption engine: one word per cue, ~14% card height, lowercase, centred.
3. Slow the cut rate to ~2–4 cuts/10s and let shots hold.
4. Only then investigate the scene-tinted colour.
