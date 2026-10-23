# caption-clips

THE single caption skill: burns the locked **spice** caption style (the Oliver look) onto
short-form clips. There is ONE style for all footage.

> **This README is the human orientation only. `SKILL.md` is the authority** — read it for the
> actual pipeline, flags, presets, and gates.
>
> ⚠️ Rewritten 2026-08-03. The previous version documented a pipeline that no longer exists
> (a UGC/Poppins + "pro"/Proxima two-style splitter with `split_clips.py` → `transcribe.py` →
> `generate_ass.py` → `burn_captions.py`). Those styles and `generate_ass.py` were removed
> 2026-06-11; `references/styles.md` (their spec) was deleted 2026-08-03. A fresh session
> grepping this file used to find the retired pipeline first.

## The actual pipeline (one command)

```bash
python3 scripts/spice_caption.py <input.mp4> <output.mp4> [--context "guest asks, Alex answers"]
```

Chain: `transcribe_lv3` (Groq w/ coverage-heal gate) → `align_to_silence` → `oliver_format`
(text normalization, v2 spec) → `caption_director` (LLM per-word weight/size/italic stream,
with API → `claude` CLI → deterministic fallbacks) → `generate_spice --burn` (chunker +
two-layer gblur shadow composite) → `caption_qc` (blocking: refuses anything that isn't the
locked spice render).

## Presets

`presets/spice.json` is the base. Variants (`spice_alex58`, `spice_chin78`, `spice_bubble`,
`spice_alex58_white`, `spice_acq_testimonial`, `spice_longform`) declare `"extends":
"spice.json"` and carry ONLY their deltas — so the locked shadow/weights blocks live in exactly
one file. Resolution happens in `generate_spice.load_preset()`. Never copy the base again.

## Correction vocab

Review-note fixes (misheard words, casing, proper nouns) go in **`vocab/shared_vocab.json`**,
which BOTH normalizers (`oliver_format.py` and the /edit-path `spice_normalize.py`) load. Never
add a fix to only one of them — that drift shipped the same defects twice.
Per-project names (guests, companies) go through `ACQ_CAPTION_VOCAB`, not into the skill.

## Folder layout

```
caption-clips/
├── SKILL.md          ← the authority: pipeline, flags, gates, Premiere overlay mode
├── README.md         ← this file (orientation only)
├── presets/          ← spice.json base + thin `extends` variants
├── vocab/            ← shared_vocab.json (both normalizers read it)
├── references/       ← oliver_caption_formatting_spec.md is the v2 spec of record
├── scripts/          ← spice_caption.py is the entry point (see SKILL.md for the rest)
├── training/         ← frozen corpus study artifacts (not part of the runtime path)
└── fonts/            ← proxima_full/ is the live family
```

## Requirements

- An FFmpeg built with **libass** (`brew install ffmpeg-full`; the stock formula often drops it).
  The skill auto-detects a capable `ffmpeg`; `FFMPEG=/path/to/ffmpeg` overrides.
- `ANTHROPIC_API_KEY` for the caption director (falls back to the `claude` CLI, then to
  deterministic styling — confirm the log says `styled via …`, not `-> deterministic`).
