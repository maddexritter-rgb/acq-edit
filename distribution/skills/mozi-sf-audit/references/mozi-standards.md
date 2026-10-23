# Team Alex V1 MVP Standards (Mozi Media)

Source: Mozi Media's Team Alex SF V1 MVP Standards. Verbatim 16-point checklist + exceptions. Last updated 2026-05-04 (added items #3 placement, #4 dialogue-sync, #9 music balance per Oliver Albert feedback).

## Review gate

- ✅ **Edit meets standards** → move to "Final Review"
- ❌ **Edit does not meet standards** → add review notes, move to "Needs Revision"

## Subtitles

### 1. No spelling errors / missing / double words
Whatever Alex says should be shown in the subtitles.

**Exceptions:**
- Filler words may be removed: "like..", "uhm", "you know", "so", etc.
- Complex wording may be simplified

### 2. No blank gaps between each subtitle
Subtitles should flow continuously. Exception: intentional pauses of >1s–2s are fine (they create emphasis).

**Audit threshold:** any gap > 0.05s (≈1.5 frames @ 30fps) and < 1.0s flagged. >1s = treated as intentional pause.

### 3. Default subtitle placement on the lower half of the screen
- Subtitle anchor must be in lower half (y > height/2)
- Must NOT cover the subject's mouth/face

### 4. Subtitle timing matches the timing of dialogue
Cues should appear within ~1–3 frames (33–100ms @ 30fps) of the dialogue actually being spoken. Not earlier, not later.

**Audit method:** silencedetect maps speech regions; flag any cue displayed >50% during a silence interval.

### 5. All words lowercased by default
Exceptions:
- Proper nouns / names (people, products, brands, places)
- The pronoun "I" and its contractions: "I", "I'm", "I'll", "I've", "I'd"

### 6. Alex's subtitles differently colored than guest/caller subtitles
Standard Team Alex styling:
- **Alex:** white
- **Guest / caller:** yellow italic

### 7. All subtitles within the UI safezone
Frame.io reference: inside the clip, press the "G" key 4 times for a 9:16 safezone overlay.

Danger zones (Instagram reel 1080x1920):
- Top 13% — username overlay, back button
- Bottom ~18% — likes / comments / share / caption
- Sides ~5% — minor, still avoid

## Audio

### 8. Audio levels around -6dB
Flag if it sounds quiet. Peak should be in the -8 to -3 dBFS range.

### 9. Music shouldn't be loud enough to drown out dialogue
If music is present, it must be ducked under speech. Heuristic: clip should still drop below -30 dB during dialogue gaps. If audio never drops below -30 dB, music is likely too loud.

### 10. No overly compressed audio
The audio should still have dynamic range. Over-compression = "pumping" or "wall of sound" flat quality.

### 11. No audio clipping
No samples at or near 0 dBFS. If peaks are hitting -0.5 dBFS or higher, the audio was likely clipped.

### 12. No audio pops / clicks
Check:
- Very beginning of clip (first 100ms)
- Very end of clip (last 100ms)
- Any cut point where the editor joined two audio clips

## Video

### 13. Alex always centered in the frame
Rule of thumb: Alex's face should stay within the center 40% of the frame width for >90% of the clip's duration. Brief (<1s) movements out of center are fine.

### 14. Enough space at top of frame so Alex isn't cut off by UI overlay
Top-of-head padding should be at least 13% of frame height (≈250px on 1920).

### 15. No dead spaces / black frames
Most common at the beginning, end, or mid-clip cut joins. Any black frame >2 consecutive frames (~66ms at 30fps) flagged.

### 16. ~3 video frames at the beginning before audio comes in
Why: gives the viewer a moment to "land" on the video during the swipe, and avoids an audio pop from an abrupt start.

**Range:** 3–5 frames (100–166ms @ 30fps) of silent video lead. **More than 5 frames = the cut included pre-speech silence; tighten the head.**

## Quick summary (from PDF)

1. Spelling errors?
2. Gaps in subtitles?
3. Subtitle timing?
4. All words lowercased?
5. Subtitle color?
6. Audio quiet?
7. Music too loud?
8. Audio compressed/clipping?
9. Audio pops?
10. Alex off-center/out of frame?
11. Any dead frames?
12. 3 video frames at the beginning before the audio starts?
13. Anything cut off by/overlapping with UI?

## How the audit skill maps to these

The `mozi-sf-audit` skill automates:
- Check 1 (spelling) — pyspellchecker + proper-noun whitelist
- Check 2 (gaps) — subtitle timing diff > 0.05s flagged
- Check 3 (lower-half placement) — y-anchor parsed from .ass; face overlap manual
- Check 4 (dialogue sync) — silencedetect intervals vs cue display windows
- Check 5 (lowercase) — regex
- Check 6 (color) — .ass style parse
- Check 7 (safezone) — bbox intersection with platform safe zones
- Check 8 (levels) — ffmpeg volumedetect
- Check 9 (music balance) — silencedetect heuristic
- Check 10 (compression) — LUFS LRA analysis
- Check 11 (clipping) — astats sample_peak
- Check 13 (centered) — face detection across frames
- Check 14 (top padding) — face-detection top-of-head metric
- Check 15 (dead frames) — blackdetect
- Check 16 (3-frame lead) — silencedetect at clip head

Surfaced for manual eye:
- Check 12 (pops) — surfaces likely-pop timestamps for listen
