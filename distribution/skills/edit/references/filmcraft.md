# Filmcraft execution

This is an execution route, not a second editorial system. The current source-word selection, compiled literal dialogue, inspected paired-sample decisions and owning skills' finishing plans remain authoritative.

## Code and configuration

- `edit/scripts/filmcraft_client.py`: isolated headless MCP transport, receipts and command discovery. Explicit binary and session paths; no hardcoded workspace or brand; no blind retry after an uncertain response.
- `assembly-design/scripts/apply_filmcraft_assembly.py`: canonical source-linked assembly adapter. Uses the existing word compiler, paired-seam solver and word-coverage validator. Creates a **new** `.fcproj` in a new output directory, then reopens and checks frame/sample geometry, continuity, source clocks and native links. It never overwrites a reviewed project.
- Existing Premiere code and `apply_native_assembly.py` remain the Premiere route; follow [Premiere startup](premiere_start_here.md) and [execution contract](premiere_execution_contract.md).

Keep machine-specific binary/repository locations and tested finishing adapter paths in the project's `10_WORK/filmcraft-backend.json`, not skill text. Record repository commit, local patch hash, adapter code hashes and capability limits. Preserve the tested code alongside the project; do not rely on recollecting transient commands. Revalidate after an engine or adapter change.

Discover commands rather than guessing:

```bash
python3 edit/scripts/filmcraft_client.py --binary /path/to/filmcraft-cli \
  --session /project/10_WORK/new-discovery --tool command_list
```

The client exposes `tool(name, args)` and `run(command, params)`. Available interfaces include `media_import`, `sequence_inspect`, `render_frame`, `command_run`, and job polling. Inspect the installed command schema before a new operation. `file.exportMedia` starts a job; wait for `jobs.list` completion and verify the file. Closing an active export is refused. An uncertain mutation requires inspection/reconciliation before another attempt.

## Assembly packet

Pass JSON with explicit `compiled`, `clip_id`, `decisions`, `routing`, `picture`, `audio`, optional `phonemes` and `title`. Paths are absolute. `compiled` is the existing v2 design's `compile_assembly.py` output; `decisions` is `edit.paired-seam-decisions/v1`, not timestamp-only proposals. Routing JSON contains `media` (played PCM), `picture`, zero-based `stream`/`channel`, `source_clock_offset_samples: 0`, and `evidence: {path, sha256}` identifying the source-clock/routing comparison.

```bash
python3 assembly-design/scripts/apply_filmcraft_assembly.py \
  --packet /project/10_WORK/filmcraft-assembly.json \
  --binary /path/to/filmcraft-cli --out /project/10_WORK/new-assembly
```

Use `--validate-only` to inspect without launching the engine. Read the compiler's joined dialogue and continuation before execution. Partial locator conflicts retain their actual local review status; no helper certifies listening.

The initial adapter supports constant source/sequence frame rate, unit speed, one video source and mono/stereo matched-rate PCM. Its paired solver requires an integer samples-per-frame grid; unsupported clocks/mixes must be explicitly conformed or handled by a verified precision route, never rounded silently. Original picture and decoded WAV must share source zero. The adapter's independent audio placement preserves the shared source clock and existing AV links.

Use a separate matched-rate PCM WAV for Filmcraft dialogue until that installed codec path is verified. A tested Matroska PCM route introduced a small rendered offset despite correct timeline numbers; do not generalize container metadata or successful import into sample accuracy. Compare native PCM export with intended source samples and decoded delivery audio, especially around every join. No fixed compensating offset belongs in this skill.

## Finishing and revisions

→ Use skill: `horizontal-to-vertical` for the framing plan; `caption-clips` for semantic cards/style; `music` when applicable; `render` for manifest/cache execution. Filmcraft adapters translate those outputs into native Motion/text/audio operations. They do not replace the owners' decisions with a local selector or keyword caption director.

Use the tested finishing adapters pinned in `filmcraft-backend.json` within their stated capability limits. For caption appearance and the canonical native shadow helper, → Use skill: `caption-clips` [Filmcraft route](../../caption-clips/references/filmcraft_captions.md). Update old project-local caption adapters to that helper before reuse and record its hash. Native italic still differs from ASS shear; visually check the requested style on a new font or layout. Preserve current card geometry and timing.

Render/export headlessly from the editable project. Save/reopen; verify source/timeline ticks, frame counts, sample mapping, caption text/timing and rendered framing. A correct command receipt is insufficient. Use the pre-render command wrapper below, then one file-integrity check; no model audit loop by default. Keep native, rendered, acoustic and human approval statuses separate.

For revisions, snapshot the current project/sequence, read actual native items and modify only the requested layers. The fresh-construction adapter is not a revision tool. Keep a combined flat review timeline and stable clip IDs; do not regenerate old selections over manual edits. Premiere interchange remains a separate tested capability, not an assumed property of `.fcproj` output.

For scoped delivery metadata housekeeping, run `edit/scripts/sanitize_delivery.py`
on a new export copy and verify the exact sanitized bytes, as in
[the delivery export procedure](native-export.md). Preserve the original native export.

## Pre-export completeness

Before expensive caption/video export, require one framing result for every current
picture span and verify exact ordered source ranges, not only counts. Reuse the owning
reframe skill's `track_item(..., cache_dir=...)`; never trust a bare tracking list left
by an earlier revision. Use Assembly Design's deterministic construction check first;
a second ASR call is only for a concrete unresolved source ambiguity. Any
word repair changes the current input revision before dependent work starts. Build
against an immutable revision and publish outputs only after its checks complete;
a concurrent edit must start a new revision, never change inputs beneath a renderer.

→ Before export follow [pre-render construction](../../assembly-design/references/pre-render-construction.md), including the guarded exporter command. Wrap it in the [run clock](timed-execution.md). The same contract applies to Premiere; preserve each backend’s native scope and lease requirements.
