---
name: broll-cutaway
description: Insert full-screen cinematic B-roll cutaways into a vertical short — each one replaces the whole 9:16 frame with cropped-to-fill footage for ~2s, bracketed by a white flash-in → diagonal glare-sweep → flash-out so the cut reads as intentional and premium (not a raw jump). This is REAL footage insertion (sourced + eyeballed for quality), NOT the punch-in zooms of b-roll-injector. Captions get burned AFTER, on the output (2-pass), via caption-clips. Use when the user says "add b-roll", "insert b-roll", "b-roll cutaway", "add footage to this clip", "cinematic cutaway", "flash transition b-roll", "make this less flat with footage", or hands over a finished vertical clip and wants premium full-screen inserts on specific lines. Trigger keywords broll, b-roll, cutaway, insert footage, add b-roll, cinematic b-roll, flash glare transition, full-screen insert, footage overlay.
---

# B-Roll Cutaway — full-screen footage inserts with a flash/glare transition

The look: on a key line the whole frame cuts to cropped-to-fill cinematic footage for ~2s, with a white **flash-in → diagonal glare sweep → flash-out** hiding the in/out cuts, captions still riding on top. It makes a flat talking-head clip feel directed. Reverse-engineered from a founder short Maddex signed off on ("premium and cinematic").

> **Sibling skills.** `b-roll-injector` = subtle punch-in ZOOMS on a static shot (no footage). **This skill = actual FOOTAGE cutaways.** `caption-clips` = captions, burned AFTER this (2-pass).

## The 5-step workflow

### 1. Pick the moments (1 insert per ~8–12s; don't bury the speaker)
Read the transcript. Insert footage ONLY where it adds something the face can't — a thing being named/described (the *product*, the *money*, the *mentor*, the *place*). Leave conversational/emotional lines on the speaker's face. 3–4 inserts in a 50–60s clip is plenty. A person *is* the right visual for "talking / listening" — don't force stock there.

### 2. Source it — and EYEBALL it (premium is a human call)
```bash
S=__ACQ_SKILLS__/broll-cutaway/scripts
python3 $S/fetch_broll.py --search "cinematic <topic> b-roll 4k" --n 6     # list candidates
python3 $S/fetch_broll.py --id <VIDEO_ID> --sections "*0-90" --out src     # 4K, video-only chunk
python3 __ACQ_SKILLS__/watch/scripts/contact_sheet.py src.webm --n 16 --cols 4   # LOOK at the PNG
```
Reject anything stocky, **watermarked** (Envato/Shutterstock/iStock), or low-res. Prefer 4K, shallow depth of field, real cinematic grade. You cannot automate "premium" — open the sheet and judge with your eyes.

### 3. Build the insert spec (`inserts.json`)
```json
[
  {"src": "code.mp4",   "at": 4.8,  "in": 7.0,  "dur": 2.0},
  {"src": "mentor.mp4", "at": 9.4,  "in": 0.0,  "dur": 2.0},
  {"src": "money.mp4",  "at": 37.3, "in": 23.0, "dur": 2.0}
]
```
`at` = where on the BASE timeline · `in` = in-point inside the source · `dur` = length (default 2.0). Land `at` on the word/phrase. **Place inserts AFTER any hook/title that's still fading** — a full-screen insert will clip it mid-fade.

### 4. Composite (auto-crop to fill + flash/glare + VideoToolbox)
```bash
python3 $S/insert_broll.py --base CLIP.mp4 --out CLIP_broll.mp4 --spec inserts.json
```
Sources are auto-cropped to fill the base 9:16 frame. The flash/glare overlay is generated per duration and cached in `~/.cache/broll-cutaway`. Encodes via the ACQ VideoToolbox standard (`_shared/fast_encode.py`). Base audio is preserved. Use `--no-transition` for hard cuts, or `--insert src=..,at=..,in=..,dur=..` for one-offs without a JSON file.

### 5. Captions LAST (2-pass)
Burn captions on the OUTPUT, never before — a subtitles filter as the last node eats the overlay pad:
```bash
# via the caption-clips skill, or directly:
ffmpeg -y -i CLIP_broll.mp4 -vf "subtitles=captions.ass:fontsdir=<FONTS>" \
  -c:v h264_videotoolbox -b:v 14M -tag:v avc1 -pix_fmt yuv420p -c:a copy FINAL.mp4
```
If you already have an approved audio mix (e.g. voice+music) on another version of the same-length clip, you can graft it on instead of re-mixing:
```bash
ffmpeg -y -i FINAL_videoonly.mp4 -i APPROVED_with_music.mp4 -map 0:v -map 1:a -c copy FINAL.mp4
```

## Verify (always)
Pull stills at each insert + its flash frames and LOOK:
```bash
for t in <at> <at+1> <at+dur>; do ffmpeg -y -ss $t -i FINAL.mp4 -frames:v 1 /tmp/c$t.png; done
```
Check: the vertical crop didn't decapitate the subject; the flash hides BOTH cuts; captions sit on top of the footage.

## Gotchas (learned the hard way)
- **Eyeball the footage.** Most "b-roll 4k" results are stocky or watermarked; the cinematic ones are rarer. Never ship without looking at a contact sheet.
- **Vertical crop** of a 16:9 shot can cut a head/subject off — spot-check the cropped still.
- **Captions after, 2-pass.** Never inline subtitles in the overlay pass.
- **Place inserts after a fading hook/title**, or the insert clips it mid-fade.
- **VideoToolbox** via `_shared/fast_encode.py` — never hand-write libx264 (the script handles it).
- Keep `dur` ≥ ~1.2s so flash-in and flash-out don't overlap.

## Tuning the transition (scripts/gen_transition.py)
Standalone, if you want a custom look (slant, streak softness, flash intensity, duration):
```bash
python3 $S/gen_transition.py --out xn.mov --dur 2.0 --glare-angle 0.30 --glare-width 95 --flash 238
```

## Health-check
```bash
python3 -c "import numpy, PIL; print('deps ok')" && ffmpeg -version >/dev/null && yt-dlp --version
```
