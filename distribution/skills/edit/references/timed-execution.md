# Timed construction is the default

First executable action on an editing request: initialize the clock in the current
workspace, before other skill reading, feedback inspection, downloads or project
scaffolding. If a parent `/edit` run already has a clock, reuse it. Never reset the
clock at render start. If startup happened before initialization, explicitly report
that omission; do not backdate it or claim complete measurement.

Use the skill's actual installed location for the commands below:

```bash
python3 edit/scripts/run_clock.py --log /workspace/run-unique/events.jsonl init --cache-state cold
python3 edit/scripts/run_clock.py --log /workspace/run-unique/events.jsonl phase feedback_and_design
python3 edit/scripts/run_clock.py --log /workspace/run-unique/events.jsonl run --stage source_ingest -- python3 /path/to/ingest.py
```

Switch foreground phase **before** each stage: intake/skill reading, feedback,
source ingest, editorial construction, boundary resolution, framing/captions,
pre-render preparation, native execution/export, integrity, and delivery. Phases
include reasoning, manual inspection, tool overhead and waiting; they partition
wall time. Wrap each executable operation with `run --stage NAME -- COMMAND ...`.
A bridge wrapper must wait for its actual asynchronous job completion, not merely
submission. For direct MCP calls record the containing foreground phase and actual
job timings from the backend; do not invent per-call durations.

Failures keep their return code and elapsed time. Retry in the same clock. An
interrupted command remains visible as unfinished. Do not restart the log after
context loss, an error or resuming a job. Do not log credentials or raw command
arguments. Explicit user pauses count in wall time; label them as a separate phase.

After the playable review page/files and timeline have been verified and shown:

```bash
python3 edit/scripts/run_clock.py --log /workspace/run-unique/events.jsonl finish > /project/10_WORK/timing.json
```

The first phase starts at initialization; no foreground time after that is
unattributed. Phase timing is not the same as individually timed model thoughts.
Use `report` for an in-progress snapshot; `finish` is one-way. Report total elapsed,
phase times, overlapping command durations, failures, first-playable timestamp and
cache state. Never sum overlapping operations into wall time. Label warm-source
replays separately from cold-source selection tests. Implementation/fix time counts
in the total and gets its own phase; encoder time is not end-to-end speed.

## Export once from checked construction

→ Use skill: `assembly-design`, [pre-render construction](../../assembly-design/references/pre-render-construction.md).

Default export policy replaces repeated model-audit chains, second-ASR sweeps and
scorecard gates in routed references. Preserve source-grounded design, native
readback, exact media identity and a single delivered-file integrity check. If that
check detects a real export failure, repair that failure and rerun only affected
outputs, recording the attempt. Do not reroll unchanged clips for another verdict.

Cache inputs bind media identity, ordered source ranges, frame/sample rate, script
and model/preset versions. Reuse an artifact only when its recipe and completed
output identity match. A filename, previous success log or frame count alone is
insufficient. Do not round a duration independently of the cache producer: use
rational frame/sample clocks and the producer's exact conversion for its API.
Required picture lead, crop, captions and audio gain belong in the construction
before export; never run a blind post-export ripple helper. Applying the same
finishing recipe twice must not add another lead or duplicate captions.

Audit skills remain standalone and available when explicitly requested. This change
does not turn waveform energy, ASR agreement or command success into listening proof.
