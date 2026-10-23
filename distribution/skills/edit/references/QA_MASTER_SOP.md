# 🎬 WHAT MAKES A GOOD Q&A / HOTLINE — MASTER SOP

> **The single source of truth for the EDITORIAL cut of an Alex Hormozi Q&A short.**
> Spine = **Oliver's team SOPs** (our master editor — the authority we replicate): the *CLIPPER AI
> PROMPT*, the V1/V2 mining prompts, and the dated Alex/Oliver/Julian insight log. The **250-pair
> raw→final data analysis** QUANTIFIES Oliver (it agrees with him); where they ever differ, **Oliver
> wins.** Visual/caption/audio locks come from the *Q&A SF Visual Guide*. Every session lesson folded in.
>
> Lives in TWO places (identical): `__ACQ_SKILLS__/edit/references/QA_MASTER_SOP.md` (loads on `/edit`)
> and `__ACQ_ASSETS__/SOPs/QA_MASTER_SOP.md` (drag-and-drop into any session).
>
> **The bar:** one clean **Problem → Solution** loop that makes Alex look like THE authority on business,
> delivers value before the viewer thinks about scrolling, and a cold viewer with zero context gets it.
> Oliver's proof it's working: the 2M+ clips all share these traits.

---

## ⚡ Q&A ONE-SHOT CONTRACT — execute top-to-bottom, do not skip (this is how a cold session ships it right)
A new session handed Q&A footage MUST run these in order. Steps 4 & 5 are **ship-blockers** (a clip that
fails them does not get encoded or delivered — gate, don't warn). Perfect isn't a promise; it's what's left
after nothing broken can pass.

1. **LOAD** this file (the WHAT) + [`clipper_ai_prompt.md`](clipper_ai_prompt.md) (the cut-design prompt) +
   [`qa_worked_examples.md`](qa_worked_examples.md) (APPROVED gold cuts — pattern-match to these). All three, before cutting.
2. **DESIGN the cut.** Best path = the self-correcting designer `scripts/cut_design.py --raw <interaction.txt>`
   (generates with the CLIPPER method + worked examples, scores against the gate, and REPAIRS until it PASSES —
   this is what makes a cold session land ~89 instead of 58). Or by hand with the CLIPPER method: Contrast Hook
   (what-they-do → revenue) → find the PAYOFF (portable principle) → work BACKWARDS for the minimum reasoning
   ladder. ONE problem. Keep Alex's full WHY. (How the skill keeps improving: [`qa_improvement_loop.md`](qa_improvement_loop.md).)
3. **LENGTH** = build the complete arc. Q&A diagnostic clips run **~90–150s** (Oliver's real cuts: 68–172s,
   median ~109s). Never a sub-40s skeleton. Don't force-compress to 75s; don't pad either.
   ⚠️ **The 3 things a cold session gets wrong (cold-start validation, avg 58/100) — fix these explicitly:**
   • **DELETE the diagnostic middle once the answer lands.** Cold cuts ran ~2× Oliver by keeping Socratic
     back-and-forth after the point was made. Arc = hook → minimum WHY → answer. Extra rounds of diagnosis = cut.
   • **HUNT BACKWARD for the guest-context beat** when the winning line isn't where the topic starts — never
     open cold on Alex's rhetorical question with no guest setup (a cold viewer must know who the advice is for).
   • **Go one beat FORWARD past a tactic to the quantified result** — end on "you'll sell more than a hundred
     carts," not the label "that's lead gen." Numbers over feelings when Oliver had numbers.
4. **🔒 `qa_editorial_score.py` MUST EXIT 0** on the clip's spoken transcript. (Blocks plain/revenue-first
   hooks, tactic/wind-down endings, failed portability, amputated reasoning, sub-100-word skeletons.) Fix until PASS.
5. **🔒 `qa_prebuild_audit.py` MUST EXIT 0** before the 4K encode (split-screen + dynamic guest framing +
   both-mics@1.0 + money captions + music-intro + guest-eye + payoff-extension). Fix until PASS.
6. **🔒 POST-BUILD AUDITS — MANDATORY, do not skip (these are the ship gate):** run on the rendered clip and
   FIX every flagged item before delivery — `reqc.py` (loudness/ending/mechanics), **`audit-captions`**
   (accuracy vs audio · spelling · ACRONYM casing · speaker color · timing · seam position), `audit-visual`.
   ⚠️ **audit-captions is NOT optional and must actually RUN.** On StageQA it was skipped/stalled across V1→V2→V3,
   so caption errors shipped THREE times (yellow-on-Alex, "decadere"→"decidere", "the md"→"MD", a stray "sure").
   Run it as the SKILL directly (deterministic), never rely on a parallel workflow agent that can stall.
7. **SELF-CHECK (optional, recommended):** score the cut against the nearest [`qa_calibration/`](qa_calibration/)
   case with `qa_calibration_score.py` — am I landing like Oliver? Target ≥75/100.
8. **VISUAL/AUDIO/CAPTION defaults** (§6–9 below) are baked into `qa_assembly.py` / `spice_normalize.py` (incl.
   ACRONYM uppercasing: MD/CEO/ROI/…) — don't re-derive them.
9. Deliver LOCAL; show Maddex; WAIT. Frame.io = Alex only, explicit per-file "push".

> What's GUARANTEED by the gates (can't ship wrong): hook class · payoff class · portability · one-arc ·
> substance floor · split-screen grammar · dynamic guest framing · 2-mic audio · money captions.
> What still needs JUDGMENT (the SOP guides, the corpus measures): WHICH interaction, and the exact
> hook/payoff word boundaries. The gates make the floor high; the SOP + corpus raise the ceiling.

---

## THE MODEL: "ONE-HIT," not "The Journey" (Alex + Julian, 2/11/26)
The old approach captured the "organic flow" of a conversation. Data killed it — long setups and
multi-step narratives cause drop-offs. The standard now:

| | ❌ Legacy | ✅ New Standard |
|---|---|---|
| Focus | Comprehensive storytelling | **High-speed tactical payoff** |
| Host entry | Delayed (20s+) | **Alex's first word < 5s** (15s max) |
| Arc | Multi-step problem/solution | **1 Problem → 1 Solution** |
| Length | 2:00 | **90–150s diagnostic band (see §LENGTH below — binding).** The 1-pager's "60–75s / 90s cap" was the *stated* target; Oliver's real cuts median ≈109s |

"We want **The Lesson, not The Journey.**" "There is no such thing as too long, only too boring" —
but for this format 2 minutes is a hard friction point. If a clip doesn't serve the central payoff, cut it.

---

## THE PRIORITY STACK (when rules conflict, obey in this order — CLIPPER PROMPT)
1. **Single tension → payoff arc, no loose threads.**
2. **Widely applicable** — resonates with the broadest audience of business owners, not just this guest's niche.
3. **Starts at the meat** — no preamble, no pleasantries.
4. **Clean ending** — resolves the tension, nothing trailing.
5. **Brand alignment** — Alex = authority; guest represented accurately; nothing restructured to misrepresent either.

---

## EDITING PROCESS — build in this order (CLIPPER PROMPT): HOOK → PAYOFF → TENSION

### Step 1 — THE HOOK (first ~5–15s)
- **Alex must speak/react within the first 5 seconds** (15s absolute max). If the guest's uninterrupted
  setup runs >10s, **intersperse Alex's reactions/nods** — never a long unbroken guest monologue.
- **Audible hook = the CONTRAST HOOK** (Alex's own directive, 2/14/26 — the #1 lever):
  lead with **WHAT they do**, *then* the **revenue**. The mundane-activity + big-number contrast creates
  the "wait, how do you make that much doing THAT?" → "holy shit" reaction.
  - ✅ "I sell property in the UAE and we do $6 million." · "I print stickers and I make $1.5M a year."
  - ❌ Revenue-first sounds like empty bragging: "We do $6M selling property." / a bare "$1.5M" ("I don't know why I should care").
  - **Highlight the mundane** — if the model sounds simple/boring, lean in; that contrast is the magnet.
- **HOOK FILTER — the opener must have ≥1 of these two** (else it's "Preface Bloat," the #1 cause of
  underperformance — Oliver 2/11/26):
  1. **Short preface** — drastically reduced setup before the interaction (≤15s, ideally a self-intro + the contrast number), OR
  2. **Immediate attention-grabber** — a high-impact/controversial line or punchy reaction *before* any
     context ("Well, that's a racket", "we make $10M… our profit is shit", "your kids will disappear").
- **CUT from the hook:** greetings ("hi, my name is…", Alex's "hey man, what's up") unless truly needed;
  backstory, location, pleasantries, "wealthier than me" filler — anything that isn't the core setup.
  Trim setup to 2–3 concise sentences, original wording only.
- *(Data backing: flat `plain_statement` opener = 0.23x DEATH, 49% of bottom-25; confession/vivid/contrarian
  = the wins. The contrast hook IS the cognitive-dissonance/contrarian win. Never open mid-sentence/lowercase.)*

### Step 2 — THE PAYOFF (find this SECOND, before context)
- Find the **ONE resolution** the whole clip drives toward. It must: clearly resolve the hook's tension ·
  be a **concrete statement** (not vague) · be understandable **without extra context** · and be one of:
  **actionable advice · belief-breaker · Alex's professional opinion.**
- **Payoff filter:** widely applicable (answers a question many owners have) · objectively easy to
  understand · clearly tied to the hook's problem.
- **Remove everything after the payoff lands.** Build to ONE dominant resolution; if several insights
  appear, keep only the strongest.
- **End on the portable principle, HARD** (live frame, no fade/freeze). **NEVER end on** a wind-down /
  trailing-off / guest reaction (0.06x, deadliest), a **niche tactic that only helps this one guest**
  (0.11x), a CTA/pitch (0x), or a dangling question. If the natural end is a bare tactic → **extend one
  sentence to the principle behind it.** Intertwine the takeaway into the arc; don't tack a "lesson" on at the end.

### Step 3 — THE TENSION (work BACKWARDS from the payoff)
- From the payoff, keep **only the minimum context a first-time viewer needs** for it to land.
- **Preserve the problem-solving dynamic:** Alex asks → guest gives context → Alex digs deeper → guest
  reacts → Alex lays the foundation → solution. **Keep Alex's full reasoning chain** (diagnosis + the WHY
  + the texture) — that's the substance that fills 60–75s. Don't reduce to hook+payoff bookends.
- **ONE problem only.** If Alex solves several, pick the one with the most audience value; **"kill your
  darlings"** — cut even an amazing moment if it doesn't serve the single arc. (Multi-point conversation →
  output as SEPARATE clips, never chained.)
- **Cut all side-quests, caveats, and tangents.** A 2–5s value-adding sidestep can stay; a 10–30s
  side-segment cannot. Gut-check: "WHICH specific question are we answering?"
- *(Data backing: cut host interjections 75% · tangents 59% · the competing 2nd thread 57% · redundant
  examples 54% — keep the ONE most visceral. Winner median ≈ 150 words.)*

---

## EDITING RULES (CLIPPER PROMPT — apply throughout)
- Remove filler, false starts, stutters. Tighten while keeping the speaker's natural voice.
- Merge adjacent same-speaker utterances; keep only the strongest of duplicate examples/analogies.
- **Noise/fragment rule:** an utterance that's pure crosstalk/noise/pre-chatter → cut entirely.
- **Fragment-after-trim rule:** never leave a standalone discourse marker ("So / Well / Right / Okay /
  Yeah / Mhm / Great / Alright") or a one-word fragment — remove it.
- **One solution, not multiple.** Don't smuggle a second insight in after the payoff.

## CONGRUENCE CHECK (read KEEP-lines in order, as a cold viewer — before finalizing)
- **Clean opening:** the first kept line is a complete, coherent sentence — ideally the contrast hook.
  No greetings, pre-chatter, or mid-thought start.
- **No mid-sentence starts:** if a removal makes the next kept line begin mid-sentence, extend the trim to fix it.
- **Authentic flow:** every line flows naturally into the next; no jarring jump.

## BRAND ALIGNMENT CHECK (CLIPPER PROMPT — never violate, even to tighten the arc)
- Protect the authenticity of the moment. Represent Alex's advice **parallel to his message, not
  perpendicular.** Represent the guest accurately and respectfully.
- Every cut should *increase* the odds a viewer respects Alex as a business authority and wants to
  attend ACQ workshops / do business with ACQ. If a cut would misrepresent either party → don't make it.
- **CLIENT-PULL SAFETY (Shy → Oliver, 2/16/26):** guests sign waivers (≈3 pulls in 6,000), so don't
  over-worry — BUT **stay away from specific/sensitive details**: exact price points ("my price is $X"),
  "I fired [name]", anything a client could later want hunted down. **Use revenue/profit framing only
  ("I make $X revenue / profit"); give away as little as possible.**

---

## LENGTH (binding)
- **Q&A DIAGNOSTIC clips run LONG — ~90–150s, not 60–90s.** ⚠️ The 1-pager says "60–75s target / 90s cap,"
  but that is the *stated* target; **Oliver's ACTUAL published Q&A cuts from one L1 session measured
  68 / 80 / 101 / 109 / 113 / 172s — median ≈109s** (calibration corpus cases 001–007, verified from the
  real reels). He runs long because he KEEPS the full reasoning ladder (see Step 3). So: build to the
  complete arc, expect ~90–150s, and don't force-compress a dense interaction to hit 75s. The "boredom
  threshold," not a hard 90s cap, is the real limit. (A genuinely tight interaction can still be ~70s — golf
  carts was 68s — but most land 100–120s.)
- **Never a sub-40s skeleton** — that has never shipped (the "28s" error). Hard floor ≈ 100 words.
- **Format matters:** this ~90–150s band is the Q&A DIAGNOSTIC format (guest + Alex, split-screen). It does
  NOT apply to Alex monologue / aphorism clips, which run ~30–40s — don't pad those to 100s.

## TRIAL ROLL (optional A/B — "we find out what works through testing; we don't guess")
For a significant clip, produce 3 variations: **Trial 1 Traditional** (short preface w/ contrast hook →
context → payoff) · **Trial 2 Direct Impact** (open on Alex's high-energy reaction/punchline, then context)
· **Trial 3 Cold Open** (teaser cut at peak tension — e.g. "everyone's going to think you're crazy" — do
NOT resolve it in the intro, then fast setup → payoff).

---

## VISUAL (Q&A SF Visual Guide)
- **Open on the SPLIT-SCREEN 50/50** — Alex TOP / guest BOTTOM, same proportions, **drop shadow on Alex**
  + soft seam. Then cut to the single angle of whoever's speaking; switch on the SPEAKER.
- **Guest panel = DYNAMIC TARGET framing** (`guest_split.mode=target`): face = **34% of panel height,
  centered 34% from top**, solved per-frame (X+Y tracking). NEVER a fixed zoom. (`guest_panel_render.py`.)
- **Colorgrade:** Alex bright/saturated; guest cool/blue. Hard-cut ending on a live frame.

## CAPTIONS (Q&A SF Visual Guide — exact)
- **Proxima Nova, size 80, text-box 150.** **Guest = yellow `#FECB00`/`#FED90F` Medium Italic** (highlights
  Black Italic); **Alex = white `#FFFFFF` Medium** (highlights Black). EYEBALL the color split (diarization mis-tags).
- **All lowercase** except proper nouns + "I/I'm/I'd/I've/I'll". **Money compact, symbols always**: `$100K`,
  `$3.5M`, `85%` (engine `spice_normalize.py`; `caption_lint` = 0 spelled-number errors). Single-line, no
  dead gaps, word-synced, spelling double-checked. Title card (if any): SF Pro Black, all-caps, 160px,
  white + one yellow word, dark-grey box.

## AUDIO (session-locked + the subfolder presets)
- **Both lavs (Alex + guest) at weight 1.0 the WHOLE time** — `speaker` is caption-color only; never duck
  the off-mic (reads as a mic cut). Log = "2-mic conv mix", dynamic range ≳35 dB, no `[audio][WARN]`.
- **Music: NONE on Q&A/hotline clips** (baked ruling 2026-06-22, copyright + taste; `qa_assembly`
  hard-ignores `--music`; reaffirmed 2026-08-03 — no music on >60s shorts). For the formats that
  still take a bed (≤60s monologue/listicle): per-clip vibe via the calibrated matcher; **`--music-ss`
  past any slow intro** (beat-drop ≈ clip start); bed ~10–13 dB under the −16 LUFS voice. Premiere reference presets in the SOP folder's
  `drive-download…/`: *Mozi Clean Audio*, *Mozi Music (2026)*, *Mozi Custom Reverb Fade*, *Mozi Hotline Flashback Vocal Reverb*.

## MECHANICS / PRE-RENDER GATES
- 4K `ACQ_QA_RES=2160`. Before encode: `qa_prebuild_audit.py` (boundary-tail, guest-completion,
  payoff-extension, intro=biz+problem, music profile, guest-eye) + `qa_editorial_score.py` (this SOP's
  editorial gate). `reqc.py` on the delivered file. Deliver LOCAL; Frame.io = Alex only, explicit per-file "push".

---

## PRE-FINALIZATION CHECKLIST (confirm BEFORE outputting any clip)
1. Does **Alex speak/react within 5s** (15s max)?
2. Is it a **single, clean Problem → Solution loop** (one problem, no second insight)?
3. Is runtime **in the 90–150s diagnostic band (cap ~155s; §LENGTH is binding — a genuinely tight interaction can land ~70s)** and **not a sub-40s skeleton**?
4. Does the hook use the **Contrast Hook** (activity → revenue, mundane framing — not revenue-first / not a flat line)?
5. Does it pass the **hook filter** (short preface OR attention-grabber) — no Preface Bloat?
6. **PORTABILITY:** read first line + last line cold — hook intrigues AND payoff resolves, standalone? (2.89x predictor.)
7. **Brand + client-pull safe:** Alex looks like the authority; no exact prices / "I fired xyz" / sensitive specifics?
8. Run `qa_editorial_score.py` → PASS. Then visual/caption/audio/mechanics gates.
