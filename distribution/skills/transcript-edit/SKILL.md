---
name: transcript-edit
description: Descript-style word-level clip editing. Given a rendered clip, exports a plain-text transcript (prose + per-word view) the user can edit by deleting words/sentences. Re-renders the clip from source with ONLY the kept words — cuts snap to acoustic silences (via ffmpeg silencedetect), so no half-words, no mid-phoneme clicks, no "ob-vious" / "gives yo-" artifacts. ALWAYS use silence-snap (`--silence-map`) on any transcript-driven cut. Triggers: "edit the transcript", "cut out [word/filler]", "apply my edits to clip X", "remove filler words", "trim these words", "Descript-style edit", "word-level cut", "transcript-driven edit".
---

# Transcript-Edit — Descript-Style Word-Level Clip Cutting

Lets a human editor cut video by deleting words from a text file. The skill
handles the alignment, cut-point snapping, concat, and re-caption. Replaces
chat-based "cut out 'so' at 3.4s please" back-and-forth with a single
round-trip edit.

## When to use

- User says: "cut out [word]", "edit the transcript", "apply my edits"
- User hands you back an edited .txt transcript
- You're fixing filler words / pauses / misspoken words in a rendered clip
- Surgical single-word cuts that would be painful to describe in prose

**Do NOT use for** initial clip assembly from raw long-form — that's
the retired `shortform` pipeline. This skill edits ALREADY-assembled clips.

## Workflow (the only correct way)

```
┌─────────────────┐   export   ┌──────────────────────┐
│  Rendered clip  │ ─────────► │  _transcript.txt     │
│  (A_final.mp4)  │            │  _transcript_edit.txt│
└─────────────────┘            └──────────────────────┘
                                          │
                                          │ user edits:
                                          │ deletes words,
                                          │ reorders, etc.
                                          ▼
                               ┌──────────────────────┐
                               │  User edited .txt    │
                               └──────────────────────┘
                                          │
                   apply w/ --silence-map │
                                          ▼
┌─────────────────┐   concat   ┌──────────────────────┐
│ Source vertical │ ─────────► │  clip_v2.mp4         │
│ (pre-music)     │            │  (silence-snapped)   │
└─────────────────┘            └──────────────────────┘
```

## Scripts

- **`scripts/export_editable_transcript.py`** — dumps a clip's transcript as
  prose + per-word text files, ready for the user to edit.
- **`scripts/apply_transcript_edit.py`** — takes the edited .txt + silence
  map + source MP4 and produces a new MP4 with only the kept words,
  re-captioned via `caption-clips` (historically the retired shortform Pro preset).

## 🚨 CRITICAL SOP — always pass `--silence-map`

**Whisper word boundaries are NOT phoneme-accurate.** They're alignment
approximations. Cutting at `word.end` leaves the vowel tail audible.
Cutting at `word.start` eats the consonant attack of the next word.

Result without silence-snap: `"ob-vious"`, `"gives yo-"`, click artifacts
at every cut boundary.

### The rule

**Every cut boundary must land INSIDE an acoustic silence region.**

### User's framing (exactly right)

> "To cut out 'so': make one cut BEFORE 'so' is even said, and one cut
> right before the next word starts. Delete the middle segment. Join the
> two clips. No half-word left behind."

### How silence-snap works

1. Run `ffmpeg silencedetect -30dB -d 0.08` on the source audio →
   `silence_map.json` (list of silent intervals)
2. For each keep-range boundary:
   - **Cut-OUT** (end of keep-range, before a skipped section): snap to
     silence.start + 20ms → cut lands 20ms into silence
   - **Cut-IN** (start of keep-range, after a skipped section): snap to
     silence.end − 20ms → kept range starts just before speech onset

`apply_transcript_edit.py` does this automatically when
`--silence-map <path>` is passed.

## Canonical workflow

```bash
# 0. Extract audio + build silence map (once per clip)
ffmpeg -i clip.mp4 -vn -ac 1 -ar 48000 clip_audio.wav
python3 __ACQ_SKILLS__/_shared/legacy-shortform-runtime/scripts/silence_map.py \
    clip_audio.wav --noise-db -30 --min-dur 0.08 \
    --out silence_map.json

# 1. Export transcript for user editing
python3 scripts/export_editable_transcript.py \
    --transcript clip_transcript.json \
    --out-dir ~/Downloads/editable/ \
    --name <clip_name>

# 2. Send user the .txt. They delete words/lines. Save.

# 3. Apply edits with silence-snap
python3 scripts/apply_transcript_edit.py \
    --clip source_vertical.mp4 \
    --transcript clip_transcript.json \
    --edited user_edited.txt \
    --silence-map silence_map.json \
    --out clip_v2_voiceonly.mp4

# 4. (Optional) re-reframe + re-mix music + re-burn captions per
#    the retired shortform SOP (historical; that skill no longer exists).
```

## Input formats accepted by `--edited`

**Prose** (easiest for user):
```
Most of our lives are spent with only hard decisions left.
The only way to make a hard decision...
```

**Per-line with timestamps** (precision):
```
[ 0.30]  Most
[ 0.46]  of
[ 0.68]  our
...
```

Auto-detected. User deletes words/lines in either. Use `difflib.SequenceMatcher`
to align the edited token stream back to original word indices.

## Output

- `<name>_v2.mp4` — new MP4 with only kept words, silence-snapped cuts, Pro
  captions re-timed to new timeline, no music (add via `vibe_music.py`)
- `<name>_v2.ass` — regenerated ASS for the new timeline

## Locked-in lessons

**2026-04-23 — "ob-vious" / "gives yo-" bug:** Without silence-snap, cut
boundaries fell at Whisper's `word.end` which sometimes lands mid-phoneme.
Phoneme-accurate alignment isn't possible from LLM transcripts — must use
acoustic silence detection. Every transcript edit from 2026-04-23 onwards
MUST pass `--silence-map`.

**Do NOT work from post-render MP4s.** Use the VERTICAL (pre-music,
pre-caption) as source. Burning captions on a previously-captioned clip
double-burns them; mixing music over already-mixed music stacks it 2x.

## Related skills

- **retired `shortform` pipeline** (historical; superseded by `edit` / `caption-clips`).
  Its two still-used scripts now live in `_shared/legacy-shortform-runtime/scripts/`:
  `silence_map.py`, `transcribe_groq.py`
- **music** — added after the edit; owned by `/edit` via `_shared/pick_music.py`
- **`face-tracker` + `dynamic-zoom`** — apply zooms/pans on the edited clip
