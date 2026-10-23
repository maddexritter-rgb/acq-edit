# Segment-aware single-pass captions (height + color by camera angle)

How to vary caption HEIGHT (and color) per camera angle without splitting/re-encoding the file.
Detect camera-switch boundaries ONCE, store as frame numbers, then every downstream op partitions
by a `seg_ids` array. One source, one pass, one output — segment awareness lives purely in data arrays.
(This is the generalized version of what `caption-app/worker/layout_analyze.py` + generate_spice `--layout`
already do for Y-position; documented here so color, Y, tracking, smoothing, audio all share one boundary pass.)

## The 3 data structures
1. **`_scene_frames: set[int]`** — frames where a camera switch happens. Run ffmpeg scene detection
   (`select='gt(scene,0)'`), which scores each frame 0.0–1.0 vs the previous; a hard cut scores >0.20.
   Convert each cut timestamp to a frame: `frame = int(round(timestamp * fps))`.
2. **`seg_ids: array[int]`** — length = total frame count; `seg_ids[frame]` = which segment (0,1,2,…) that
   frame belongs to. Built in the tracking loop:
   ```python
   cur_seg = 0
   for n in range(total_frames):
       if n in _scene_frames:
           cur_seg += 1          # new segment starts at each cut
       seg_ids[n] = cur_seg
   ```
3. **Per-segment processing** — any op that must be independent per camera angle uses `seg_ids` as a mask:
   ```python
   for s in range(num_segments):
       mask = (seg_ids == s)
       segment_data = all_data[mask]
       result[mask] = process(segment_data)   # write back into the full array
   ```

## Face tracking (per segment)
- At each boundary frame: reset the nearest-face tracker (`last = None`).
- Interpolate missing detections ONLY within a segment, never across a boundary.
- Smooth each segment's X values separately.
- Y-lock: `median(Y for THIS segment only)` — each speaker gets their own eyeline.

## Caption HEIGHT by angle — MEASURED from Oliver (2026-06-10, the part Maddex wants)
Measured from Oliver Albert's 24 published workshop Q&A clips (599 captioned shots —
`caption-app/training/height_study/REPORT.md`). The driver is **FACE SIZE in the final
frame, not the layout label**:

| shot (by largest face height) | caption-Y center | why |
|---|--|--|
| **WIDE** — full-body stage / audience-wide (face < 11% of frame H) | **45%** | face sits high, body fills center → caption rides over the torso |
| **TIGHT** — medium / closeup (face ≥ 11%) | **50%** | subject fills frame → caption over the chest |
| **SPLIT-screen** (stacked angles) | **50%** | in the seam between the two faces |

So Oliver uses two discrete anchors — **45% wide / 50% everything tighter** — a ~5% (≈190px
@4K) lift on wide shots. He NEVER goes below ~50% (the old `safe_y_pct` 0.60 fullscreen value
sat ~310px too low — 8.1% mean error vs 1.3% for the 45/50 rule). Encoded in
`layout_analyze.safe_y_pct()`; static no-layout default = 50% in `spice.json`.

Per segment, `safe_y_pct` is decided ONCE from the shot's **median** face height and assigned
as a clean anchor (never an average — averaging blends wide+tight flicker into a mushy ~47%
that doesn't match Oliver and can miss the jump threshold). generate_spice's `--layout` track
then gives each cue its Y by the segment its midpoint lands in.

### WHEN the height changes — FRAME-EXACT (Maddex: "the second the frame switches, or it looks shitty")
The Y must snap on the **first frame of the new shot**, never 1-2 frames late. Three precision
rules make it frame-exact (verified by `caption-app/training/height_study/qc_caption_snap.py`,
the cut "verify by the signal" principle → measured caption-snap == picture-cut, Δ=0):
1. **Cut detection runs on EVERY frame** (cheap grayscale absdiff), decoupled from the expensive
   sampled face pass. Subsampling the scene score (`--sample-every>1`) attributes a cut to the
   nearest sampled frame → snap lands 1-2 frames late. Cuts must be detected at full frame rate.
2. **After resolving speech lifetime, split only surviving caption cues that span a cut** into two events at the cut frame —
   same text, Y snaps instantly (no tween). It nudges the split time back HALF a frame so
   `ts()`'s centisecond rounding lands the new Y ON the cut frame, not the frame after.
3. The ~3-frame `tpad` audio-lead is applied AFTER the subtitle burn, so picture and caption
   shift together and stay locked — never reorder those filters.

Both the caption-app and /edit's `qa_assembly` build the `--layout` track by running
`layout_analyze` on the FINAL reframed video (so face size is measured in the delivered frame).

## Caption COLOR by angle (same mechanism)
For each segment, determine who's speaking — from diarization, or simply by which camera is active
(guest cam = guest = yellow; host cam = Alex = white). Build `color_per_seg = {0:"white",1:"yellow",…}`.
When generating the ASS, each word's frame → `seg_ids[frame]` → `color_per_seg[seg]` → that word's color.

## Key insight
Boundary detection is done ONCE and stored as frame numbers. Every downstream operation (tracking,
smoothing, Y-lock, caption height, caption color, audio mix) just partitions by `seg_ids`. Never split
the file, never re-encode intermediate pieces, never concat.

## ONE voice per cue — NEVER mix Alex (white) + guest (yellow) in one caption line (2026-06-10)
Maddex's rule, confirmed by studying Oliver: a caption cue is MONOCHROME — all white (Alex) or
all yellow (guest), never both. When Alex asks and the guest answers, the question ends on its
own line and the answer starts fresh; you must NEVER see white and yellow words on the same line.
The SPICE chunker (`generate_spice.py`) enforces this with a HARD CUE BREAK at every speaker
change (`voice_of(i) != voice_of(prev)`), and the orphan-merge step only folds a lone word into a
neighbor of the SAME voice. Bug it fixed: the char/word packer was merging the tail of one
speaker with the head of the next into a mixed line (e.g. white "oh" + yellow "not very";
"you have competitors"; "okay so what"). Verified on the BuyTheFrontEnd Q&A: 5 mixed cues → 0,
cue count unchanged (95→94). NOTE on QC: a pixel scan of the burned frame for white+yellow
FALSE-POSITIVES constantly (white shirts / the white ACQUISITION.COM logo / mic flags sit behind
the caption) — verify mixed cues on the .ass (distinct `\1c` per cue), or by eye, NOT by frame color.

## WHO SAID WHAT — per-word speaker by MIC ENERGY + turn-taking (2026-06-10, the real fix)
The "one voice per cue" break only works if each word's COLOR (speaker) is right. The original
color came from the EDL's per-CAMERA-SHOT speaker, so a short turn-reply ("yes", "cool", "no")
spoken at a boundary was tagged as whoever held the previous shot — a uniformly WRONG-colored cue
that slipped past the mixed-voice check (Maddex: Alex's "cool" was yellow; the guest's "yes" white).
Fix lives in `edit/scripts/speaker_diarize.py` (`resolve_speakers`), shared by `qa_assembly.py`
AND `qa_build.py`:
1. **MIC ENERGY = ground truth.** Q&A clips carry separate per-speaker mics (`sync.speaker_mics`).
   Map each word's clip-time → mic-source time (cumulative segdur) and compare RMS on the alex vs
   guest mic. One mic louder by ≥ **6 dB** → that speaker, full stop.
2. **CONVERSATIONAL TURN-TAKING** for the low-margin boundary words (bleed/overlap, < 6 dB): a short
   REPLY token ("yes/yeah/no/cool/okay/right/exactly/sure/…") belongs to the RESPONDER = the OTHER
   speaker from the word before it. (That's how "cool" after the guest → Alex/white, and "yes" after
   Alex's "are you the biggest?" → guest/yellow, even when the mics read ~equal.)
3. **EDL shot-speaker** only as the final fallback.
Verified on BuyTheFrontEnd: "cool"→alex(white, own line), "yes"→guest(yellow, own line),
"in australia"→guest, the whole "because yes I could buy them" answer→guest; 0 mixed-voice cues.
Debug any clip with `ACQ_DIAR_DEBUG=1` → prints per-word shot→resolved + mic dB + *FLIP* marks.

### Robustness: mic-diarization auto-falls-back when mics don't isolate (2026-06-10, swindle)
The mic-energy approach assumes the per-speaker mics actually ISOLATE the speakers. Not always true:
on swindle (NeverOutsourceSelling) the guest was barely on any mic (all 4 mics −41 to −106 dB; the
raw mix was −31 LUFS, rescued by loudnorm), and Alex's lav read ~17 dB hot even on the GUEST's words —
so naive "louder mic = speaker" flipped the guest's "enterprises/it/I" to Alex. `resolve_speakers`
now (in `edit/scripts/speaker_diarize.py`):
- **Calibrates per clip**, anchored on the EDL shot-labels: learns the midpoint between how shot-guest
  vs shot-alex words read on the mics, and only trusts the mic if those anchors actually SEPARATE
  (≥6 dB) with enough real-speech samples each. The mic decision uses `ddb` vs the calibrated `mid`
  (not vs 0), so a hot-baseline lav doesn't bias everything one way.
- **When the mics DON'T separate** (poor isolation, too few anchors) → it trusts the editor's
  shot-speaker entirely (no mic override, no turn-taking) — which is correct, because the camera
  followed the speaker. Turn-taking for quiet reply tokens fires ONLY when the mic calibrated (so it
  can't over-fire and mislabel, as it did on swindle's "right?").
- **Absolute speech floor** (−40 dB): word-tails/pauses/bleed read low on both mics and never decide.
Result: tom (good isolation) → calibrated mic + turn-taking (cool→alex, yes→guest); swindle (poor
isolation) → shot-speaker, 0 false flips. Debug: `ACQ_DIAR_DEBUG=1` prints per-word shot→resolved,
ddb vs mid, absolute mic dB, and whether the clip calibrated.


## Speech lifetime before layout segmentation

A layout boundary does not justify extending a finished phrase. First map the last
spoken word/release into the current edit clock, then apply any readability hold.
If speech has finished before a camera or layout change, cap that hold at the cut
(or earlier at the natural phrase out). Do not duplicate the old text onto the new
shot for a few frames, snap it to a different Y, or restart its animation. A clean,
caption-free pause is correct. Do not fill it merely to avoid an empty caption band.

Pass the assembly-owned picture cut frames to `build_profile_manifest` through
`picture_cut_frames` (CLI: `--picture-cuts <frames.json>`). Its `cap_hold_at_picture_cut` helper operates on whole semantic
cards BEFORE layout segmentation. Custom Filmcraft/Premiere adapters must use the
same lifetime rule, remove empty continuation pieces, and apply identical intervals
to foreground and every shadow layer. Store `speech_end_frame` from mapped source
word/release evidence. Never use an already padded caption end as speech evidence.

When speech genuinely continues across a picture change, retain the necessary
caption and semantic identity without replaying its entrance. A minimum-duration
filter must never delete a short spoken word. Check every cut for a tail-only
continuation and reject it before export; inspect the frame before, at and after the
changed boundary. Both backends obey the same rule.
