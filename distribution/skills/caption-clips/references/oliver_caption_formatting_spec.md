# Caption Transcript Formatter — Oliver's Acquisition.com spec (authoritative, v2)

> Source: Oliver Albert (Acquisition.com lead editor). **v2 received 2026-07-06** (Drive file
> `16dKAXI5chZEISnav_JWuYuSUu06_Ru_7`); supersedes the 2026-06-11 v1 in full. This is the AUTHORITATIVE
> caption standard: **Part 1 (text formatting)** is implemented in `scripts/oliver_format.py` (worked
> examples = the test suite `scripts/test_oliver_format.py`) and runs as the normalize step of the spice
> chain. **Part 2 (subtitle segmentation) is IMPLEMENTED (2026-07-06)** in the `generate_spice.py`
> chunker: soft-18 / hard-25, pace-adaptive tiers, onset/silence boundaries, atomic collocations,
> filler/stutter/false-start handling, per-cue curly quotes, sequential 5-frame timing floor. The
> locked lessons (speaker-change hard break, pause pre-reveal split, orphan-merge) are preserved;
> `caption_lint.py` gates the widths (warn >18 / err >25).
>
> Key v1→v2 behavior changes (all implemented): money comma band narrowed to $1,000–$1,999 (so
> "$10K" not "$10,000"); implied-money "very large" threshold $100M→$1M; billion/trillion lowercase;
> large NON-money numbers now scale to K/M ("50K subscribers", never "50,000"); new ordinals rule 4b;
> expanded dictionary (Skool, gonna be/wanna be, vs, cus', mhm, places/languages).
>
> Palette note (Maddex, 2026-07-06): guest yellow = **#FED90F** as this spec states. There is NO
> separate emphasis color — emphasis follows the speaker's voice color (Alex's emphasis stays white,
> carried by weight/size/italic; a guest's stays yellow). This replaces the 2026-06-22 distinct
> emphasis hex.


A style spec for short-form video captions. It has two parts:

- **Part 1 — Text Formatting:** how to normalize the words themselves (numbers, money, capitalization, punctuation, spellings).
- **Part 2 — Subtitle Segmentation:** how to group the formatted words into single-line caption cues (where to break, what to keep together, timing).

Part 2 runs **after** Part 1. The rules are derived from editor-reviewed before/after caption pairs and refined by iteration; they're a practical standard, not a theoretical one — where a call is genuinely a matter of meaning, that's flagged as a manual/judgment step.

For multicamera footage, every supplied shot boundary is a hard cue boundary before all linguistic
break heuristics. Do not carry a grouped card across a cut or pre-reveal a word whose onset belongs to
the incoming angle. A height change alone is not a valid split because it preserves the wrong words.

---

# PART 1 — TEXT FORMATTING

## Processing Order

Apply transformations in this exact sequence to avoid conflicts between rules:

1. **Common words dictionary** — match terms and lock in their final form. Dictionary output is authoritative and cannot be modified by any later rule.
2. **Number words → digits** — convert written numbers to numerals, including compound numbers.
3. **"one" vs "1" + ordinals** — decide whether "one" stays a word or becomes 1; convert ordinals ("third" → "3rd"; "first"/"second" only before an ordinal-signaling noun).
4. **Listicle & sequence labels** — "number N" → "#N"; sequence words ("step one") → "step #1" / "day 1".
5. **Money formatting** — dollar amounts and scale (requires step 2 first).
6. **Symbol & multiplier rule** — "dollars"/"percent" → "$"/"%", "times"/"x" → "X" (requires step 5 first).
7. **Large non-money numbers** — apply the money scale structure (commas, then K/M/billion/trillion) WITHOUT "$" to any number ≥ 1,000 that isn't money — always "300K", never "300,000" (4-digit years excepted).
8. **Capitalization** — lowercase default with all exceptions.
9. **Punctuation cleanup** — remove all disallowed punctuation.

**Idempotency:** if a term is already in correct output form (e.g. "$1K", "ROI", "1-on-1", "AI", "10X", "1,000"), leave it as is — do not re-process.

---

## Rule 1: Capitalization

All words are **lowercased by default**. Exceptions:

**Always capitalize:**
- "I" in all forms and contractions: I, I'm, I'll, I'd, I've — including a cut-off pronoun "i-" → "I" (dangling dash stripped, see Rule 2).
- All proper nouns and names: Alex Hormozi, Leila Hormozi, Sharran Srivatsaa, Gym Launch.
- **Places** — states, cities, countries, continents: utah → Utah, texas → Texas, mexico → Mexico; multi-word as the exact sequence: las vegas → Las Vegas, new york → New York, san francisco → San Francisco, north carolina → North Carolina, united states → United States.
- **Languages & nationalities:** spanish → Spanish, english → English, danish → Danish, french → French, chinese → Chinese, american → American, etc.
- All acronyms: AI, ROI, CEO, CFO, SOP, CAC, LTV, EBITDA, KPI, CTA, B2B, B2C.
- Abbreviations/initialisms where capitalization is standard: U.S.
- "X" as a multiplier suffix: 10X, 5X (see Rule 6).

*Maintain curated lists for places/languages. Words that are ALSO common English are deliberately left lowercase to avoid miscapitalizing — "polish" (verb), "turkey" (food), "nice", "mobile". Add explicit exceptions where a specific place/name is genuinely needed.*

**Keep lowercase (abbreviations that don't follow the capitalization rule):** etc. · e.g. · i.e.

**Note:** "billion" and "trillion" in money/scale amounts are **lowercase** ("$1 billion", "2 trillion") — see Rule 6.

**Sentence-starting words are never capitalized** unless they qualify under an exception above.

---

## Rule 2: Punctuation

**Remove:**
- Commas — except inside a number: 1,000.
- Periods — except inside a number ($1.2M), part of a standard abbreviation/initialism (U.S. / e.g. / i.e. / etc.), or part of a domain name (Acquisition.com).
- **Dangling trailing dashes** — a hyphen/en-dash/em-dash at the END of a token with nothing after it (broken compound or cut-off word): "short-" → "short", "i-" → "I", "make-?" → "make?". **Keep internal hyphens** in compounds: "short-term", "well-being", "1-on-1" are untouched.
- **Incomplete-word fragments are REMOVED** — a cut-off with a **1–2 letter stem + hyphen** is a half-word, drop it entirely: "s-", "va-" → removed. **Exceptions:** "a" (kept) and "i" (→ "I"). Longer stems that ARE words keep the dangling-dash behavior above ("short-" → "short").

**Keep:**
- Question marks: ?
- Exclamation marks: !
- Apostrophes in contractions: I'm / I'll / I've / I'd / don't / can't.

---

## Rule 3: Number Words → Digits

Convert all number words to numerals.

- "one" → 1 (but see Rule 4 for when "one" stays a word)
- "two" → 2 · "three" → 3 · "ten" → 10 · "twenty two" → 22 · "fifty" → 50
- "one hundred" → 100 · "five hundred" → 500 · "one thousand" → 1,000
- (apply to all number words and compound number words)

### Compound Numbers

Combine adjacent number words built from multiplier words (hundred, thousand, million, billion, trillion) into a single numeral.

- "fifty thousand" → 50,000
- "one hundred thousand" → 100,000
- "two million" → 2,000,000
- "three hundred million" → 300,000,000

### The word "a" as a quantity

The article "a" can stand in for "one" ("a thousand" = "one thousand"). Whether it's consumed depends on context:

- **Drop "a"/"an" before a spoken scale number:** "a thousand" → "1,000", "a hundred" → "100", "a hundred bucks" → "$100", "a million people" → "1M people". The number is the quantity, so the article is removed (money and non-money alike).
- **Inside money context, "a" is consumed into the amount:** "a thousand dollars" → "a $1,000" (the "a" reads as the article for the item being priced); but a standalone money answer — "how much do you charge?" / "a thousand" → "$1,000" (here "a" is the quantity and folds into the amount). "a grand" → "$1,000".

**Exception — "zero":** "zero" stays "zero" unless directly followed by dollars, dollar, percent, percentage, %, or $, in which case it becomes "0".
- "zero people" → "zero people"
- "zero dollars" → "0 dollars" (then money rule → $0)
- "zero percent" → "0 percent" (then symbol rule → 0%)

---

## Rule 4: "one" vs "1"

Applies only to the word **"one"**. All other number words always convert to digits (Rule 3).

**Default — convert "one" → "1"** when it's a specific count (after most words: verbs, quantifiers, content words).
- "there's only one way" → "there's only 1 way"
- "just one more rep" → "just 1 more rep"
- "at least one person" → "at least 1 person"

**Exception — keep "one" as a word** when the immediately preceding word is a conjunction, article, or discourse opener AND the following word is not a money word or another number (here "one" functions like "a / a certain"):

Trigger words that keep "one": **and, but, or, so, yet, nor, if, when, while, because, although, though, since, unless, after, before, until, as, once, whereas, whether, the, a, an, another, no, every, any, each, that, this, which, such, well, now, look, okay.**

- "so one thing I want you to know" → "so one thing…" (kept)
- "one of the biggest mistakes" → "one of…" (kept — no preceding word)
- "and one day it clicked" → "and one day…" (kept)
- **"another one" → "another one"** and **"no one" → "no one"** (never "another 1" / "no 1").

**Dictionary-locked phrase:** "one shot" is always kept as "one shot".

> "one" IS converted to "1" if the next word is a money word (dollars, grand, etc.) or a number — those signal a real quantity.

---

## Rule 4b: Ordinals

**"third" and above always convert to ordinal numerals**, regardless of what follows:
- third → 3rd, fourth → 4th, fifth → 5th, … tenth → 10th, eleventh → 11th, … twentieth → 20th, thirtieth → 30th, … hundredth → 100th.
- "the third time" → "the 3rd time", "I came in fourth" → "I came in 4th".

**"first" and "second" stay as words by default** — avoids overlap with the time unit ("a second", "thirty seconds") and idioms ("second nature", "first of all", "at first").

**Exception:** when "first"/"second" is directly followed by an **ordinal-signaling noun**, convert to "1st"/"2nd":
- "the second thing" → "the 2nd thing" · "second option" → "2nd option" · "first step" → "1st step".

**Ordinal-signaling nouns:** thing(s), option(s), step(s), reason(s), point(s), way(s), place, time, lesson(s), rule(s), principle(s), mistake(s), tip(s), day, week, month, year, quarter, round, attempt(s), choice, version, draft, chapter, phase, stage, half, part, example, priority, pick, question, idea, level.

---

## Rule 5: Listicle & Sequence Labels

### Listicle ("number N" → "#N")

Whenever "number" directly precedes a numeral, convert to "#N" (regardless of the preceding word). Runs after Rule 3.
- "number two" → "#2" · "number one" → "#1" · "law number 1" → "law #1" · "rule number 2" → "rule #2" · "week number one" → "week #1".

### Sequence labels

When a label word is directly followed by a numeral, format the sequence item.

**Use "#N" (hash)** after these list-item words: **thing, step, tip, rule, law, point, reason, principle, habit, mistake, tactic, strategy, lesson, factor, secret, key, part, phase, level, option, pillar, trait, example, chapter, myth, hack, takeaway.** Applies to spoken-word AND digit forms — the noun stays, only the numeral gets "#".
- "step one" → "step #1" · "step 1" → "step #1" · "tip three" → "tip #3" · "thing two" → "thing #2".

**Use plain "N" (no hash)** after these time/stage words: **day, week, month, round, level, season.**
- "day one" → "day 1" · "week one" → "week 1" · "round two" → "round 2".

(If the speaker literally says "week number one", the listicle rule wins → "week #1".)

---

## Rule 6: Money Formatting

### Threshold Table

| Spoken amount | Output | Example |
|---|---|---|
| zero dollars | $0 | "zero dollars" → $0 |
| $1 – $999 | $N | "five hundred dollars" → $500 |
| $1,000 – $1,999 | $N,000 (comma form) | "a thousand dollars" → $1,000 |
| $2,000 – $999,999 | $NK | "ten thousand dollars" → $10K, "$100,000" → $100K |
| $1M – $999.9M | $NM | "two million dollars" → $2M |
| $1B – $999.9B | $N billion | "one billion dollars" → $1 billion |
| $1T – $999.9T | $N trillion | "one trillion dollars" → $1 trillion |

"billion"/"trillion" are full **lowercase** words with a space ("$1 billion", "$2 trillion"). "M" and "K" are single capital letters, no space ("$2M", "$50K").

**Surface form is irrelevant.** The money rules apply identically whether the amount arrives as comma-grouped digits ("300,000"), bare digits ("300000"), or number words ("three hundred thousand") — all become **$300K** in money context. An **already-"$" literal** is normalized too: a whole-dollar amount is re-formatted to the table ("$100,000" → $100K, "$2,000" → $2K, "$1,000,000" → $1M; "$1,500" stays in the comma band). Amounts with real cents ("$19.99") and values already in K/M form are left as-is.

### The $1,000–$1,999 comma band

Only this narrow band keeps the **$N,000** comma form. Everything from **$2,000 upward** uses **$NK** (then $NM, billion, trillion), regardless of how it was spoken.
- "a thousand dollars" / "one thousand dollars" → $1,000
- "fifteen hundred dollars" → $1,500
- "two thousand dollars" → $2K · "ten thousand dollars" → $10K

### "Grand" = $1,000

Multiply the number before "grand" by $1,000, then apply the threshold table.

| Spoken | Output |
|---|---|
| "a grand" / "one grand" | $1,000 |
| "5 grand" / "five grand" | $5K |
| "100 grand" / "a hundred grand" | $100K |
| "500 grand" / "five hundred grand" | $500K |

**ONLY when "grand" is the money word** (standalone / ends the amount). If a NOUN follows "grand", it's an adjective — leave it as the word: "a grand opening" (NOT "a $1,000 opening"), "a grand slam offer", "a grand total", "a grand vision/plan/prize/scheme". Convert where nothing or a non-noun follows: "made a grand" → "made $1,000", "a grand a month" → "$1,000 a month", "a grand in revenue" → "$1,000 in revenue".

### "Bucks" = colloquial dollars

Treated like "dollars": **delete it right after a money amount**, keep it otherwise.
- "$1M bucks" → "$1M" · "20 bucks" → "$20".
- Leave it when NOT after a money number: "a couple bucks" stays "a couple bucks".

### Bare K / M numbers are money

A number already written with a **K or M suffix** ("250K", "10K", "2.5M") reads as money → prepend "$": "250K" → **$250K**, "2.5M" → **$2.5M**. **Guard:** if a counting noun follows (followers, subscribers, views, downloads, people, years, steps, units…), it's a quantity — leave it: "100K followers" stays "100K followers".

### "$N" + scale word

When a dollar sign lands on a number followed by a stranded scale word, recombine into one money token.
- "$100 million" → $100M · "$5 thousand" → $5,000 · "$2 billion" → $2 billion.

### Implied Money Context

A number can be money even when "dollars"/"$" isn't spoken. Four ways it qualifies — checked in order:

**1. Rate phrase (highest priority).** A number directly followed by "a"/"an" + a rate unit (hour, day, week, month, quarter, year) is money. The leading "a" (= "one") is dropped.
- "a million a month" → "$1M a month" · "two hundred thousand a week" → "$200K a week".

**2. Counting-noun guard (blocks money).** A number directly followed by a counting noun is a quantity, NOT money. Counting nouns: year(s), month(s), week(s), day(s), hour(s), minute(s), point(s), people, person, customer(s), client(s), editor(s), employee(s), rep(s), user(s), member(s).
- "the past five years" → "the past 5 years" · "two points, three points" → "2 points, 3 points" · "five people" → "5 people".

**3. Very large numbers.** Anything that resolves to **$1 million or more** is money, no trigger needed.
- "two million" → "$2M" · "200 million or 500 million" → "$200M or $500M".
- (The counting-noun guard still wins: "two million people" stays "2,000,000 people".)

**4. Reliable trigger words.** A number in close proximity (≈8 words before / 3 words after, including across a sentence boundary) to any of these is money: money, cash, cashflow, revenue, profit, EBITDA, pricing, price, cost, salary, fee, charge (charging/charged), budget, expense, income, earnings, wage, raise, rate.
- "we did 44 million in revenue" → "we did $44M in revenue" · "how much do you charge?" / "a thousand" → "$1,000".

**"margin" is NOT a reliable trigger** — numbers near "margin" are usually percentages. Let the % rule handle them; don't money-format just because "margin" is nearby.

**Context-neutral words — not triggers on their own:** deal, sale, sales, payment, invoice, quote, bonus. Only money-format a number near these if an explicit money indicator is already present ("$", "dollar/dollars", or a reliable trigger).
- "a 100 dollar deal" → "$100 deal" · "50 sales" → stays "50 sales" · "one deal" → stays "1 deal".

**Year guard:** a bare 4-digit number that looks like a year (1900–2099) spoken as digits is NOT money-formatted, even next to a trigger. "in 2024 our revenue grew" → stays. Amounts spoken as words ("two thousand") are exempt from this guard.

**When ambiguous, do not money-format.** Bare single/double-digit numbers that are only *implicitly* money from broader conversation ("we went from 5 to 44" meaning $5M to $44M) are left as plain numbers for manual review.

---

## Rule 7: Symbol & Multiplier Rule

Convert trailing unit words to symbols when they directly follow a number.

| Word | Symbol | Placement | Example |
|---|---|---|---|
| dollar / dollars | $ | before the number | "fifty dollars" → $50 |
| percent / percentage | % | after the number | "fifty percent" → 50% |
| times | X | after (no space) | "five times" → 5X |
| plus | + | after (no space) | "1 plus" → 1+ |

- "thirty percent growth" → "30% growth" · "ten times bigger" → "10X bigger" · "100 times" → "100X".
- **"plus" → "+" ONLY directly after a number/money/percent token** ("$5M plus" → "$5M+", "50% plus" → "50%+"). Otherwise it stays the word: "a plus player".

**Normalize the "x" multiplier to capital "X":** "10x" → "10X", "10x'ing" → "10X'ing", "2xing" → "2Xing".

**Multiplier words → "NX":** "double" → 2X, "triple" → 3X, "quadruple" → 4X.
- "double revenue" → "2X revenue" · "triple your output" → "3X your output".

**Percentage range:** when a bare number is joined by "to"/"through" to a number that already carries "%", the leading number takes "%" too.
- "10 to 20%" → "10% to 20%" · "ten to twenty percent" → "10% to 20%".
- (A non-percentage range is untouched: "5 to 10 people" stays.)

**Do not convert** when the unit word has no specific number directly before it: "a lot of dollars" stays; "what percentage did you get" stays; "many times over" stays.

Runs after Rule 6 — don't reprocess an already-formatted money amount here.

---

## Rule 8: Large Non-Money Numbers

A number ≥ 1,000 that is NOT money still follows the **same scale structure as the money table — without the "$"**. Surface form is irrelevant; a large non-money number is **always** "300K", never "300,000".

| Value range | Format | Example |
|---|---|---|
| 1,000 – 1,999 | comma form | "one thousand" → 1,000 |
| 2,000 – 999,999 | NK | "fifty thousand" → 50K, "five hundred thousand" → 500K |
| 1,000,000 – 999.9M | NM | "two million people" → 2M people |
| 1 billion+ | N billion / N trillion | "two billion" → 2 billion |

- "fifty thousand subscribers" → "50K subscribers"
- "300,000 customers" / "three hundred thousand customers" → "300K customers"
- "two million people" → "2M people"

**Year exception:** a bare 4-digit digit token in **1900–2099** reads as a year and is **left untouched** ("back in 2024 we launched" → no change). Applies only to that narrow range — a 5–6 digit value like "300,000" is never a year, so it always abbreviates.

---

## Rule 9: Common Words Dictionary

The dictionary is the **source of truth** — it overrides every other rule. Once a term matches, its output is final.

**Special phrases:**
- "one on one" → 1-on-1
- "one shot" → one shot (locks "one" as a word)
- "going to be" → gonna be
- "want to be" → wanna be

> Casual contractions apply ONLY before the verb "be". Do not generalize "going to" → "gonna" or "want to" → "wanna" elsewhere — "going to the gym" must stay "going to the gym".

**Single-word swaps (house spelling):**
- "versus" → vs
- "'cause" → cus' (contraction of "because"; leading straight or curly apostrophe). A bare "cause"/"because" is left alone.
- "mm" → mmh (backchannel; only the standalone token "mm").
- "mm-hmm" → mhm — and the whole m-h-m affirmative family (mmhmm, mhmm, mm-hm…; pattern m+ h+ m+, hyphen ignored). Does NOT touch "mmh" (no trailing m) or "mm", and never touches "hmm" (starts with h).

**Names and brands:**
- Alex Hormozi
- Leila Hormozi — **"Layla" is an ASR misspelling → correct to "Leila".**
- Sharran Srivatsaa
- Steve Jobs
- Gym Launch
- Acquisition.com
- **Skool** (the community platform). The brand spelling always capitalizes. The homophone **"school" → "Skool"** too — EXCEPT in an education context: skip when preceded by an education modifier (high, business, grad, law, med, middle, elementary, trade, public/private, old, Sunday…) or followed by an education noun (district, year, teacher, bus, project, kids…). So "high school" / "business school" / "school district" stay lowercase; bare "go to school" → "Skool".

**Places & languages** (curated lists; capitalize — see Rule 1): US states, major cities, countries/continents, and languages/nationalities. Common-English collisions (polish, turkey, nice, mobile) are intentionally excluded.

> **Exact-sequence rule for multi-word names whose parts are common words.** Capitalize only when the full sequence appears. "Gym Launch" and "Steve Jobs" each contain an everyday word, so those words stay lowercase on their own:
> - "gym launch" → "Gym Launch", but "going to the gym" → "gym", and "we launch tomorrow" → "launch".
> - "steve jobs" → "Steve Jobs", but "he created jobs" → "jobs".
>
> Single-word names that are never common words (Alex, Hormozi, Leila, Sharran, Srivatsaa) are still capitalized on their own.

**Acronyms and abbreviations.** Two mechanisms:
(a) any token **already in ALL-CAPS** (2+ letters, optional plural/possessive "s") is preserved as-is — AC, VIP, VIPs, CEO's, TV, DM, USA (this prevents sentence-start lowercasing from turning "AC" → "aC");
(b) the curated list below is matched **case-insensitively** so a lowercase spelling is fixed too — "qr" → "QR", "roi" → "ROI":
AI · ROI · CAC · LTV · EBITDA · KPI / KPIs · CTA / CTAs · B2B · B2C · QR · CEO · CFO.

---

# PART 2 — SUBTITLE SEGMENTATION

How to GROUP the formatted words into single-line caption cues. Runs AFTER all Part 1 formatting.

**Inputs assumed:** word-level timestamps from the transcription tool (trusted as-is — timing is not adjusted) and, critically, **speaker labels (diarization)**.

## S1: Hard constraints

- **One line per cue.**
- **2–3 words per cue** target; **4 visible words maximum**. Historical six-word examples are not permission for dense cards.
- **Width: ~13–14 characters median, ~18 soft cadence cap, HARD MAX 25 characters** (incl. quote marks) — the caption safe-zone width. A cue wider than 25 chars overflows / wraps to 2 lines, which is not allowed. Break *before* a word that would exceed 25. Stay well under in general.
- **5-frame minimum (~208ms @24fps) — ABSOLUTE.** No cue is ever shorter than 5 frames. Guaranteed by a **sequential timing layout**: walking cues in order, `start = max(this cue's first-word start, previous cue's end)` and `end = max(start + 5 frames, next cue's start)`. So every cue is ≥5 frames and no two cues overlap — and nothing is dropped to achieve it: a crammed cue just **pushes** the following cues a few frames later, self-correcting at the next pause. (Compute the floor at ~210ms so whole-ms rounding can't dip below 5 frames.)
- **No overlap / no co-display (HARD):** two cues never overlap in time; a cue's out-time never exceeds the next cue's in-time. Two speakers must never be on screen simultaneously.
- **Never end a cue on a determiner/article** (a, an, the, and possessives my/your/his/her/its/our/their). A determiner always needs its noun — keep it with the following word (break before it).
- **Never start a cue with a short object pronoun** (me, him, her, us, them) — it left-attaches to the verb in the previous cue ("what's stopping" | "me" → "what's stopping me"). Deliberately conservative: NOT it / that / this / you, which double as clause-starting subjects and would mis-merge. Only merge when the result still fits ≤25 chars.
- **Never end a cue on a negated auxiliary / semi-modal** (didn't, don't, can't, won't, wanna, gonna, gotta…) — it needs the verb that follows, so push it to the next cue ("didn't" | "wanna do…" → "didn't wanna" | …). Only merge when it fits ≤25 chars.
- **Dense-cue reading bump:** reading comfort is **characters per unit time**, not chars or duration alone. A cue shown at **>2.0 visible characters per frame** (≈48 chars/sec — too fast to read) gets **+1 frame** of screen time (the next cue is pushed one frame; still no overlap). One-frame cap; fires on only the densest ~1% of cues.
- **Maximum cue duration ~2 seconds.**
- **Timing model:** in/out times come from the sequential layout above. Net behavior is **gapless** — the prior caption holds through a pause rather than flickering a blank. **No automatic on-screen blanks** (auto-blanks produce "random" mid-sentence gaps; real gaps are added by hand). A post-pause word still appears only when spoken, because the pause forced a *break* and the layout never starts a cue before its word.
- **Merged-token timing:** when formatting merges words ("27 million" → "$27M"), the merged caption spans the FULL time of all merged words so it doesn't vanish mid-word.
- **Prefer shorter cues.** 25 chars is a ceiling, not a target — given a choice, break shorter.
- **Respect the timing:** a word is never shown before it is spoken. A pause before a word pushes it to the next cue, starting at its own in-time.

## S2: Where to break (priority order)

These rules are a **syntactic proxy for what is really a semantic decision.** A human editor segments by the meaning and natural flow of the sentence. A deterministic tool leans on the parts of that flow it can see — speaker turns, sentence/clause/comma boundaries, conjunctions — plus timing signals and a length cap. The residual gap is genuine meaning-based judgment (best closed with an LLM-in-the-loop pass that reads the sentence like the editor does).

1. **At every speaker change — ALWAYS (non-negotiable).** A cue never contains two speakers. If a second speaker interrupts mid-sentence, their words get their OWN cue. Two cues also never overlap in time — two speakers never on screen at once (a cue's out-time is capped at the next cue's start).
   - **KEEP interjections — show them.** A second speaker's interjection gets its own cue and is shown (laid out sequentially; if crammed it's pushed a few frames, not dropped). The **ONLY** time an interjected word is dropped: a lone word from the other speaker that **STARTS at ~the same instant** as the original speaker's word (true talk-over, within ~100ms / ~2–3 frames) — then prioritize the speaker already talking. Do NOT drop merely because an interjection is short or the speaker resumes soon after.
2. **At sentence-final punctuation** (. ? !).
3. **At a timing boundary — two signals, high priority.** Break after a word when EITHER:
   - **(a) Silence** — the gap to the next word (`next.start − this.end`) is **≥250ms** (a real pause), OR
   - **(b) Onset / phrase-final lengthening** — the onset interval (`next.start − this.start` = the word's own spoken length + the silence after it) is **≥400ms absolute**, OR **≥1.6× the LOCAL average onset** (rate-adaptive — catches boundaries in fast passages where 400ms is never reached). Speakers stretch the last word before a boundary, so a long-then-gap word marks a break even when bare silence is short.

   Either way the word before the boundary ends its cue; the next word starts a fresh cue at its own in-time. **Filler caveat:** ignore the onset signal right after a dropped filler — that gap was the filler, not a lengthened word.

   *Why timing can't do more:* in fast content, ~95% of word-to-word silences are <200ms (continuous speech), and at the editor's break points the silence is the SAME as mid-phrase — so most breaks have NO acoustic cue and must be decided by meaning. The signal lives in word *lengths* (start-to-start), not the gaps. Pushing timing harder (e.g. splitting at the largest gap) slices phrases like "real estate" because gaps are uniform. Onset is as far as timing legitimately goes.
4. **At commas WITH a small gap (≥~80ms)** once the cue has ≥2 words. A comma placed with **no** gap after it (≤~80ms) is a **disfluency comma** (e.g. around a discourse "like", or "a, uh,") — do NOT break there; it would slice a phrase.
5. **Cadence cap — PACE-ADAPTIVE (primary rhythm-setter).** Target cue length scales with the speaker's **local speaking rate** (avg ms/word around the cue): **fast speech → MORE words/cue, slow speech → FEWER.** Tiers:
   - **slow** (onset ≥440ms) → ~2 words / ~13 chars
   - **medium** (≥250ms) → ~3 words / ~17 chars
   - **fast** (<250ms) → ~4 words / up to the 25-char safe-zone

   When the cap is reached, break there UNLESS **(a)** it would split a **glued unit** — number/money + its noun ("2 things", "$100K revenue"), verb + object pronoun ("stopping me"), neg-aux/semi-modal + verb ("didn't wanna"), or determiner + noun — defer one word; or **(b)** a clean seam is reachable within the defer budget.

   **Why pace-adaptive:** too few words at a fast pace is hard to read; too many at a slow pace reveals upcoming words and kills anticipation.

   **Also: eliminate 1-word cues** — never strand a single word unless a sentence end or a clear above-average pause justifies it.
6. **Chunk-aligned seam targets.** Land the break just **before a conjunction/preposition** (and, but, so, or, because, on, in, to, with, from, about, of, for, at, into) that starts the next chunk, **before a determiner/possessive** (a, an, the, my/your/his/her/its/our/their) that starts a new noun chunk (the mirror of "never break AFTER a determiner" — so "I'm growing | a business", not "I'm growing a | business"), or right after a comma / sentence end.
   - **EXCEPTION — don't strand a connector a pause will end:** if that connector is itself immediately followed by a pause (≥250ms), it belongs to the *current* phrase — keep it and let the pause break after it (e.g. "turn … machine on" + pause → keep "on" with "machine").

   *Ceiling note:* seam-targeting only fixes seams the rules can see. It won't keep every collocation intact ("kind of", "a lot of") nor always strand/keep a determiner the way a human would — those are true semantic calls (→ LLM-in-the-loop, not more thresholds).

## S3: Keep atomic (never split across a cue boundary)

- **Money amounts** ($500K, $2.7M, $1,000) and **number + unit** (2,000 sq ft, 72 hours, 30 days, 100 carts, 3,000 subscribers). **Number/quantity + time-unit is merged atomically:** 6 months, 10 years, a year, a month, 3 weeks, 5 days (units: second/minute/hour/day/week/month/year/decade/quarter, singular & plural; quantity = a digit, a "$"-amount, or a/an).
- **Listicle / ordinals** (#1, 2nd place).
- **A short determiner/article + its noun** (the wholesale end).
- **Common collocations / idioms — fixed multi-word units that mean one thing.** word of mouth, Facebook ads, social media, real estate, cash flow, rule of thumb, supply and demand, return on investment, etc. These stay in ONE cue; if they don't fit, break before/after the whole phrase, never inside it. This is a curated, freely-extensible list.
  - **Common short chunks that also stay whole:** a lot of, kind of, sort of, a couple of, a little bit, a little, you know, I mean, I don't know, a year, a month, be able to, business model(s), make sure, less money, more money, all of a sudden.
  - *Caution:* very frequent short discourse chunks (i think, you have, and then, do you) were deliberately NOT added — they only look "always together" because cues are ~3 words; forcing them atomic would block good breaks. The deeper lesson: the editor's cohesion is grammatical chunking, not a fixed idiom set. This list is a cheap floor; an LLM pass is the general solution.
- **Money phrases stay whole (glue, never split):**
  - **Money + rate:** $1M a year, $2K a month, $100K a day, $200 an hour (money amount + a/an + time-unit).
  - **Money + identifier:** $1M in revenue, $5M in profit, $5K LTV (money amount + optional in/of/per + a financial identifier: revenue, profit, sales, income, LTV, ARR, MRR, CAC, EBITDA, margin…).
  - (A real pause still wins — timing is respected.)

## S4: Special cues

- **Interjections & backchannels** get their own short cue: sweet!, amazing!, okay, yeah/yea, mmh, mhm, well.. .
- **Filler words are DROPPED entirely** — matched by the families u+h+ (uh, uhh…), u+m+ (um, umm…), u+h+m+ (uhm, uhmm…), and e+r+m* (er, err, erm…), i.e. any length of repeat. This is the ONLY filler class removed — oh, ah, ooh and discourse markers (like, you know, I mean) are LEFT AS-IS. **Exception:** a filler carrying a double-quote ("uh") is quoted dialogue → kept. When a filler is dropped, absorb its spoken time into the previous word (so the gap isn't read as a pause) and clear a comma setting it off. (Do NOT drop mm / mmh / mhm / hmm — those are kept backchannels.)
- **Quoted / hypothetical dialogue:** break **FINER than normal speech — ~1–2 words per cue** — each quoted fragment its own cue, wrapped in quotes (and italicized as styling).
- **Enumerations of numbers/money** break **per item** ($10M / $15M / $20M each its own cue; $3M or / $4M to $5M), not bundled into a ~3-word cue.
- **Repeated-word stutters are removed.** Collapse an immediate exact-duplicate word: "the the best way" → "the best way", "so that's that's how" → "so that's how" (keep the earlier token's start, absorb the later one's end/punctuation).
- **Repeated-PHRASE false-starts are removed.** An immediately-repeated 2–4-word group (same speaker) drops its FIRST copy: "depends how, depends how this" → "depends how this"; "I think, I think if you sold" → "I think if you sold". **Guards:** a 3rd repeat = emphasis → keep; a sentence end (. ? !) closing the first copy = rhetorical "X. X is…" → keep.
  - **EXCEPTION — "is is"** is a valid extraposition ("the thing is, is that…") — NOT collapsed. Instead the segmenter **never shows two identical words in one cue**, so it splits: "the thing is" | "is that". (General rule: any identical adjacent pair that survives de-dup is split across cues.)
- **Emphasis-repeat keep-list.** A single word repeated for emphasis is NOT collapsed like a stutter when it's a common emphasis word: very, really, yes, yeah, yep, no, nope, right, exactly, never, ever, always, stop, wait, totally, definitely. (Distinguishes "right, right, right" emphasis from "the the the" function-word stutter.)
- **Non-verbal actions** (*inhales*) get their own cue — manual annotation.
- **Punctuation conventions:** trailing-off / mid-thought pause → ".."; keep ? and !. **Dangling trailing dashes are STRIPPED** ("short-" → "short", "you make-" → "you make", "i-" → "I", "so-" → "so"). Internal hyphens in compounds are kept ("short-term", "well-being").

## S6: Quotation marks (honor the transcription, re-wrap per cue)

The transcription reliably marks reported/hypothetical speech with quotation marks — a word opens the quote with " and a later word closes it. **Honor that detection, but reformat so every cue inside the quoted span carries its OWN open + close curly quotes:**

- Detect the span from the straight " marks (opening = leading ", closing = trailing "). Strip the straight marks.
- Wrap the quoted portion of **each** cue in the span: an opening curly quote before the first quoted word, a closing curly quote after the last. A multi-cue quote shows marks on every cue.
- The opening cue may keep its lead-in outside the quote (it's like "you know what").
- **Per-speaker only:** if the other speaker interjects mid-quote, their cues are NOT quoted — the span belongs to the speaker who opened it; skip the interrupter and resume marking when the owner continues.
- **Only honor what the transcription marked.** If it didn't add quotes, do not invent them — those are manual editor judgment and stay out of scope.

## S5: Dependencies & manual pass

- **Speaker diarization is required** and drives both the speaker-turn breaks AND the coloring. The cue font color = the diarized speaker: **the guest = yellow (#FED90F), the host = plain/white.** **Color assignment is by ROLE, not speaker index:** the guest (yellow) is whoever pitches their business ("I sell… / we do $X"); the host asks/advises. Don't assume the first speaker is the guest — identify the guest by the opening business pitch.
- **Missed words:** transcription captures nearly everything, but a couple of short backchannels can slip; the tool cannot segment words it never received — expect a light manual add.
- **Editorial annotations** are hand-added and not auto-generatable: *inhales*, bracketed clarifications (the store), and profanity censoring (f*ck). Quotes the editor adds where the transcription didn't mark them remain manual.

---

## Known Gaps (still handled manually / pending)

1. **Spoken variations for acronyms** — "B to B" → B2B, "return on investment" → ROI, "artificial intelligence" → AI, etc. are pending a reviewed variations list.
2. **Additive & decimal compound numbers** — multiplicative compounds ("fifty thousand") are handled; additive ("twenty-five thousand" = 25,000) and decimal ("2.3 million") are not yet combined. Compound spoken ordinals ("twenty-first" → 21st) likewise not yet combined.
3. **Contextual millions on bare digits** — implicitly-large money from earlier context ("we went from 5 to 44" meaning $5M to $44M) is left as plain numbers for manual review.
4. **STT name misspellings** — phonetic misspellings of proper names (especially Sharran Srivatsaa and Leila Hormozi) are not yet fully mapped.
5. **A long incomplete word** (e.g. "necessa-") isn't caught by the 1–2-letter fragment rule and would pass through as "necessa" — would need a dictionary entry.

---

*This spec covers text formatting and segmentation only. Word-level highlight styling (which key words pop in a different color/weight) and cue placement/animation are handled downstream and are not part of these rules.*
