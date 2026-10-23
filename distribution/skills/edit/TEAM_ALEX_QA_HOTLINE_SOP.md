# Team Alex — Q&A & Hotline Shorts SOP (official, ingested 2026-06-06)

The canonical Acquisition.com rubric for selecting + editing Alex Hormozi Q&A and Hotline shorts,
distilled from the official Team Alex 1-pager docs + trainings + Alex/Julian/Oliver insights.
**This is the rubric for `tam_select` (which moment to clip) AND `tam_tighten`/`tam_tighten_short`
(how to cut it).** Source PDFs preserved in `references/team-alex-sop/`; audio presets in `presets/audio/`.

> THE EVOLUTION (2/11/26, Alex + Julian): moved OFF "organic flow / comprehensive storytelling" ONTO
> a **"One-Hit" model** — high-speed tactical payoff, host enters <15s, ONE problem → ONE solution,
> **90 seconds or less**. "There is no such thing as too long, only too boring," but 2 min is a hard
> friction point. We want **The Lesson, not The Journey.**

> **CUT MECHANICS — shared engine rules (apply to Q&A AND Hotline; 2026-06-07).** These govern HOW the cut is
> built once the moment is picked (full rationale: [`references/assembly_cut_standard.md`](references/assembly_cut_standard.md) lessons 20–29):
> 1. **Groq-accurate transcript cache before any boundary** — local `whisper-cli` timing drifts seconds over a long
>    session → cuts land on the wrong audio. Transcribe each mic/source ONCE with Groq, then SLICE.
> 2. **Multi-source (hotline caller + Alex, or multicam): EDL segments must be DISJOINT in source time** — mic bleed
>    REPLAYS any line covered by two segments. Check `scripts/qa_overlap_check.py EDL.json`; **whisper the RENDER**
>    (the recon can't hear duplications or fused/clipped edges).
> 3. **90s HARD CAP** ("90 seconds or less" above) is a gate — `qa_audit` flags >90s. Cut tangents/proof/elaboration
>    to fit, never the reasoning or the payoff. (Exception: a literal one-to-one of a published reference.)
> 4. **If Oliver already published the moment, reproduce his cut ONE-TO-ONE** (lines/order/trims) — don't improvise.
> 5. **Revisions are cheap** — reframe masters are content-addressed in `_qa_mastercache/` (track-once), so re-cut freely.

---

## 1. PICK THE MOMENT (selection — `tam_select`)
A clippable moment has all five: **clear introduction · clear problem · tension · widely applicable ·
clear payoff.** Gut-checks: *Is this too niche? Is the problem clear? Is there clear tension?*

- **Widely applicable / broad TAM is paramount** — the problem AND the solution must resonate with the
  broadest audience of business owners, not just the guest's niche. Simple, low-level topics (raise
  prices, first hire, delegate, where to advertise, find your ideal customer) > niche/expert topics.
- **Tension is what makes it take off** — a reframe, Alex challenging a belief, a line that stops the scroll.
- **Likeable guest** — viewers root for a struggle ("stuck at $500K for 3 years"), not bragging.
- **One question = one short.** If a conversation covers multiple points, output them as SEPARATE clips —
  never chain Problem A → Solution A → Problem B. Frame each as "WHICH specific question are we answering?"
- Mine **10–30 candidates** per long-form transcript; rank by TAM + tension + payoff strength.

## 2. THE HOOK (first 5–15s)
**Audible hook = the CONTRAST HOOK (money-first, but ACTIVITY → REVENUE order).** This is Alex's own
directive (2/14/26): a bare number is abstract ("I do $1.5M" → *don't care*); pairing a **mundane/specific
activity** with a massive result creates cognitive dissonance ("I print stickers and make $1.5M a year"
→ *holy shit*). 
- ✅ Lead with the **What** (industry/activity), pair the **Result** (revenue) immediately after, then the
  **problem**. *"I sell property in the UAE and we do $6 million in revenue."* / *"I own a dance school with
  800 students and we're at $2 million."*
- ❌ Never revenue-first ("We do $6M selling property" = empty bragging). **Highlight the mundane.**
- Two valid hook styles (pick ≥1): **Short Preface** (≤15s setup, e.g. dentist 12s / time-study 13s) OR
  **Immediate Attention-Grabber** (a striking number, surprising constraint, or punchy reaction —
  *"Well, that's a racket"*, *"we make $10M… our profit is shit"*, *"we've closed down for new sales"*).
- **STRIP all greetings/pleasantries** — no "Hi, my name is…", no "Hey man what's up, what can I help you
  with?" — UNLESS truly necessary. Start on the exact syllable of the business/problem.
- **The 5–15s Host-Entry rule:** Alex must speak or react within the first 5s (viral standard) / 15s (hard
  rule). If the guest's uninterrupted setup exceeds 10s, intersperse Alex's reactions/nods.
- **Cold-open / "Immediate Next Frame" rule:** you MAY open on a punchy Alex reaction, but the *immediate
  next line* MUST be the core context that sets it up — no transitions/pleasantries after the hook. Cut a
  teaser at PEAK tension (before the explanation) and don't resolve it in the intro.

## 3. TENSION (the problem-solving middle)
Pattern: **Alex asks a clarifying question → guest reveals something → Alex reacts / challenges the belief
→ Alex digs to isolate the real constraint → lays the foundation for the advice.** Keep ONLY the minimum
context the payoff needs. Cut side quests, caveats, long backstory, multiple problems. A 2–5s sidestep that
adds value can stay; a 10–30s tangent cannot. *What are we solving? Most value in the least time? Any
unnecessary context? What applies to most other businesses?*

## 4. PAYOFF (the single resolution, at the end)
ONE solution — never multiple. It must resolve the hook's tension, be concrete (not vague), and be
understandable without insider knowledge. **Payoff types:** tactical instruction (the time study) ·
capital-allocation reframe (pay in growth vs profit) · constraint diagnosis (fix supply before demand) ·
hard-truth belief-breaker (*"It's hard. It never stops being hard."*) · Alex's professional opinion. The
payoff should arrive **as early as possible** (value before they think about scrolling), and the clip ENDS
the moment it lands — **remove everything after.** Decisive, complete, nothing trailing. Kill your darlings:
an amazing line that doesn't serve the one arc gets cut.

## 5. LENGTH & PACING (official, stricter than the shipped long-tail)
- **Target 60–75s. HARD CAP 90s.** ⚠️ SUPERSEDED for Q&A/hotline DIAGNOSTIC clips (2026-08-03):
  the binding band is **90–150s, cap ~155** — QA_MASTER_SOP §LENGTH (Oliver's real published cuts
  median ≈109s; the 60–75/90 figure was the stated target, not the measured practice). The 60–75s
  band still applies to highlight-mid recuts. (Alex's first word <5s for the viral tier — unchanged.)
- WPM is high (~230); cut filler/false-starts/stutters; keep punchy; preserve voice + intensity; cut
  repetition unless it adds emphasis; keep emotional reactions when useful ("That will not grow the business.").
- **Strict chronology — DO NOT REARRANGE.** Quotes stay in the exact order spoken (you may DROP the middle to
  jump hook→payoff, but never pull a later quote to the front). Direct quotes only; no fabrication.
  ⚠️ SUPERSEDED by the cut-diff data (2026-06-14, 1,110 pairs): **EXTRACT-AND-WELD is normal and
  tier-neutral** (~30% reach-back in every tier; weld lift 1.33) — relocating the best payoff/hook line IS
  allowed when the weld is grammatically seamless and passes the cold-viewer test. See qa_clip_patterns.md
  + SKILL.md 4b (one coherent arc, no Frankenstein splices — that part of this rule still holds).

## 6. HOTLINE-SPECIFIC (the caller format — our footage)
The "live phone call" illusion is a TRAP — leaning into it tanks watch time to 12–17s. **Prioritize
information density over natural conversation.**
- **Strip ALL pleasantries** ("Hello", "How are you", "Nice to meet you", "I can't believe I'm talking to
  you"). Start on the syllable the caller states their problem, OR a high-impact Alex reaction.
- **Ruthless caller trimming — be a translator.** Don't let the caller speak at natural pace; chop pauses,
  fillers, backstory. (30s caller story → one compressed sentence: *"I run a physical business, I work 6 days
  a week, and my revenue dropped when I hired people."*)
- **Overcompensate for static visuals:** the format is just Alex + a caller-ID graphic, so auditory pacing +
  text animations move twice as fast. Tight cuts, momentum toward the solution.
- **Bridge the gaps** with fast text-on-screen so aggressive chops read as stylistic, not glitchy.

## 7. BRAND ALIGNMENT (apply throughout — a gate, not a nicety)
Before any cut: *Does it protect the authenticity of the moment? Is Alex's advice represented the way it was
intended (parallel to his message, not perpendicular)? Is the guest represented accurately? Does it increase
the odds viewers respect Alex as a business authority and want to attend workshops / do business with ACQ?
Could any cut be BAD for the brand?* If a trim would misrepresent Alex or the guest, **don't make it — even
if it tightens the arc.**
- **Sensitive-detail caution (Julian/Shy):** prefer "I make $X revenue/profit" over exact **prices**; avoid
  "I fired [name]" and other specific/sensitive identifiers — give away as little as possible so clips don't
  have to be hunted back down for client-success. (Guests sign waivers; takedowns are ~3/6000, so don't
  over-worry selection — just don't surface needlessly sensitive specifics.)

## 8. VALUE FRAMEWORK (final QC before ship)
Real solution to the guest's problem? · Problem clearly defined? · Tension/stakes established? · Enough
context for the advice to make sense? · Caveats unrelated to the problem removed? · Alex's advice clearly
stated + understandable? · Alex within 5–15s? · Single clean Problem→Solution? · Under 90s (target 60–75)?

## 9. TRIAL ROLL (optional A/B, for IG trial reels — stack in Frame.io)
3 variants per strong clip: **T1 Traditional** (preface → context → payoff) · **T2 Direct Impact** (open on
Alex's reaction/punchline, then context) · **T3 Optimized Cold Open** (teaser cut at peak tension → fast setup → payoff).

## 10. VISUAL / POLISH (Stage 2–3) — from the Visual Guide
> **Detailed companions (this session, empirical):** [`references/alex_visual_guide.md`](references/alex_visual_guide.md)
> (4 angles + framing params, reverse-engineered from 8 of Oliver's June Q&A exports) and
> [`references/audio_music_presets.md`](references/audio_music_presets.md) (the Mozi chains → exact ffmpeg recipes).
>
> **Visual hierarchy (the #1 thing to get right — verified against Oliver's real clips):** ALEX is the visual
> star, NOT the guest. The guest is mostly *heard* (yellow captions) while you HOLD on Alex listening; show the
> guest only briefly (split-screen / quick in-crowd cutaway). This is the visual expression of the "Alex within
> 5s" rule — a long full-screen tight portrait of a random guest inverts the hierarchy and reads wrong.
> Keep BOTH a close and a wide per speaker (Alex Main/Wide, Guest Main/Wide) and cut between them; Alex Wide =
> a clean 3/4 "cowboy" shot (head→mid-thigh), not full-body-tiny and not chest-up.
- **Captions: Proxima Nova, size 80, text box 150 (avoid UI cutoff), lower-mid.** Dual style:
  **GUEST/CALLER = gold italic (#FED90F or #FECB00)**, Medium-Italic default / Black-Italic highlight word.
  **ALEX = white (#FFFFFF)**, Medium default / Black highlight, NON-italic. (Matches our locked pro-caption pipeline.)
- **Reframe 9:16:** Hotline = Alex-only (headphones/desk + caller-ID). Q&A = split-screen 50/50 (Alex top,
  guest below, drop shadow on Alex's half) OR angle-switch (Alex main / guest main / wides).
- **Grade:** Alex = bright, saturated. Guest = cool/blue tones. **Upscale:** Topaz 4K, original FPS.
- **Zooms:** dynamic + emphasis punch-ins. **No title-card hooks for our cut** (another team owns title cards;
  text-on-screen *bridges* for hotline chops are different and OK).
- **Audio presets** (`presets/audio/`, Premiere/Audition — import when grading, or replicate the chain in FFmpeg):
  - **Mozi Clean Audio** = DeNoise → Parametric EQ → Hard Limiter → Volume (Alex voice cleanup). FFmpeg ≈ `afftdn` → `equalizer`/`firequalizer` → `alimiter` → 2-pass loudnorm.
  - **Mozi Preset For Music (2026)** = Parametric EQ → Stereo Expander → Volume → Reverb (music bus).
  - **Mozi Hotline – Flashback Vocal Reverb** = AUMatrixReverb for the caller's voice (the hotline "phone/flashback" character).
  - **Mozi Custom Reverb Fade** = reverb-tail fade for transitions/endings.

---
## How this maps to the tools
- `tam_select.md` enforces §1–2 (pick the moment, contrast hook, broad TAM, brand-safety).
- `tam_tighten_short.md` enforces §2–6 (contrast hook order, Alex-within-5–15s, tension→payoff, 60–75/90-cap,
  ruthless hotline trimming, strict chronology, brand alignment).
- Stage 2–3 (reframe + captions + grade + audio presets) enforces §10.
