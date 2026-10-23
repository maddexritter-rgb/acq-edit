# Caption example set — train the director on "good" vs "bad"

Oliver's suggestion (2026-06-04): *"do some subtitles, have the AI do it, make your own corrections, and feed it those results so it knows what good looks like and what bad looks like."* This file is that ledger — append approved decisions (GOOD) and flagged mistakes (BAD) as they come in. The `caption_director` should read this before styling a new clip.

## ✅ GOOD — from Oliver's own reels (2026-06-04)
**Reel DT-dF3eDpt2 (heart-surgeon close)** and **DVOj1vBDuP0 (the ham story):**
- **Color = whose voice.** Alex's own narration = WHITE. The instant he voices/quotes someone else — a character, a customer, a "here's what you say" script — it's **YELLOW + ITALIC + quotation marks**, and snaps back to white when he narrates again.
  - ham story: `"mom"` · `"the sides"` · `"of your ham cut off"` · `"Miller family tradition"` · `"but why??"` · `"sweetie"` · `"so small"` — every character line, yellow+italic+quoted.
  - heart-surgeon: the line to say → `"where you're"` `"coming from"` (yellow+quoted).
- **Quote marks on EVERY caption segment** of the span (per-cue), not just the first/last.
- **A quoted span is contiguous + UNIFORM.** From the first word to the last word of what Alex says *as someone else*, every word is yellow+italic+quoted — **function/connective words included** (the, a, that, I, to, he, had, an, until, your...). Color/italic/quote are all-or-nothing across the span; only emphasis (weight/size) varies inside it. When Alex's own narration resumes between two quotes ("and everyone will be like,"), it snaps back to white and a *new* quote opens after it.
- **Emphasis is meaning-based:** only a genuinely key word goes heavier/bold (`rule`, `business`), or a word gets italic for single-word stress (`specific`). Most words are plain white.
- Placement ~40% up from the bottom; clean single line, 2–4 words.

## ❌ BAD — flagged on the spice V2s (Oliver, 2026-06-04)
- **Auto-emphasis on the trailing word.** "It always makes the LAST word scale up + extra bold." → only emphasize meaningful words, never formulaically.
- **Music swapped to a harder/energetic track on V2.** Off-brand for Alex; changes the feel on touchy subjects → keep V1's (softer) music.
- **Captions too low** (~30% up) → raise to ~40% up.
- **Quotes clunky or missing.** Reported speech not caught, or only one quote mark across a multi-cue span → catch all spans, quote per segment.
- **PARTIAL-SPAN quote — the big one (Excuses V3, 2026-06-04, Maddex relaying Oliver).** Inside a quoted phrase the director colored only the "key" words and left the function words WHITE: `"live` ·the· `life` ·that I· `want` ·until I· `die"`, and `"oh yeah,` ·he had an· `excuse"`. WRONG — a quote is **all-or-nothing**: every word from the first to the last of the reported phrase (the, that, I, until, he, had, an) is yellow+italic+inside the quotes. *Why it matters:* this is the exact thing Oliver kept flagging; partial yellow makes it read like two half-quotes instead of one line of someone-else's speech. **Fix baked:** the director now emits reported speech as `voice_spans:[[first_idx,last_idx]]` and force-sets the whole range guest+italic+quoted, so it can't drop a function word again.
- **Whole clip set to one heavy weight** (all Extra Bold) killing the emphasis contrast — only do a heavy base as a deliberate one-off for legibility on busy clothing.

## How to use
Before styling a clip, the director reviews these. After each review round, append the new GOOD (approved) and BAD (flagged) examples here with a one-line reason.
