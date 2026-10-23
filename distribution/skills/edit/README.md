# edit

THE master clip-creation orchestrator. Raw footage in, finished short-form clips out.

## What it does

**Start here: [`RUNBOOK.md`](RUNBOOK.md)** — the single execution standard (its top block is the
copy-paste master prompt). `SKILL.md` is the reference library and law behind it.

One universal spine (steps 0–10) for ALL footage types — monologue, Q&A, hotline, podcast, multicam:

```
scaffold → source-intel → detect → transcribe → mine → pick → validate →
cut + clean → QC → DELIVERY MODE (8B Premiere timeline = default · 8A headless render)
→ re-QC → non-negotiables → 6 parallel audits → deliver
```

Two branch points: **speaker count** (1 vs 2) and **camera count** (1 vs multi). Everything else is the same.

## Inputs

- Raw footage (MP4/MOV, any resolution)
- Optional: separate lav/mic WAVs, EDL, sync config

## Outputs

Finished clips in `~/Downloads/<brand>/YYYY-MM-DD_<slug>/20_DELIVER/`, ACQ-named.

## Downstream skills (this skill orchestrates, they own their capability)

| Skill | Capability |
|---|---|
| `horizontal-to-vertical` | Face-tracking + 16:9→9:16 reframe |
| `caption-clips` | SPICE captions (Proxima Nova, per-word emphasis) |
| `cut` | MFA forced-alignment precision cutting |
| `render` | Manifest-driven, stage-cached build (route 8A headless) |
| `source-intel` | Pre-edit footage analysis (faces, cameras, audio) |
| `mozi-sf-audit` · `scorecard-audit` | Mechanics + narrative audit gates |
| `audit-visual` · `audit-audio` · `audit-captions` · `audit-script` | The 4 tunnel-vision audit agents |
| `monday` | Frame.io + Monday delivery (explicit push only) |
| `_shared/` | Shared engines (speech_map_cut, precision_cut, fast_encode, window_validator, asr, parallel) |

## Key rule

This skill ORCHESTRATES. It owns mining, boundary-picking, filler surgery, and the delivery handoff. For each downstream step it says "use skill: X" — it never duplicates their instructions.

## Usage

In Claude Code: `/edit` or ask for clips.

## Dependencies

- FFmpeg (with libass)
- Python 3.10+
- Groq API key (for transcription) or faster-whisper (local fallback)

## Note on `assets/`

The `assets/` directory (overlay / transition / text media packs, ~11GB) is **gitignored** —
it's binary media, not skill logic, and exceeds GitHub's file-size limits. Those packs live
locally only. Everything that defines the skill's behavior (SKILL.md, `references/`, `config/`,
`presets/`, `prompts/`, `scripts/`, `luts/`) is tracked.
