# FFmpeg recipes — clip-miner

## Audio sync (cross-correlation)

Done in `scripts/sync_audio.py` via `librosa.load` + `scipy.signal.correlate`. FFmpeg is not directly involved for offset-finding; it's a Python + scipy job because FFmpeg's `xcorrelate` filter is flaky across versions.

## Single-clip trim + audio replace + filler cuts

The `cut_clip.py` script builds one `filter_complex` that:

1. Trims each KEEP segment of the video (filler-inverse intervals within the clip window)
2. Trims the matching keep segments of the WAV
3. Concatenates them
4. Prepends black lead-in video + silent audio for N frames
5. Appends black tail + silent audio for N frames
6. Applies audio fade-in/out on the main audio (S-curve ~67ms each end)
7. Optional `lut3d` filter for color grading

Example filter_complex (2 keep segments, 3-frame pads, with LUT):
```
[0:v]trim=start=0.000:end=5.200,setpts=PTS-STARTPTS[v0];
[0:v]trim=start=5.400:end=27.89,setpts=PTS-STARTPTS[v1];
[1:a]atrim=start=0.000:end=5.200,asetpts=PTS-STARTPTS[a0];
[1:a]atrim=start=5.400:end=27.89,asetpts=PTS-STARTPTS[a1];
[v0][v1]concat=n=2:v=1:a=0[vmain];
[a0][a1]concat=n=2:v=0:a=1[amain];
color=c=black:s=3840x2160:r=29.97:d=0.100,format=yuv420p[vlead];
color=c=black:s=3840x2160:r=29.97:d=0.100,format=yuv420p[vtail];
anullsrc=channel_layout=stereo:sample_rate=44100:duration=0.100[alead];
anullsrc=channel_layout=stereo:sample_rate=44100:duration=0.100[atail];
[vmain]lut3d=file='/path/to.cube'[vgraded];
[amain]afade=t=in:st=0:d=0.067,afade=t=out:st=27.523:d=0.067[amainfaded];
[vlead][vgraded][vtail]concat=n=3:v=1:a=0[vout];
[alead][amainfaded][atail]concat=n=3:v=0:a=1[aout]
```

## Keyframe-aware seek vs frame-accurate seek

`cut_clip.py` places `-ss` AFTER each `-i` so seeks are frame-accurate (but slower — FFmpeg decodes from the nearest keyframe and discards). This is necessary because our seek targets are arbitrary speech-boundary times, not keyframes.

If you don't care about frame-accurate starts (e.g. shipping a 5-second preview), move `-ss` BEFORE `-i` — FFmpeg will seek via the container index, which is ~100x faster but lands at the nearest keyframe.

## LUT application (lut3d filter)

```bash
ffmpeg -i input.mp4 -vf "lut3d=file='/path/to/grade.cube'" -c:a copy out.mp4
```

Supports `.cube` (common) and `.3dl` (Autodesk / Davinci). Place the file path in single quotes to survive filter-graph parsing.

**Partial-strength LUT** (blend original and graded):
```
[0:v]split[a][b];
[a]lut3d=file='grade.cube'[graded];
[graded][b]blend=all_mode=normal:all_opacity=0.5[vout]
```

## Audio fade (S-curve approximation)

`afade=t=in:st=0:d=0.067` (fade-in over 67ms starting at t=0).
`afade=t=out:st=27.523:d=0.067` (fade-out ending exactly at clip-end).

The SOP asks for an S-curve — FFmpeg's default `afade` uses the `tri` curve which is linear. For a softer S:
```
afade=t=in:curve=hsin:st=0:d=0.067
```
Options: `tri`, `qsin`, `hsin`, `esin`, `log`, `ipar`, `par`, `qua`, `cub`, `squ`, `cbr`. `hsin` (half-sine) is the closest to an audio-engineer S-curve.

## Preserving 4K output

Default encode is `libx264 -preset medium -crf 18`. At 4K @ 30fps for 30s, expect output ~150 MB. Not a problem for local storage but trim down with `-crf 22` or scale-to-1080p filter for upload.

## Probe video metadata

```bash
ffprobe -v error -select_streams v:0 \
  -show_entries stream=width,height,r_frame_rate,duration \
  -of json input.mp4
```
