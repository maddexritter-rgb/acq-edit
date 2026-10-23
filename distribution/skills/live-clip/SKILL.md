---
name: live-clip
description: THE live-clipping skill. While a YouTube livestream is STILL RUNNING, loop-download it, keep a rolling word-level transcript, detect each COMPLETED interaction (a hotline caller wrapping up, a chat Q&A answered), and hand each one into the open Premiere project as an assembly-cut sequence (mid + short per interaction) for the editor to nudge while the stream continues. When the stream ends the editor has already adjusted most cuts and says "finish them" → reformat/captions/CTA/deliver via the existing skills. Trigger keywords - live clip, clip the live, live clipping, we're going live, clip this livestream while it's live, start the live loop, live-clip dry run.
---

# /live-clip — clips shipped before the stream ends

For any Premiere access, follow [Premiere Agent startup and advanced stage routing](../edit/references/premiere_start_here.md). Use the configured new bridge by default; if MCP tools are missing in this chat, use its CLI. Keep this skill’s existing creative scope and read-only limits.


> **Session going sideways or starting fresh? → `__ACQ_SKILLS__/edit/RUNBOOK.md`** — the
> command-by-command master workflow with a copy-paste MASTER PROMPT at the top. Every
> quality step there is a blocking gate; run it exactly.


## Two run modes — pick FIRST
- **ATTENDED ROLLING (THE mode — Maddex, 2026-08-01; cloud autonomy cancelled, not worth it):**
  editor at the Mac for the whole stream. Cuts land in Premiere every **5–10 min** as interactions
  complete; the editor approves/nudges each cut; the moment a clip is approved it gets the FULL
  finish **while the stream continues** — reformat + keyframing + captions (+ music) + export +
  gate — so finished, ready-to-post clips accumulate WHILE Alex is still live. Rolling, per clip:
  never batch the finish to the end.
- **AUTOPILOT** (editor genuinely away — fallback only): → **read `AUTOPILOT.md`** — playbook cuts
  + BLOCKING `live_qc_gate.py`, shorts-that-pass auto-push, mids local-only. Armed via
  `scripts/start_liveclip_autopilot.sh`. Lid OPEN + plugged in.

**The rolling loop:** ingest → transcribe → mine COMPLETED interactions → extract media →
assembly-cut XML into the open Premiere project → editor approves a cut → THAT clip is finished
immediately (Phase 2, per clip) → next mining cycle. Stream end = only a final sweep, not a
20-min finish job.

This skill owns ONLY the live loop (ingest / rolling transcript / completion detection /
Premiere handoff). Everything downstream is pointed-to, never duplicated:
mining judgment and precision cuts → **assembly-design** ·
reframe → **horizontal-to-vertical** · captions → **caption-clips** · mid CTA + contract →
**highlight** `highlight_cut.py` · delivery → **monday** (permission gate applies, ask every time).

## 🔒 Non-negotiables
0. **FORMAT ROUTING (Maddex, 2026-07-31 — this was missed once, never again): HOTLINE CALLERS
   and guest Q&A interactions get the L1 Q&A TREATMENT, ALWAYS.** Load
   `__ACQ_SKILLS__/edit/references/QA_MASTER_SOP.md` + `qa_worked_examples.md` +
   `clipper_ai_prompt.md` BEFORE cutting any caller interaction: CLIPPER design (contrast
   hook what-they-do→revenue · Alex speaks <5s · ONE problem arc built BACKWARDS from the
   payoff · diagnostic middle deleted once the answer lands · host interjections/tangents/
   2nd-threads cut · ~90–150s) and **`qa_editorial_score.py` must EXIT 0** on the kept text.
   The "mid = RAW single span" rule belongs ONLY to MoreMozi /highlight channel deliverables —
   applying it to an L1 hotline is a defect. Solo chat questions (no caller) = monologue rules.
1. **Banned-guest gate on EVERY segment** before it is extracted or XML'd:
   `__ACQ_SKILLS__/highlight/scripts/banned_guest_gate.py --shoot-date <today> --text-file <segment transcript>`
   (exit 2 = that interaction is dead, skip entirely; exit 3 = registry stale → re-sync first,
   do it BEFORE the stream starts). Re-gate each finished cut before delivery, as always.
2. **Only COMPLETED interactions get cut.** Completion = payoff + closing exchange has
   happened AND the host has clearly moved on (next caller / next question / new topic) AND
   the end is ≥60s behind the newest transcribed word. Never cut an arc still in flight.
3. **A mid is RAW** — one span, Q-in → A-out, no internal cuts (highlight non-negotiable #3).
   Shorts carry the internal cuts; the editor adjusts those in Premiere before finish.
4. **Never auto-deliver.** The loop STOPS at sequences in Premiere. Finish runs only when the
   editor says so; Frame/Monday push only on an explicit "push" for those files.

## Setup (before going live — do a 2-min preflight the day before)
- Scaffold the project: `bash __ACQ_ASSETS__/scripts/new_project.sh <brand> Live<Date>`
  (brand defaults to alex). `<work>` below = the project's `10_WORK/live/`.
- Premiere open with the target project + Premiere Agent Lab panel running; pass the shared startup doctor and live snapshot.
- Banned-guest registry synced ≤14 days.
- Mac: lid open + plugged in; `GROQ_API_KEY` reachable.

## Phase 1 — the live loop (one Claude session runs this)
```
# start ingest, detached (real live):
nohup python3 __ACQ_SKILLS__/live-clip/scripts/live_ingest.py live <URL> --work <work> &
```
Then loop every ~2–3 min (Monitor/wakeup or manual) until INGEST_DONE:
1. `live_transcribe.py --work <work>` — appends new words → `rolling.txt` / `rolling_words.json`.
2. Read the NEW tail of `rolling.txt`. Apply highlight's STAGE-1 mining judgment to spot
   interactions that just COMPLETED (rule 2 above). Track state in `<work>/segments.json`
   (`pending` → `cut` → `handed_off`), so nothing is mined twice.
3. Per completed interaction (gate it first — non-negotiable 1):
   - Pick spans from `rolling_words.json`: mid = one span (open on the question, end on the
     closing exchange); short = tightened spans (assembly-design judgment; boundaries on silences,
     mind the cold-start +0.10–0.15s head rule).
   - **🔒 EVERY boundary goes through `_shared/speech_map_cut.py --source <media> --words <words>
     --spans <spans>` and must come back exit 0** — THE cut engine (2026-07-31): Silero
     speech map + RMS; a cut may ONLY land on a frame inside a verified non-speech gap
     (speech_end+25ms .. next_onset−40ms), edge-hugging for pacing. FUSED verdict = no gap
     next to the intended word → do NOT cut there: merge through the connective speech or
     move the boundary to the candidate words it prints (loop until exit 0). Never ship a
     boundary the engine refused — that is exactly where clipped words and bumps come from.
   - `live_extract.py --work <work> --t0 <first span start - 10> --t1 <last span end + 5> --slug SEG<NN>_<Slug> --out-dir <proj>/10_WORK/live_segments`
   - **🔒 ANGLE CUTS (Maddex standard, 2026-07-31): every span is split at the EXACT frame the
     program feed switches camera angle** — so downstream keyframing never drags across a framing
     change. Detect once per stream: ffmpeg scene scan at 0.06 → `scripts/verify_switches.py`
     (face-box IoU/height jump across the cut frame kills gesture false-positives; catches the
     subtle "zoomed out a little" switches) → pass the verified list to every XML via
     `--switch-times`. Switches landing in dropped footage need no split (the director switches
     between interactions — verified on the 2026-07-31 stream: 71 switches, ~all between arcs).
   - **🔒 ONE review TIMELINE, not N sequences** (Maddex, 2026-07-31 "this is so disorganized"):
     `scripts/live_review_xml.py` — all clips on a single sequence, 20s gaps, a NAMED MARKER at
     each clip's first frame (edit-skill 8B-1 layout). Per-clip `live_xml.py` sequences only when
     explicitly asked.
   - Import the XML into the open project (import as media targeting bin `LIVE_INCOMING`;
     GUARD every Premiere op — verify `app.project.name` is the target project at execution
     time, the active project can switch mid-run when the editor is also clicking).
   - Tell the editor in one line: `SEG04 PricingCaller in — mid 6:10, short 41s, 3 cuts.`
4. The editor nudges the `_SHORT` sequences as they land (mids are raw — usually untouched).

Latency ≈ chunk (2 min) + transcribe (~sec) + completion buffer (1 min) + extract/XML (~sec):
**an interaction is in Premiere ~4 min after it ends.**

## Phase 2 — ROLLING FINISH (per clip, the moment the editor approves its cut)
Triggered per clip by the editor ("SEG04 good" / thumbs-up on the cut), NOT at stream end.
1. Read the adjusted `_SHORT` cut back from Premiere (his items = truth; never re-derive spans).
2. Finish that ONE clip end-to-end while the stream continues (the proven 2026-07-31 in-Premiere
   recipe — see edit-skill 8B + memory `project_live_clip_skill`): 9:16 face-tracked keyframing
   split at the verified angle-cut frames (X-only keys, static per-angle scale/posY) → spice
   caption overlays (PNG-codec, alphaUsage=1, layout clamp 0.58–0.70) → measured music bed
   (~12dB under voice) → export → gates (black-frame head, 1080x1920, −13..−18 LUFS,
   banned-guest re-check) → `20_DELIVER/` under its ACQ name.
3. Tell the editor in one line: `SEG04 DONE → 20_DELIVER (41s, −16.4 LUFS)`. Keep mining in
   parallel — finish jobs run in the background, never block the loop.
4. Mids stay RAW + local (MoreMozi rule) → `highlight_cut.py` CTA at stream end.
5. Frame/Monday push: ONLY on an explicit "push" from the editor for named files — accumulating
   finished clips locally during the stream is the default.
Stream end = a sweep: finish any approved-but-unfinished cuts, concat chunks →
`00_SOURCE/<stream>.mp4`, run the mid CTAs, final ledger.

## Dry run (same code path, zero risk — do one before every new stream setup)
```
python3 .../live_ingest.py simulate <past-stream.mp4> --work <work> --speed 30 [--dur 900]
```
then run Phase 1 exactly as above. `--speed 30` replays 30× (a 2-h stream in 4 min);
use `--speed 1` for a full-fidelity rehearsal.

## Gotchas
- Chunk durations are keyframe-snapped, NEVER uniform — all absolute time comes from
  `manifest.json` (ffprobe-measured). Do not multiply index × chunk seconds.
- `live_extract.py` refuses ranges not fully ingested ("too close to the live edge") —
  that's the safety working; retry next cycle.
- Live HLS caps at 1080p and the manifest URL expires after ~6 h — fine for ≤2-h streams;
  restart ingest (it resumes into new chunk numbers) if a stream runs longer.
- The stream's program feed has built-in camera switching — reframe already handles cuts
  (face-track default). Audio is the stream's board mix (correct per Q&A audio doctrine).
