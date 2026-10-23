# Long-form → short-form CLIP patterns (data-backed, updated 2026-06-14)

> **Source:** 602 finished Instagram-reel CLIPS matched back to their raw long-form source
> (the speaker's own long-form channel — the true raw→clip population), via transcript→
> transcript diffing of what editors KEEP / CUT / RELOCATE. Q&A and hotline are EXCLUDED
> (different craft → `qa_clip_patterns.md`). Supersedes the earlier 8-clip version.
>
> **How to read LIFT:** lift = (top-quartile-by-views rate within a category) ÷ 0.25 base.
> **lift > 1 = a real performance edge · lift ≈ 1 = neutral (common but not a lever) · lift < 1 = drag.**
>
> ⚠️ **These are PRIORS + a candidate-ranking + a taste-checklist — NOT a deterministic picker.**
> A 5-lens adversarial panel showed held-out prediction barely beats the modal baseline: the
> corpus tells you the DISTRIBUTION of winning moves, not the exact cut for one clip. Judgment
> still picks; the audit gates (mozi-sf-audit · scorecard-audit · audit-script) enforce the bar.
> The matcher only catches near-verbatim edits, so structure *prevalence* skews light-edit
> (the LIFT numbers are computed within the matched set and are directionally sound).
> Full provenance + caveats: `content-skill-system/clip-intel/source_match/PROVENANCE.md`.

---

## 1. OPENS — what earns the scroll-stop  (open_type lift)

| Open | Lift | n | Use |
|---|---|---|---|
| **Cut to the payoff** | **1.68** | 19 | Skip the setup, open ON the punch itself. The single best open. |
| **Extreme number** | **1.43** | 64 | Lead with the striking quantity/stat ("a 97% renewal rate"). |
| **Keep the clean source open** | **1.43** | 39 | If the source already opens cold on the thesis, KEEP it — don't reach past a clean open. |
| **Direct address** | **1.28** | 75 | Name the viewer's situation ("if you have less than $100K in savings…"). |
| bold_claim | 0.96 | 195 | **NEUTRAL.** The most common open, but no edge *alone* — pair the claim with a number/stakes/vehicle. |
| anecdote | 0.97 | 119 | **NEUTRAL.** Fine, not an edge by itself. |
| **Question** | **0.18** | 45 | 🛑 **AVOID — the strongest negative signal.** Convert a question hook into the claim it implies. |
| vague / other | 0.12 | 32 | 🛑 AVOID. |

> **Myth corrected:** "open on a bold claim / personal anecdote" was base-rate, not performance.
> The edge is to **open on the PUNCH (cut-to-payoff), a NUMBER, or the VIEWER'S SITUATION — and
> never on a question.** (The question result matches the known clip-intel "question ≈0.48× AVOID".)

**Relocate vs keep:** welding the best buried line to the front (structure = weld_reorder) wins
(lift 1.33). But a clean *existing* open also wins (1.43) — **don't reach past a clean open just
to reorder.** Always strip preamble/throat-clear before the hook either way.

---

## 2. EXITS — end on the peak, never on a truncation  (exit_type lift)

| Exit | Lift | n | Use |
|---|---|---|---|
| **Punchline / emotional peak** | **1.61** | 67 | The #1 exit edge. End on max energy / the landing line. |
| **Complete punchy sentence** | **1.39** | 23 | A clean, *complete* strong line — completeness is fine, see below. |
| **Imperative button** | **1.33** | 75 | A short command that resolves the arc ("Do what you want."). |
| principle / aphorism | 0.89 | 346 | **NEUTRAL-DRAG.** 57% of clips end here, but it is NOT an edge — don't optimize to land on a tidy maxim. |
| **Cut before the explanation** | **0.35** | 46 | 🛑 **WORST exit.** Ending right before "the reason that works is…" as a cliffhanger HURTS. |

> **Myth corrected (important):** the old rule "cut BEFORE the explanation = exit signal" is the
> **worst-performing exit (0.35).** Disambiguate the two senses of "cut the why":
> - ✅ **Interior:** cut the abstract justification *between* concrete beats (keep the vehicle, cut the lecture).
> - 🛑 **Exit:** do NOT *end* on the truncation-before-the-why. End ON the peak or a complete punchy line.
>
> Mid-word cliffhanger exits (`trails_off`) are weak/low-n (n=7, lift 1.14) — not the broad win
> the 8-clip sample implied. A **complete** strong beat (1.39) beats a trail-off. End on the peak.

---

## 3. STRUCTURE — find/weld ONE clean arc; don't Frankenstein-trim  (structure lift)

| Structure | Lift | n | What it is |
|---|---|---|---|
| **Front-trim** | **1.48** | 27 | Cut ONLY the preamble before the hook; ship the rest. Best when the take is already clean. |
| **Weld one arc to front** | **1.33** | 129 | Sprawling source → pull the single best line/arc to the front, discard the rest. |
| **Verbatim lift** | **1.16** | 141 | A tight self-contained take ships ~as-is. Over-cutting kills it. |
| **Interior-trims** | **0.72** | 301 | 🛑 The DEFAULT move (50% of clips) — and it **UNDERPERFORMS.** "Death by a thousand cuts." |

> **THE structural insight:** the winning move is to **FIND or WELD a self-contained arc, not to
> heavily interior-trim a messy passage.** If you find yourself making many interior cuts to
> rescue a chunk, you picked the wrong chunk — pick a cleaner arc or weld one.
> (`multi_topic_merge` lift 2.99 but n=4 — illustrative only.)

**MATCH SURGERY TO SOURCE** (the meta-rule — survived 5/5 verification):
- **Tight self-contained take → ship ~verbatim** (front_trim / verbatim_lift). Don't over-edit.
- **Sprawling talk → isolate / weld ONE arc, discard the rest** (weld_reorder).
- Isolate, don't dilute. Compression isn't proportional — you keep one arc, not a thinned tour.

---

## 4. WHAT TO CUT — the execution checklist  (cut taxonomy, raw→clip)

Ranked by how often editors cut it (% of clips). This is HOW you execute a structure — craft
mechanics, **not a view lever on its own** (cut-frequency is editor habit, verified):

1. **Tangents / digressions** — 53% of clips, 36% of all cut-spans. **The #1 cut.**
2. **Redundant restatement** / weaker second pass of the same point — 51%.
3. **Framework scaffolding** ("in this video I'll cover… number one… step two") — 29%.
4. **False starts / self-repairs** — 31%.
5. **Discourse markers / hedges** ("you know," "like," "I mean," tag-"right?") — 29% / 18%.
6. **Personal preamble / throat-clear** ("this'll sound lame," greetings, "where was I") — 14% / 11%.
7. **Abstract justification (the "why")** — 10%. Keep the concrete vehicle; cut the lecture around it.
8. **Weak / second example** — 14%. After a strong example, a weaker one dilutes.
9. **CTA / outro** ("link in bio," "go to <site>/roadmap," "free gift") — 6%.
10. **Name-drops** that add nothing — 6%.

Compress any multi-turn dialogue inside a story to **setup line + result line**; delete the middle.

---

## 5. KEEP — the concrete vehicle  (survived 5/5 verification)

Keep the **STORY / NUMBER / WORKED EXAMPLE / DEMO** — the specific illustration IS the value.
Cut the abstract framework labels and the justification around it. **SHOW, don't tell:** the clip
should SHOW the idea through a concrete vehicle, never EXPLAIN it abstractly.

---

## 6. PODCAST (2-person clips) — what FLIPS vs monologue  (n=158, directional)

Validated on the 158 podcast-clip pairs in the corpus (small sample → directional; let the JUDGE,
which is source-agnostic, do the primary ranking). For podcast scoring use
`config/clip_lift_podcast.json`, NOT the monologue table.

**Transfers cleanly:** end on the **PUNCHLINE-PEAK** (lift 1.97 — even stronger) · `principle` exit is
a drag (0.76) · **AVOID question opens** (0.56) · **front-trim** works (1.18) · cut tangents →
restatements first (identical taxonomy).

**FLIPS — do NOT carry the monologue rule across:**
- **OPENS:** **bold_claim WINS (1.32)**; extreme_number (0.40), anecdote (0.54), direct_address (0.93)
  are WEAKER — the reverse of monologue. Lead a podcast clip with the sharp **CLAIM**, not the number.
- **STRUCTURE:** **weld-to-front UNDERPERFORMS (0.63)**; **interior_trims is FINE (1.10) and dominant**
  (~66% of podcast clips). Don't yank a distant line to the front across a 2-person exchange — **trim
  WITHIN the dialogue.** (Monologue is the reverse: weld wins, interior-trim drags.)

---

## Anti-patterns (corrected)

1. 🛑 Don't **open on a QUESTION** (lift 0.18) — turn it into the claim it implies.
2. 🛑 Don't **end on a truncation-before-the-explanation** (lift 0.35) — end on the peak / a complete line.
3. 🛑 Don't **default to heavy interior-trimming** (lift 0.72) — find or weld a clean arc instead.
4. 🛑 Don't assume a **bold claim or anecdote carries the open** (neutral) — pair it with a number/stakes/vehicle.
5. 🛑 Don't optimize to land on a tidy **"principle"** (neutral) — land on the PEAK.
6. 🛑 Don't keep **tangents, redundant second passes, scaffolding, or the abstract "why."**

---

## Provenance & honesty
602 raw→clip pairs; lift = winrate ÷ 0.25 base. Built by transcript→transcript diff
(`source_match/match_reels.py`), labeled by a 16-agent fan-out, aggregated lift-first on the
long-form-only subset (`aggregate_longform.py` → `clip_rules_longform.json`), and stress-tested
by a 5-lens adversarial panel that caught + corrected prevalence-as-endorsement overfitting.
Low-n categories (contrarian-open n=1, multi_topic_merge n=4, principle-open n=4) are
illustrative only. These are priors — the audit gates set the final bar.
