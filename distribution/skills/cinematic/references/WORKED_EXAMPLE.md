# WORKED EXAMPLE

## ⭐ V30 — the approved CAPTION build (2026-08-09)

Editor: *"this is so much better, so so much better."* Reached after ~10 rejected caption versions.
Render: `10_WORK/build/V30_preview.mp4`. **These are the caption numbers to hit on a new clip:**

| | value |
|---|---|
| face | **Open Sauce Sans** — Medium / Bold / ExtraBold / Black |
| emphasis | **weight** per word · **size** per cue only (1.00 / 1.10 / 1.15) |
| weight mix | base 35 · strong 28 · emph 24 · peak 13 (of 100 words) |
| **animation** | **ONE word per cue moves** — 26 cues × 1 · 4 × 2 · 2 × 0 |
| direction | **one per cue**, cycling across cues · travel **36px** · uniform magnitude |
| placement | block ink-centred at **X 0.45 / Y 0.50** of the card |
| width | p25 0.28 · med 0.42 · p90 0.63 of card (`MAXW` 620) |
| cues | **33** · median hold **0.99s** · only 6 under 0.7s · 2–4 words |
| lines | **one line per cue** — never stack, never two sizes on a baseline |
| gates | card-bounds 0 outside · dark-flip live (24 black / 76 white) |

The four errors that took the longest, all the same shape — **varying per WORD what belongs to the
CUE**: motion, direction, magnitude, size. Only weight is per-word.

Source narration for the fix is in `10_WORK/course_transcript/` (1211 cues pulled from the
lesson's own subtitle track).

**Not yet built**, both from that transcript and both still worth doing:
snap caption boundaries to **cut points** (not just word onsets), and put the **camera-movement
adjustment layer ABOVE the text** so type rides the move.

---

# The first approved build (structure/cut)

**`BlackDotRoom`** — the clip this skill was reverse-engineered on, approved 2026-08-09.
Source project: `~/Downloads/alex/2026-08-08_EditStyleStudy/` (`10_WORK/00_RUN_LEDGER.md` has the
full blow-by-blow, including every wrong turn). Render: `10_WORK/build/V14_preview.mp4`.

Use these as the target numbers on a new clip. If a build lands far from them, something is wrong.

## The finished shape

| | value |
|---|---|
| duration | 32.12s picture + **1.71s black tail** = 33.83s |
| loudness | **−14.6 LUFS** |
| picture | 28 shots · **6.8 cuts/10s** · median shot 1.46s · open 3.04s · close 1.83s |
| captions | 29 semantic chunks → **100 per-word items** across 5 tracks |
| caption hold | median **0.92s** · min 0.38s · **zero** under 0.20s |
| caption sync | **0/100** words off their onset |
| tracks | V1 picture · V2 split · V3 matte · V4–V8 caption words · A1 voice · A2 music |

## The cut (this came from `/edit`, not from here)

Raw window 33.65s → **32.12s**, removing 1.53s of dead air that a transcript alone could not see:
- a **0.86s** pure-silence island hiding *inside* a stretched word ("there", labelled 1.30s)
- a filler "and" plus a **1.54s** pause immediately before the payoff

Two Whisper label lies caught by RMS, either of which would have shipped a defect:
- the ending: labels said `work` and `we` were fused; measured, `work` ends 13936.49, then **0.18s
  of −92 dB silence**, then `we`. The engine's edge-hug had swallowed "we" → FALSE ENDING.
- the head: the onset snap sat in a −38 dB plateau and leaked a "So"; the real notch was at
  −80.9 dB, narrower than one 23.976 frame.

## Build order that worked

```
/edit ............. locked cut → cuts.json + timeline_words.json
face_frame.py ..... per-shot Motion (YuNet, CONFIDENCE-picked)
chunk_captions.py . semantic chunks (median hold 0.92s)
caption_type.py ... one PNG PER WORD (render(block, only=k))
build_xml.py ...... xmeml → Premiere, native layers
preview.py ........ 30s local render for the delta loop
```

## Assets it used

- b-roll: Matrix (white void) · Whiplash · Wolf of Wall Street · Social Network · American Psycho —
  from `__ACQ_ASSETS__/assets/broll_lib/pp/` (H.264 transcodes, never `raw/`)
- music: *clubbed to death* (Matrix soundtrack) — quiet intro under the hook, mid dip, lift at ~25s
  landing under the 30.06s payoff. Prenormalised to `MUSIC_bed.wav` with `-vn`.
- type: HelveticaNeue Bold (ttc **index 1**) at −2.5% tracking · Didot Italic on the cards

## What the editor rejected along the way

Read `CASEBOOK.md` for the full list. The short version:
1. decorating a raw window instead of cutting it
2. a fabricated gold-gradient + glow caption style (invented from ONE frame)
3. a muddy warm/vignette colour grade — **the editor grades; this skill does not**
4. the "settle down" caption entrance — horizontal slides + fades are the house style
5. block-level caption animation — it must be **per word**
6. caption timing in blocks (median hold 0.28s, 31 states under 0.20s = a strobe)
