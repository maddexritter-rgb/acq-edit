# /live-clip AUTOPILOT — no-human mode (the editor is away)

You are the supervisor session for a livestream being clipped with NOBODY watching.
Follow this exactly. When in doubt: HOLD the clip, never ship it. A held clip costs
nothing; a bad clip on the shared review account costs trust.

## Inputs (given by the watcher that spawned you)
- `WORK` — the live work dir (`<proj>/10_WORK/live/`), where ingest is already writing chunks.
- `PROJ` — the project root (`~/Downloads/<brand>/<date>_<slug>/`).
- Delivery policy (Maddex, 2026-07-30, standing for this batch):
  **SHORTS that PASS the QC gate → auto-push to Frame.io + Monday** (`frame_upload.py
  <files> --maddex-approved` then `deliver_links.py`, from
  `__ACQ_ASSETS__/content-skill-system/mondayframeworkflow/`).
  **MIDS → LOCAL ONLY**, into `PROJ/20_DELIVER/mids/` — never uploaded anywhere.
  **Failed-gate clips → `PROJ/10_WORK/held/`** with their `.qc.json` — never shipped.

## The loop (repeat every ~3 min until INGEST_DONE and no pending segments)
1. `python3 __ACQ_SKILLS__/live-clip/scripts/live_transcribe.py --work $WORK`
2. Read the NEW tail of `$WORK/rolling.txt`. Find interactions that just COMPLETED:
   payoff + closing exchange done, host clearly moved on, end ≥60s behind the newest
   word. Track them in `$WORK/segments.json` (`detected` → `built` / `held`); never
   mine the same span twice.
3. Per completed interaction:
   a. **Slice words + gate**:
      `live_words_slice.py --work $WORK --t0 <q_start> --t1 <a_end> --media-start 0 --out /tmp/seg.txt` —
      first run it with `--media-start 0` JUST for `--text-out`, then run the banned-guest
      gate on that text: `__ACQ_SKILLS__/highlight/scripts/banned_guest_gate.py
      --shoot-date <today> --text-file <text>`. Exit 2 → mark `held_banned`, SKIP entirely.
   b. **Extract media**: `live_extract.py --work $WORK --t0 <q_start-10> --t1 <a_end+5>
      --slug SEG<NN>_<Slug> --out-dir $PROJ/10_WORK/live_segments` → note `media_start`.
   c. **Re-slice words rebased**: `live_words_slice.py ... --media-start <media_start>
      --out SEG<NN>_words.json`.
   d. **🔒 FORMAT ROUTING FIRST (2026-07-31): a HOTLINE CALLER / guest Q&A interaction is an
      L1 Q&A CLIP — QA_MASTER_SOP treatment (CLIPPER design, contrast hook, one arc, kill the
      diagnostic middle, ~90–150s, `qa_editorial_score.py` exit 0), NOT a raw mid.** The RAW
      single-span rule below applies ONLY when building a MoreMozi /highlight channel mid.
      **MoreMozi MID** (RAW, one span): find the word INDEXES of the question's first word and
      the answer's last word in SEG words, then
      `highlight_cut.py --src <seg.mp4> --words SEG<NN>_words.json --keep '[[i0,i1]]'
      --out $PROJ/10_WORK/mids/<slug>_mid.mp4` (CTA auto-appends; contract must say
      `cta_appended:true`), then loudness-normalize the SPEECH portion to -14 LUFS
      (see step e — normalize BEFORE the gate). Gate: `live_qc_gate.py --kind mid
      --spans '[[t0,t1]]' --words SEG<NN>_words.json --clip <mid>`. Pass →
      `PROJ/20_DELIVER/mids/` with the ACQ name; fail → held.
   e. **SHORT** (only if the moment carries alone — not every mid deserves a short):
      pick keep-spans per the cut playbook (sentence-boundary seams ONLY, spans anchored
      to WORD TIMES from SEG words — never raw LLM timestamps; 25–60s target; open on
      the hook; kill rambles), then run **`speech_map_cut.py` (MANDATORY, loop to exit 0)** — cuts only on verified
      non-speech frames; FUSED = merge through or move the boundary, never cut fused speech.
      Cut:
      `_shared/faded_trim_cut.py --source <seg.mp4> --words SEG<NN>_words.json
      <spans_file> <out>` where spans_file = `{"spans":[{"a":<word_i0>,"b":<word_i1>},…]}`
      (WORD-INDEX spans) → **loudness-normalize** (the live board feed runs ~-29 LUFS —
      the gate WILL fail it raw): `ffmpeg -i in -af loudnorm=I=-14:TP=-1.5:LRA=11
      -c:v copy out` (audio-only re-encode; do the same to every mid AFTER highlight_cut)
      → reframe (canonical):
      `horizontal-to-vertical/scripts/qa_reframe_v2.py --preset podcast <in> <916.mp4>`
      → captions (**this exact recipe fixes the too-high captions — verified on frame
      2026-07-30**): `caption-clips/scripts/layout_below_chin.py <916.mp4> layout.json
      --lo 0.58 --hi 0.70` then
      `caption-clips/scripts/spice_caption.py <916.mp4> <out> --layout-file layout.json`
      (floor 0.58 = never high; up to 0.70 slides below the chin on leaned-in faces) →
      gate: `live_qc_gate.py --kind short --spans <spans> --words SEG<NN>_words.json --clip <short>`.
   f. **Ship or hold**: gate exit 0 + banned-guest re-gate on the clip transcript →
      short goes to `PROJ/20_DELIVER/shorts/` (ACQ name: `ALEX_SF_LIVE_<Title>_Maddex_<YYYYMMDD>_V1.mp4`)
      and is pushed (frame_upload + deliver_links). Exit 2 → `held/` + move on.
4. Append one line per event to `$PROJ/10_WORK/00_RUN_LEDGER.md` (segment, verdicts,
   shipped/held). This ledger is what Maddex reads Friday night.

## Judgment rules (compressed from the SOPs — the full docs win if you can read them)
- Mining: a hotline caller or a chat Q&A = ONE interaction. Open ON the question
  (guest asking = the hook). Mid ends on the closing exchange ("Thank you / You bet").
- Shorts: ONE arc, cold-viewer complete (question context REQUIRED — a bare answer is
  a dead clip), hook in the first 3s, hard-end ON the payoff (never fade, never freeze).
- Pacing (Julian, 2026-07-28): do NOT cut every pause. Keep natural breathing;
  only cut fillers/restarts/rambles at clause boundaries.
- Cold-start rule: first kept word of any span → start +0.10s into its silence gap
  (Whisper/ASR hallucinates "And/So" on zero-gap opens).
- Numbers of shorts: quality over count. 3 great shorts beat 10 mediocre ones.

## Failure discipline
- Any script errors twice in a row on the same segment → mark it `held_error`, log,
  MOVE ON. Never stall the whole loop on one segment.
- If ingest dies (INGEST_DONE missing + newest chunk >6 min old + stream still live per
  `yt-dlp --print is_live <url>`): restart `live_ingest.py live <url> --work $WORK`
  once; if it dies again, keep transcribing/cutting what exists and log LOUDLY.
- NEVER touch Frame/Monday for mids, failed clips, or anything a gate blocked.
- End of stream: after the last segment settles, concat all chunks →
  `$PROJ/00_SOURCE/<stream>.mp4` (stream copy), write the final ledger summary, and
  post the summary as a Slack DM draft for Maddex (slack-voice rules; DRAFT ONLY).
