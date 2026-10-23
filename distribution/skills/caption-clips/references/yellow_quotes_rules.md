# Yellow + Quotes — the decision rules (when YES, when NO)

The single authoritative ruleset for the spice caption color/quote axis. The `caption_director.py`
SYSTEM prompt encodes this; this doc is the human/agent reference. Append new calls as Oliver reviews land.

## The ONE principle
**COLOR = WHOSE VOICE.**
- **White** = Alex speaking as *himself* (narration, argument, direct address to the viewer).
- **Yellow `#FED90F`** (was `#FECB00` pre-v2) = Alex speaking *as / quoting / role-playing someone else*.
- **Quotes `" "`** wrap that other-voice speech. On reported speech, **yellow + italic + quotes always travel together** — same span, same words.

Color is about *voice*, nothing else. It is NOT an emphasis tool.

## ✅ YELLOW + ITALIC + QUOTES — YES (a voice that isn't Alex-as-himself)
- **Character dialogue** in a told story — `"mom"`, `"but why??"`, `"sweetie"`, `"Miller family tradition"`
- **A customer / objection / what "people" say** — `"yeah, he had an excuse"`, `"you are a special snowflake"`
- **A "here's what you say" script / line to deliver** — `"where you're coming from"`
- **A saying / aphorism** he quotes
- **A hypothetical person's words** — *the people who love you might say,* `"...you are special..."`
- **A study / source quoted in its own voice** (the instructions, the line said to subjects)

## Live guest speech is not a quotation

A guest speaking directly in the exchange uses yellow italic captions throughout
their turn, **without quotation marks**. Speaker identity controls that treatment;
`quote` / `q` means actual reported, read-aloud, imagined or role-played speech.
Do not derive quotation marks from a yellow voice span or from italic styling.
A guest can quote someone too, but only that specifically represented line gets
quotation marks. Host narration returns to its own voice and upright styling.

## ❌ NOT YELLOW — stays WHITE (Alex's own voice / other axes carry it)
- **Alex's own narration, argument, or direct address** — *"you're not gonna earn anyone's respect"*
- **Numbers & money** — `$100M`, `19`, `2 min` → emphasize with **WEIGHT / SIZE**, never color
- **Proper nouns** — `Princeton`, `Apollo Creed`, `Bangladesh` → **capitalize + keep white**
- **Emphasis / punchline words** — a key word goes heavier **WEIGHT** or bigger **SIZE**, NOT yellow
- **Rhetorical questions Alex asks as himself** — *"is that what you really want?"*
- **The lead-in to a quote** — *"and everyone will be like,"* / *"the people who love you might say,"* is white; the quote that FOLLOWS is yellow

> Litmus test: *Could you put "—he said" or "—they'd say" after it?* If yes → yellow+quoted. If it's Alex making his own point → white.

## How a quote renders (mechanics)
1. Reported speech is a **CONTIGUOUS SPAN**: opening quote on the FIRST word, closing quote on the LAST.
2. **Per-cue quotes** — every caption segment of the span shows its own `" ... "` (Oliver's rule), not just the first/last cue.
3. **ALL-OR-NOTHING** — *every* word first→last is yellow+italic+quoted, **including function/connective words** (the, a, that, I, to, he, had, an, until, your, of...). Never leave a mid-quote word white. (Emphasis weight/size MAY still vary word-to-word inside the span.)
4. **No bleed** — the word *immediately after* the quote is WHITE. The quote must not color the next word.
5. **Separate spans** — narration that resumes between two quotes is white; open a NEW span for the next quote.

## Mechanism (automated, so it can't regress)
`caption_director.py` expands `voice_spans: [[first_idx, last_idx]]` into per-word
voice color, then emits **`voice_spans: []`** to prevent time-range color bleed.
Live guest turns receive the profile's italic base without automatic `q`.
Explicit per-word `q` classifies actual quoted speech independently of voice color.
`generate_spice.py` renders those independent voice, italic and quotation decisions.

## Worked examples (real clips, 2026-06-04)
- **Excuses** — `"you know what, I'm going to continue to live the life that I want until I die"` is ONE span: every word yellow+quoted, **not just** *live/life/die*. `"he had an excuse"` (×2): all four words, **not just** *excuse*.
- **Mediocrity** — `"yeah, you know what, you are special, you are a special snowflake, your mama might still love you"` is ONE span. The next word `you're` is **WHITE** (Alex resumes) — this is the no-bleed rule (it was wrongly yellow until fixed).
- **Capacity** — the Princeton **"Good Samaritan"** study is Alex *narrating* (he voices no character) → **all white**; `Princeton` / `Samaritan` capitalized, never yellow.

---
*Append approved YES/NO calls from future Oliver reviews here so the director keeps learning.*
