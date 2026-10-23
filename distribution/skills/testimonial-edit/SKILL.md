---
name: testimonial-edit
description: THE skill for long-form 16:9 sit-down testimonial edits (workshop/event client testimonials, e.g. L3-style renewals). Raw interview → compliance-clean story CUT first (Premiere sequence for review), THEN graphics + captions + loudness as a second pass after the cut is approved. Encodes the human-cut standard extracted from the editor's own Premiere pass (2026-07-14 Stetson diff). Trigger keywords - testimonial edit, L3 testimonial, event testimonial, renewal testimonial, cut this testimonial, testimonial batch.
---

# testimonial-edit — long-form 16:9 testimonial cuts

For any Premiere access, follow [Premiere Agent startup and advanced stage routing](../edit/references/premiere_start_here.md). Use the configured new bridge by default; if MCP tools are missing in this chat, use its CLI. Keep this skill’s existing creative scope and read-only limits.


## ⭐ FAST PATH — the proven end-to-end batch pipeline (locked 2026-07-15, editor-approved)
This is the sequence that produced the approved L3 batch (23 clips, native-editable Premiere).
Run it in order. All scripts are in `scripts/`; agent tasks in `agent_tasks/`; Premiere
ExtendScript templates in `scripts/premiere_jsx/` (set the `WORK` var to the job's `10_WORK`).

0. **Scaffold + download** (footage-fetch) → copy raw to `00_SOURCE/<event>/`. Fetch Poppins
   600/700/800 into `10_WORK/fonts/` (fonts skill / Google Fonts API).
1. **Transcribe** each source → `10_WORK/<event>/<person>/clip_00.json`
   (`edit/scripts/transcribe_groq.py <src> <boundaries.json>`; boundaries = whole file).
2. **CUT** — → Use skill: `assembly-design` for the source-word story and frame
   boundaries, retaining testimonial-specific compliance and texture rules below.
   The existing native adapter consumes `cutlist_v2.json` (`agent_tasks/1_cutlist_task.txt`).
   Follow THE CUT RULES below + `__ACQ_SKILLS__/assembly-design/references/assembly-boundaries.md` (compliance,
   arc, fewer-longer-takes). Camera-roll files = one person each; detect empties (room tone).
3. **CARDS** — one agent per clip → `cards.json` (reverse-engineer the REAL interviewer
   questions from transcript gaps). Task: `agent_tasks/2_cards_task.txt`. 3-6 per clip.
4. **OPENING** — one agent per clip → `opening.json` (business-intro, Stetson style).
   Task: `agent_tasks/3_opening_task.txt` (keep|replace|prepend).
5. **FINALIZE cuts**: `build_final.py <workdir>` per clip → snaps every boundary OUTWARD-only
   to silence + applies opening → `cutlist_v3.json` + `cards_final.json`. EYEBALL the first-span
   text after; hand-tighten fused/sparse intros in `cutlist_v3.json` (name fused to business,
   sparse intros — see 2026-07-15 fixes).
6. **PREP**: `prep_clip.py <workdir>` per clip → `premiere_plan.json` + `captions.srt`
   (interleaves 2s card beats, times captions off Groq words, no gaps).
7. **ASSETS**: `make_manifest_and_flat.py <project_root>` (manifest + flat plan) →
   `gen_supers.py <project_root>` → `gen_cards.py <project_root>`.
8. **BUILD in Premiere** (bridge; ONE project open only — it acts on the frontmost project):
   `premiere_jsx/1_assemble_sequences.jsx` (cuts+cards+super, no blur/audio) →
   `2_blur_add.jsx` → `3_blur_set_and_mute.jsx` (separate passes; see gotchas) →
   `4_build_flat_review.jsx` (flat ALL_L3_REVIEW) → `5_flat_blur_mute.jsx` (run TWICE).
9. **VERIFY**: DOM read-back — every card beat Blurriness===220 AND its audio clip disabled;
   spot-check first-span openings. (Can't screenshot native seq — export_frame/AME broken.)
   For a real look, `verify_burn.py <workdir>` renders an ffmpeg proxy of ONE clip to watch.
10. **GATE**: editor reviews the flat `ALL_L3_REVIEW`, does the ~10% human pass in place.
11. **FINISH (after approval)**: export + captions (see stage-2 below), deliver, sync sheet.
    → To publish the finished testimonials to YouTube as **unlisted** (title convention +
      monetization off + no end screen), use skill: **testimonial-upload**.

**Hard-won pitfalls (all cost a rebuild — do NOT repeat):**
- Verify effects by DOM read-back, NEVER by ffmpeg burn — ffmpeg applies its own blur and HIDES
  a flat native sequence.
- QE `getItemAt(i)` ≠ DOM clip i (leader + gaps are QE items). Build `real[]` = QE items with a
  valid `.name`; `real[d]` maps to DOM clip d.
- `setValue(blur,220)` won't commit in the same script as `addVideoEffect` → separate passes.
- SNAP boundaries OUTWARD-ONLY or you clip leading/trailing words ("Marketing"→"agency").
- Cards: silent audio + 2.0s fixed + blurred moving footage (Blurriness 220). Mute by TIME-match
  (audio track desyncs from video index after the sweep).
- Opening = Stetson style (business spoken, name in super). Spans need NOT increase in source
  time — a prepended intro can come from anywhere (TC's was at 24 min). No strict-increasing guard.
- ONE Premiere project open; re-open + verify seq name before mutating.

---

**Two-stage workflow, HARD GATE between them (editor's rule, 2026-07-14):**
1. **CUT** — story cut only, assembled as a native Premiere sequence (via the Premiere MCP
   bridge) + a plain preview render. STOP. The editor reviews/adjusts the cut.
2. **FINISH** — only after the cut is approved: name super, typicality disclaimer,
   captions, loudness. Engine: `scripts/build_testimonial.py` (cut-locked spans in →
   finished master out).

Never ship stage-2 output from an unreviewed stage-1 cut.

## Pipeline (per testimonial)
1. Transcribe: Groq word-level (`edit/scripts/transcribe_groq.py`, whole-file boundaries).
2. Compliance scan of the transcript → cut list constraints (→ Use skill:
   testimonial-review for the disclaimer/prohibited-representation reference).
3. Build the cut list per **THE CUT RULES** below.
4. Assemble in Premiere via MCP bridge (`insertClip` ExtendScript pattern — see
   `scripts/premiere_assembly.md`), one sequence per person: `<PERSON>_<EVENT>_V1`.
5. Render a plain cut-only preview (no gfx/captions) into `10_WORK/` for review.
6. GATE: editor reviews. Apply notes in Premiere / re-cut.
7. FINISH pass on the approved spans (`scripts/build_testimonial.py`).

Seam mechanics (silence-snapped splices, true acoustic ends, fades, ASR-blindness traps):
→ READ `__ACQ_SKILLS__/assembly-design/references/CLIP_CUTTING_PLAYBOOK.md` BEFORE cutting.
Its active assembly rules are in `assembly-boundaries.md`; old finishing/audit instructions are historical.

## THE CUT RULES — extracted from the editor's own Premiere pass (Stetson diff, 2026-07-14)
The reference edit was 15 long continuous takes where the automated draft had 19
micro-splices. Direction of every correction:

1. **Fewer, longer takes.** Prefer ONE continuous run per thought. Do NOT splice around
   small stumbles inside a flowing answer — a mid-sentence splice reads broken (playbook
   Seam Rule 1). Only cut at real thought boundaries.
2. **Texture stays.** Keep recall beats ("Oh, the accountability. That was again why I
   decided…"), sincere buttons ("That's just great."), emphasis repeats ("a clean… a clean
   blueprint"), reflective trails ("I don't know if there's any one thing I was really
   worried about."). An over-sanitized testimonial reads fake. Cleaner ≠ better here.
3. **Self-restated questions are KEEPERS.** "Why did I decide to renew?" / "What would I
   tell another business owner?" work as chapter headers — keep them when the subject says
   them mid-flow. (Interviewer's own voice is still always cut.)
4. **No bare Q&A one-word answers stitched into a fake intro.** If "state your name" got a
   two-word answer, DROP it — open on the first natural sentence ("I own a media company
   called…"). The name lives in the super (stage 2).
5. **Cut wind-ups, not endings.** Rambling lead-ins ("Plus some of the challenges we were
   facing before attending was, I mean,") get trimmed — start at the substance ("a big one
   was just hiring people"). But let sentence ENDS run out naturally.
6. **Boundary padding:** IN ≈ 0.08–0.12s before the first word's TRUE acoustic onset
   (Whisper labels stretch early — trust the ear/energy, tight to speech). OUT ≈ +0.25–0.4s
   after the last word's true end, and up to ~1.3s where the natural pause breathes. The
   old −0.10/+0.15 default is too tight on the out.
7. **Front-of-answer throat-clear goes.** "Really good. Really good, honestly. Like it's
   really" → start at the content word ("amazing to have a clean blueprint…").
8. **Timeline starts at 0.5s** (half-second leader before the first clip).
9. **Runtime 2:30–4:30**, conversational pacing, natural pauses kept. No hyper-cutting,
   no fades, HARD end on the payoff line (fence-sitter advice / "worth it" / room-energy).
10. **Frame-exact assembly**: floor(t×fps) on both ends; spans strictly increasing,
    disjoint in source time.

## Compliance (from the disclaimer reference + editor's calls on the template)
- CUT: specific revenue/income dollar figures; **past-results growth multiples**
  ("10x since last time", "doubled our business"); guarantees ("it pays for itself");
  profanity.
- KEEP: operational scale facts (employee/location counts); vague success ("completely
  changed", "huge ROI"); **forward-looking aspiration** ("take that and 10X again" — the
  editor restored this on the template); mild non-guarantees ("it will help").
- Typicality disclaimer burn happens in stage 2 (engine default: ≥15s on screen).

## Assembly + engine
- Premiere: `scripts/premiere_assembly.md` (project item in/out + insertClip loop,
  frame-exact positions; bridge gotchas documented there).
- **Stage-2 finish = REMOTION LIQUID GLASS (editor-picked from a 3-style bake-off,
  2026-07-14).** Engine: `scripts/remotion-finish/` (Remotion 4 project — copy to the
  job's 10_WORK, npm install once). Flow per person:
  1. `build_master_example.py` pattern: ffmpeg EDL replication of the APPROVED Premiere
     timeline (takes + question cards: gblur sigma 34 @1080p + card PNG overlay + silent
     audio + 0.5s black leader) → 2-pass loudnorm −16 LUFS / TP ≤ −3 → `master_cut.mp4`.
  2. Caption props JSON — SAME LOGIC AS SHORT-FORM (editor rule 2026-07-14), via the
     canonical spice chain on the MASTER's audio (`spice_chain_example.py`):
     whisper-cli DTW (ggml-large-v3, ~/.claude-video-vision/models/) → token→word merge →
     normalize_transcript → normalize_simple → spice_normalize → generate_spice chunker
     with --preset spice_longform.json (long-form lines: tier_caps slow 3w/20c, med 4w/26c,
     fast 6w/30c, hard_max 30 — generate_spice reads preset "tier_caps" since the
     2026-07-14 additive patch; short-form presets unaffected). Parse .ass Dialogue events
     → DEDUPE layered shadow/text duplicates → LONG-FORM MERGE (combine adjacent cues to
     ≤28 chars when gap ≤0.30s and no sentence end at the seam — the pace-tier breaks are
     tuned for 9:16 and read choppy on long-form). Then: strip ALL punctuation (keep $%#&'),
     ALL-CAPS, ~4-frame lead (Oliver 3–5), NO GAPS (butt-join; extend ≤1.2s hold),
     hard-clip cues at question-card windows. Target: ~20-22 char avg, 30 max.
     Per playbook: ACCURACY SCAN the cue text before batch delivery (ASR mishears).
  3. HARD-LINK master into `remotion/public/` (symlinks 404 in Remotion's server;
     videoSrc prop = bare filename, resolved via staticFile).
  4. `npx remotion render TestimonialFinish out/<PERSON>_FINISH.mp4
     --props=props/<person>.json --codec=h264 --crf=18 --concurrency=8`.
- The look (composition `TestimonialFinish.tsx`): glass caption chips bottom-center
  (rgba(19,22,40,0.42) bg + backdrop blur 18 + 1px white/28% stroke + inset top highlight,
  radius 26, Poppins 600 46px white, NO animation — hard on/off (editor note 2026-07-14)); super top-left 0.8→12s is
  PLAIN text (editor 2026-07-14): NO glass chip — same type language as the question cards,
  Poppins 800 white w/ soft shadow (line1 44px, line2 26px), hard on/off; typicality disclaimer 17px bottom 0.5→15.5s. ACQ tokens: Sambucus
  #131628 / Indigo #6f00ff / Lavender #a08bec.
- Preview render (stage 1): plain ffmpeg select cut, no gfx/captions.
- Reference base look: static 16:9 interview, no music, no endcard, no b-roll; question
  cards per the section above.

## QUESTION CARDS — REVERSE-ENGINEER FROM THE REAL INTERVIEWER QUESTIONS (editor rule 2026-07-15)
EVERY testimonial must have question cards (3-6). Do NOT keyword-match a generic set — that
misses real questions and leaves clips with zero cards. Instead: the interviewer's real
questions live in the transcript GAPS before each kept answer span (interviewer voice is cut
from the answer but present in the raw transcript). Per clip, extract the actual question
before each distinct answer, rewrite it TIGHT / 2nd-person / ALL-CAPS / 2-3 lines (reuse the
reference canonical wording when a question matches a standard L3 theme), and write
`cards.json` = {"cards":[{"span":<idx>,"lines":[...]}]}. Fan out one agent per clip
(/tmp/cards_task.txt pattern). prep_clip.py consumes cards.json; gen_cards.py renders unique
content-hashed PNGs (dedupe across clips) into 10_WORK/_cards2/. Card before each DISTINCT
question only (not continuation spans); always card the fence-sitter/advice question.

## QUESTION CARDS (original reference notes) — part of the reference look (reverse-engineered 2026-07-14)
~4 cards per 4-5min edit, placed before SELECTED answers (an accent, not every question):
- ~3s each (72f @23.976). Footage keeps playing under a HEAVY gaussian blur (NOT a freeze);
  use the guest's listening/idle beat just before the answer (source seconds preceding the
  answer's in-point). AUDIO FULLY SILENT under the card. No captions during the card.
- Text: the interviewer's question rewritten tight in 2nd person, 2-3 centered lines,
  mid-frame (block center = 50% height), ALL-CAPS Poppins ExtraBold white, soft drop
  shadow. Measured @1080p: cap height ~65px (font ~92px), line pitch ~146px, max width
  ~86%. POPS on/off hard — no fade.
- Build (Premiere-native, works around broken add_text_overlay): render each card as a
  transparent PNG at sequence res (PIL, Poppins-800, shadow = blurred black copy offset
  +16px @2160p, blur 22, alpha 150) → import → V2 overwriteClip at the card position,
  set clip.end for exact 72f. Blur the V1 beat via QE:
  `qe.project.getActiveSequence().getVideoTrackAt(0).getItemAt(domIdx+1)
   .addVideoEffect(qe.project.getVideoEffectByName("Gaussian Blur"))` (QE index =
  DOM index +1 when the only gap is the 0.5s leader), then set "Blurriness" ≈220 @2160p
  via DOM components. Disable the beat's A1 clip (.disabled=true).
- Insert beats in DESCENDING timeline order (inserts shift everything after them; V2
  placement happens AFTER all inserts, at the final shifted positions).
- Question text: reuse the reference's exact card copy when the interviewer asked the
  same question; otherwise mirror its phrasing style ("DID YOU HAVE DOUBTS AND FEARS
  AROUND SIGNING UP FOR L3?").

## Working relationship with testimonial-review (compliance)
`testimonial-review` (org skill) is THE compliance reference — but its stock flow reviews
PUBLISHED videos (YouTube transcript → 7 disclaimer types → tracker Column I write-back).
For edits, ADAPT it: run its disclaimer-types + prohibited-representations rules against
the RAW transcript and convert violations into cut decisions (stage 1) + disclaimer burns
(stage 2). Note: only `disclaimer-types.md` of its 6 reference docs exists locally; the
authoritative source is the live Google Doc it cites. Open question to carry per job:
the skill mandates a ≥10s typicality burn, but reference edits may omit it — confirm
with the requester whether to bake it in or add at publish.

## Batch discipline
- One project folder per job (`00_SOURCE/<event-date>/…`, work in `10_WORK/<event>/<person>/`).
- **NAIL ONE FIRST — hard rule from the editor (2026-07-14): fully finish ONE testimonial
  through both stages and get it approved before cutting any more.** Batching before the
  template is blessed produced a full batch of rework. One at the center, then scale.
- Per-person work dir holds: `clip_00.json`, `cutlist.json`, `premiere_spans.json`,
  preview + finished renders. Tracker row updates at delivery.
