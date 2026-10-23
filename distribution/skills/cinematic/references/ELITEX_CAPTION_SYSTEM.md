# THE ELITEX CAPTION SYSTEM — from the creator's own course (2026-08-10)

Extracted from the **ElitexVision™ Editing Mastery** course ("Full ElitexVision Editing Tutorial",
44:02, 582 subtitle cues / 5,252 words). This is the same creator whose reels we reverse-engineered
in `VARIANT_matted_bigword.md`. **Where this file and that one disagree, this file wins** — it is
him explaining his own method rather than us inferring it from pixels.

Full transcript: `2026-08-08_EditStyleStudy/10_WORK/elitex_course/`.

## 🛑 HE EDITS IN CAPCUT, NOT PREMIERE
Every technique below is CapCut. We had been decoding Premiere presets from a *different* creator's
pack. The techniques port, but the tool names do not.

---

## ⭐ THE GLASSY TEXTURE — SOLVED: IT IS AN **OVERLAY BLEND MODE**
> *"Right click on the caption and select **create a compound clip**, then go to video on the
> right, **blend mode**, and choose **overlay**… it already looks pretty aesthetic and I really
> use this effect very often."*

**This is the single most valuable line in the course.** We could not measure it because
**overlay blend is NON-LINEAR** — it darkens where the plate is dark and lightens where it is
light — so our stroke-vs-background *linear* correlation returned nonsense (−0.96 to +0.17 across
frames of the same word) and we concluded "opaque, mechanism unknown."

> **A non-linear compositing mode cannot be detected with a linear correlation test.** When a
> measurement flips sign across frames of the same element, suspect a blend mode, not noise.

**Brighter variant:** *"right click the compound clip, copy it, and stack it a little bit higher —
it becomes brighter and more visible."* Duplicating the overlay layer compounds the effect.

## THE FIVE CAPTION TREATMENTS HE ACTUALLY USES
1. **Overlay blend** (above) — his default and most-used.
2. **Inverted / negative text.** Copy the A-roll clip under the caption, place it one layer above,
   `Adjust → Curves` → **invert all curves**, then `Mask → Text` and select the text. The letters
   show the inverted image. Uses his **second font**, slightly smaller.
3. **"Mini zoom"** — a built-in CapCut In-animation, applied per caption.
4. **Keyframed slide-in, two lines stacked** — see the keyframe rule below.
5. **Stacked rows** — text layers manually stacked, each word keyframed in individually.

## 🛑 THE KEYFRAME RULE (this is the animation we got wrong)
> *"Do NOT add the keyframe at the start of the text line, but where it should **arrive** — a
> little bit up front. If you want it to come in from a direction, move it to the negative
> direction and the keyframe will be set automatically. **The first keyframe must be set to
> EASE OUT.**"*

Set the **destination** keyframe first, then displace backwards. First keyframe = **ease out**.
That is the opposite construction order from ours, and ease-OUT (not our smoothstep-in-and-out)
is what he specifies.

## 🛑 WORDS PER LINE — HE EXPLICITLY REJECTED PER-WORD
> *"Split it so that each line has about **two words**, or sometimes even one word or three words…
> you could say I want to cut each word individually but **trust me I've tried that already — it
> just becomes too exhausting and too much work**."*

Two words is the default; one or three as needed. **Per-word is a dead end he already walked.**
(Our engine animates per word. His does not.)

## 🛑 SPLIT ON THE AUDIO WAVEFORM, NOT THE TRANSCRIPT
> *"Look down at the audio track to see where the splits should happen. When the bar goes up, the
> pitch gets a little bit higher — that's usually when a new word comes in."*

Matches what we learned the hard way lifting a second speaker: **the envelope is the truth, the
transcript's word boundaries are not.**

## 🛑 PURE WHITE, NO SHADOW — HE AGREES
> *"You can go to shadow and turn it on… but honestly I wouldn't really recommend it because it's
> not very aesthetic. **I usually just use pure white** unless you really need a shadow."*

Independent confirmation of the editor's standing no-shadow ruling.

## ORDER OF OPERATIONS
> *"**Designing the captions should be the very last thing you do** for the video — after that
> comes quality adjustments."*

Cut → clips → overlay → **then** caption design → then quality. Also: *"you always need to think
ahead about your captions"* while cutting — which clip will carry which caption line.

⚠️ **CapCut gotcha:** turn **"apply to all captions" OFF** before styling individually, or one
size change propagates to every caption at once.

## QUALITY PASS
`Enhance Quality → Level → AIHD` per clip. ~30 min for 20 clips. Optional but he recommends it.

---

## ⭐ HIS ACTUAL ASSETS — pulled from the course (all local now)

### FONTS — we had both wrong
| role | we guessed | **he actually uses** |
|---|---|---|
| main | Helvetica Neue Bold / Open Sauce Sans Black | **Europa Grotesk SH Demi-Bold** (`europa-grotesk-medium.ttf`) |
| second | Snell Roundhand Black | **Roundhand Bold** (`Roundhand Bold.ttf`) |

Installed to `assets/fonts/`. Our IoU test picked plausible neighbours, never the real face —
**a glyph-shape match on a handful of samples cannot identify a font; the creator's own file can.**
(We were close on the second font: the right *family* of engraver's script, wrong cut.)

### CARD OVERLAYS — his real mask PNGs, and they confirm our measurement to 1px
`assets/card_overlays/` — authored at 900×1600, so **×1.2 to reach 1080×1920**.

| overlay | hole @1080×1920 | position |
|---|---|---|
| **1:1 (the square card)** | **931 × 931** | x=76, y=496, centre y=**961** |
| 16:9 | 931 × 523 | x=74, y=698 |
| STACK OF 3 | 931 × 1615 | x=76, y=152 |
| STACK OF 2 | 889 × 1540 | x=96, y=190 |
| 4:3 · 3:4 | — | also present |

We measured **932 × 932 at x75 / y495 / centre 960** off his reels. His own file says
**931 × 931 at x76 / y496 / centre 961**. **A one-pixel agreement** — the pixel measurement was
sound. Use the PNGs directly for a true one-to-one; they carry his exact corner radius.

### MEDIA LIBRARY — all downloaded
- **348 b-roll clips / 1.96 GB**, foldered **by film**: Batman · Blade Runner · Breaking Bad ·
  Creed · Fight Club · Good Will Hunting · Oppenheimer · Peaky Blinders · Rocky · Southpaw ·
  Pursuit of Happyness · Social Network · Wolf of Wall Street · Whiplash · F1 · plus
  Kobe / Jordan / Cristiano / McGregor and aesthetic + sports + random sets.
  **The folder-per-film structure is exactly our one-film-lock rule** — we had 12 clips, now 348.
  → `assets/broll_lib/elitex_raw/` (transcode to `pp/` H.264 before any Premiere timeline)
- **505 visuals** (58 MB) → `assets/elitex_visuals/`
- **66 music tracks** (231 MB) → `assets/elitex_music/` — index with `music_index.py` as a new lane
- 6 card overlays, 2 font families

---

## 🛑 HIS SOURCING SYSTEM — he says it beats editing
> *"**Editing is not the most important on social media. It really comes down to sourcing.**
> Even good editing alone won't get you very far… We are **not trying to reinvent** something.
> We are **recreating ideas that already worked**."*

The method, verbatim from "Sourcing viral & winning videos" (11:08):
1. Work **only inside your niche** — go through accounts in that niche and nothing else.
2. Establish the account's **average** views.
3. Find the **outliers against that average** — *"if the average of the account is like 5k and the
   video got 1 million, it clearly stands out. These are winning clips."*
4. **Small pages with outlier videos are the strongest signal.**
5. Look at the **last 10–15 days, max 30** — recency matters.
6. Recreate the proven idea; do not invent a new one.

**Where this differs from ours:** `/edit` mines a source we already own and ranks candidates by
intrinsic quality. He starts from **proven demand** — an idea that already outperformed — and works
backwards to footage. Both are valid; his is the demand-first order. `clip-intel` is the tool we
already have for the outlier-vs-average step.

### His b-roll sources
4K movie/aesthetic scenepacks from YouTube: **@TheBeautyOf** and **@theclipof**.
Visuals from **Pinterest**. Download tooling is listed in "Downloading the videos".

## WHAT THIS CHANGES FOR US
| we built | he does |
|---|---|
| per-word items, motion-blurred 36px slide | **2-word lines**, keyframed ease-out slide |
| opaque white fill | **overlay blend compound clip** (the glassy look) |
| smoothstep in-and-out | **first keyframe = ease out** |
| chunk from transcript timings | **split on the audio waveform** |
| flat white only | white + **inverted-curve text mask** as a second treatment |

**Highest-value port, in order:** (1) overlay blend on the caption layer, (2) two-word lines,
(3) ease-out destination-first keyframes.

---

## ✅ PORTED AND RENDERED (2026-08-10, DreamsWillDie V8)
Implemented in `preview.py` / `caption_type.py` / `chunk_captions.py`:

| | before | now |
|---|---|---|
| fill | opaque white alpha-composite | **overlay blend, `OVERLAY_PASSES=2`** |
| font | Helvetica Neue / Open Sauce | **Europa Grotesk SH** (his file) |
| emphasis | 4-step weight ladder | **size + caps** — he ships ONE weight |
| cue length | 2–4 words | **2 words** |
| card | our 980 approximation | **his 931 geometry** |

```python
# per channel, backdrop bd and source src in 0..1
overlay = np.where(bd <= 0.5, 2*bd*src, 1 - 2*(1-bd)*(1-src))
```
Apply the **matte to the caption alpha BEFORE blending** — knocking out after blending reveals
unblended picture. Env: `CINEMATIC_OVERLAY`, `CINEMATIC_OVERLAY_PASSES`.

### ⭐ THE COLOUR MYSTERY, FINALLY CLOSED
We saw cyan/pink in his captions → measured ink R−B as **neutral** → concluded we had imagined it.
**Both readings were correct.** The ink IS neutral white; the colour appears at COMPOSITE time
through the overlay blend picking up the plate. Proof in our own render: "So you" over a dark car
shot comes out **gold**; "SMALLER" over a warm shopfront comes out warm.

> **When an observation and a measurement disagree and you trust both, the answer is usually a
> mechanism you have not modelled — not an error in either.** Measuring the ink harder was never
> going to find a blend mode.

⚠️ **Trade-off:** overlay nearly erases text on very dark plates (0.02 → 0.04). That is why he
says to stack the compound clip. 2 passes is the floor; use **3 on dark b-roll**.

### ⭐ CONFIRMED ON A FRESH REEL (@elitexvision, 15fps, every frame)
Pulled 6 new reels off his profile and read one frame-by-frame. Two things settled:

**1. The overlay blend is beyond doubt.** In one reel: `RICH` renders **orange** over an
orange skin/pool plate · `WHY NOT` renders **blue** over a gold plate · `decide` takes the purple
of a suit. Neutral ink, colour entirely from the composite. Exactly what our V8 reproduces.

**2. THE ACCUMULATE-STACK IS CORE, NOT OCCASIONAL — and it is the biggest remaining gap.**
Observed building across shots:
> `YOU WANT` → `YOU WANT TO BE` → `YOU WANT TO BE` / **`RICH`**

The line grows word-group by word-group; when it wraps, the earlier line **stays on screen** and
the new group appears beneath it. The whole phrase then clears at once. We replace every cue, so we
never build a phrase — this is the difference between his captions reading as one sentence landing
and ours reading as a ticker.

Also confirmed: cues are **2–3 words**, **CAPS for the emphasis phrase** / lowercase for connective
tissue, held **~11–13 frames at 15fps (0.7–0.9s)**, centred, and **no slide on entry**.

### ✅ ACCUMULATE-STACK — BUILT (V9, 2026-08-10) · `scripts/chunk_accumulate.py`
Phrases now BUILD and clear together, matching his `YOU WANT → YOU WANT TO BE → …/RICH`:

```
And        ████████████████████████████
like       ···█████████████████████████
someone's  ····████████████████████████
dreams     ·················███████████
will       ····················████████
DIE        ······················██████     <- all clear together at the phrase end
```

**The implementation is far smaller than it looks.** The renderer already positions word k inside
a multi-line block via `render(block, only=k)`. So the whole change is: **make the BLOCK a PHRASE
instead of a CUE.** Each word then runs from its own onset to the *phrase* end and accumulation
falls out for free — no compositor change at all.

- `chunk_accumulate.py` replaces `chunk_captions.py` for this variant. Phrase shape measured off
  his reels: **2 words per line · max 3 lines · max 6 words**.
- **Break on MEANING, not on a word count.** A pure word cap split *"make sure that the person who
  is dreaming"* mid-thought. `CLAUSE_OPEN` closes a phrase before a new clause once it has ≥3 words.
- Gate: every word in a phrase must share the same `t1` (17/17 on the build).
- Shot cuts must be re-snapped after switching chunkers — the cue grid changes completely.

### ⚠️ CORRECTION — HE USES BOTH MODES, AND HIS CUT RATE IS NOT A CONSTANT
Measured across **6 fresh reels** off his profile:

| reel | duration | shots | cuts/10s |
|---|---|---|---|
| Db3mAw8hwU1 | 27.4s | **1** | **0.4** |
| DbnzPt3Ba6Q | 24.3s | 2 | 0.8 |
| DbtKhlhBCZc | 22.3s | 3 | 1.3 |
| Db1DkgZBxbq | 30.0s | 7 | 2.3 |
| DbqcerYhv1X | 24.2s | 6 | 2.5 |
| Dbv-2kJBybu | 19.3s | 13 | **6.7** |

**0.4 → 6.7 cuts/10s.** My earlier "1.7–4.4, 2–4× slower than ours" was drawn from three reels and
is too narrow. He has no fixed cut rate; one clip is a **single 27s held shot**.

**And captions do NOT always accumulate.** That same single-shot reel REPLACES, one line at a time
(`I give you` → `is for` → `recognition` → `career` → `opportunity` → `along with`). So:

> **Accumulate and replace are two modes he switches between, not one system.** Our
> `chunk_accumulate.py` is one of them; `chunk_captions.py` is the other. Pick per clip — a long
> held shot suits replace (nothing else is changing, so the caption carries the rhythm); a
> multi-shot sequence suits accumulate (the phrase holds the thought together across cuts).

`opportunity` renders **italic** in that reel — the italic treatment from his course, in the wild.

### STILL NOT PORTED
- **Destination-first ease-out keyframes** (we still use smoothstep both ends). Last one.

---

# 🛑 CAROUSEL MASTERY — the lesson that settles the matte (extracted 2026-08-10)

The course's *Carousel Mastery* lesson (9:13) is about static slideshows, but it is **the only
place he states the text-behind-subject technique outright.** Full transcript:
`~/Downloads/alex/2026-08-08_EditStyleStudy/10_WORK/elitex_course/ELITEX_carousel_mastery.txt`

**1. THE MATTE IS CONFIRMED — it is his method, not our inference.**
> "We take the original image at the bottom of the timeline, we copy it and place it above the two
> text layers **and remove the background.** The person is now in front and the text is behind."

That is exactly what `matte.py` (u2net_human_seg) reproduces. VARIANT_matted_bigword.md derived
this from pixels; this is the author confirming it. No further verification needed.

**2. 🛑 LEGIBILITY OUTRANKS THE EFFECT — and his fix is POSITION, not a weaker matte.**
> "The text still needs to be readable. People need to understand what the quote says. **It doesn't
> make sense to hide everything completely behind the person so nobody can read it.** So we can
> move the text slightly higher, or adjust the position of the main image a bit lower."

So `CINEMATIC_MATTE_STRENGTH` (our partial knockout) is OUR invention — a fine fallback, but the
FIRST move is always to place the caption where the subject is narrow. That rule already existed
in VARIANT_matted_bigword.md from silhouette measurement; it now has the author's own backing.

**3. THE OVERLAY BLEND — confirmed again, WITH ITS PURPOSE.**
> "Select both text layers, **create a compound clip, then blend mode, overlay**… the text
> automatically **adapts to the colour in the background.** …**duplicate the compound clip and
> place it on top** — that makes the text a little bit brighter, and we could repeat that."

`OVERLAY_PASSES` IS his duplicate-to-brighten. And note the stated purpose: **colour adaptation**,
not texture. That is why applying it to every word reads as murk — see the V9 correction below.

**4. ⭐ NEW, NOT YET IMPLEMENTED — recolour the BACKGROUND ONLY.**
Duplicate the plate above the text, remove its background, then grade the BOTTOM copy: the plate
behind the words darkens while the subject stays untouched.
> "It will only affect the background. So the face and the ball will not change at all."

This is the clean answer to captions dying on a bright plate — strictly better than dimming words.
🛑 **NOT WIRED UP AND MUST NOT BE SWITCHED ON UNASKED — this is a colour change, and COLOUR GRADE
IS MADDEX'S JOB.** Offer it; never apply it.

**5. Optical alignment, not just left-alignment.**
> "**Zoom in fully and look closely at the individual letters**, then I check where I can place the
> line so that it fits perfectly over the other word."

He aligns stacked lines by eye at 100% zoom. We left-align on a fixed x — close, but this is why
his stacks look tighter.

**6. Carousels, if ACQ ever wants quote posts:** 3:4 ratio, AI-HD upscale every image, logo
top-right or bottom-left, two stacked text layers, then the compound-clip overlay.

---

# ✅ V9 → V12 CORRECTIONS (DreamsWillDie, 2026-08-10)

Editor on V9: *"the captions are very hard to see. You have this effect that you're adding on to
all of them, and I think you should only use it occasionally as a way to emphasize words, just
like how we changed fonts… The captions are a bit too high. They should be centered."*

| change | from | to |
|---|---|---|
| overlay blend | every caption | **beat words only** (`style in emph/peak`) |
| caption block | high-left | **`CX_FRAC, CY_FRAC = 0.28, 0.50`** — vertically centred, still left-aligned |
| matte strength | 0.70 | **0.35** |
| MAXW | 620 | 520 |
| b-roll | mixed films | **Good Will Hunting, one film**, from his course library |
| music | — | his 66-track library |

### 🛑 THREE RENDERER BUGS THIS SHOOK OUT — all fixed in `preview_matted.py`

**a. `int()` truncation ate a pixel.** `S = CARD/ch` then `int(ch*S)`: for ch=1388,
`int(1388 * (980/1388))` = `int(979.9999…)` = **979**, so the final 980 crop died with
*"Invalid too big or non positive size."* Fixed with `max(CARD, int(round(...)))`. Any source
height that doesn't divide exactly hits this — it is luck, not correctness, when it works.

**b. The blend silently deleted every non-beat word.** The old form rebuilt the frame from the
plate alone (`_out = _bd*(1-_al) + _bl*_al`), so any word that wasn't an emphasis word vanished
whenever a beat word was on screen. Now the blend **recolours the caption layer in place and keeps
its alpha**, so it stays a transparent overlay and everything else carries through.

**c. 🛑 THE MASK MUST COME FROM THE PIXELS YOU DREW.** The emphasis mask was taken from
`cache[c["file"]]` — the *un-animated* glyph — while the word is composited from `cur`, the slid +
faded copy. The mask sat ~36px off the ink, stamping BLACK through the gap: a black word ghosted
beside the white one. Now the mask accumulates from `cur` in the same loop.

### 🛑 OVERLAY DIMS TEXT ON DARK PLATES BY DEFINITION
`bd<=0.5 → 2*bd*src`, so a white word over a dark hat (bd≈0.15) lands at 0.30 — grey. The mode
only blows to white where the plate is ALREADY bright. So the blend is now **weighted by plate
luma**: full overlay on a bright plate (glassy AND legible), straight white where it would go grey.
**Emphasis must read STRONGER than body text, never weaker.**

### 🛑 MEASURE THE FULL-RES FRAME — THE CONTACT SHEET LIES, AGAIN
Twice this session I "saw" a dim caption in a 466px contact-sheet tile and started chasing it. Both
times the full-res pixels said otherwise (`OR` peaked at 237/255 — bright). Thin white strokes over
a busy plate lose contrast when downscaled. **Crop the full-res frame and read the numbers before
changing anything.** This is the same trap as the "wasnothing" chase.
