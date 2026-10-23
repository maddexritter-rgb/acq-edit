# HARD-WON LESSONS — the /edit casebook

*Extracted verbatim from SKILL.md on 2026-08-03 so the spine could be read as a checklist.*

**Nothing here is deleted knowledge — it is the WHY behind the gates.** Every lesson below is a real
shipped defect. Most are now enforced in CODE (`reqc.py`, `qa_gauntlet.py`, `window_validator.py`,
`ending_check.py`, `qa_prebuild_audit.py`, `non_negotiables_check.py`), which is why SKILL.md now
states the rule and points here instead of retelling the story on every run.

**When to read this file:** when a gate fires and you want to know what it is protecting against;
when you are tempted to override a rule; when onboarding onto the pipeline. Not needed on a clean run.

---

## 1. THE L1 Q&A BATCH POST-MORTEM (2026-06-14 → 2026-06-16) — 8 revision rounds
> **🛑 POST-MORTEM FROM L1 Q&A BATCH 2026-06-14 → 2026-06-16 — READ FIRST IF EDITING Q&A**
>
> 8 rounds of revisions on an 18-clip batch before Maddex was satisfied. ALL the defects were preventable with stricter pre-/post-build audit. Root causes + what to do every Q&A run, going forward:
>
> ### Why the mistakes happened
> 1. **I treated playbook non-negotiables as advisory** — silently fell back to "simplest valid floor" (single-cam Alex) instead of doing split-screen. The playbook EXPLICITLY listed split-screen as non-negotiable #2. **FIX:** `non_negotiables_check.py` runs as a HARD GATE. Defensive pre-justification in the delivery README ("happy to do X as a V2 pass") is the smell — if I'm writing it before the user complains, I'm cutting a corner.
> 2. **I configured visual params (zoom, eye) once GLOBALLY and shipped without per-clip visual verification.** Guests differ — Tanya (short) needs zoom=1.15/eye=0.18; Brian (tall) hits the reframer's source-bound limit at the same settings; Trey (medium) worked at 0.95/0.10. There is NO single zoom that satisfies all guests. **FIX:** Step 9 now requires per-clip OPEN-FRAME extraction + visual face-position measurement BEFORE staging.
> 3. **I shipped music tracks with slow build-up intros without profiling.** øfdream 27s, øneheart 17s, Gods creation 25s, Labrinth 4s — all bled boring intro under the hook. **FIX:** STEP 7 of qa_playbook.md mandates RMS profile of every picked track; if beat-drop > 1s, `--music-ss <N>` is required. Audit gate G5 automates this.
> 4. **I cut segments on Whisper's word.end labels without padding for soft consonants.** "road." (-d) and "one." (-n) got mid-syllable clipped because Whisper's labels are 0.1–0.25s early on soft tails. **FIX:** G1 boundary-tail audit catches every flagged segment-end pre-build.
> 5. **I cut cameras mid-completion.** Cut to Alex while Trey was still saying "yeah trying to figure out…" — the source-time jump reads as "muted guest mic." **FIX:** G2 guest-completion audit catches same-conversation cam-cuts that skip prev-speaker words.
> 6. **I ended clips on mid-thought, not the natural button.** Trey closed on "biggest, baddest one." instead of the punchier "So give the sickest one away." 1s later. **FIX:** G3 payoff-extension audit reads the 3s past EDL's last word for an imperative/connector-led button.
> 7. **I optimized one clip at a time instead of running a batch-wide audit before each rebuild.** Every revision round revealed defects I should have caught proactively. **FIX:** `qa_prebuild_audit.py` runs all gates (G1-G7 blocking + G8 advisory) in <5s on the EDL before any 4K encode burns 5–8 min. Cheaper to fail at audit than at human review.
>
> ### The Q&A discipline going forward (autonomous-safe)
> Run this loop per clip, in this order:
> 0. **Design the CUT with the CONTRAST HOOK + HOOK→PAYOFF→TENSION method (`references/clipper_ai_prompt.md`) — the DEFAULT, not a remembered option.** WHAT-they-do→revenue hook; end on the portable PRINCIPLE, never a bare tactic/wind-down. Spine = [`references/QA_MASTER_SOP.md`](references/QA_MASTER_SOP.md).
> 1. Design EDL + corrections.json + pick music
> 2. **`qa_editorial_score.py` MUST EXIT 0** on the clip's spoken transcript (HARD GATE, not advisory — blocks plain/revenue-first hooks, tactic/wind-down endings, failed portability, sub-100-word skeletons). Compounding standard: gate, don't warn. [[feedback_compounding_standard_default_plus_gate_2026-06-12]]
> 3. **`qa_prebuild_audit.py` MUST EXIT 0** before any encode (G1–G7 blocking; G8 pacing = advisory)
> 4. Build via qa_assembly
> 5. **Extract open frame at t=1.0s. If split-screen, measure guest face position in lower panel.** If face center > 35% of panel height → rebuild with lower eye / higher zoom OR document the source-bound limit (tall guest in centered CCAM)
> 6. Head-trim if onset > 0.10s, reqc, stage
> 7. Mozi-sf-audit + scorecard-audit (post-build)
> 8. ONLY then declare clip ready
>
> A clip that skips any of these steps is a clip that ships defective. The L1 batch took 8 rounds because I skipped steps. Don't skip steps.

---

## 2. ALEX SINGLE-CAM DESK/TALKING-HEAD — the locked recipe & its scars (2026-06-11)

> Hard-won on the StayInAGreatMood batch. For a 1-speaker / 1-camera Alex desk or stage
> talking-head, these are the DEFAULTS — set them in the manifest and the clip comes out right
> the FIRST time. Each gate below maps to a real mistake made this session; do NOT repeat them.

> ### 🛑 MANDATORY OPENER GATE — RUN ON **EVERY** CLIP, EVERY TIME (not just flagged ones)
> The #1 process failure this session: the gates existed but were run REACTIVELY — only on clips
> Maddex flagged — so a dead-air open (TheSecondArrow: 0.66s of silence + an "and so" before the
> hook) and a rambly aside ("I've been looking into Buddhism lately, weirdly enough") shipped.
> Before showing the user ANY clip, run BOTH checks on ALL of them — it is your job to catch
> these, NOT the user's. These are RULES, not taste:
> 1. **Onset (measure, don't eyeball):** transcribe/RMS the first ~1.5s. First audible speech must
>    be within ~50ms of frame 1, AND the first word must be the intended hook word. ASR labels lie
>    by seconds — snap the in-point to the measured acoustic onset, not `word.start`. If there's a
>    lead, trim it (`leadfix.head_trim`) or hard-set `cuts.json`, then re-measure.
> 2. **Editorial opener (cold-viewer):** the clip must open on the HOOK. CUT any preface
>    ("with all that being said"), filler conjunction ("and so", "so"), or personal aside
>    ("…weirdly enough") that sits BEFORE the hook. If you ever catch yourself writing "aside is
>    acceptable / adds personality," that's a skipped check — apply the rule and cut it.
> Do this per-clip and report the opener of each ("opens on: '<first words>', onset Xms") before delivery.

**Manifest defaults (pipeline `single`):**
```json
"reframe":  { "preset": "alex-listicle", "zoom": 1.4, "eye_y": 0.30, "res": "4k" }
"captions": { "preset": "<abs path to a y58 spice preset>", "no_layout": true }
"mix":      { "music": "<vibe_music.py pick>", "voice_lufs": -16, "music_lufs": -30, "limiter": 0.45 }
"leadfix":  { "head_trim": 0.0 }   // bump to ~0.08 only if the opener has a small lead beat
```

**REFRAME** → `horizontal-to-vertical` (qa_reframe_v2), always from the **4K master**, output `--res 4k`.
- **zoom 1.4** for desk talking-head. `source-intel`'s recommended zoom OVER-shoots on wide shots
  (it suggested 2.2 → "way too zoomed", head cut off). 1.4 ≈ the canon crop. Verify face has headroom.
- **PER-CUT single-pass**: the render `reframe` stage passes `--cut-frames` (from `cut.meta.segments`)
  so the tracker resets at each content seam — each cut framed independently, ONE encode. Do NOT
  per-segment-then-concat (wobble at every seam) and do NOT whole-clip-continuous (pans across seams).
- **🔒 FACE TRACKING IS THE DEFAULT — EVERY CLIP, ALWAYS. (house standard, non-negotiable.)** The X
  crop follows the subject's smoothed face-box so the camera stays on the speaker — that's what makes a
  reframe look alive, and Maddex expects it on every clip. Do NOT disable it. **NEVER add `--lock-x` /
  `reframe.lock_x:true` by default** — that pins the crop static and KILLS the tracking (the bug Maddex
  caught 2026-06-12: a podcast close-up shipped as a dead static crop because lock_x was set "for
  talking-heads"). When in doubt, TRACK. (Y stays locked to the eyeline via the preset — separate axis,
  always fine.)
- **`--lock-x` is a RARE EXCEPTION, NOT a podcast/talking-head default.** The ONE narrow case it exists
  for (Alex PeaceOrPower, 2026-06-12): a near-motionless seated speaker whose micro-shifts read as a slow
  pan. Reach for it ONLY when a SPECIFIC *delivered* clip visibly shows an unwanted slow pan AND Maddex
  asks to lock that clip down. Default stays tracking.

**CAPTIONS** → `caption-clips` spice via the render `captions` stage (it re-transcribes the cut
audio and runs `spice_caption.py` — it IGNORES any manifest `.ass`, so caption Y is controlled by the
PRESET, not a hand-built file).
- Style = **spice** (the Oliver look), NEVER `pro`/`pro_locked` (legacy flat) and NEVER the
  deterministic fallback. The director (`caption_director.py`) MUST run for real per-word
  weight/size/italic/yellow. **If the Anthropic API is out of credits it auto-falls back to the
  `claude` CLI** (added 2026-06-11) — confirm the log says `director: styled via claude CLI`, NOT
  `-> deterministic`.
- **Height = y≈58 (renders ~59%, top of the tank-top V / lav-mic line)** via `captions.preset` +
  **`no_layout: true`**. WHY no_layout: `spice_caption`'s per-angle layout analyzer overrides the
  preset Y to ~50% on single-angle footage, which Maddex calls "way too high" — and it silently
  ignores every preset/.ass edit (the cause of the long "still too high" loop). `--no-layout` honors
  the static preset Y. **UPDATE 2026-06-12 (Alex PeaceOrPower):** podcast/multicam ALSO wants captions pinned to the
  **chest/shirt line ~60%** (`y_percent_from_top:60` + `--no-layout`), NOT the analyzer's ~50% — Maddex
  showed reference clips at ~61% across BOTH camera angles (FIXED, not per-angle). Default to `--no-layout`
  at y58 (desk) / y60 (podcast); reserve the live per-angle analyzer only where per-shot height is truly wanted.

**MUSIC — THE CHAIN IS FOUR NUMBERED STEPS. STEP 1 IS NOT SKIPPABLE. (gate added 2026-08-02
after a batch shipped all-Calm because the session skipped classify and pattern-matched a
reference batch that happened to be all-Calm — the lane step IS the recipe, a prior batch's
folder is NOT):**
1. **CLASSIFY the lane PER CLIP** — `vibe_music.py` Groq classify on EACH clip's transcript →
   vibe → folder (hype_money → Trap · viral_fun → Core · reflective → Calm · cinematic →
   Trending). 🛑 NEVER pick a single folder for a whole batch by hand/by analogy to a previous
   batch. If Groq is down, classify in-session with the same 4-label rubric from
   `vibe_music.py` CLASSIFY_SYSTEM — per clip, written down (a ledger row with each clip's lane).
2. **PICK within each clip's lane with THE CALIBRATED MATCHER:**
   `python3 __ACQ_SKILLS__/_shared/pick_music.py --folder "<lane folder>" --used "<recent picks>"`
   — ranks by similarity to the `_APPROVED.txt` centroid, excluding `MUSIC_BLACKLIST.txt` +
   already-used (verify the --used exclusion actually filtered; it has silently no-opped —
   re-filter manually if used tracks still rank). READ
   `content-skill-system/(1) Tik Tok/MUSIC_RULES.md` for the rules this implements. NEVER
   hand-pick by title; do NOT use `vibe_music.py`'s `pick_track` as the chooser — random-in-folder,
   ignores the approved lane (2026-06-12: 5 rejects in one batch).
3. **CHECKS per pick:** distinct track per clip (rule 3) · rotation — rest tracks used in recent
   batches (rule 2) · SPOKEN-INTRO check (rule 6: transcribe first ~15s; lone one-liners =
   Whisper hallucination = clean; real clustered sentences = contaminated → next rank) ·
   RMS/beat-drop intro offset (slow build → `--music-ss`/offset past it; known: Gods creation 25s,
   Snowfall 24s).
4. **EAR + FEEDBACK LOOP:** the ear is the final judge — render, offer swaps. When the user
   approves a track, ADD it to `_APPROVED.txt` (rule 7) so the lane sharpens.

**CUT BOUNDARIES** → `make_cut`/word-gap, but **ASR WORD TIMESTAMPS LIE — by SECONDS, not just ms.**
This session Whisper labeled "Sometimes" 2.2s before it was spoken (at the start of a pause), so the
clip opened on dead air + a stray "said". GATES:
- **Snap the clip IN-point to the ACOUSTIC onset (RMS / silencedetect), NOT the ASR word.start.**
  Verify the first 0.1s of the delivered clip is speech (the head-trim gate, edit step 7d). If the
  Whisper label and the measured onset disagree, trust the measurement and hard-set `cuts.json`.
- **Drop opener PREAMBLE bloat** ("with all that being said," "long story short," …) — `make_cut`
  strips a known list; open on the first real hook word.
- **Cut absorbed pauses INSIDE a single ASR token** (word-gap can't see them — split the span
  explicitly or it ships a 2s dead beat mid-sentence).
- **End on the real PAYOFF, not early** — extend the out-point to Alex's actual last point, then
  hard-end (no fade).
- **CLEAN SPLICES — snap every cut to inter-word silence** (2026-06-12, Alex PeaceOrPower): the END label
  often sits AT the next word's start, so cutting on it lands mid-word → chopped words + clicks/pops (the
  #1 audio complaint this batch). End on the TRUE acoustic word-end, snap the cut to the quietest ~10ms
  window in the silence, ≥12ms fade. **`_shared/faded_trim_cut.py`** does exactly this AND probes/preserves
  source fps — use it on 23.976 sources where `precision_cut.py` (forces 30fps) corrupts timing. Verify
  per-cut pre/post RMS ≤ ~−28dB. Full SOP: `CLIP_CUTTING_PLAYBOOK.md`.

**VERIFY BY MEASUREMENT, NEVER BY EYE.** I misjudged caption Y as 52% when it was 66% repeatedly.
Caption position = burn-on-black or diff grade-vs-captions frames; audio onset = RMS per 0.1s;
clipping = waveform, not a re-transcript. Prove it on the REAL delivered file before "done".

**INFRA GATES:**
- **Disk**: 4K stage caches + `_segments` scratch fill the data volume fast (hit 97% / 0 bytes mid-render
  this session → corrupt output). `df -h /System__ACQ_EXTERNAL_VOLUME__/Data` before a big batch; clear
  `v_new/*/10_WORK/stages/*/​*_segments` (regenerable) and `/tmp/*.mp4|wav|png` when low.
- **Corrupt-cache trap** (FIXED 2026-06-11): a render that dies on out-of-space leaves a partial
  `.mp4` that EXISTS — the engine used to serve it as a valid cache HIT. The engine now probes each
  cached output (`_valid_mp4`: size + ffprobe duration) and re-renders if corrupt. If you still see a
  stage's output fail to open downstream, delete that stage's cache file and re-render.


---

## 3. GIT DISCIPLINE (full text; the operative rule is summarized in SKILL.md)

> **Two layers — never conflate them:**
> - **Skill layer** = `__ACQ_SKILLS__/` — the live "brain" Claude actually runs. Skills load ONLY from here. NEVER relocate it; it is not, and cannot become, the GitHub folder.
> - **Repo layer** = the GitHub copies you commit and share with the team. Project repos live in the user's `~/Documents/GitHub/` folder. (The `edit` skill is special: it lives in-place at `__ACQ_SKILLS__/edit`, which is itself a git repo; the full pipeline is mirrored to a bundle repo via its `sync.sh`.)
>
> **The rule, every work session:**
> 1. **Test the change locally as a skill FIRST.** Make the skill edit → apply it to a real video → confirm it works. NEVER commit broken or untested work.
> 2. **When it works, commit it to GitHub** — at every natural stopping point and at session end. A change that exists only in the local skill (the "brain") and not in a repo is at risk and invisible to the team.
> 3. **Always be able to answer "where is this change recorded?"** — in the repo, or only as a functional skill in `__ACQ_SKILLS__`? Reconcile the two before stopping (diff the live skill against its repo — *is local the same as remote?*).
> 4. **Shared, not siloed.** Skills live in GitHub so anyone can branch → improve → merge to main and everyone gets the upgrade. Innovation must not be bottlenecked by one person.
> 5. **After editing any skill, TWO repos may need updating:** the affected in-place skill repo (commit + push) **and** the pipeline bundle (run its `sync.sh`, which re-copies every skill and pushes). Don't leave one stale.
>
> Practical default: at the end of any session where a skill changed, commit + push the affected repo(s). If unsure, ASK "should I commit this to GitHub?" — once it's tested and working, the answer is yes.

---

## 4. NO FALSE ENDINGS — the CMO note (2026-06-17)

> The CMO's #1 note on the first ad batch: *"often the AI cuts off the speaker and goes to the end
> bumper."* A clip that ends MID-SENTENCE — speaker still talking — then jumps to the end card / hard-end
> reads as broken. **This is now a HARD GATE on every `/edit` delivery, for ALL content domains — Q&A,
> workshops, ads, listicle, podcast, monologue, anything. A clip with a cut-off sentence does NOT ship.**
>
> **The rule (one canonical home: `_shared/ending_check.py`):** the clip's last kept word must be
> **sentence-terminal in the source**, OR the next source word must begin a **new turn** (interviewer
> question / new sentence). If the SAME speaker keeps going on the same clause → FALSE ENDING → extend to
> the true sentence end (or pick a self-contained closing line). Also a false ending if the clip ends ON a
> connector/function word (and/but/so/which/to/the…).
>
> **Enforced in TWO places (defense in depth):**
> - **PRE-cut — `window_validator.py` Rule 4 PAYOFF_TRUNCATED (Step 5a).** Now also catches a CONTENT-word
>   ending where the source continues (not just function-word endings). ERROR = BLOCK before any render.
> - **POST-delivery — `reqc.py` FALSE-ENDING gate (Step 8b).** Runs on the actual delivered file, every
>   render incl. `--bump`. Pass **`--project <clip_dir>`** so it maps the clip's last word back to the
>   source and sees the continuation (without it, only a connector ending is catchable from the tail).
>
> Both call the same `ending_check`. WHY the testimonial batch shipped two cut-offs (TenOutOfTen "…to the
> next **level**", GivingItAway "…all **away,**"): `build_ad.py` skipped the gate. Lesson — **any
> clip-builder, in ANY domain, MUST run the ending gate.** Don't assume hand-picked boundaries are
> complete; verify against the source.

---

## 5. THE LAWS OF REVISION — full narrative + the regressions behind each

> The goal is a FULLY AUTONOMOUS editing workflow. It only works if the safety gates run themselves
> and BLOCK on failure — they cannot depend on the operator remembering to re-check. Every law below
> is a real, painful regression from the StayInAGreatMood batch: round 1 shipped clean, then a long
> tail of revisions made it WORSE and re-introduced errors round 1 never had. Encode these or repeat them.

> **LAW 1 — EVERY render re-runs the FULL automated gate. A spot-check is NEVER enough.**
> The #1 meta-failure: after round 1 passed, each revision (music swap, recut, the Y fix, a caption
> tweak) was followed by checking ONLY the one thing changed. Regressions slipped through unaudited and
> shipped. RULE: after ANY `engine.py` run — first build OR `--bump` revision — run
> `python3 __ACQ_SKILLS__/edit/scripts/reqc.py <delivered.mp4>` (or `--batch <20_DELIVER/vN>`) on the
> ACTUAL delivered file, and it must exit 0 before the clip is collected/shown. No exceptions, no "I
> only changed the music so the cut is fine" — re-run the whole gate. reqc.py is the automated form of
> the PER-CLIP QC LEDGER below.

> **LAW 2 — Boundary edits are PER-CLIP, with full word context. NEVER mechanically batch-move cuts.**
> The single worst move of the session: a script that auto-snapped 13 cut OUT-points to the nearest RMS
> "valley" across the batch. A valley-snap is blind — it doesn't know if it's slicing a word in half or
> leaving half a double-take, and it pulls the cut EARLIER, which CLIPS MORE of the word. RULES:
> (a) change one boundary at a time, looking at the word-level transcript + RMS around THAT seam.
> (b) a clipped-word fix EXTENDS the OUT past the word's true acoustic end (ceiling = next word's onset),
>     it does NOT retract to a valley. (c) never run a loop that moves many boundaries by a rule.

> **LAW 3 — VERIFY THE FIX ACTUALLY ACHIEVED ITS GOAL on the delivered file. "I edited the spec" ≠ fixed.**
> SadnessVsAnxiety shipped a double-take TWICE because an early "fix" only removed the PAUSE between the
> two takes, not a take — and the result was never re-checked. RULE: after a fix, prove the specific
> defect is gone on the rendered output (transcribe the head for an opener fix; n-gram/listen for a
> double-take; waveform/ear for a clipped word) — not on the spec, not by assuming.

> **LAW 4 — NEVER trim a within-take SILENCE pause on single-cam gesturing footage. It jump-cuts.**
> Removing an internal pause hard-cuts from the subject's position before the pause to his position
> after — if he MOVED during it (gesturing, drawing, leaning), his body teleports. 61 such jump cuts
> shipped in one batch from an auto dead-air splitter (build_cuts `split_silences`). The discriminator:
> a same-take seam is a jump ONLY when the removed gap is PURE SILENCE (no words). A gap WITH words is
> an intentional content cut (removed double-take) and its jump is the accepted cost. RULE: keep spans
> CONTINUOUS through internal pauses (the pause is usually him drawing = content); only trim a pure-
> silence pause after confirming LOW motion across it (full-frame Δ ≤ ~14). reqc.py's JUMP-CUT gate
> (`--project`) blocks pure-silence seams with cross-seam Δ>14. (This is the reconciliation of the old
> "cut tighter" pressure: tighten by motion, not blindly.)

> **LAW 5 — A reframe/zoom/format change REBUILDS via the engine; NEVER re-mux a foreign audio track onto a re-cut video.**
> StudioL zoom-out (2026-06-16): I re-cut each answer's VIDEO from source but re-muxed the ORIGINAL saved
> audio (`-map <foreign>:a`) to keep the music. The re-cut video and the saved audio had DIFFERENT cut points
> → audio/video DESYNC ("the audio continues but his cut changes") + caption MISALIGNMENT (captions off a
> third timeline) on the WHOLE batch. ACQ review called every clip terrible. RULE: to change framing/zoom,
> re-run the engine manifest with the new reframe — the cut stage cuts video AND audio from the SAME in/out
> (synced) and captions regen from THAT audio (aligned). Put music in the MIX stage so the clip's own audio
> is lav+music. Concat Q+A with `concat=n=N:v=1:a=1` (each clip's OWN audio) — NEVER a foreign `-map x:a`.
> (The off-camera QUESTION audio is the ONLY safe swap: isolation preserves timing, Alex isn't lip-syncing it.)
> Also: a "contiguous" answer usually still has small dead-air trims — let the engine cut it, don't assume one
> span. See [[feedback_revision_engine_one_cut_2026-06-16]].

> **LAW 6 — A revision touches ONLY what the note touches. PRESERVE every un-noted layer EXACTLY — especially
> the CAMERA layout (split-screen vs single, and who's on screen).** Recurring regression (Maddex 2026-06-22):
> a clip's V_n was correctly multicam (split-open → guest-Q single → Alex-A single), then a revision whose notes
> were only about cuts/captions/music came back FLATTENED — split-screen gone or the wrong person on screen —
> because the editor regenerated the EDL/angles from scratch instead of preserving them. Client never asked for
> that; it's pure regression. RULE: revisions are SURGICAL — re-cut the marked spans as INTERNAL trims that keep
> every retained word on the SAME camera it was already on; do NOT re-decide camera angles, do NOT collapse a
> split, do NOT switch Alex↔guest, do NOT touch grade/reframe/music unless a note explicitly says so. The
> revision PROMPT must SPELL OUT the layout to hold (which ranges stay split / Alex / guest) — derive it from the
> shipped V_n pixels (contact-sheet the delivered file), not a stale EDL. After re-render, VERIFY the layout
> sequence is unchanged. "No note about it" = "must come out identical," never "free to redo."
>
> **LAW 7 — a REVISION must pass `_shared/revision_verify.py` BEFORE delivery (deterministic note-application gate).**
> ThreeFunctions V4 (2026-06-22) bounced because the session never checked its own output applied the notes — it
> shipped 2 skipped notes, a garbled payoff, a "so I" false ending, and re-introduced filler, and a human reviewer
> caught it = a wasted round-trip. The gate that prevents that: build a notes SPEC ({expect_gone, expect_present,
> end_on, filler_guard}) from the revision prompt and run `revision_verify.py --prior <prior w_norm> --new <new
> w_norm> --spec spec.json` — it diffs the new transcript vs the prior + the spec and FAILS on any uncut note,
> missing target wording, leaked/false ending, or filler that INCREASED vs the prior cut. Proven: it flags every
> V4 defect. "Did the revision do all the notes?" is answered by this tool, NOT by the next human review. Pair it
> with reqc (mechanics/ending/loudness). A revision is not done until revision_verify exits 0.
> **EVERY revision prompt MUST follow [`references/revision_prompt_template.md`](references/revision_prompt_template.md)** —
> it bakes in LAW 6/6b/7. Author a `notes.json` (exact verbatim cuts), auto-generate the spec with
> `_shared/revision_spec_from_notes.py --notes notes.json --out spec.json`, and paste it into the prompt's §SELF-CHECK
> so the downstream session self-blocks until every note is applied. NEVER hand-write a revision prompt without the §SELF-CHECK.
>
> **🚦 THE GAUNTLET — run `scripts/qa_gauntlet.py` before delivering ANY Q&A clip (first build OR revision).** This is
> the enforcement of every gate in ONE blocking command — it moves QA from after-delivery (a human catches it = a
> round-trip) to before-delivery (a tool catches it in-loop). It runs, and BLOCKS on FAIL: editorial (hook/payoff/
> portability) · qa_prebuild G1–G8 (ending + pacing) · `framing_gate` (face-too-wide, floor 13% of frame) · reqc
> (res/loudness/ending/jump-cut/harsh-seam) · revision_verify (notes applied, revisions only).
> `python3 scripts/qa_gauntlet.py --clip DELIVERED.mp4 --project DIR [--single-cam-span "S E"] [--prior P --spec S]`
> Fix every ✗ and re-run until it exits 0; THEN run the 3 LLM auditors (audit-captions/visual/audio) it prints; THEN
> deliver. The ledger (`references/qa_notes_ledger.json` + `scripts/qa_ledger_summary.py`) tracks which note-classes
> the gauntlet now enforces — every new review note gets logged there and its prevention wired into a gate.
>
> **LAW 6b — a revision is a SURGICAL trim of the PRIOR cut, NOT a re-cut from source.** (StageQA/ThreeFunctions
> V4, 2026-06-22.) The notes were cuts-on-V3; the editor instead REBUILT the EDL from raw with fresh word
> boundaries — and the new boundaries RE-INTRODUCED filler V3 had already removed ("right"×3, "um you know", "of
> like"), chopped the answer into 0.6s micro-segments, garbled the payoff line with a spliced false-start, and
> leaked a dangling "so I" past the intended hard-end. A re-cut from source throws away the prior version's hard-won
> word-level cleanliness. RULE: start from the PRIOR delivered cut's word selection and REMOVE only the noted spans
> (word-span deletions snapped to silence); never re-pull the whole EDL from raw for a revision. After re-render,
> diff the new transcript against the prior one — any word that APPEARED (filler, stammer, "so/like/um") that the
> prior clean cut lacked is a regression, not an edit. Verify by re-transcribing cut tails, never ASR-on-clipped.

> **ASR BLIND SPOTS (relearned every session — stop relearning them):**
> - **Clipped words are INVISIBLE to a re-transcript** (ASR reads a chopped word as whole). Confirm word
>   integrity by waveform/spectrogram or EAR. An "ASR-timestamp clipped-word scan" is NOISE — it flags
>   every sentence-final word (proved 2026-06-12); do not build or trust one.
> - **Whisper word timestamps lie by up to ~2s at zero-gap boundaries.** Snap in/out to MEASURED acoustic
>   onsets/valleys (RMS per 10ms), never to `word.start`/`word.end`.
> - **Double-takes hide inside stretched tokens** (a false-start absorbed into one long ASR word). The
>   n-gram repeat scan in reqc.py + the EAR catch these; reading the prose transcript does not.


---

## 6. PER-CLIP PRE-DELIVERY QC LEDGER (the human-readable form of `reqc.py`)

> The human-readable form of `reqc.py` (Law 1). **Run this whole checklist on EVERY clip before showing
> the user — proactively, on every render, not just clips they flag.** Verify by MEASUREMENT
> (RMS/ffprobe/transcribe/diff/EAR), never by eye, never by re-transcript alone.

**OPENER (every clip):**
- [ ] First audible speech within ~50ms of frame 1 — measure RMS, don't trust the ASR `word.start`
      (it lied by 0.66s on TheSecondArrow, 2.2s on AFewBadDays). Snap in-point to the acoustic onset;
      trim residual lead with `leadfix.head_trim` or hard-set `cuts.json`.
- [ ] First word is the HOOK — not a preamble ("with all that being said"), filler conjunction
      ("and so"), or an aside ("…weirdly enough, I've been into Buddhism lately"). Cut it. If you
      think "the aside adds personality," that's a skipped check — cut it.

**WORDS / CUT (every segment boundary):**
- [ ] No clipped boundary word — soft endings (-ful, -al, -s, -t, -th, -ing, -tion) get true-ended
      LATE; ASR `word.end` is ~0.1–0.25s early. "painful" and "optional" both shipped clipped. Pad the
      OUT-point past the soft tail (verify the next word's onset is the ceiling).
- [ ] No absorbed pause INSIDE one ASR token (a 2s dead beat mid-sentence). Word-gap can't see it —
      split the span explicitly around it.
- [ ] No double-take / restart — Alex often says a phrase, restarts, says it again
      ("Anxiety comes from many options. Anxiety comes from many options, but…"). Keep the COMPLETE
      take, cut the redundant one.
- [ ] No mid-clip filler — "you know" / "I mean" / "um/uh" (manual eye + transcript scan; word-gap
      doesn't remove them). 
- [ ] Ends on the REAL payoff, not early (DontCatchIt ended before Alex's point). Extend the out to
      the actual last line; hard-end (no fade).
- [ ] 🛑 NO FALSE ENDING / cut-off sentence — last word is sentence-terminal in the SOURCE, OR the
      interviewer takes over next. If the SAME speaker keeps going, EXTEND to the true sentence end.
      Auto-enforced: `window_validator` PAYOFF_TRUNCATED (pre) + `reqc.py` FALSE-ENDING (post, `--project`)
      + `_shared/ending_check.py`. Universal — Q&A/ads/listicle/podcast/monologue. (CMO note 2026-06-17.)
- [ ] Cut name-drops / tangents with no value and reshape to land on the payoff (the "Mark Twain,
      right, said earlier" aside — cut it; payoff = "most suffering happens in our own mind").

**CAPTIONS (every clip):** spice via director (confirm `styled via claude CLI`, not `-> deterministic`)
· height y≈58 via `captions.preset`+`no_layout:true` (NOT the ~50% layout-analyzer default) · 4K · the
render stage RE-TRANSCRIBES the cut audio, so captions can't be fixed by editing a hand `.ass`.

**REFRAME (every clip):** per-cut single-pass (`--cut-frames`), zoom 1.4 (not source-intel's over-zoom),
from 4K master, head has room (not cut off). No seam wobble.

**MUSIC (every clip):** from `vibe_music.py`/`pick_music.py`, EVERY pick filtered through
`MUSIC_BLACKLIST.txt` (shipped Clair de Lune + Danilo Stankovic — both banned). Distinct per clip.

**MECHANICS (every clip):** 4K (2160×3840) · no stray data/bin_data stream · video==audio duration ·
no black/frozen frame · hard-end on a live frame. Then the 6-gate audit (step 9).

**INFRA before a batch:** `df -h /System__ACQ_EXTERNAL_VOLUME__/Data` (4K caches fill it → out-of-space → corrupt
output); clear `_segments` scratch + `/tmp` media when low.

Report each clip's opener + any fix BEFORE delivery: e.g. `AFewBadDays — opens "Sometimes…" @40ms, music One More Light, 4K ✓`.

---

## 7. ONE CLIP IS ONE PROPOSITION — the 4:42 "short" (2026-09-20)

> A solo whiteboard monologue was mined for short-form and produced a single clip **4 minutes 42
> seconds long**. Nothing was wrong with the words in it; the arc was complete and it passed a blind
> content-unit review. It was simply **five clips fused into one** — one thesis, illustrated five
> different ways (a pitch rewrite, a personal anecdote, a throwaway aside, a ratings analogy, a
> famous ad story), all retained in one plan. The batch also came up 3 clips *short*, because every
> illustration that should have anchored its own clip was spent inside this one.
>
> **The tempting wrong fix is a duration cap. Do not add one.** The strongest reference batch on
> record runs 27–70s with no cap at all (one of its best clips is 70s), and L1 Q&A legitimately runs
> 90–150s. A ceiling would damage those formats and still not address the defect.
>
> **The real cause was scope, and it is mechanically visible.** Measured against that reference
> batch: those plans carry **zero** parallel-illustration segments (every one reads
> `context → reasoning… → reward`) and keep **9.5–37%** of the words inside their own
> `interaction_words` bounds, each of which spans a single bounded exchange (341–1061 words). The
> 4:42 plan carried **five** illustration segments, kept **66%**, and had set
> `interaction_words` to **the entire source file**. That last field is the deepest cause: declaring
> the whole video one "interaction" makes everything downstream inherit that scope. Q&A and
> diagnosis get their unit boundaries free — a question opens one, its answer closes it. **Monologue
> and lecture footage have no delimiter at all**, so unless a boundary is set deliberately, the unit
> silently defaults to the whole file.
>
> **FIX:** `assembly-design/SKILL.md` now opens construction with "Scope one clip before
> constructing it" — one proposition, proven one way, paid off once; several illustrations of one
> thesis are several candidate clips, and the three signals above (parallel illustrations, keep
> ratio, undelimited interaction) are checked before compiling. `profiles.md`'s Monologue profile now
> requires finding the unit boundary first. `editorial-calibration.md` carries the same three as
> failure signatures. **Duration is a symptom to investigate, never a rule to enforce** — a clip far
> past its format's normal length means re-examine scope, not trim words toward a number.

---

## 8. THE ACTIVE PROJECT MOVES UNDER YOU — the wrong-project delete (2026-09-20)

> Building a clip through the Premiere MCP bridge while the editor had a second project open — and a
> second session of their own touching the same Premiere instance — an agent verified project
> identity once, then fired several mutating calls in a row without re-checking. Between them the
> active project switched. `select_all_clips` + `remove_selected_clips` **deleted 9 clips out of the
> editor's other project**, one the agent had explicitly promised not to touch.
>
> **Active project and active sequence are shared global state.** They follow whichever window or
> session last had focus and change with no action of yours. A verification from three calls ago is
> stale. The rule already existed in this runbook, but as one clause inside a Step-0 preflight
> bullet, restated 170 lines later as "before EVERY bridge **batch**" — and a batch is not a call.
> That ambiguity is the whole defect.
>
> **Recovery is worse than expected: the bridge's own undo does not work.** `app.project.undo is not
> a function`; `multiple_undo` returned `0 undone`. The only thing that recovered the clips was the
> editor running Edit → Undo in the Premiere UI. There is no MCP-side undo to fall back on
> mid-incident — do not assume one while deciding whether to keep going.
>
> **FIX:** the Step-0 gate is split — session-start coordination stays, and the per-call check is now
> its own standing rule naming the exact mutating calls and stating that each one needs its own fresh
> read-back; Step 8's guarded-ops bullet is tightened to match and cross-linked as the same rule.
> **If it happens anyway:** stop every further mutating call, do NOT save that project, tell the user
> exactly which project/sequence and how many items were hit, and have them undo in the UI. An
> unsaved wrong mutation is recoverable; a saved one may not be.

---

## 9. CUT AT AN ASR LABEL, CLIP THE WORD — and the engine already existed (2026-09-20)

> A monologue clip shipped with audibly clipped words at multiple internal cuts. The cause was
> literal: spans were built from raw AssemblyAI word-label timestamps and handed straight to
> Premiere as in/out points, with **no padding, no acoustic verification, no snapping**. That is
> precisely what `cut/CLIP_CUTTING_PLAYBOOK.md` has forbidden since 2026-06-12: *"ASR word-label
> timing is NOT a safe cut point… the label sits a hair EARLY (shaves soft consonants) OR exactly at
> the NEXT word's start… label+pad is NEVER sufficient."*
>
> **Why the law got skipped — the routing bug.** Step Zero's reading list carried
> `CLIP_CUTTING_PLAYBOOK.md` as item (e) *inside* a block prefaced "mandatory for business-owner
> diagnostics, **not ordinary podcast interviews or monologues**." The session classified its source
> as monologue, correctly concluded the list was not mandatory, and so never read the one file in it
> that is universal cutting craft rather than Q&A doctrine. **Fixed: the playbook is now its own
> ALWAYS-REQUIRED item at the top of the gate, for every format.**
>
> **Then it got worse: the capability was rebuilt from scratch, badly.** Rather than using
> `_shared/faded_trim_cut.py` (locked 2026-06-12: true-acoustic-end detection, `quietest()` /
> `snap_start()` / `snap_end()`, ≥12ms afade per splice, probes and preserves source fps) or
> `_shared/snap_to_silence.py` (locked 2026-07-07, "63 cuts, zero clipped words"), the session wrote
> a one-off RMS snapper — which then shipped its own bug: the start-edge search window was allowed
> to extend *past* a word's onset, and because an unvoiced consonant ("th-") measures quieter than
> the silence before it, the snap landed **inside** the word it was meant to protect.
>
> **Two lessons, both general.** (1) **Search for the existing engine before writing one** — this
> capability existed twice over, locked and battle-tested, and `_shared/` is where cutting engines
> live. A hand-rolled replacement inherits none of the scars the locked one was built from.
> (2) **A snap toward "quietest" must be bounded by the word it protects** — a start edge may never
> resolve later than its word's onset, an end edge never earlier than its word's true acoustic end.
> Low energy is not the same as absence of speech. Assert the invariant in code and check every
> boundary against it; do not eyeball a table of deltas and call it verified.

---
