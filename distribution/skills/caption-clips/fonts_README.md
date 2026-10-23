# Fonts

Drop your font files into this folder. FFmpeg reads them via `fontsdir=` in the subtitles filter — no system install needed.

## Required

### UGC style (`presets/ugc.json`)
- `Poppins-SemiBold.ttf` — [Google Fonts](https://fonts.google.com/specimen/Poppins), free.

### Pro style (`presets/pro.json`)
- `ProximaNova-Medium.otf`
- `ProximaNova-Semibold.otf`
- `ProximaNova-Bold.otf`
- `ProximaNova-BoldIt.otf`

Proxima Nova is a paid font — buy from [Mark Simonsson](https://www.marksimonson.com/fonts/view/proxima-nova) or your Adobe Fonts / Monotype subscription. You are responsible for your own license when redistributing this skill.

## Filename ≠ family name

The **filename** must match what's in the preset's `file` field (e.g. `ProximaNova-Bold.otf`). The **family name** (used inside the `.ass` `\fn` tag) must match what's in the preset's `family` field and what's embedded in the font's metadata.

Use `ffprobe`/`fc-query` to check the actual family name inside a font:

```bash
fc-query -f '%{family[0]} — %{style[0]}\n' fonts/ProximaNova-Bold.otf
```

If `fc-query` isn't installed:

```bash
python3 -c "from fontTools.ttLib import TTFont; t = TTFont('fonts/ProximaNova-Bold.otf'); print([r.toStr() for r in t['name'].names if r.nameID in (1,4,16)])"
```

If the name doesn't match your preset's `family` field, edit the preset.

## Adding your own style with a different font

1. Drop the `.ttf`/`.otf` files here.
2. Copy a preset in `../presets/` and change the `family` / `file` fields.
3. Run the skill with `--preset presets/yourstyle.json --style yourstyle`.
