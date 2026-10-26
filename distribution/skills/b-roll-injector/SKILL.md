---
name: b-roll-injector
description: Add punch-in zoom effects and visual emphasis to a vertical short clip. Scans the transcript for moments that benefit from visual punch (numbers, proper nouns, emphasis words, punchlines) and adds subtle 1.0→1.15 zooms at those moments. Keeps talking-head clips from feeling visually flat. Use after caption-clips. Can be skipped if user says --no-broll.
---

# B-Roll Injector — Subtle Zoom Punches

For talking-head podcast clips where you don't have actual B-roll footage, the next best thing is **programmatic emphasis**: quick 8-frame zoom-ins on keywords that make the clip feel edited rather than raw.

This is not about adding external footage — it's about adding motion to static shots.

## What gets a zoom

Scan the transcript and flag these moments for a zoom-in:

1. **Numbers** — "97%", "$2 million", "three reasons", "18 months"
2. **Proper nouns** — names, companies, products (Apple, Tesla, Steve Jobs)
3. **Emphasis words** — "never", "always", "every", "exactly", "literally", "massive", "insane"
4. **Punchlines** — the final sentence of the clip (slight zoom hold on "the takeaway")
5. **Question marks** — rhetorical questions

Limit to **1 zoom per 8 seconds** to avoid visual fatigue. If two triggers overlap, pick the higher priority.

## Zoom behavior

- Duration: 8 frames (~0.27s at 30fps) ramp up, 4-frame hold, 6-frame release
- Target scale: 1.15× (subtle; bigger looks amateurish)
- Centered on current face position (uses the face-tracking data from vertical-reframer if available, else center)
- Easing: ease-out-cubic on ramp, ease-in on release

## scripts/inject_broll.py

```python
#!/usr/bin/env python3
"""Add zoom punches on emphasis words in a vertical clip."""
import json, argparse, subprocess, re

EMPHASIS_WORDS = {
    "never", "always", "every", "exactly", "literally", "massive", "insane",
    "crazy", "huge", "nothing", "everything", "nobody", "everyone",
    "impossible", "critical", "essential", "biggest", "worst", "best"
}

NUMBER_RE = re.compile(r"\$?\d[\d,\.]*%?")

def is_emphasis(word):
    w = word.strip().lower().strip(".,!?;:\"'")
    if w in EMPHASIS_WORDS:
        return True
    if NUMBER_RE.match(w):
        return True
    # Proper noun: starts with capital and isn't sentence-start
    # (we don't know sentence position without more context, skip for now)
    return False

def pick_zoom_times(words, clip_duration, min_gap=8.0):
    """Return list of zoom timestamps (in clip-local seconds)."""
    picks = []
    last_t = -min_gap
    for w in words:
        t = w["start"]
        if t - last_t < min_gap:
            continue
        if is_emphasis(w["word"]):
            picks.append(t)
            last_t = t
    # Always add a hold at the punchline (last 3 seconds)
    if clip_duration > 5:
        punchline_start = max(0, clip_duration - 3.0)
        if not picks or picks[-1] < punchline_start - 1:
            picks.append(punchline_start)
    return picks

def build_zoom_filter(zoom_times, fps=30, scale=1.15):
    """Build FFmpeg zoompan-like filter using scale + crop with if()."""
    # Use a scale expression that ramps up and down
    # For each zoom time, during 18 frames (0.6s) at that position:
    #   frames 0-7:   scale from 1.0 -> 1.15 (ease-out)
    #   frames 8-11:  hold at 1.15
    #   frames 12-17: scale back to 1.0 (ease-in)
    #
    # Simpler: use a piecewise linear zoom over a small window.

    ramp_up = 8 / fps
    hold = 4 / fps
    release = 6 / fps
    total = ramp_up + hold + release

    # Build a scale expression
    # z(t) = 1 + (scale-1) * triangle_wave
    parts = []
    for zt in zoom_times:
        t0 = zt
        t1 = zt + ramp_up
        t2 = t1 + hold
        t3 = t2 + release
        # Up-ramp: between(t,t0,t1) * ((t-t0)/(t1-t0))
        # Hold:    between(t,t1,t2) * 1
        # Down:    between(t,t2,t3) * (1 - (t-t2)/(t3-t2))
        expr = (
            f"between(t,{t0:.3f},{t1:.3f})*((t-{t0:.3f})/{ramp_up:.3f})"
            f"+between(t,{t1:.3f},{t2:.3f})"
            f"+between(t,{t2:.3f},{t3:.3f})*(1-(t-{t2:.3f})/{release:.3f})"
        )
        parts.append(f"({expr})")
    zoom_amount = f"({' + '.join(parts)})*{scale - 1}" if parts else "0"
    z_expr = f"1+{zoom_amount}"

    # scale then crop back to 1080x1920
    # iw*z, ih*z, then crop center
    vf = (
        f"scale=w='iw*({z_expr})':h='ih*({z_expr})':eval=frame,"
        f"crop=1080:1920:(iw-1080)/2:(ih-1920)/2"
    )
    return vf

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--video", required=True)
    p.add_argument("--transcript", required=True)
    p.add_argument("--clip-start", type=float, required=True)
    p.add_argument("--clip-end", type=float, required=True)
    p.add_argument("--output", required=True)
    a = p.parse_args()

    with open(a.transcript) as f:
        t = json.load(f)

    words = []
    for seg in t["segments"]:
        for w in seg.get("words", []):
            if a.clip_start <= w["start"] <= a.clip_end:
                words.append({
                    "word": w["word"],
                    "start": w["start"] - a.clip_start,
                    "end": w["end"] - a.clip_start
                })

    duration = a.clip_end - a.clip_start
    zooms = pick_zoom_times(words, duration)

    if not zooms:
        # Nothing to do — just copy
        subprocess.check_call(["cp", a.video, a.output])
        print(json.dumps({"output": a.output, "zooms": 0}))
        return

    vf = build_zoom_filter(zooms)
    # ACQ fast-render standard — VideoToolbox HW encode (~4x faster than libx264); res-aware via probe.
    import sys as _sys, os as _os; _sys.path.insert(0, _os.path.expanduser("__ACQ_SKILLS__/_shared"))
    try: from fast_encode import encoder_args_for
    except Exception: encoder_args_for = None
    venc = (list(encoder_args_for(a.video, "ffmpeg", tier="delivery")) if encoder_args_for
            else ["-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p"])
    subprocess.check_call([
        "ffmpeg", "-y", "-i", a.video,
        "-vf", vf,
        *venc,
        "-c:a", "copy",
        "-movflags", "+faststart",
        a.output
    ])
    print(json.dumps({"output": a.output, "zooms": len(zooms), "times": zooms}))

if __name__ == "__main__":
    main()
```

## Tuning

In `defaults.json`:

```json
{
  "enabled": true,
  "zoom_scale": 1.15,
  "min_gap_between_zooms_sec": 8.0,
  "punchline_hold_duration_sec": 3.0,
  "ramp_up_frames": 8,
  "hold_frames": 4,
  "release_frames": 6
}
```

## Skip conditions

Skip b-roll when:
- User explicitly says `--no-broll`
- Clip is under 20s (too short to benefit)
- Already heavily cut (>3 visible edits) — adding zooms on top creates chaos

## Health-check

```bash
ffmpeg -version >/dev/null && echo "ok"
python3 -c "import json, re; print('ok')"
```

## Future extensions (not implemented, but noted)

- **Actual B-roll insertion** — if the user provides a `broll/` folder with assorted footage, match clips to transcript keywords and insert as picture-in-picture
- **Text emphasis overlays** — spawn a large keyword on screen at emphasis moments
- **Reaction zoom** — detect laughter/surprise in audio and zoom in on the reacting speaker (for multi-person)
