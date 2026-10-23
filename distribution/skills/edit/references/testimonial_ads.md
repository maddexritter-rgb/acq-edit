# Testimonial ADS — the locked SOP (paid social ads from attendee/customer interviews)

> Added 2026-06-16 after the first real testimonial-ad batch. This is a DISTINCT job type from
> Alex Q&A/listicle content clips — it has its own format, audio rules, reframe approach, and a
> hard compliance gate. Every rule below maps to a real mistake made on that batch; the **WHY**
> lines are the root cause so the mistake is not repeated. Brand-agnostic — uses the brand's own
> assets/disclaimer by path, never hardcoded here.

## When this applies
Raw footage = on-camera attendee/customer interviews (an off-camera interviewer asks; the guest
answers), destined for **paid social ads** (Facebook/Meta/IG). Often shot handheld at an event,
frames contain background people, and the "before/after" structure may be split into folders.

## 🔑 RULE 0 — STUDY THE BRAND'S EXISTING FINISHED EXAMPLES FIRST
Before cutting anything, get the previous editor's finished clips for THIS content line and study
them: length, caption treatment, disclaimer wording/placement, CTA/end-card, structure.
**WHY:** the first clip shipped at 35s with a full 4-beat arc; the brand's house style was PUNCHY
(some 15s) and ended on an end-card CTA, not the structure I invented. I burned a round because I
designed from first principles instead of matching the proven, approved style. Match first, improve second.

## FORMAT (the ad arc) — UPDATED 2026-06-17: lead with the QUESTION (context-first)
- **interviewer QUESTION → guest ANSWER → animated end-card CTA.** The CMO's strong preference
  (2026-06-17): when the guest was clearly *prompted* ("How was the workshop?", "What's the most
  painful moment?", "Tell me about your business"), **INCLUDE that off-camera question first**, then
  hard-cut to the answer — it grounds a cold viewer who otherwise hears an answer floating with no
  setup. This SUPERSEDES the original "cut all the interviewer's questions". (Only open straight on
  the answer when the guest launched in UNprompted, or the only question is a mid-sentence fragment —
  forcing a broken question reads worse; ~3 of 22 in the first batch were answer-open.)
  - The question is off-camera + roomy → **isolate it** (ElevenLabs `audio-isolation`, HTTP or MCP;
    needs ≥4.6s so pad-then-trim), **level-match to the guest** (loudnorm −16), and caption it (spice).
    Guest stays on-screen (listening) during the question. Build: `build_qa_ad.py` (question seg →
    answer seg via `build_ad` → end card), batch driver `wave_qa.py` off a `qa_spec.json`.
  - 🛑 **The question must OPEN on the question — no leading buffer (CMO rejected 67Percent for this).**
    Whisper mis-labels the question's first word EARLY (sometimes ~1–2s), so the extraction grabs
    leading pre-roll — SILENCE (67Percent shipped 1.32s of dead air) OR prior VOICED audio
    (KnockedItOut shipped 2s of garble before "How was the workshop"). A silence-only head-trim
    catches the first, NOT the second. **FIX (`build_qa_ad` head-trim, LOCKED):** transcribe the
    ISOLATED Q audio, find where the question's first word ACTUALLY starts, and trim both video+audio
    to ~60ms before it (`_question_onset`, falls back to silence-onset). Result: opens on the first
    spoken word of the question every time. VERIFY: transcribe the head with a ≥4s window (a short
    window over the music bed makes Whisper return garbage/empty — not a real defect) and confirm the
    first word lands <~0.2s in.
  - 🛑 **Question-phrase resolution gotchas:** anchor the Q to the QUESTION ITSELF, not a loose
    lead-in — "all right" / "so" / a name sitting at t≈0 (pre-roll) balloons the cut to ~15s of
    silence (SimpleSolutions). And a fast-spoken question (~1.4s) is fine but reads quick.
- Still cut ALL pre-roll logistics chatter ("hold it near your mouth"). Keep it punchy
  (question + answer ≈ 15–55s). Hard-end the answer into the card. Route around profanity + forward-
  looking earnings projections (see compliance).
- Variants the brand may want, per guest: **after-only** (result), **before-only** (their pain/why
  they came — works as a relatable-problem ad into the CTA), **before/after** (same guest, pre + post).

## 🛑 COMPLIANCE — HARD GATE (paid ads are a restricted category)
- **Burn the brand's exact results-disclaimer on EVERY clip**, e.g. (ACQ): 3 centered white no-box
  lines "Information not typical. / These are examples, not guarantees. / Results may vary." Match
  the brand's wording + placement from their existing clips.
- At SELECTION: keep specific results the guest states (that's the testimonial) but do NOT cut toward
  an implied universal guarantee, and **avoid forward-looking earnings projections** ("this will
  skyrocket us to $100M") — the disclaimer covers atypical-results, NOT guarantee/projection claims.
  **WHY:** a "$100M" clip was tempting but a projected income claim is the exact thing Meta rejects;
  dropped it. Run `anthropic-skills:testimonial-review` on each finished clip.

## 🎵 AUDIO — OWNED / LICENSED MUSIC ONLY (UPDATED 2026-06-17)
- Paid ads CAN have a music bed — but it must be **music you OWN or have a paid-ad sync license for.**
  Default = **generate an original bed** (ElevenLabs `compose_music`, owned outright = zero copyright
  risk), vibe-matched per clip. Sit it ~14 dB under the voice (bed loudnorm ≈ −30 LUFS vs voice −16),
  `aloop` to cover any length, gentle 0.4s/0.8s in/out fades, `amix …:normalize=0` → `alimiter`. A
  small library of beds (a couple variants per vibe — uplifting/confident/warm/energetic/reflective)
  assigned round-robin within vibe gives variety without a unique track per clip. End-card ding stays.
- 🛑 **NEVER use the organic `(1) Tik Tok` / trending library on a PAID ad.** **WHY:** it's commercial
  copyrighted tracks (Drake, Doja, Daft Punk… even the "(Instrumental)" ones — the composition is still
  owned). Fine for ORGANIC posts (those platforms carry a music license); on a paid Meta ad on a shared
  account it gets the ad muted/rejected + risks a claim. The original "ads = NO music" rule was the
  safe-but-blunt version of this; the real rule is **owned/licensed only** — surface the copyright risk
  if handed a commercial library and offer to generate originals or pull from a cleared stock library.
- **WHY the bed at all:** the CMO asked for music under all of them (2026-06-17). Verify the VOICE
  still transcribes clean over the bed (voice dominant) on every clip.

## 🎥 REFRAME — 2D FACE-PIN KEYFRAMING (shaky, multi-person footage)
- The footage is often already 9:16 (rotated 4K) but SHAKY, with background attendees. Goal:
  guest "completely centered, locked X and Y". **Do per-frame 2D FACE-PIN:** detect the LARGEST
  face (= foreground guest) every frame, light-smooth the path, crop so the face maps to (0.5, eye_y)
  EVERY frame → the guest is pinned and the shake is cancelled. Tool: `_shared/testimonial_reframe.py`.
- 🛑 **NEVER use vidstab here.** **WHY:** vidstab globally stabilizes and rubber-banded/"swam" the
  whole frame — ACQ called it "so fucking glitchy". A global stabilizer is the wrong tool for
  "lock the subject"; per-frame face-pinning is. (This is the house "keyframing" ACQ meant.)
- 🛑 **qa_reframe_v2 is NOT the tool for shaky multi-person footage.** **WHY:** it locked onto
  background attendees / got ~6 face hits, and its Y-LOCK assumes a STABLE camera (it can't cancel
  2D shake). Two traps: (a) multi-face frames need an explicit LARGEST-face pick; (b) the YuNet
  detector threshold is `--score`, NOT `--face-conf` (I set the wrong one and detection didn't change).
- **VERIFY by measurement:** extract CONSECUTIVE frames and confirm the guest's face holds the same
  screen position across them (the wobble is invisible in a single frame). Never trust one frame.

## ✂️ CUT — drop the trailing interviewer tag (ADAPTIVE-FLOOR ACOUSTIC PEEL, do NOT trust Whisper)
The clip must hard-end on the GUEST's last word; an off-camera interviewer tag ("Awesome / Thanks /
Perfect / Sweet / Beautiful") must be peeled. This is harder than it looks — THREE compounding bugs,
each of which defeated a naive fix on the real batch (all 2026-06-16):
1. **Whisper labels the final word with a bogus-long end** (e.g. `it.` = 133.11→135.59, a 2.48s
   "word") that swallows the pause AND the tag → `faded_trim` ends ON the tag.
2. **Whisper is non-deterministic** — on different passes it DROPS the tag word entirely, or fuses the
   pause into the prior word so the word-GAP reads ~0. Neither word-text nor word-gaps are reliable;
   a "strip trailing closer word" or gap-threshold heuristic silently no-ops on a bad pass.
3. **A fixed silencedetect floor (−30dB) can't see the pause** — at a noisy event the inter-turn pause
   is room tone ~−28dB, LOUDER than −30dB, so it is never flagged as silence.
**FIX (`build_ad.py tail_clean`, LOCKED):** measure the tail's `mean_volume` (volumedetect), set the
silence floor ADAPTIVELY to `mean+1dB`, detect pauses there, and peel SHORT (<1.2s) trailing speech
islands sitting after a real pause (the tag) + trailing dead air. The acoustic floor is
DETERMINISTIC (identical cut every run); Whisper is used ONLY as a safety VETO — transcribe the region
about to be dropped and abort if it holds ≥2 substantive guest words (so "...program for you" /
"...it was amazing" are never eaten). VERIFY by re-transcribing the delivered testimonial tail — but
Whisper may DROP the tag on the verify pass too, so trust the acoustic peel LOG line, not one ASR read.

## 🛑 OPENER — open on a CLEAN clause, never mid-phrase (CMO note 2026-06-17, A015 rejected)
The answer must OPEN on a clean clause start — same Seam-Rule-1 bar the playbook sets for every cut.
**WHY:** I gated ENDINGS but not OPENERS, so 5 of 21 in the batch opened mid-clause — A015 shipped
"…the workshop? **Then** you don't know…" (the source is "…right? But then you don't know…"), and
others opened on a dangling "if…" / mid-sentence object. **Two failure modes, two fixes:**
1. **Leading-connective BLEED** — `faded_trim` grabs the tail of the word before the span start, so a
   span starting after "But then" opens on "Then". FIX: `build_ad.py head_clean` strips a leading
   discourse-marker/CONNECTIVE (and/but/so/then/or/because/well/um/yeah…) — but 🛑 NOT content pronouns/
   articles (you/know/like/the/that): stripping a leading "You" decapitates a "You don't know…" hook.
2. **Mid-clause SELECTION** — the picked phrase itself starts mid-sentence ("if you want to come…",
   "I was above product-market-fit" = object of "what I got from today was that I…"). FIX: pick the
   start at a real clause boundary (a word preceded by a sentence-terminal / pause), or open on the
   guest's direct answer to the question.
**AUDIT openers AND endings together** before delivery — `qa_cut_audit` workflow / `ending_audit.py`
read each clip's opener + ending against the source. Don't gate only one end of the cut.

## 🛑 ENDING — land on a COMPLETE thought, then the end card (THE #1 CMO note, 2026-06-17)
CMO feedback on the first batch: *"often the AI cuts off the speaker and goes to the end bumper."* This
is the single most important defect class for testimonial ads — a clip that ends MID-SENTENCE and
slams into the end card reads as broken. **ROOT CAUSE:** `build_ad.py` builds from hand-picked
phrase-pairs and (unlike the Q&A spine) did NOT run a payoff/boundary gate — so any end phrase that
landed mid-clause shipped that way. **FIX (LOCKED):** `build_ad.py ending_gate()` runs at build time
and REFUSES to render if the last span's end word is mid-clause (not sentence-terminal AND the next
source word is the same speaker continuing, with no interviewer turn after) — exit 2, fix the phrase.
RULE when picking the last span: end on a word that carries **sentence-terminal punctuation** in the
source, OR where the **interviewer takes over** next. If the speaker keeps going, EXTEND to the true
sentence end (or pick a different, self-contained closing line — often the guest's "...don't even
think twice, just book it" / "...worth every cent" button later in the interview beats a mid-answer
stop). Audit the WHOLE batch with `10_WORK/scripts/ending_audit.py` (shows each clip's end word + the
source continuation) before delivery — 🛑 = false cut. (Generalizes to all clips: the Q&A/podcast spine
already enforces this via `window_validator` Rule 4 PAYOFF_TRUNCATED + the G3 payoff-extension audit —
any NEW clip-builder must run an equivalent ending gate; don't assume hand-picked pairs are complete.)
- 🛑 **PUNCTUATION ≠ LANDING — ending quality is an EAR/JUDGMENT call the gate can't fully make (A015,
  2026-06-17).** A015 shipped ending on "...energy that you started seeing from the team." — Whisper put
  a PERIOD after "team", so the punctuation-based ending_gate passed it. But in the source he barrels
  on with only a 0.08s gap into "So, so fucking cool!" — rising intonation, no real pause — so the clip
  ends MID-RISE and reads as cut off. Two lessons: (1) a clean ending needs a real PAUSE after the word
  (or an interviewer turn), not just a Whisper period — but source gaps are often zeroed/unreliable, so
  (2) ending QUALITY (does it LAND a satisfying payoff vs TRAIL into more of the same thought) is a
  SEMANTIC/ear judgment — run a per-clip judgment pass (an agent reads end-line + continuation: "lands on
  a payoff?" vs "trailing clause rising into more?"), don't trust the punctuation gate alone. A strong
  payoff word followed by a NEW sentence = LANDS (trim the next sentence, fine); a weak trailing
  subordinate clause with no pause into the SAME thought = cut-off.
- **If a guest's only clean landing is short or his payoff runs into profanity, SHIP THE SHORT LANDED
  CUT, don't force a longer one that trails.** A015's substance ran one breath into an f-bomb with no
  clean stop, so the only landing was his direct answer "Man, so amazing." → a clean ~7s "How was the
  workshop? / Man, so amazing!" beats a 16s cut that ends mid-rise. Short-but-landed > long-but-cut-off.

## 🔍 QC AT SCALE — fan-out audit is ADVISORY, not a gate (separate real defects from pedantry)
A per-clip QC workflow (one agent transcribes each clip's head+tail and judges it) is the right way to
sweep a batch fast. **But it OVER-FLAGS** (consistent with the house audit rule): it calls warm-but-
substantive opens ("The workshop was amazing. Loved it. Got clarity on...") and complete tactical
payoffs "weak/mid-sentence". Treat its output as a TRIAGE list, not a fail list. The only HARD fails
worth a re-render: (a) a real **trailing interviewer tag**, (b) a tail that ends on a dangling
connective/fragment ("...what you need to, **which**"), (c) **technical** defects (data stream, missing
A/V). Genuine **weak openers** (name/logistics intro, "my name is…", leading filler) are worth fixing
for an AD. Everything else — judge, and usually KEEP. Also: the auditor's ASR drops words too, so a
"tail ends mid-word" flag may be a Whisper false-negative — VERIFY the actual file before re-cutting
(on this batch, a "StrictSOPs ends on 'really really'" flag was wrong; the file ends on "useful").

## 🎨 CAPTION COLOR — solo testimonial = ALL WHITE (force it, don't trust the director)
A solo testimonial has ONE speaker → ALL captions white. The spice caption DIRECTOR non-
deterministically tags some words "guest" (yellow #FECB00) on a solo clip — so half a batch shipped
with yellow captions, half white. **WHY it happened:** I ran the director with no single-speaker
context and trusted its color choice. **FIX (deterministic):** in the testimonial preset set BOTH
`colors.alex` AND `colors.guest` to `FFFFFF` — then the director's voice choice can't matter, every
word renders white. (`spice_bubble.json` / `spice_acq_testimonial.json` already do this.) VERIFY caption
COLOR in QC, not just presence — an auditor that only checks "captions present" misses this.

## 🔊 LIMITER + DING — paid ads to −1.5 dBTP
Mix bus ends on `alimiter=limit=0.85` (≈ −1.5 dBTP). **WHY:** clips peaked at 0.0 dBFS (inter-sample
clipping risk). 🛑 The success DING is the culprit — it's a sharp transient that SLAMS 0 dBFS and slips
PAST a limiter's attack. FIX: lower the ding SOURCE volume (`volume=1.5`, not 2.7) AND alimiter=0.85.
Voice alone is fine; it's the ding that needs taming. QC must check max_volume ≤ −1.0 dB.

## 🎬 HEAD-CLEAN — open on the guest, not the interviewer Q / filler
The cutter can leak a leading interviewer question ("How was the workshop?") or a filler word
("yeah/Oh/Well/So") before the guest's first content word. **FIX:** `build_ad.py head_clean()` —
transcribe the first ~3s; if the first segment is an interviewer question (Q-word + "?"/topic) jump to
the answer; else skip leading filler words; trim the head (fail-safe, capped at 3s). Pairs with
`tail_clean` (trailing tag). NOTE `tail_clean` gap = 0.40s (0.22 ate sentence-internal short words like
"...what to | ignore" — only a ≥0.4s pause is a real interviewer tag).

## 💬 CAPTIONS — spice + translucent bubble
- House caption style (spice) PLUS a 50% black rounded bubble behind each cue (matches the brand's
  finished clips; improves legibility on bright outdoor backgrounds). Engine support is in
  `caption-clips/generate_spice.py` gated on a preset `bubble` key (`spice_bubble.json`); use
  `--no-layout` (single-subject). Keep the bubble pad TIGHT (pad_x≈0.34em, pad_y≈0.17em) — too much
  padding reads as a fat box — and keep `blur` LOW (≈2, NOT 5): a high blur washes the 50% pill into a
  soft halo that reads as "no bubble" on bright outdoor backgrounds (QC agents split on bubble-vs-no-bubble
  at blur 5). It must render as a DEFINED translucent rounded pill. (libass mis-anchors `\p1` drawings
  under `\an5`; the engine anchors the bubble `\an7` + offset `\pos`.)
- LEAD with CONTENT, not the guest's name/logistics intro ("My name is X, I run Y") — head-clean trims a
  leading interviewer Q/filler but NOT a long self-intro, so pick the opening span ON the substance.
  And avoid awkward verbatim fragments as the payoff (e.g. "at the very last heavy hitter…") — pick a
  complete, cold-viewer-coherent sentence even if it runs a few seconds longer.

## 🎬 END CARD — animated branded CTA (Remotion, via /promo)
- Replace any founder-video CTA with an animated end card built in the brand's look (`/promo` /
  Remotion): brand mark + headline + a glowing CTA button + subtext. Animate: a cursor moves in →
  the button flashes/glows → clicks → confetti burst + success ding. Recreate in the real brand kit
  (so the button truly animates) rather than animating a flat exported image. Append after the testimonial;
  carry the ding synced to the click. Reference build: the project's `10_WORK/endcard/` Remotion project.

## RECIPE (per clip) — reference impl in the project's `10_WORK/scripts/`
`build_ad.py`: cut (`_shared/faded_trim_cut.py`, word-index spans, fps-preserved) → `tail_clean` →
`_shared/testimonial_reframe.py` (2D face-pin) → uplifting grade → spice+bubble captions → assemble
[testimonial + end card], voice + ding, NO music, disclaimer burned. `before_after.py` builds a
same-guest pair (BEFORE/AFTER labeled segments + end card). Match same-guest before/after with SFace
embeddings (cosine ≥ 0.363 = same person) and **visually confirm each pair** before shipping —
a 0.74 "match" was two different people (one clip had two faces). Never ship a fabricated pair.

## DELIVERY
LOCAL ONLY → `20_DELIVER/` (sub-folders `after_only/ before_only/ before_after/`). 🛑 NEVER Frame, NEVER
Monday for these (non-Alex; and even then only on explicit per-file permission). Build a contact sheet.
