# "Spice" Caption Style — reverse-engineered spec
Source: 4 reference reels (DVw9xlgDqqx, DVrhFBOEo2f, DVgogm0DiWc, DVeTI7lkh2S), 2026-06-03.
Goal: replicate the team's best editor's dynamic caption styling + encode the decision logic.

## Visual base
- **Font:** **Proxima Nova — FULL family** (14 weights) extracted from the user's Adobe Fonts cache (CoreSync livetype) into `caption-levelup/fonts_proxima/`, each renamed to a unique libass family: Thin, Light, Regular, Medium, Bold, Extrabold, Black (+ each Italic). Use per-word weight as the emphasis dial (Oliver uses the whole range: Light/Thin to de-emphasize, Medium/Bold for emphasis, Extrabold/Black for the payoff word). **Italic = gentle `\fax` shear (~-0.12, ≈7° forward/RIGHT; positive fax leans LEFT in libass), NOT synthetic `\i1` (~12°, too leaned)** — tunable. (True italic weight files are also installed if proper italic letterforms are ever wanted.)
- White fill; light dark stroke + soft shadow for legibility (lighter than the pro_locked shadow).
- Centered, single line, **2–4 words per screen**, word-group reveal synced to speech, snappy cut-on transitions.
- Position ≈ vertical centre (y≈48–55%); on split-screen Q&A it sits on the seam between the two shots.
- lowercase by default; numbers as **digits + abbreviated** ($12M, $8M, 150).

## The 5 styling axes (THE LOGIC)
1. **COLOR = whose voice is this?**
   - **WHITE** = Alex's own voice — direct narration AND his own hypothetical reasoning.
   - **YELLOW (#FED90F, brand yellow — was #FECB00 pre-v2)** = a DIFFERENT voice — the live guest in a Q&A, OR Alex impersonating a customer / objection.
2. **WEIGHT (bold) = vocal stress.** Bold the 1–2 KEY content words per phrase — the semantic payload: nouns, numbers, negations ("not", "never"), vivid verbs, the punchline word. Glue/function words (the, of, to, is, a, you, and, with) stay Regular. Roughly 30–50% of words end up bold.
3. **ITALIC = "this isn't flat present-tense narration."** Used for: (a) quoted / role-played / hypothetical speech; (b) the reflective/emotional payoff of a story; (c) single-word contrast or vocal stress ("you'll lose *some*"); (d) the "other voice" / guest lines (often italic in newer edits).
4. **QUOTES " " = explicitly role-played / reported speech.** Always italic; color follows whose voice (yellow if impersonating someone else, white if Alex's own hypothetical).
5. **SIZE = intensity (MEASURED from 19 clips / 1,271 captions, 2026-06-03).** Detector = (white|yellow) pixels gated by a near-black stroke, per-caption pixel height normalized to each clip's median (baselines vary 80–136px @4K, so size is RELATIVE). Findings: **~27% of captions bumped ≥1.15×; only 6% ≥1.4×, 3% ≥1.6×.** Among bumps: **p50 1.28× · p75 1.36× · p90 1.60× · peak ~1.8–2.0×** → implementation tiers **emph 1.25 / strong 1.5 / peak 1.85**. **Triggers:** numbers/money (mean 1.15× vs 1.04× overall; `$100M`,`$500K` are the biggest + yellow), the **payoff/punchline** word or line, **key/identity & proper nouns** (chiropractor, Atlanta), **vivid/expressive words** (terrifying, "pff"). **Size is its own axis** — yellow 1.07× vs white 1.03× (≈color-neutral) — and **STACKS** with weight + color + italic. Applies per-word (inline number bigger than neighbors) OR per-line (whole punchy phrase). Method/scripts: `analysis/analyze_size.py` + `aggregate_sizes.py` + `build_size_montage.py`. NOTE: the bbox-height metric is mildly confounded by ascenders/descenders, and ratios >~2.2× in the raw data are title-card/hook overlays (excluded) — the tiers above are the robust read, confirmed visually.

## Evidence (from the reels)
- white + bold key word: `the skill of **sales**` · `is a **hard pitch**` · `**most expensive**` · `and **not** cancel them?` · `pacing **$12M** this year` · `**any** business that exists`
- yellow (live guest): `if you were in my shoes?` · `we wanna pull that` · `I just feel like` · `and then solve more`
- yellow + italic + quotes (Alex voicing a customer objection): `"if I raise my prices"` · `"all my customers!"`
- white + italic + quotes (Alex's own role-play reasoning): `"cool we can hire"` · `"all market for me"` · `"we also wanna"`
- italic reflective payoff: `treat people` · `that they would buy` · `to myself`
- italic contrast: `you'll lose *some*`
- number → digit + bold: `**2** can play that game` · `**$12M**`

## The PROCESS to encode it (proposed)
1. **Word-level transcript** (already have it; for Q&A add speaker diarization → who is Alex vs guest).
2. **LLM "caption director" pass** — feed the transcript to a model that emits a per-token style stream: `{text, color: white|yellow, weight: regular|bold, italic: bool, quote_open/close: bool}` by applying the 4 axes above. This is where the "logic" lives — it's a semantic decision, so an LLM (not regex) makes it.
3. **generate_ass v2** — extend the ASS builder to honor per-token weight/style/color + quote marks, mapping to the 4 font styles (R / Bold / Italic / Bold-Italic) and 2 colors. (Today's generate_ass only does single-axis emphasis.)
4. **Burn** at the 4K preset onto the clean (un-captioned) vignette.

## Test target
`work/clean_source_4k.mp4` (ActionsOverFeelings, solo Alex, 2160×3840, no captions) + `work/transcript.json`.
Solo clip → mostly white; bold the key words; italic on any reflective/contrast lines or quotes.

## TIMING & CHUNKING — data-derived from Oliver's 19 clips (2026-06-03)
Method: word-level Groq transcript of all 19 (6,348 words / ~601 sentences / ~10.6 words/sentence) + vision-read of the burned captions at sentence/pause boundaries. (Tesseract OCR was unreliable on the stylized split-screen text — bright faces survive thresholding — so caption frames were read directly with vision.) Transcripts saved at `analysis/transcripts/*.json`.

**THE RULE THAT MATTERS (the "two sentences on one line" bug):**
- **Hard break at EVERY sentence boundary (. ? !). Never put two sentences in one caption.** Data: **81% of Alex's sentence-ends have ~0 pause** (he runs sentences together), yet Oliver breaks the caption at the boundary EVERY time (verified at zero-pause boundaries in both Q&A and Workshop clips: "years."→new, "mood."→new, "common."→new "#1…", "too."→new). So the break is **punctuation-driven, NOT pause-driven**. The merge bug happens when the transcript isn't punctuated → the chunker never sees the boundary. **FIX: run `punctuate_transcript.py` FIRST, then ALWAYS split at . ? ! (and at , for long clauses).**
- Within a sentence: keep the SOP caps — **≤3 words AND ≤18 chars** per caption.
- Secondary: also start a new caption at a **mid-sentence pause > ~0.4s** (rare — only 13 across all 19; needs WhisperX-grade word timing to detect, since Groq word-ends are mostly 0-gap, so this is a nicety, not the main rule).
- Reveal is **word/chunk-synced** to speech onset; **zero-gap** (continuous, no blank frames); Text-Down-Small drop-in per cue.

**Confirmed on-top styling** (matches the 4-axis spec): color = voice (white Alex / yellow guest + quoted), bold = stress words, italic + "quotes" for role-play/quoted, **digits** for numbers, and **#1 / #2 / #3 numbering on listicle items**.

So the chunker order is: punctuated transcript → split at sentence (.?!) ALWAYS → split at clause (,) → then pack ≤3w/≤18c → optional pause split → THEN the styling layer tags color/weight/italic/quotes/numbering.

## Open questions (blocking exact replication)
- Exact font + Italic/Bold-Italic files (is it Proxima Nova full family?).
- Confirm the color/voice + italic rules match the editor's intent.
- Build the reusable engine (LLM director + generate_ass v2) vs hand-style this one clip first.
