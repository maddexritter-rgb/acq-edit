---
name: cinematic
description: THE cinematic-card short-form style — a rounded square card floating on black, fast film-clip b-roll, two-voice captions, interstitial title cards. Reverse-engineered from reference reels and measured, not guessed. Run AFTER /edit has produced a locked cut; this skill owns the LOOK, /edit owns the CUT. Use when the user says "make it cinematic", "the card style", "/cinematic", "that IG cinematic edit", "square card style", "movie b-roll style", or hands over reference reels in this style and asks to replicate them.
---

# cinematic — the card-style look

For any Premiere access, follow [Premiere Agent startup and advanced stage routing](../edit/references/premiere_start_here.md). Use the configured new bridge by default; if MCP tools are missing in this chat, use its CLI. Keep this skill’s existing creative scope and read-only limits.


> **This skill owns the LOOK. It does not cut.** Run **`/edit` FIRST** to produce a locked,
> gate-passed cut (boundaries via `speech_map_cut`, filler/dead-air surgery, ending gate). Then run
> `/cinematic` to build the look on top of it. A beautiful card wrapped around an uncut ramble is
> still an uncut ramble — that was the single biggest note on the first build.
>
> Downstream capabilities stay in their own skills and are POINTED TO, never duplicated:
> `cut` (boundary law) · `horizontal-to-vertical` (reframe presets) · `caption-clips` (the spice
> style, which is a DIFFERENT style — do not mix) · `render` (manifest builds) · the step-9 audits.

---

## 📐 START HERE
- **🚀 `references/RUNBOOK.md` — READ THIS FIRST TO BUILD A CLIP.** The end-to-end sequence,
  every command, in order, with the target numbers at each step and a trap table. Two shipped
  clips went through it exactly as written. **This file is the rules; the RUNBOOK is the recipe.**
- **`references/WORKED_EXAMPLE.md`** — the approved builds with their target numbers.
  Land near these or something is wrong.
- **⭐ `references/ELITEX_CAPTION_SYSTEM.md` — THE CREATOR'S OWN METHOD, from his course.**
  Supersedes anything inferred from pixels. Solves the glassy texture (**overlay blend mode**),
  gives the keyframe construction (destination first, **ease out**), and says two-word lines —
  he tried per-word and abandoned it. He edits in **CapCut**, not Premiere.
- **`references/VARIANT_matted_bigword.md`** — the same style measured off his reels. Useful for
  the numbers (card geometry, cut rate, silhouette placement); defer to the course file on method.
- **`references/STYLE_SPEC.md`** — the measured style constants.
- **`references/CASEBOOK.md`** — why every rule below exists. Read it before overriding one.

---

## 🔒 THE MEASURED STANDARD — `references/STYLE_SPEC.md`

Every number in that file was measured off reference frames, not eyeballed. The load-bearing ones:

| element | value |
|---|---|
| canvas | 1080×1920, pure black |
| **card** | **980×980 square**, x 50–1029, y 470–1449 (vertically centred), **corner radius 48px** |
| split variant | 2× 980×696, 29px gap, stack top at y=258 |
| shot rhythm | median 0.8–1.2s · 7–10 cuts per 10s · open long (3–4s) · close long (1.6–1.8s) |
| tail | **1.6–1.9s of pure black with the music still playing** |
| loudness | −14 LUFS integrated |
| caption colour | **FLAT WHITE**, or **BLACK** on a bright plate. No gradient, no glow, **NO SHADOW — EVER** |
| caption cap height | p50 ≈ 44px (4.5% of card) · p90 ≈ 86px (8.8%) — **big words are RARE** |
| caption block width | 0.25–0.45 of the card — **1–3 words**, then it clears |
| caption alignment | **CENTRED** (measured centre x 0.49–0.52, y 0.50–0.56) |
| caption case | lowercase body + **ALL CAPS on beat words** (~10% of words). Caps and the big size tier go together |
| type voices | **Helvetica Neue Bold** (body — IDENTIFIED, mean IoU 0.788 over 8 clean samples) + **Snell Roundhand Black** — a bold engraver's SCRIPT, on interstitial cards. NOT a Didone italic (measured: ink 0.252/aspect 2.69 vs reference 0.263/2.76) |

---


> ## 🛑🛑 NEVER USE A SHADOW ON THIS STYLE
> Editor, explicitly: *"Don't ever use shadow for these types of edits."* It is also what the
> reference measures — the ring test on white type over movie b-roll gives 3–9px = 149.8 (that is
> glyph antialiasing), 9–17px = 88.7, background 84.1. **No darkening anywhere.**
> If white type is illegible the answer is **black type**, never a shadow, never a scrim, never a
> glow. `caption_type.py` has no shadow code path at all — keep it that way.
> Verify: alpha in a ring 2px out should be <10 and ~0 by 8px. A shadow reads >20 out to 8–20px.

## 🛑 HARD-WON RULES — every one of these shipped a defect first

1. **CAPTIONS ARE FLAT WHITE.** Measured over 1,473 text-bearing frames: mean glyph RGB
   (238, 233, 232), R−B median +2.6. On warm-lit shots the type *looks* warm because the shot is
   warm — proof: in one reference shot "DO" reads white and "HARD" reads warm two frames apart, the
   only difference being what is behind the strokes. **Never build a gradient or a glow.**
2. **GENERALISE A STYLE RULE FROM A DISTRIBUTION, NEVER FROM ONE FRAME.** The gradient above was
   invented by over-reading a single payoff frame. Sample the whole reel before trusting any rule.
3. **CONTACT SHEETS ARE FOR STRUCTURE ONLY** — cuts, order, layout. They are downsampled; measuring
   colour or size off them gives garbage. Colour/size come from FULL-RESOLUTION frames.
4. **MEASURE OUR OWN CAPTIONS FROM THEIR ALPHA MASKS**, never by detecting text in a composite.
   The "bright pixel with a dark neighbour" detector fires on a bright window with dark mullions —
   it contaminated both sides of a comparison and nearly drove captions 2× too wide.
5. **FACE-TRACK THE A-ROLL. ALWAYS.** A fixed centre crop put the subject half out of the card.
   Detect per shot with YuNet and **pick the face by CONFIDENCE, never by area** — largest-area
   picked a wall fixture (score 0.60) over the real face (0.93).
6. **xmeml POSITION IS IN FRAME-HEIGHT UNITS:** `premiere_x = 0.5 + xml_horiz × (H/W)`. Passing
   `(px − 0.5)` straight through lands the crop ~44% off. Use `pos_to_xml()` in `build_xml.py`.
7. **PIL's `getbbox()` IS ORIGIN-RELATIVE** — it returns ascent 0 for every line and silently
   collapses leading so captions overlap. Use `getbbox(text, anchor="ls")`.
8. **PREMIERE CANNOT DECODE AV1.** yt-dlp defaults to it. Transcode every source — master AND
   b-roll — to H.264 before it touches a timeline. The MCP will report `imported: N` while Premiere
   is throwing a rejection dialog, so **the tool's success value is not proof of import**.
9. **EVERY BRIDGE CALL CARRIES THE PROJECT GUARD.** Premiere's active project switches under you.
   One un-guarded `importFiles` dropped a whole sequence into an unrelated project.
10. **NEVER HAND-LAY AUDIO onto an XML-built sequence.** `audioTracks.addTracks` is not a function
    and falls through to Audio 1; `overwriteClip` on a linked A/V item drags the video with it and
    wiped V1 from 24 clips to 3. Put audio in the XML. `app.project.undo` is not exposed and
    reopening does not revert.
11. **LETTERBOXED FILM B-ROLL NEEDS NO CROP EFFECT.** Set Motion Scale = `980 / visible_height × 100`
    and the visible band maps exactly onto the card hole; the black bars fall outside the matte.
12. **THE EDITABILITY INVARIANT HOLDS** (see `edit/RUNBOOK.md`). Cuts are real clipitems on the
    source, framing is Motion values, captions are overlay items. Never bake and import.

---

## ✅ THE STRUCTURAL GATE — run this diff before calling a version done

Caption look is only half of it. These four numbers caught real defects that eyeballing missed.
Render our cut with `preview.py`, sample both at 15fps, and compare:

| metric | reference | why it matters |
|---|---|---|
| **cuts / 10s** | **6.9–9.1** across six reels (median shot **0.63–1.27s**) | ours sat at 6.8 / 1.46s and felt sluggish |
| **text runs** | **1** (text is on screen ~96% of the time, essentially continuous) | ours had **12** — the captions were blinking off between phrases |
| **black tail** | **1.6–1.9s** | measure at luminance < 6, not < 3; a legitimate tail reads ~3.4 not 0 |
| opening / closing shot | 3.3s / 1.6s | open long, close long |

### 🛑 FADE ONLY AT A REAL SPEECH PAUSE
Caption states are back-to-back, so a phrase-end fade ramps alpha to zero with **nothing behind
it** — a visible blink. The reference holds text almost continuously. Fade only where the gap to
the next chunk exceeds ~0.25s; everywhere else the next caption simply takes over.
(Fades went 40 → 1 and the blink count went 12 → 1 when this was applied.)


### 🛑 RAISE THE CUT RATE WITH B-ROLL CUTAWAYS, NOT BY SPLITTING A-ROLL
The longest shots are always A-roll, and splitting one is a jump cut. Cut AWAY instead — that is the
reference's own device. Insert a short, visually distinct b-roll beat inside a long A-roll run, and
pick a source that differs from BOTH neighbours (see the near-identical-moments rule above).

Leave the **cold open** (~3s) and the **payoff** long — the reference does. Only the middle tightens.

Worked: 4 cutaways inserted into A-roll runs of 1.3–2.4s took the build from **6.8 → 8.0 cuts/10s**
and median shot **1.46 → 1.13s**, with all four registering on a scene-detect pass.

### 🛑 A CUT BETWEEN NEAR-IDENTICAL MOMENTS OF THE SAME SOURCE IS NOT A CUT
Adding shots to raise the cut rate did nothing until the moments were made visually distinct —
splitting one film at two similar timestamps (a face at 29.6s and the same face at 33.5s) registers
as no change at all. Verify with a scene-detect pass: every planned boundary should appear within
0.15s of a detected change. If it does not, pick a genuinely different moment or a different film.
**Exception:** a card → card+element beat (empty white card, then the dot/type appears) is meant to
be a low-change transition — that is the reference's own device, not a defect.

---

## 🎞️ CAPTION ANIMATION — measured off the reference, not guessed

**MEASURED across all three reels — 58 caption entrances probed at native 30fps:**

| how a caption enters | share |
|---|---|
| **fade-in** (fast: 1–3 frames) | **39–56%** |
| slide (any direction) | 63% |
| — of slides, **HORIZONTAL** | **71%** |
| direction mix | **right 28% · left 17% · down 13% · up 6% · no move 37%** |
| travel distance | median **36px** (3.7% of the 980 card), p75 78px |

**Slides and fades COMBINE** — a caption typically slides in *and* fades in. Ease-out, not linear.
Beats travel further (~1.9×) and fade slightly slower (3 frames vs 2).

🛑 **DO NOT USE A "SETTLE DOWN" ENTRANCE AS THE DEFAULT.** The Alex Shorts preset
("Text Down Small", position 0.49609375 → 0.5 over 12 frames = eases down 7.5px) is the *rarest*
direction in the reference (down/up together are only 19%) and the editor explicitly rejected the
look. Horizontal slides are the house style.

🛑 **PROBE FADES WITH REGION INTENSITY, NOT A BRIGHTNESS THRESHOLD.** A thresholded glyph mask
only sees the caption once it is *already* bright, so a first pass reported **zero fades** across
all three reels when in fact 39–56% fade in. Track mean intensity inside the SETTLED caption's
bounding box across frames −1…+5; a fade ramps, a cut steps to full in one frame.

🛑 **ONLY THE FIRST STATE OF A PHRASE ANIMATES.** With per-word building, animating every
accumulating word jitters. ~40 entrances per clip, not 100.

🛑 **SCALE THE ANIMATION TO THE STATE.** 82% of our caption states are shorter than the preset's
0.5s — a fixed-length animation is truncated and never settles. Use
`min(5 frames, state_duration − 1)`.

Editor presets live in `__ACQ_ASSETS__/assets/caption_anims/` (Fade · Pop · Rotate · Tweet
String · Text Down Small). They animate **`AE.ADBE Geometry2` (Transform)**, not text properties,
so they apply to ANY clip — our PNG caption overlays included. `build_xml.py` reproduces the same
motion natively (`motion_anim()` + `opacity_in()`), so no preset needs to be applied by hand.




### 🛑 THE PREVIEW MUST PLAY THE **CUT** AUDIO

`preview.py` renders our timeline for measurement. If it pulls a CONTINUOUS slice of the master
instead of the cut spans, picture and captions run on the cut timeline while audio runs on the raw
one — a **progressive desync equal to everything /edit removed** (1.53s on the reference build),
worst at the ending, which is where it gets noticed.

Build a `VOICE_cut.wav` by concatenating the exact frame-snapped spans from `cut/cuts.json` (12ms
edge fades) and feed the preview THAT. Verify by transcribing 3-second windows at four points and
matching against `timeline_words.json` — expect 85–100% word match, and **100% at the ending**.

Two smaller preview traps found with it:
- **Segment-concat rounding shortens the picture.** 28 segments each rounding down cost 4 frames;
  the card died before picture-out. Pad and `trim` to exactly `DUR` before appending the tail.
- **The caption overlay repeats its last frame over the black tail** (ffmpeg overlay default
  `eof_action=repeat`), leaving text floating on black. Generate caption frames for the FULL
  `DUR+TAIL` with blanks after `DUR`, and clamp each item to `min(t1, DUR)`.

**The Premiere XML was correct throughout** — A1 already used the three cut spans. This was a
preview-only defect, but the preview is what gets reviewed, so it reads as a defect in the edit.




### ✅ FONT IDENTIFICATION — the method that finally worked

Earlier attempts failed (whole-word IoU ~0.20 for every candidate = no separation) because glyphs
were extracted off BUSY plates. The fix is to hunt for frames where the caption sits on a **clean,
dark, low-variance background** first — `scripts/glyph_hunt.py` scores every frame by the variance
of the background *around a dilated glyph mask* and keeps the cleanest.

With clean glyphs, IoU discriminates properly (8 samples across all six reels):

| font | mean IoU |
|---|---|
| **Helvetica Neue Bold** | **0.788** ✅ |
| Helvetica Bold | 0.747 |
| Inter Bold | 0.703 |
| Proxima Nova Bold | 0.696 |
| Montserrat Bold | 0.588 |

**BODY = Helvetica Neue Bold** (`HelveticaNeue.ttc` index 1) at ~-2.5% tracking.
**CARDS = Snell Roundhand Black** (`SnellRoundhand.ttc` index 2) — a bold engraver's script.

🛑 **CAPS ARE REAL — an earlier version of this file wrongly said "lowercase only".** The clean
specimen shows `NOT · WORKLOAD · LOSE · SOUL` in ALL CAPS while connective words
(`that is · then · more · only · jumps off · but`) are lowercase. **Caps ride WITH the big size
tier** — roughly 10% of words, the same rate as the emphasis tier.

### 🛑 ANIMATION: EASE IN *AND* OUT, AND DO NOT BE TIMID
Editor: the entrances read *jarring* and *too subtle* at the same time. Both come from the same
curve. A cubic ease-OUT starts at MAXIMUM velocity — 17.6px on the first frame — which is the snap.

| | wrong | v1 fix | **CURRENT** |
|---|---|---|---|
| easing | cubic ease-out | smoothstep `u·u·(3−2u)` | **smoothstep** |
| travel | 36px | 64px | **150px** |
| duration | 5 frames (209ms) | 9 frames (375ms) | **55% of the word's own hold**, min 10 frames |
| fade-in | 2 frames | 2 frames | **200ms (5 frames), flat** |
| peak per-frame jump | 17.6px | 10.6px | ~22px |

Velocity ramps and falls symmetrically. Longer and larger reads *calmer*, not busier — the jarring
came from the abrupt start, not from the distance.

🛑 **The 36px and 64px numbers were both too small, and the reason matters more than the number.**
36px came from tracking caption centroid across entrance frames. But **captions fade in while they
slide**, so a brightness-thresholded tracker cannot see the word until it is already bright — by
which point most of the travel is over. The instrument under-measured every time.

The corrected figures come from a purchased preset pack that **states** travel and duration
(its most restrained tier is 161px / 1627ms / 200ms fade). See `references/COURSE_TEARDOWN.md`.

> **When a reference does two things at once, never measure one of them with a detector that the
> other one blinds.** Prefer a source that *states* the value — a preset, a spec sheet — over a
> pixel measurement of a composite. Related to the "distribution, not one frame" rule, but about
> the *instrument* rather than the sample size.

**Before raising travel, check edge runway:** measure each word's alpha bbox against the canvas
edge in its entry direction. The compositor pastes a full-canvas layer at an offset, so a word
with less runway than the travel gets its leading edge **clipped** instead of sliding in whole.
At 150px only 1 of 121 words is short, and it carries no text.

Scale-based entries beat slides on the hook: in the pro pack's own usage counts, a **slow
continuous scale-in** is the single most-used move (12 uses vs 7 for the busiest wipe).

### 🛑 A SLIDE MUST NEVER BE WIDER THAN THE GAP TO THE NEXT WORD
Words in a chunk sit side by side with normal word-spacing. Two words mid-slide at different
elapsed times sit at **different offsets**, so a travel bigger than the gap makes one word cross
straight over its neighbour. At 150px `because` + `there` rendered as **"becausehere"**. 64px is
proven. Raise travel only with a gap check, and never above the smallest inter-word gap.

**And do not port hook-text values onto per-word captions.** The pro pack's 161px/1627ms slides
are for **title cards and hook text that live for seconds**. A per-word caption lives ~0.9s — a
slide set to 55% of its hold never settles, so every word drifts for over half its life. That is
what made V21 read as mush. Animation should be a small fraction of the hold, not a majority.

### 🛑 THE CAPTION FILL DEFAULT MUST BE WHITE, NEVER "gradient"
`render()` used to default to `fill="gradient"` — the cream→gold + glow that was fabricated from
one frame and rejected outright. A new caller that simply **forgot to pass a fill** silently
re-shipped the rejected look, and it took a bbox that was 70px too tall to notice. The gradient is
opt-in only now. Any rejected style left reachable by omission WILL come back.

That same glow is why the size ladder was wrong for so long: it inflated every measured box by
~70px, so two separate "ours is 1.2x over" readings drove the ladder **down** when it was already
too small. **Measure type from the alpha mask, and confirm no effect is inflating the box first.**

### 🛑 EVERY WORD MUST SIT INSIDE THE CARD — GATE IT
The **tallest** style sets the anchor, not the body size. A hero word's ascent punched 5–16px above
the card top while every body word looked fine. `gen_captions.py` now fails loudly with the word,
its style, and the overflow in px. Zero words outside the card is the pass condition.

### 🛑🛑 CAPTIONS ARE CENTRED ON THE CARD — THIS IS THE BIGGEST SINGLE TELL
Measured over **297 caption boxes across all six reels**:

| | X centre (frac of card) | Y centre |
|---|---|---|
| reference | p25 0.47 · **MED 0.50** · p75 0.51 | p25 0.47 · **MED 0.50** · p75 0.57 |
| what we shipped for 20 versions | **0.30** fixed | **0.13** fixed |

We pinned every chunk to a fixed top-left corner. **That one fact — not the font, not the size —
is what made the captions read wrong on every shot.** Nudge X off centre only when a specific
source frames its subject hard to one side; that is a per-source adjustment, never the style rule.

The anchor is the first baseline, so a block can only be centred *after* measuring its rendered
mask — see `place_block()`. Do not try to compute it from font metrics.

### 🛑 WIDTH IS THE HONEST MEASURE OF WEIGHT, NOT GLYPH HEIGHT
A short word and a long word at the same point size read completely differently, so height alone
kept saying "we match" while the captions plainly didn't. Caption-box width / card:

| | p25 | med | p75 | p90 |
|---|---|---|---|---|
| reference | 0.29 | 0.39 | **0.50** | **0.63** |
| ours (before) | 0.28 | 0.42 | **0.79** | **0.91** |

The body was already right — only the **emphasis tier** was wrong, at ~1.5× the reference, so big
words spanned nearly the whole card. Two fixes: scale hero/mega 0.65×, and set `MAXW` to the
reference p90 (**620px**), not to the card width. A caption that spans the whole card reads as a
subtitle, not as this style. **When a size check and your eye disagree, measure width.**

### 🛑🛑 EMPHASIS IS **WEIGHT**. SIZE IS **PER CUE**. THIS IS ALREADY SOLVED IN `caption-clips`
Do not invent a caption emphasis model here. `caption-clips/SKILL.md` has the locked house one,
proven on shipped work, and this skill must follow it:

> *"Weight = vocal stress. Proxima Nova ladder: Medium (base) → Bold → Extrabold → Black."*
> *"Size = intensity, subtle (10–15%). **Per CUE only** — a size bump lands on a single-word caption
> OR the whole line, **never one word inside a multi-word line**."*

We had it exactly backwards: emphasis by **size**, mixed **inside** a line. To make that fit, mixed
sizes then had to be stacked onto separate lines — and that stacking *is* the jumping the editor
saw. Editor: *"the words are kind of jumping up there… it's glitchy, it's not smooth."*

Deterministic assignment (no LLM needed — it is the director's own fallback rule):
function word → `base` · content word → `strong` · longest content word in the cue → `emph` ·
number/money → `emph` · listed beat word → `peak`. Cue bump: 1.15 if the cue carries a number,
1.10 if it is a single word, else 1.00.

**Anything that varies per WORD when it should vary per CUE reads as jitter.** That covers size,
entrance direction, and animation magnitude — all three were per-word here and all three were wrong:

| | was | now |
|---|---|---|
| entrance direction | `DIRS[(cue+word) % 4]` — three words, three directions | **one direction per cue** |
| anim magnitude | 1.7 on beats, 1.0 elsewhere | **uniform 1.0** |
| travel | 64px | **36px** (house drop-in is 8px @1080) |

Variety belongs **across** cues, never inside one.

### 🛑🛑 ONLY **ONE WORD PER CUE** ANIMATES — APPROVED BUILD
The single change that turned the captions from *"this sucks"* into *"so much better"*. Source is
the course author narrating the move himself:

> *"selecting the **one word** that you want to have a slide in effect on — you can do like a
> little slide in up."*

Animating every word makes a 3-word cue fire **three separate entrances** — that is the
"glitchy / words jumping" read, and no amount of easing or travel tuning fixes it. The **stressed**
word moves (`emph`/`peak`); every other word simply appears. Landed at 26 cues with one moving
word, 4 with two, 2 with none.

Pairs with the per-cue rule above: **size, direction, and now motion itself are all per-CUE
decisions.** The only thing that legitimately varies per word is **weight**.

### 🛑🛑 NO PUNCTUATION ON CAPTIONS. EVER.
Editor ruling 2026-08-09: *"No punctuation on these. Ever."* Commas, periods, question marks,
exclamation marks, colons and semicolons **never render**. `chunk_captions.py` has `show()`, which
strips them from the DISPLAY text only — the chunker still **reads** punctuation to decide where a
chunk breaks, it just never shows it. **Apostrophes stay** (they live inside words: *there's*,
*won't*, *you're*).

Gate it: `re.search(r"[.,?!;:]", cue_text)` must return nothing across every cue before rendering.

### 🛑🛑 A CUE IS ATOMIC — EVERY WORD IN IT CLEARS AT THE CUE END
Editor screenshots: *"sometimes the captions lay on top of each other as they're coming in and
out"* — `WHITEhad a`, `intoyou were locked`, `interestingthe most`.

Cause was a per-WORD minimum duration (`t1 = max(cue_end, t0 + 0.35)`). A word starting late in its
cue got extended **straight through the boundary** — 24 of 100 words bled up to **0.27s** into the
next cue — and because every cue is centred, the outgoing word landed on top of the incoming one.

- **Read-time is a CUE-level concern.** Enforce it by chunking, **never** by extending a word.
- A word too short to read gets its onset pulled **EARLIER** (bounded by the cue start), never held
  later. `MIN_WORD = 0.24s`. Arriving a little ahead of its onset is imperceptible; an 0.08s flash
  is not.
- Gate: **0 words may extend past their cue's end.**

### 🛑🛑 A CUE MUST NEVER STRADDLE A PLATE-LUMA FLIP — MOVE THE **CUT**, NOT THE COLOUR
Editor: *"we need to time the B-roll and the captions to pop up at the same time… we can't make
those black because the B-roll hasn't started yet."*

A b-roll cut landing mid-cue splits the cue across a dark plate and a bright one, and **no single
ink colour is right for both halves**. `into and` (2.45–3.69) straddled the white-void cut at 3.10:
half on Alex wanting white, half on the void wanting black.

**The fix is always to move the CUT to the cue boundary** (3.10 → 3.69), never to recolour mid-cue.
`gen_captions.py` gates this and reports every offender — it immediately caught a second one nobody
had noticed (a cut at 5.50 sitting 0.03s before a cue edge, luma 233 → 126).

### ⚠️ "THE SHOT IS WHITE" ≠ "THE TEXT IS ON WHITE"
On the white-void b-roll the **card mean is 234** but the luma **under the glyphs** is 181 → 83 → 35,
because the captions are centred and the subject's dark figure is centre-frame. The words sit on
*him*, not on the white. White ink is correct there; black would be illegible.

**Always sample under the glyphs** (`plate_luma(plate, mask)`), never a card average. If a caption
genuinely should be black over a bright shot, the caption has to be **moved off the subject onto the
bright area** — that is a layout decision, not a colour one.

### 🛑 `cropdetect` EVERY FILM SOURCE BEFORE IT ENTERS THE `CROP` TABLE — NEVER ASSUME 16:9
Editor: *"we want to keep everything in the exact same mask… some of the B-roll doesn't fit."*
Both Whiplash clips report 1920×1080 to `ffprobe` but the real picture is **1920×800 with a 140px
black bar top and bottom** — 2.4:1 cinemascope baked into a 1080 frame. Declaring them 1080 scaled
the *bars* into the card, so the b-roll sat letterboxed inside the rounded square.

```bash
ffmpeg -hide_banner -ss 12 -i clip.mp4 -t 6 -vf cropdetect=24:2:0 -f null - 2>&1 | grep cropdetect | tail -1
```
**A film source's container size is not its picture size.** Verify by measuring the luma of a thin
strip just inside the card's top and bottom edges — near-black on both means letterboxed.
(That check flags an intentional black `card` too; exclude card shots before reading it.)

### 🛑 THE A-ROLL SCALE FLOOR IS "FILL", AND `face_frac` IS WHAT DRIVES IT
Editor: *"Alex is too zoomed in and too far to the right."* `face_frame.py` sizes the shot from
`face_frac` (face height as a fraction of the card), and 0.42 produced **140–150%** scale on this
source. Fill for a 1080-tall source in a 980 card is **90.7%** — anything far above that is real
zoom. Dropping to `face_frac 0.28`, `face_x 0.58` landed **93.5–100%**, i.e. essentially fill.
**Compute the fill floor (`CARD / source_height`) and compare before accepting a framing pass.**

### 🛑 `words_fmt.json` CAN DROP A LEADING WORD — `locked_transcript.json` IS AUTHORITATIVE
Editor: *"Alex says 'If there's a lot of stakes' and the captions only say 'there's a lot of'."*
The formatted word list began at `there's`; the locked transcript had `If` at 0.10–0.28 and the
audio contained it all along. **Build `timeline_words.json` from `locked_transcript.json`.**
Read the first cue against the first spoken words before rendering — a dropped leading word is
invisible in every count-based check.

### 🛑 THE BLACK-FRAME REPAIR PASS WILL EAT AN INTENTIONAL BLACK CARD
A `card` shot with `fill="black"` renders at (8,8,8) and drops just under the repair threshold
after h264/yuv encoding — so the preview's artifact-repair replaced **every frame of a 1.08s
"BEFORE YOU FAIL" card** with a neighbouring shot and deleted the beat silently. The log said
`repaired 35 black boundary frames`; 35 frames at 23.976 *is* the card.

`preview.py` now excludes every frame inside a `card`/`dot` shot before repairing. **A repair pass
must know what is intentional.** Sanity check: repaired-frame count should be a handful (boundary
artifacts). If it is close to a shot's frame count, it ate the shot.

### ✅ SECOND CLIP FROM THE SAME SOURCE — the pipeline as run (2026-08-09)
`UnreasonableToFail`, 24.4s, from an already-mined candidate list (74 candidates, this one q87).
**Do not re-mine a source that `/edit` has already mined** — check `clips/` and `candidates_final.json`
first; the cut, transcript and speech map were all already there.

```
cut_spans.json + words_fmt.json      -> cut/timeline_words.json (t0/t1, timeline-relative)
ffmpeg spans -> concat               -> AROLL_window.mp4 + VOICE_cut.wav   (identity media_offsets)
chunk_captions.py                    -> generated_groups.py   (retarget EMPH/EMPH_PHRASES per clip)
   ^ CHUNK FIRST: shot cuts must land on cue boundaries, so the cue list has to exist first
plan_v2.py                           -> SHOTS, every t0 on a cue boundary
face_frame.py                        -> cut/aroll_framing.json  (then eyeball for outliers)
gen_captions.py                      -> per-word PNGs + manifest + 3 gates
preview.py                           -> build/V*.mp4
```
Landed at 18 shots · 7.4 cuts/10s · median shot 1.24s · 33 cues · all three gates PASS.
`media_offsets.json` is needed in **both** `cut/` and `premiere/assets/` (plate.py reads the latter).
Editor: *"at the very end Alex is kinda too zoomed in… not cropped like the beginning."* The face
tracker had produced **scale 143.0 / px 0.01** for the final shot while all six others sat at
**90.7 / ~0.36**. One outlier row, invisible in any per-frame metric, obvious in the table.
**Print the per-shot scale/position table and eyeball it** — a shot that disagrees with its
neighbours by >15% is a tracker failure, not a creative choice.

### 🛑 SMOOTHNESS = MOTION BLUR + AN OPACITY FLOOR + AN EASE RAMP
The author builds his slide from scratch on camera, and the recipe has three parts. We had one.

1. **Motion blur.** He uses the **Transform** effect specifically because plain Motion cannot blur:
   *"turn the shutter angle up — if this isn't checked the motion blur won't take effect."* And the
   value is explicit: *"uncheck use composition shutter, throw this all the way up to **360**."*
   A hard-edged step per frame is what reads as stepping. Renderer: average **6 sub-positions
   across the full frame interval** (360° = whole interval; 180° still steps).
2. **Opacity ramps from ~28%, never 0.** *"Make this like about **30 or 25%, not from zero**."*
   From zero a word blinks into being; part-visible, it arrives.
3. **Bezier temporal interpolation + a velocity ramp** — our smoothstep already matches this.

⚠️ **Blur only the word's bbox** (padded by travel). Averaging six full 1080×1920 float canvases
per frame is ~300MB/frame and will stall the render.

### ✅ LETTER SPACING = −4%, A STATED VALUE
*"Turn the letter spacing down, which makes everything look a lot more clean — about a value of
like **−40**."* Premiere's units are 1/1000 em, so −40 = **−4%**. We were at −2.5%.

### ✅ CAPTION-TRACK SETTINGS HE NAMES OUTRIGHT
From Premiere's "create captions from transcript": characters-per-line **low** (*"so there's not
many words popping up"*), minimum duration **low**, **single** line, and **zero gap between
captions** — *"you don't want any gaps at all, otherwise it'll look really really bad."*

### ⚠️ HE USES A SHADOW; WE DO NOT
He feathers a shadow *"a lot"* and drops its opacity *"just where it's super super subtle."*
**The editor has ruled shadow out for this style outright** — that instruction wins. Recorded only
so the discrepancy isn't rediscovered as a missing feature.

### 📌 NOT YET BUILT — worth doing
- **Snap caption boundaries to CUT points**, not only to word onsets.
- **Camera-movement adjustment layer ABOVE the text**, so type rides the move.
- **"Staircase"** multi-line emphasis: offset lines diagonally, slide each in, stagger from the top
  of the staircase downward, then nest to move as one.
- Premiere-native path is the **Text Animator**: `Object Type = Word` in Advanced Controls (it
  defaults to letter-by-letter), then tune **Word Bias** for the stagger — values change with font,
  size and spacing.

### 🛑 CAPTIONS ARE **WHITE**. BLACK IS AN EXCEPTION, NOT A BALANCE
Editor: *"I don't like that there's black text that you randomly use… it was just a one-off
scenario when it went to an all-white background."*

The dark-flip guard is a **legibility escape hatch for pure-white plates only** — never a
general two-colour scheme. Its threshold was 128, the midpoint of the luma range, so it fired on
any merely *bright* plate: **24 of 100 words went black**.

Measured under the actual glyphs: p50 70 · p90 190 · **p95 255**. The real all-white interstitials
are a pin-clean **255**; everything between 128 and 200 is just bright footage. `WHITE_PLATE = 200`
leaves black on **9 words, every one of them luma 255**.

> **A guard's threshold belongs at the edge of the case it protects against, not at the midpoint
> of the range.** A midpoint threshold turns an exception into a policy.

### ✅ FACE: OPEN SAUCE SANS (not Proxima) — the author states it outright
> *"go to Open Sauce Sans Black — that's looking way better to me."*

`/edit`'s spice captions use Proxima; **this style uses Open Sauce Sans**. Open Sauce ships the same
4-step ladder (Medium → Bold → ExtraBold → Black), so keep `/edit`'s **weight logic** and swap only
the family. Corroborated independently by our own glyph IoU — Open Sauce Black won outright on one
reel (0.84 / 0.88 / 0.86). Fonts in `assets/fonts/`.

### ⚠️ EMPHASIS IS CONTRAST, NOT A ONE-WAY SIZE RAMP
The author makes an emphasis word **smaller** and switches it to a script face — then says
*"we're just playing around at this point."* So his emphasis goes in **either** direction and is
partly hand-picked by feel. Systematise the weight ladder, but do not assume bigger is the only
emphasis move, and leave room for a hand override.

### 📄 GETTING A LESSON'S CONTENT WITHOUT TOUCHING THE VIDEO
Course platforms (Whop → `<mux-player>`) expose an English subtitle track. Do **not** rip the
stream. Reach the `<video>` through the shadow DOM, set the subtitle track `mode='showing'`, then
**seek across the full duration in ~45s steps accumulating cues into a Map** — cues only load with
their segment, so one read gives you the first 30s and nothing else. Gap-check afterwards and
re-seek the gaps. 57 min → 1211 cues. The narration is the part the asset files never contain.

### 🛑 READ-TIME: CHUNK LONGER, NOT SHORTER
Editor: *"way too fast to barely read."* Capping chunks at 3 words produced 40 cues with a median
0.99s→0.82s hold and 14 of them under 0.7s. The locked spec is **pace-adaptive 2–4 words** with a
5-frame absolute floor plus a dense-cue reading bump. Going to 4 gave 33 cues, median **0.99s**,
only 6 under 0.7s. **More words per cue means more time per cue — shorter chunks read faster, not
slower.**

### ⚠️ DON'T DEBUG YOUR OWN CONTACT SHEET
A "wasnothing" collision chased through two rebuilds turned out to be the 980→490px downscale in
the review sheet, not the render. Measured gaps were 22–27px at 52px glyph height (~0.45 ratio,
normal). **Confirm a defect in the full-res frame or in the geometry before fixing it.**

### 🛑 A SIZE CHANGE STARTS A NEW LINE — NEVER SET TWO SIZES ON ONE BASELINE
The reference stacks mixed sizes in a tight column — *"can do / **hard** / things"*, small/BIG/small
— and only shares a baseline between words of the **same** size (*"you went into"*). Setting a
small word beside a big one made `The one` read as a typo with `one` floating above `The`.

### 🛑 SENTENCE CASE FOR BODY; ALL CAPS ONLY FOR A STANDALONE BEAT
The reference is lowercase almost everywhere (*"that is"*, *"at the"*, *"when you say"*). Caps are
reserved for a rare beat word that appears **alone on screen** (`RELENTLESS`, `OBSESSION`).

### 🛑 ONE FACE AT ONE SIZE IS NOT A STYLE
The build shipped with a single face because the serif path required **every** word in a chunk to
be in a hand-listed set, so it never fired — and `EMPH` held three words, so 34 of 37 chunks
rendered at the identical size. Editor: *"I don't think you even use different fonts or anything."*

The reference is a **gradient**, not one body size plus rare beats — text-box height p25 **49px** ·
p50 **70px** · p75 **97px** · p90 **121px** (36 clean specimens, 6 reels). Reproduce it by making
weight track **function**: function words drop a tier, content words hold the line, the beat word
changes **face** as well as size. Target: over half of chunks using more than one style.

| role | face | why |
|---|---|---|
| body | Helvetica Neue Bold | IoU **0.788**, the best match |
| emphasis / beat | Open Sauce Sans Black | IoU 0.763, won one reel outright — a genuinely different letterform |
| hook / title card | Akira Expanded | IoU 0.312 — that low score *confirms* it is display-only, never captions |
| card accent | Snell Roundhand Black | the engraver's script on the interstitials |

Fonts live in `assets/fonts/`. A missing face falls back **loudly** to the body face — never silently.

### 🛑 B-ROLL IS THEMED AND STRATEGIC — NOT A GRAB BAG
Editor: *"We have to be intentional with the B-roll. There has to be a strategy behind it. You
don't just throw up random clips for no reason."*

**Pick ONE film and stay in it.** If the clip opens on a Matrix white void, every cutaway after it
is Matrix. One film = one visual world; mixed films read as random even when each clip is apt.

**Map the film's own arc onto the argument.** For BlackDotRoom the Matrix arc *is* the point:
Construct white void ("a white room with nothing in it") → the dojo, training ("struggle to do the
work") → **the woman in red, which in the film is literally a test of whether you get distracted**
("other more interesting things to do than the work") → bullets / becoming The One ("put yourself
in a situation where work becomes the most interesting thing"). Each cutaway earns its place.

**B-roll does not have to run the whole time.** A-roll carries the connective tissue. A healthy
split is roughly **40% A-roll · 48% b-roll · 11% cards** — b-roll appears where it says something.

### 🛑 CAPTIONS GO IN THE SUBJECT'S NEGATIVE SPACE ON A-ROLL
The face is framed at 0.62 of the card, so the empty side is the LEFT. Put type upper-left and
middle-left — never centred over the subject, never directly above his head. On **b-roll and cards**
keep captions centred (there is no subject to avoid).

### ⚠️ PREVIEW-ONLY: BLACK FRAMES AT SEGMENT BOUNDARIES
Concatenating per-shot segments leaves an occasional black frame at a boundary (seek/keyframe
artifact). It does NOT exist in the Premiere timeline, which uses real clipitems with in/out points.
`preview.py` repairs it by replacing any all-black card frame with its neighbour.
Frame-exact segments (`-frames:v`) reduce it 9→7; the repair pass takes it to 0.
🛑 Do NOT "fix" it with a pre-roll `trim` — that desynchronises the seek and blacked out whole
segments (9 → 119 black frames).

### 🛑 CAPTION LEGIBILITY IS MEASURED PER SHOT, NOT PER CLIP

White type dies on a bright plate (the Matrix white-void b-roll measures **luma 236 under the
glyphs**). The fix is not a shadow — it is to measure and switch:

| luma under the glyph pixels | fill |
|---|---|
| **> 128** | **black type** (the reference does exactly this on its white cards) |
| **≤ 128** | **flat white** |

**TWO STATES ONLY.** Plate luma is strongly bimodal (p50 62, p75 181), so one threshold is clean —
a middle band covered only 2 of 60 items and was not worth a third state.

🛑 **A CAPTION WORD MUST BE SPLIT AT EVERY SHOT BOUNDARY IT SPANS.** Captions persist across cuts,
so one word can ride from a bright plate onto a dark one — the word "there" spanned 3.69→5.53 across
THREE shots. Decided as one item it falls back to a weak compromise and stays invisible on the
bright half. Split it: each piece gets its own fill, only the FIRST piece animates in (later pieces
are continuations with no entrance).

`plate.py` reconstructs the card content at time *t* so `caption_type.plate_luma()` can measure it.
Measure **under the glyph pixels**, never over the bounding box — a bbox mean averages in dark
background and hides a white-on-white collision.

### 🛑 ANIMATE PER WORD, NOT PER BLOCK

Each WORD is its own timeline item, entering at its OWN measured onset with its OWN direction,
accumulating into the phrase. A whole-block PNG cannot do this — animating it moves every word
together, which is wrong.

Editor's example: for *"to do the work"*, `to` slides up, `do` slides down, `the` and `work` both
come in from the left. Consecutive words sometimes SHARE a direction (~35%); the rest vary.

**This is why caption timing has to be word-exact.** Blocks hide timing error; per-word animation
exposes it immediately.

Implementation: `caption_type.render(block, only=k)` draws word *k* at its position in the full
block layout, so every word is a separate transparent overlay that lines up perfectly with its
neighbours. Words within one chunk overlap in time, so they need **one caption track per slot**
(max words in a chunk — typically 5: V4…V8). Item span = word onset → chunk end.

### 🛑 CAPTION TIMING — the thing that reads as "really bad"

Word-perfect sync is NOT the same as good timing. A build can be 0/100 words out of sync and still
feel terrible. What actually breaks it:

| symptom | cause | fix |
|---|---|---|
| strobing | accumulating word-by-word to an arbitrary word cap, then resetting mid-phrase | **semantic chunks that REPLACE** |
| meaningless flashes | function words shown alone (`a` for 0.12s, `that you were` for 0.04s) | glue words never end a chunk |
| unreadable | 31% of states under 0.20s, min 0.04s = ONE frame | enforce a minimum hold, merge short chunks forward |

**Targets, measured against the reference:** median hold **≈0.9s**, minimum **≥0.35s**,
**zero** states under 0.20s. Compare: the bad version was median 0.28s / min 0.04s / 31 states
under 0.20s — with perfect word sync.

`chunk_captions.py` implements it: break on MEANING (close a chunk only when the next word opens a
new phrase and the current chunk does not end on a glue word), keep compound beats whole, then
merge anything below the minimum hold into its neighbour. Only the beat WORD goes big — never
uppercase the whole chunk.

## 🔊 MUSIC — non-negotiable on this style

The editor's note: *"Music is really important on these types of edits."* A cinematic card edit
without a bed is not the style.

🛑 **AN AUDIO-ONLY FILE MUST NOT CARRY A `<video>` BLOCK IN xmeml.** Emitting
`<media><video><width>0</width>...` made Premiere link the music as video and the sequence played
**completely silent** while the track still showed a clip. Use `filedef(..., audio_only=True)`.

🛑 **STRIP COVER ART.** Music mp3s carry an embedded mjpeg art stream — that is the source of the
"codec not supported" class of failure. Prenormalise the bed first:
```bash
ffmpeg -stream_loop -1 -i TRACK.mp3 -vn -t <total> \
  -af "loudnorm=I=-29:TP=-3,afade=t=in:st=0:d=1.0,afade=t=out:st=<total-1.5>:d=1.5" \
  -ar 48000 -ac 2 -c:a pcm_s16le MUSIC_bed.wav
```
Music selection is owned entirely by `/edit`: call `_shared/pick_music.py --transcript
<assembled_transcript.txt> --duration <seconds> --used <recent>`. Cinematic contributes its tagged
ViralREELS library to that central matcher; it does not maintain a second picker or a separate pool.
Cinematic wants a quiet intro under the hook, a mid dip, and a lift that lands under the payoff.
Final mix target **−14 LUFS**.

The shared matcher may pull from ViralREELS when its human tags and measured sound fit the clip; do
not force every cinematic-looking clip into ViralREELS. Visual treatment and emotional music intent
are related but not identical.

**SFX and transitions** live in `assets/sfx/` (riser, clicks, reverse bell) and
`assets/transitions/` (4 film burns, already native 1080×1920, 0.17–0.29s). A film burn is a
**cut accent, not a transition to hide a bad edit** — if the cut needs hiding, fix the cut.

---

## THE BUILD

```
0.  /edit  ->  locked cut (cuts.json + word-level transcript). DO NOT START WITHOUT THIS.
1.  LEARN     watch the reference AND our own output at 15fps, measure the delta   (scripts/)
2.  PLAN      shot plan + b-roll assignment                       templates/plan.example.py
3.  FRAME     YuNet face-track the A-roll -> per-shot Motion       scripts/ (see rule 5)
4.  CAPTION   chunk 1-3 words -> render states                    chunk_captions.py + caption_type.py
5.  BUILD     xmeml -> import to Premiere as native layers         build_xml.py
6.  VERIFY    preview at 15fps, diff against the reference         preview.py + analyze15.py
```

### 1 · LEARN — the delta loop (this is the engine of the whole skill)

> 🛑🛑 **LOOK AT THE REFERENCE BEFORE YOU MEASURE IT — BIG ENOUGH TO READ.**
> Twenty versions were spent tuning fonts, sizes, easing and travel while the captions sat in the
> wrong *place* on every shot. The position error was obvious in three seconds of looking at
> card-sized crops, and invisible in every number being tracked, because the numbers answered
> questions nobody had checked were the right ones. Editor: *"They're just not how I want them to
> look."*
>
> **First pass on any reference is always: crop the card, scale it to ~490px, put eight frames in a
> grid, and describe what you see** — where the text sits, how it stacks, what is capitalised, how
> many words are on screen. Only then choose what to measure. Measuring is for *confirming and
> calibrating* a hypothesis your eyes formed, never for *finding* one.

The delta loop itself. Watch the reference at 15fps, watch **our own output** at 15fps, and measure
the difference. It found every real defect; watching alone and measuring alone each missed things.
```bash
ffmpeg -i REF.mp4 -vf fps=15 -vsync 0 frames15/REF/f%04d.png     # full-res, EVERY frame
python3 scripts/watchsheets.py REF        # readable 236px tiles — for STRUCTURE
python3 scripts/analyze15.py  REF         # per-frame colour/size — for NUMBERS
```
Then the same on our render and compare. Sizes come from **our caption alpha masks** (rule 4).

### 2 · PLAN
Copy `templates/plan.example.py`, set `SHOTS` (t0/t1/kind/source), `CROP` (measure with
`cropdetect`), `FLASH` times, and the caption `GROUPS` (or auto-generate with `chunk_captions.py`).

### 3–5 · FRAME, CAPTION, BUILD
`build_xml.py` emits the sequence; import it with the project guard, then verify track counts and
spot-check a Motion value against the computed one before saving.

### 6 · VERIFY
`preview.py` renders the timeline locally in ~35s **for measurement only** — it is never the
deliverable. The deliverable is the Premiere sequence.

---

## ASSETS

- **Film b-roll library:** `__ACQ_ASSETS__/assets/broll_lib/` — `raw/` as downloaded,
  **`pp/` = the Premiere-safe H.264 transcodes; always link to `pp/`** (rule 8). Its README carries
  the measured letterbox crop per clip. Source new clips with `yt-dlp` from YouTube.
- **Fonts:** Didot Italic (`/System/Library/Fonts/Supplemental/Didot.ttc` **index 1**) and a bold
  grotesque (HelveticaNeue.ttc **index 1** — index 2 is the Italic, which silently slants everything).
  The exact reference face could NOT be identified — burnt-in text over moving footage defeats glyph
  extraction (whole-word overlay IoU ~0.20 across all candidates). Bold grotesque at ~−2.5% tracking
  is the supported claim; do not over-claim a specific family.
- **Music:** → Use `/edit`'s canonical `_shared/pick_music.py` with the locked clip transcript.
  Cinematic still wants a quiet intro, a mid dip, and a lift that lands under the payoff.

## BRAND
Generic. Brand-specific vocab, presets and overrides live in that brand's own folder and are passed
by path. `Alex` is only ever an example here, never a default baked into the code.
