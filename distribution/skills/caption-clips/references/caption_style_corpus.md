# Caption Style Corpus — distilled from 44 clips (LOCKED 2026-06-10)

Reverse-engineered by reading every burned-in caption across **24 Oliver Q&A Workshop clips + 20
Hormozi-ecosystem masterclass shorts** (caption strips diffed against word-level transcripts, color
pixel-verified). Raw per-batch evidence: `training/corpus/_nuances_batch{1-4}.md` + `_nuances_ms_batch{1-4}.md`.
This is THE house caption style for `caption-clips` (engine: generate_spice.py + caption_director.py + spice.json).

## Two presets, one shared skeleton
There are TWO color presets; everything else is identical.
- **Q&A preset (2+ speakers):** white + YELLOW. Color encodes VOICE.
- **Monologue preset (1 speaker):** WHITE-ONLY (yellow channel off). 4/5 solo Hormozi clips were 100% white.
The split is a SPEAKER rule, not a default — on a one-voice clip the Q&A preset collapses to white-only.

## COLOR (resolved — the big one)
- **Color = whose VOICE.** WHITE+upright = Alex / the answerer / the single speaker. **YELLOW (#FECB00 as measured in this corpus; current canon is #FED90F per the v2 spec) + ITALIC = the guest / second voice** (their whole turn, gated purely by who's talking; stable 2024→2026).
- **Numbers & money inherit the SPEAKER's color and are BOLD.** Guest's "$600K" → yellow+bold; Alex's "$3M"/"100%" → white+bold. (This corrects the old "numbers are never yellow" rule — they're yellow *when the guest says them*.)
- Italic in a WHITE line = emphasis/quote only (white is otherwise upright).
- Proper nouns: Title-Case, stay white, never yellow. (Some common-but-proper words lowercased, e.g. "mormon".)
- A per-word yellow KEY-WORD highlight inside a white line appears occasionally (batches 2/3) — use sparingly; the dominant, reliable system is voice-color. Do NOT blanket-yellow topic nouns.

## EMPHASIS = WEIGHT, not size (important correction)
- Emphasis is carried by **font WEIGHT on the ONE load-bearing word per cue** — at the SAME size as its neighbors (pixel-verified: bold "action" == neighbor cap-height). Ladder: Medium (base) → Bold → Extrabold → Black.
- **Do NOT scale font size for emphasis.** The size axis is effectively OFF for this style (set `auto_size` off; size bumps are rare/none). Earlier "size-bump" guidance is superseded by the uniform-size evidence.
- ITALIC = quoted / role-played / imagined / inner-voice speech, and soft qualifiers (*at least*, *violently*). Whole-line italic for register shifts; single-word italic for a soft beat.

## NUMBERS / MONEY formatting
- Money ≥ $1M abbreviated + `$`: "two and a half million" → **`$2.5M`**, "1.2" → **`$1.2M`**, "100M" → **`$100M`**. Thousands → **`$600K`** / **`$250K`** (capital K/M, `$` prefix, no space). `$`/`K`/`M` are INFERRED from context even when unspoken.
- Ranges: "$250,000, $300,000" / "150 to 250" → **`$250K–$300K`** / **`$150K to $250K`**.
- Percent → **`#%`** on each number ("60 to 70 percent" → `60%-70%`). **Editorial minus for a decrease**: "down twenty percent" → **`-20%`**.
- Multipliers: "two times" / "10x" → **`2X`** / **`10X`** (digit + capital X, often its own cue).
- Ordinals / list numbers: "number one" / "third" → **`#1`** / **`3rd`**; small counts → digits ("three locations" → `3 locations`). Bare big numbers keep commas (`1,000`).
- All numbers/money are BOLD and take the speaker's color.

## CLARIFIERS & SPECIAL TOKENS
- **`[bracket]` clarifier** when the speaker was vague/used a pronoun: "net" → `[profit]`, "the store" → `[the store]`, "Package A" → `Package [A]`. Lowercase, bold, inherits speaker color. (Oliver also sometimes silently appends the omitted word, e.g. a bare figure → "… revenue", with NO brackets — both patterns exist; brackets are the explicit-substitution case.)
- **`*asterisk*` action tags** for non-verbal: `*sigh*`, `*nods*`.
- **Quotes:** curly “ ” + italic for reported/role-played speech (inherits speaker color); upright straight quotes (no italic) for a NAMED TERM ("key man risk"). `?`/`!` may sit just outside the closing quote.
- Profanity is NOT censored.

## TEXT / PUNCTUATION / CASING
- **Near-verbatim transcription — fillers KEPT** ("I mean", "like", "you know", "nah", "gonna", "wanna", "cus'"). The edit lives in the CUT, not in rewriting the words.
- Lowercase EXCEPT `I`-forms (`I`, `I'm`, `I'd`…) and proper names.
- **Keep:** `?` `!` `…`/`..` (trail-off), trailing `-` (hard cutoff), apostrophes, in-number commas. **Drop:** sentence-final `.` and mid-sentence `,`.
- Casual respellings preserved/added: "going to"→"gonna", "want to"→"wanna", "because"→"cus'".

## CHUNKING / TIMING / LAYOUT
- **1–3 words per cue** (2–3 typical), SINGLE line, zero-gap between cues, clean open (3–5 frame lead), **HARD cut on the payoff word** (no fade).
- **Position is mid-frame and dynamic per shot** — median y≈0.55 (range ~0.43–0.69), NEVER fixed lower-third. Rides to the active-speaker panel on split-screen / picture-in-picture; sits steady ~0.53–0.58 on a full-frame stage shot. Drive per camera-angle via the segment-aware method (`segment_aware_captions.md`).
- Style holds even over B-roll.
- Shadow: soft grey feathered drop-shadow, NO hard outline (see `oliver_qa_locked_recipe.md`).

## FONT
- Proxima Nova family (Oliver Q&A + some monologues). A few monologues use a rounder geometric sans (Poppins/Montserrat-ish) — Proxima is our house default. Base = Medium, 150px @4K.

## GRAPHIC OVERLAYS (occasional, Q&A)
- **Submitted-question CARD**: name (bold) + the verbatim question (sentence-case, lighter, left-aligned, wrapped) layered above the centered captions — the "open on the context" rule as a graphic.
- **FTC disclaimer band** ("DISCLAIMER: …results may vary") shown whenever a results/income claim is made.

## DATA-QUALITY NOTE (for the corpus extractor)
The extractor's `cues.json` `yellow` boolean and whole-frame color ratio are UNRELIABLE — they false-positive on skin / warm backgrounds / logos (wrong on ~25–40% of cues). Judge caption color by reading the strip crop, or a STRICT saturated-yellow pixel test (`B<120 & R-B>110 & G-B>80`) on the caption band only. Fixed in extract_caption_strips.py.

---

## Most-flagged caption errors (from 104 real Frame.io review notes, 2026-06-10)
The actual mistakes reviewers caught + sent back, by frequency — the director + caption_lint must
never let these ship. (Full notes: training/corpus/frameio_caption_notes.{json,md}.)
1. **caption timing / sync (30)** — captions out of sync, flashing, or showing during silence. Enforced by
   generate_spice onset-correction + de-flash + min_cue_dur; verified by mozi-sf-audit dialogue-sync. #1 error.
2. **color / highlight (25)** — wrong word colored / wrong voice. Enforce voice-color + money-in-speaker-color.
3. **placement / position (19)** — too low / covering a face. Enforce mid-frame dynamic per-segment Y (~0.55).
4. **should be lowercase (18)** — stray capitals. (lint: capital advisory.)
5. **spelling / typo (15)** — run the brand vocab list; never ship an unknown proper noun unchecked.
6. **wrong word — should say X (6)**, **capitalization (5)**, **quotation marks (4)**, **font/style (3)**,
   **number formatting (3)**, **missing $ (3)**, **missing ? (2)**, **punctuation (1)**, **cut-off caption (1)**.

---

## What the Frame.io reviewers ACTUALLY demand (read from the 104 real notes, 2026-06-10)
The notes are mostly DTC monologue clips, reviewer = Jasmine. They overwhelmingly CONFIRM the locked
rules; the actionable recurring asks (do these or they come back as revisions):
- **SPLIT a cue / match Alex's dialogue timing** (8 split + 11 too-fast notes — the dominant ask): e.g.
  "separate these subtitles — 'them who have' / '5-10 years'", "split this subtitle, exceeds UI safe zone",
  "too fast to be read". → keep ≤18char/≤3word cues, snap each cue to its words (onset-correct), enforce
  min_cue_dur so nothing flashes too fast, and never exceed the UI safe-zone WIDTH. (Engine already does this;
  mozi-sf-audit dialogue-sync is the gate.)
- **Add quotation marks on reported speech** ("add quotation marks for this segment, to show this isn't Alex
  speaking") — confirms the curly-quotes+italic rule; the director must catch every role-play span.
- **Add `?` after each question** ("add question marks after each question") — keep/restore terminal `?`.
- **Capitalize brand/proper nouns** ("capitalize 'Fruit of the Loom'", "the 'p' in Princeton", "'ma' → 'M&A'").
  These are CONTEXT-dependent — do NOT auto-substitute bare tokens (would break "ma"=mom). Instead pass them
  per-clip: `--extra-proper-nouns "M&A" "Fruit of the Loom" Princeton` when the topic warrants. Watchlist to
  pass when relevant: M&A, R&D, P&L, B2B, SaaS, DTC, LTV/CAC/ROAS, brand names, place names.
- color/highlight (25), placement (18), lowercase (18) flagged most by raw count — all already locked above.
Takeaway: the #1 real-world failure is TIMING/CHUNKING (split + too-fast), not the style — so the chunker +
min_cue_dur + dialogue-sync gate matter as much as the look. Full notes: training/corpus/frameio_caption_notes.{json,md}.

---

## Baked-in status (2026-06-10) — what's CODE vs director vs manual
- ✅ CODE (spice_normalize.py): `$K/$M/$B`, `#%`, magnitude merge, big-money abbrev, number+time-unit, **`2X` multiplier**, **`#1` ordinal/rank** (last two added 2026-06-10 from the reels).
- ✅ CODE (spice.json + generate_spice): two-layer shadow, Medium base, font 150, mid-frame position, size axis OFF, animation.
- ✅ DIRECTOR (caption_director.py system prompt): color=voice, money speaker-color, emphasis=WEIGHT-not-size (phrase runs), voice_spans + brief-interjection, italic, quotes (q+i role-play / q named term). Deterministic fallback when no LLM.
- ✅ GATE (caption_lint.py + mozi-sf-audit, made accurate): money-unit caps OK, shadow-style color skipped, `?`/`!` beats not flagged as fragments, logical-word chunk count.
- ⚠️ DIRECTOR/MANUAL (NOT auto — context-dependent, auto would create errors): editorial `-20%` on a DECREASE (needs direction sense), `[bracket]` clarifiers for vague refs, brand/acronym caps (M&A, Fruit of the Loom) → pass per-clip `--extra-proper-nouns`.

**PROVEN 2026-06-10:** real BuyTheFrontEnd Q&A through `/edit` at 4K → **mozi-sf-audit VERDICT: SHIP** (13✅ 0❌ 3⚠️). Captions match Oliver (voice-color, money bold, weight emphasis, locked shadow, mid-frame); render clean (3.2-frame lead, peak -5.7dB). Remaining ⚠️ are render-side (LRA compression, 83% reframe centering), not caption defects.

---

## App entry point (caption-app :3000) — what it does right, and its one boundary
The localhost:3000 caption-app worker (`caption-app/worker/caption_one.py`) LOADS this skill
(`generate_spice.py` + `spice.json` + the gold exemplars + `caption_lint.py`) — it does not
duplicate any of it. **Tested 2026-06-10 on a real 4K Alex segment → 0 lint errors, locked
style confirmed by eye** (Proxima Medium base, weight-only emphasis Medium→Bold→Extrabold,
size axis OFF, two-layer down-right drop shadow not a stroke, mid-frame, lowercase-except-I).

- **Solo / monologue → perfect, deterministic, no API needed.** The director's deterministic
  fallback (numbers/money→bold, one key word/cue→strong) carries it; this is the operative
  path on this machine (no `ANTHROPIC_API_KEY` set).
- **Q&A guest-yellow is the ONE boundary.** The standalone app has no EDL speaker-truth, so it
  relies on the LLM director to diarize the guest from the transcript. **With no API key the
  director can't diarize → a raw Q&A clip would ship ALL-WHITE.** `caption_one.py` now GUARDS
  this: if Q&A is layout-detected but zero guest spans come back, it warns loudly and points to
  the fix (set `ANTHROPIC_API_KEY`, or run the clip through **`/edit`**, which paints
  guest-yellow deterministically from the EDL). The layout track gives face boxes but no
  active-speaker signal, so layout alone can't color the guest — `/edit` is the right path for Q&A.

---

## Caption POSITION (height) by camera angle — MEASURED 2026-06-10
Measured Oliver's actual burned-in caption-Y across his 24 workshop Q&A clips (599 shots).
**Two anchors, driven by FACE SIZE in the final frame:** WIDE full-body/audience shot (face
< 11% of frame H) → **45%**; TIGHT medium/closeup AND split-screen → **50%**. He never goes
below ~50%. The Y must snap on the EXACT frame the camera cuts (frame-verified, Δ=0) — see
`references/segment_aware_captions.md` "Caption HEIGHT by angle" for the rule + the three
frame-exactness fixes. Code: `layout_analyze.safe_y_pct()` (45/50), `spice.json`
y_percent_from_top=50 (static default). Raw study + QC: `caption-app/training/height_study/`.

---

## CRITICAL — the locked shadow REQUIRES the gblur burn, never the inline ASS shadow (2026-06-10)
The locked two-layer Premiere drop shadow only exists when captions are burned via
`generate_spice.py --burn` (it composites `*_shadow.ass` + `*_shadow2.ass` + `*_text.ass`
through ffmpeg gblur — soft σ75 + σ33 layers under crisp text). The single `cc.ass` /
`subs_text.ass` carries only an INLINE ASS approximation (`\bord\blur` at ~28% opacity) —
thin and washes out. **Never deliver by burning the single .ass with `subtitles=` ; always
route the burn through `generate_spice --burn`.**
- caption-app (`caption_one.py`): already used `--burn` ✓
- **/edit (`qa_assembly.py`): FIXED 2026-06-10** — was burning `subtitles=cc.ass` (the weak
  inline shadow); now calls `generate_spice --burn base --burn-out cc_burned.mp4` (the real
  gblur shadow) and applies the lead/limiter finishing as a 2nd pass. Verified to match Oliver.
- COST: the gblur composite at 4K is heavy (~585s for a 70s clip). A future speedup =
  compute the blur at half-res and scale the soft shadow layer back up (visually identical).

### Burn-path audit (2026-06-10) — ALWAYS the gblur shadow on delivery
All caption renderers verified to route delivery burns through `generate_spice --burn` (the
strong even dark-halo two-layer gblur shadow Maddex locked):
- `edit/scripts/qa_assembly.py` — FIXED ✓   (Q&A multicam, per-angle Y)
- `edit/scripts/qa_build.py` — FIXED ✓        (Q&A/hotline/dtc)
- `edit/scripts/multifinish.py` — already ✓
- `caption-app/worker/caption_one.py` — already ✓
- `listicle-short/scripts/build_short.py` — STILL inline (pills/numbers layered on the ass via
  spice_tabs/spice_number; needs a 2-stage gblur burn + a real-clip test → tracked separately).
RULE: never deliver by burning a single spice .ass with `subtitles=` (that's the weak inline
`\bord\blur` shadow). The inline path stays only as a no-double-encode fallback.

---

## SIZE AXIS RE-ENABLED (2026-06-11) — Oliver enlarges emphasis words
Reversed the earlier "size off / uniform" correction (that was a measurement error — descenders +
background swamped the crude bbox method). Confirmed against Oliver's published NeverOutsourceSelling
reel + the original 1271-caption analysis: **Oliver DOES increase font size on the load-bearing words**,
stacking it with weight + italic. Restored the data-derived tiers in `spice.json`:
`sizes = {base:100, emph:125, strong:150, peak:180}` (~25-30% of words bumped; common bump ~1.25x;
numbers/money/payoff ~1.5x; rare peak ~1.8x). Peak stays < 185 — the rejected "250" was the whole-caption
BASE size, not a per-word peak.
- Per-word size now applies in MULTI-word lines too (removed the old single-word-only gate) — Oliver
  bumps a key word inside a phrase, e.g. "sales and **marketing**" / "to **medium-sized**" / "**close** it I".
- Stacks independently with weight, color, italic (a guest's key number = yellow + italic + bold + bigger).
- The shadow layer scales with the enlarged glyph (both layers use the same per-word `\fscx/\fscy`).
- `caption_director.deterministic_stream` emits size (key word → emph, numbers → strong) so it's lively
  even with no LLM; the LLM prompt re-enables size; `caption_lint` allows the tiers, errors only on >185.
EXEMPLAR NOTE: the gold few-shot bank had size stripped in the 2026-06-10 "size-off" pass — regenerate it
WITH size (from Oliver's burned frames) so the LLM director also learns the size bumps (the deterministic
path already does). ITALICS confirmed: guest = yellow + italic (whole turn); Alex = white + upright.

### SIZE is PER-CUE, never one word in a line (2026-06-11 correction)
Maddex: increasing ONE word's size inside a multi-word line "looks bad, and Oliver never did that."
The rule: a size bump lands on (a) a SINGLE-WORD caption, or (b) the ENTIRE line uniformly — never on
one word among others. `generate_spice` now decides size PER CUE (every word in a cue gets the same
size): single-word cue keeps its bump; a money/number line bumps the WHOLE line to 'strong'; a line
the director sized uniformly is honored; any multi-word line with mixed per-word sizes snaps to base.
WEIGHT + italic still vary per word (bold the key word) — only SIZE is locked uniform within a line.
Enforced by `caption_lint` ("size-nonuniform" error on a multi-word cue with mixed \fscx). Verified on
swindle: 0 mixed-size cues (9 uniformly-bumped: single words + whole money lines "$2M"/"$10M").

### Text-SOP compliance (re-confirmed 2026-06-11, all enforced in code)
lowercase except proper-nouns + I-forms (normalize_simple) · single-line default · `$` prefix on money
+ `%`/`$` symbols not words + abbreviate ≥$100K → $250K/$1.2M/$20M/$3B (spice_normalize) · NO dead gaps
(generate_spice zero-gap: holds + delays next, verified max inter-cue gap 0.000s) · spelling via
per-brand vocab.txt (no blind auto-substitution). caption_lint gates spelled-money, lowercase, punct,
≤3-word chunks, size-uniform, mixed-voice.

---

## THE UNIVERSAL DEFAULT (locked 2026-06-11) — spice for EVERY footage type
`presets/spice.json` (4K) and `presets/spice_1080.json` (1080, an exact mirror — only video dims +
font px differ) are THE default caption style for ALL footage we edit: monologue, Q&A, hotline,
podcast, multicam, listicle — every type. All caption renderers default to it and route through
`generate_spice` (caption-clips = single source of truth):
- `edit/scripts/qa_assembly.py` (Q&A multicam) · `qa_build.py` (Q&A/hotline/dtc) · `multifinish.py`
  (podcast/multi) — all `--preset` default = spice; all burn via `generate_spice --burn` (gblur shadow).
- `caption-app/worker/caption_one.py` (the app) — PRESET = spice.json.
- `listicle-short/build_short.py` — spice (≥2100px) / spice_1080 (else); shadow via the tracked 2-stage burn.
EVERYTHING baked into this default: two-layer gblur Premiere shadow · per-angle height (45 wide / 50
tight, frame-exact snap) · who-said-what (mic-calibration + shot-fallback) · ONE voice per cue · SIZE
axis subtle 10-15% per-cue + safe-zone cap (≤82% width) · italics (guest) · text-SOP (lowercase, $/%,
abbrev, zero-gap). Gates: caption_lint (spelled-money, lowercase, punct, ≤3w, size-uniform, oversize,
mixed-voice) + mozi-sf-audit + scorecard-audit. KEEP spice_1080 in sync with spice.json on any change.

---

## SHADOW — FINAL, LOCKED 2026-06-11 (the months-long shadow, solved)
THE default shadow for every footage type: two-layer gblur Premiere drop shadow, TIGHTENED softness/size.
`premiere_sigma 48 / premiere_sigma2 20` (was 75/33), `premiere_border 13 / premiere_border2 6` (was 20/9),
opacity UNCHANGED (`premiere_intensity 0.70 / 1.0`), down-right offset. The dark halo hugs the letters —
more DEFINED / less diffuse than the old soft/wide version (Maddex's Premiere "softness/size" slider,
dialed toward the tight end but NOT a hard stroke). Values are font-relative (×FS/150 in generate_spice)
so 4K and 1080 render identically. Locked in BOTH spice.json + spice_1080.json. Approved by Maddex on
_swindle_1080_shadowtight.mp4 ("we finally figured out a shadow, lock it in everywhere"). Do NOT revert
to 75/33 — that was the too-soft/diffuse look.
