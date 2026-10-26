---
name: mozi-sf-audit
description: >
  Mozi Media Team Alex V1 MVP short-form audit. Runs the 16-point quality checklist
  (Subtitles x7, Audio x5, Video x4) on any rendered 9:16 short-form clip before ACQ
  handoff / Frame.io upload. Produces a pass/fail report + Frame.io-paste-ready review
  notes. Automates spelling, subtitle gaps, lower-half placement, dialogue-sync, lowercase,
  audio levels/clipping/music-balance, blackframe detection, face-centering, UI-safezone
  overlap, 3-5 frame lead. Flags the rest for manual eye. Triggers: "audit this clip",
  "run the mozi checklist", "final review", "qa this short", "check this against team
  alex standards", "is this ready to ship", "pre-handoff audit", "sf standards check".
---

# Mozi SF V1 Audit

The final-review checklist every short-form edit ships against. Based on the Team Alex V1 MVP Standards (Mozi Media). **16 checks** (updated 2026-05-04 from 13 per Oliver Albert feedback), grouped into **Subtitles / Audio / Video**. Automates ~12 of them fully, flags the rest for a manual eye.

Read `references/mozi-standards.md` for the full verbatim checklist with exceptions.

---

## When to run

**Before:**
- Uploading any finished short to Frame.io for ACQ review
- Sending a `.mp4` zip to ACQ for posting
- Marking a clip as "done" in the internal tracker

**Integration:**
- `/edit` step 9 Gate 1 (the audit fan-out), `caption-clips`, `listicle-short` → call this
  as the final mechanical gate before a clip is declared ready.
- Can also run standalone on any `.mp4` (plus optional `.ass`/`.srt` subtitle file)

**🛑 TWO MODES (2026-08-03) — pass `--fanout` inside the /edit step-9 fan-out:**
- **`--fanout`**: this gate owns **caption TEXT + placement mechanics** (spelling, doubled words,
  lowercase, subtitle gaps, lower-half/safe-zone, dialogue sync, S2 pixel color, E3 fragments) plus
  #8 levels, #10 LRA, #15c dead-beat-after-cut, #16 lead. It **SKIPS #9 music, #11 clipping, #12 pops,
  #13 centered, #14 top-pad, #15 black, #15b frozen** — `audit-audio` and `audit-visual` own those with
  stronger detectors (YuNet vs Haar, sample-railing vs volumedetect, measured bed separation vs a
  silencedetect heuristic). Measured on a real clip: **2.1s wall / 8.6s CPU vs 5.8s / 29.5s** — the
  skipped checks were two full cv2 frame loops plus raw PCM decodes, duplicated for a weaker answer.
- **standalone (no flag)**: runs everything, so a one-off audit still gets full coverage.

**Exit codes:** `0` SHIP · `2` REVISE (real failures) · **`3` INCOMPLETE — this gate's own lane never
ran** (no subtitles supplied, so every caption check skipped). A skip is NOT a pass: always pass
`--subtitles <clip.ass>` (or the project's `captions.ass`) when auditing a captioned clip.

---

## Inputs

1. **Clip path** — `.mp4` (or `.mov`) at 9:16 (1080x1920 canonical)
2. **Subtitle file** (optional but recommended) — `.ass` or `.srt`. If subtitles are burnt-in, skip and the spelling/gap/case/placement checks degrade to flag-for-manual.
3. **Speaker map** (optional, for qa-clipper format) — JSON mapping time ranges to speaker (Alex vs Guest), used by check #6 subtitle-color
4. **Platform** — `instagram` (default) / `tiktok` / `youtube-shorts` — sets the UI safezone numbers

---

## The 16 checks

### Subtitles (7)
1. **Spelling / missing / double words** — spellcheck non-proper-noun tokens; flag anything suspicious
2. **No blank gaps between subtitles** (except >1s intentional pauses) — flag any visible gap >50ms; >30% of joints with gaps = fail
3. **NEW — Lower-half placement** (not covering face) — anchor must be in lower half (y > height/2). Face overlap requires manual eye for now
4. **NEW — Subtitle timing matches dialogue** (1-3 frame tolerance) — silencedetect maps speech regions; flag any cue displayed >50% during silence
5. **All words lowercased by default** (proper nouns + "I/I'm/I'll" exempt) — regex + proper-noun whitelist
6. **Alex vs Guest color differentiation** — parse `.ass` styles; verify distinct colors
7. **All subtitles within UI safezone** — IG 9:16 = top 13% / bottom 18% / sides 5% are UI-danger zones

### Audio (5)
8. **Audio peak ~-6dB** — ffmpeg `volumedetect`; flag if peak <-12 (too quiet) or >-3 (hot/clipping)
9. **NEW — Music doesn't drown out dialogue** — silencedetect heuristic; if audio never drops below -30dB across a >10s clip, music is likely too loud
10. **No overly compressed audio** — analyze LUFS LRA; flag if <5 LU
11. **No audio clipping** — ffmpeg `astats` sample_peak; flag any sample at or near 0dBFS
12. **No audio pops/clicks** — flag first/last 100ms for manual listen

### Video (4)
13. **Alex centered in frame** — face detection per frame; % frames where face center is in center 40% of width; flag if <90%
14. **Enough space at top so UI doesn't cut off Alex** — top-of-head padding ≥13% (≈250px on 1920)
15. **No dead spaces / black frames** — ffmpeg `blackdetect`; flag any black >2 frames (66ms at 30fps)
16. **3-ish video frames lead before audio** (TIGHTENED from 3-15 → 3-5) — 3-5 frames pass; 6-7 warn; <2 or >7 fail

---

## Eyes pass — burnt-in captions (the `watch` skill)

When captions are **burnt in** (no `.ass`/`.srt` sidecar), checks #1 (spelling), #3 (lower-half placement) and #7 (safezone) degrade to "flag-for-manual". Close that gap by giving the audit real eyes via the `watch` skill:

```bash
W=__ACQ_SKILLS__/watch/scripts
python3 "$W/caption_ocr.py"   CLIP.mp4 --interval 0.5   # caption presence + y-center placement, RELIABLE (#3,#7)
python3 "$W/contact_sheet.py" CLIP.mp4 --n 12 --cols 4  # then Read the PNG with your own eyes: spelling (#1), framing (#13/#14), caption look (#5/#6)
python3 "$W/probe.py"         CLIP.mp4                    # loudness/peak/clipping (#8-#11), black frames (#15)
```

OCR is **advisory** — confirm any flagged spelling/placement on the contact sheet with your own eyes. Caption y-center target ~65–80% of height (below the chin).

---

## Run

```bash
python3 __ACQ_SKILLS__/mozi-sf-audit/scripts/audit.py \
  --clip path/to/final.mp4 \
  --subtitles path/to/captions.ass \
  --speaker-map path/to/speaker.json \
  --platform instagram \
  --out ~/Downloads/audits/<clip-stem>.audit.md
```

Output:
- `<clip-stem>.audit.md` — human-readable report
- `<clip-stem>.audit.json` — structured result (pass/fail/warn/manual per check)
- `<clip-stem>.frameio.txt` — Frame.io-paste-ready review notes (empty if all passes)

Exit code: `0` = SHIP, `2` = REVISE.

---

## Ship / Revise decision

The audit report ends with one of:

```
VERDICT: ✅ SHIP — move to Final Review
VERDICT: ❌ REVISE — N issues, see notes, move to Needs Revision
```

If SHIP, upload to Frame.io for ACQ approval.
If REVISE, open the `.frameio.txt` and paste into Frame.io review comments, then loop back to editor / `revision-planner`.

---

## Recent changes (2026-05-04)

Per Oliver Albert (Mozi) feedback on April 2026 batch:

- **Added 3 new checks**: lower-half placement (#3), dialogue-timing sync (#4), music balance (#9)
- **Tightened gap threshold**: 0.3s → 0.05s. Visible subtitle gaps now flagged as `fail` if >30% of joints affected
- **Tightened lead-frame range**: 3-15 → 3-5 frames. The previous range was letting through clips with 8-10 frames of frozen-looking pre-speech silence
- **Companion render fix**: `shortform/scripts/cut_clip.py` now auto-detects pre-speech silence in the WAV and tightens the head so the audit's 3-5 frame range is hit out of the box (controlled by `--target-head-frames` flag, default 2)

---

## Dependencies

- `ffmpeg` / `ffprobe`
- `pyspellchecker` (auto-installs)
- `opencv-python` (already installed via vertical-reframer)
- `mediapipe` optional (falls back to OpenCV Haar if missing)

## v2 checks — ADD these (from the Alex multicam round, 2026-06-07; each caught a real shipped bug)
Run these on every clip in addition to the 16-point list:
- **Video length == audio length** — `ffprobe -select_streams v:0 -show_entries stream=duration` vs `a:0`. If video is shorter, the last seconds are frozen/black (a multicam diarization-gap or short-concat bug). FAIL if `a − v > 0.3 s`.
- **No stray data / timecode stream** — `ffprobe -show_entries stream=codec_type`. A trailing `bin_data` (camera timecode) makes players freeze/black at the end. FAIL if any `data` stream present (strip with `-map 0:v:0 -map 0:a:0 -c copy -map_metadata -1`).
- **Hard-cut ending** — sample the final frame (`-sseof -0.1`); it must be a LIVE frame (brightness > ~15), never black/faded. FAIL on a fade-out or frozen frame. (Fades are banned per [[CLIP_CUTTING_PLAYBOOK]].)
- **Opens clean** — the first caption/word must NOT be leading filler ("yeah/so/and/well/okay/right/um/mm-hmm"). FLAG if it does.
- **Dual-speaker caption color** — captions colored by SPEAKER (host white / guest yellow); EYEBALL it, louder-mic diarization mis-tags. FLAG mis-colored words.
- **Context present (Q&A/commentary clips)** — does the clip include the question/story it references? If it's a bare answer, FLAG "missing context" → see scorecard-audit + [[CLIP_CUTTING_PLAYBOOK]] step 0.
