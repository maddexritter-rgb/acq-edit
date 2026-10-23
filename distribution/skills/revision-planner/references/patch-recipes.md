# Patch Recipes

ffmpeg + Python recipes for every auto-patchable issue category. Used by `revision-planner/scripts/planner.py`.

Each recipe is expected to:
- Take an input `.mp4` (and optionally `.ass`)
- Produce a patched output file
- Return exit 0 on success, non-zero on failure

All intermediate files go into `_patching/` next to the v1 clip. The final `v2.mp4` is written alongside `v1.mp4`.

---

## subtitle-text patches

### `patch_subtitle_lowercase(ass_path, word, approx_time_sec)`
Find the `.ass` Dialogue line whose time range contains `approx_time_sec` AND whose text contains `word`. Replace `word` with `word.lower()` in that line only.

### `patch_subtitle_typo(ass_path, from_word, to_word, approx_time_sec=None)`
Find lines containing `from_word`, replace with `to_word`. If `approx_time_sec` is given, restrict to lines whose time range includes it.

### `patch_subtitle_missing_word(ass_path, text_before, missing_word, text_after, approx_time_sec)`
Insert `missing_word` between `text_before` and `text_after` in the matching line.

### `patch_subtitle_double_word(ass_path, word, approx_time_sec)`
Find doubled-word pattern `word word` and collapse to single `word`.

After any subtitle-text patch, the burner must re-run on the updated `.ass` to produce a new `.mp4`.
The burner is `caption-clips/scripts/burn_captions.py` (it replaced the removed `caption-burner`
skill, and its interface is different: the video and the `.ass` are POSITIONAL, and `--start`/`--end`
are REQUIRED because the tool trims out of a source while it burns).

Here the input is an **already-cut v1 clip**, so the whole clip is the range: `--start 0` and
`--end` = the v1 clip's duration in seconds (read it with `ffprobe -show_entries format=duration`):

```bash
python3 __ACQ_SKILLS__/caption-clips/scripts/burn_captions.py \
  <v1_clip>.mp4 \
  <v1_subtitles>.patched.ass \
  --start 0 \
  --end <v1_clip_duration_sec> \
  --out _patching/<slug>.reburn.mp4
```

Pinned by `tests/test_reburn_contract.py`, which checks every documented flag against the burner's
real argparse interface and runs an end-to-end burn.

---

## subtitle-timing patches

### `patch_subtitle_gap(ass_path, between_line_a, between_line_b)`
Set `lineB.start = lineA.end + 0.01` to close the gap. Don't close gaps > 1s (those are intentional pauses).

### `patch_subtitle_duration(ass_path, line_idx, new_duration_sec)`
Adjust `line.end = line.start + new_duration_sec`.

---

## subtitle-style patches

### `patch_subtitle_color(ass_path, style_name, new_color_bgr)`
Edit the `[V4+ Styles]` block, find row where first field == `style_name`, update `PrimaryColour` to `&H00<BBGGRR>` format.
Common colors:
- White: `&H00FFFFFF`
- Yellow: `&H0000FFFF`
- Red: `&H000000FF`
- Black: `&H00000000`

### `patch_subtitle_position(ass_path, style_name, new_margin_v)`
Update `MarginV` for that style. Higher number = further from bottom (for bottom-aligned styles).

### `patch_subtitle_font(ass_path, style_name, new_font)` ⚠️
Changing font requires the font to be installed. Mark as unsafe; produce edit brief instead.

---

## audio-levels patches

### `patch_audio_normalize_peak(clip_path, target_db=-6)`
Bring the peak closer to target:
```bash
# Measure current peak
current_peak=$(ffmpeg -i $clip -af volumedetect -vn -f null - 2>&1 | grep max_volume | awk '{print $5}')
# Compute adjustment
adjust=$(echo "$target_db - $current_peak" | bc)
# Apply
ffmpeg -y -i $clip -af "volume=${adjust}dB" -c:v copy $out
```

This is the simplest fix for "audio too quiet" (re-audit should pass).

### `patch_audio_loudnorm(clip_path, target_lufs=-14)`
Full EBU R128 loudness normalization (better but slower):
```bash
ffmpeg -y -i $clip -af "loudnorm=I=${target_lufs}:TP=-1.5:LRA=11" -c:v copy $out
```

### `patch_audio_declip(clip_path)`
Soft limiter to rein in clipping:
```bash
ffmpeg -y -i $clip -af "alimiter=limit=-1.0dB:attack=5:release=50" -c:v copy $out
```

### `patch_audio_dynaudnorm(clip_path)` (use sparingly)
For "pumping" / over-compressed audio — doesn't always help, can make it worse. Only run if audit's LRA is <3.

---

## video-timing patches

### `patch_trim_black_at_end(clip_path)`
Use audit's `check_black_frames` output to find the last non-black frame, trim to there:
```bash
# If audit says black from 0:41.9 to 0:42.1, trim to 0:41.9
ffmpeg -y -i $clip -t $cutoff_sec -c copy $out
```

### `patch_trim_black_at_start(clip_path)`
Symmetric to above — find first non-black frame, start from there.

### `patch_add_lead_frames(clip_path, frames=3)`
Prepend N frames of silent black (or repeat frame-1) before the current start. Avoids audio pop:
```bash
# Generate 3 frames of silent video (ACQ fast-render: VideoToolbox HW H.264, ~4x faster than libx264)
ffmpeg -y -f lavfi -t 0.1 -i "color=c=black:s=1080x1920:r=30" -f lavfi -t 0.1 -i anullsrc \
  -c:v h264_videotoolbox -b:v 14M -tag:v avc1 -pix_fmt yuv420p -c:a aac _patching/lead.mp4
# Concat
ffmpeg -y -i "concat:_patching/lead.mp4|$clip" -c copy $out
```

Better alternative: duplicate the first frame N times (avoids a visible black cut):
```bash
ffmpeg -y -i $clip -vf "tpad=start_duration=0.1:start_mode=clone" -af "apad=pad_dur=0.1" $out
```

### `patch_trim_to_range(clip_path, start_sec, end_sec)`
Trim a clip to a new time range. Use for "cut off the last 2 seconds" style feedback.

---

## Which patches stack

Subtitle patches always go first (they change the `.ass`, which then gets re-burned).

Sequence:
1. `.ass` edits → `_patching/<slug>.patched.ass`
2. caption-clips reburn (`burn_captions.py`) → `_patching/<slug>.reburn.mp4`
3. video-timing edits → `_patching/<slug>.timed.mp4`
4. audio edits → `<slug>.v2.mp4` (final)

Each stage reads the previous stage's output. If a stage is skipped (no issues in that category), pass through unchanged.

---

## Confidence thresholds

Auto-patching is safe only if:
- Classification confidence ≥ 0.7 — don't patch ambiguous issues
- Issue has a concrete target — don't patch "make it better," only "fix X at 0:08"
- Patch recipe exists for the category — video-content issues NEVER auto-patch

When in doubt, skip the patch and add to the edit brief. False-patch is worse than manual fix.
