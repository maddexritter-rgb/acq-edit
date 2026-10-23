---
name: premiere-to-resolve
description: Convert a saved Premiere Pro project and its native XML export into an editable DaVinci Resolve project (.drp), preserving vertical framing and stacked camera tracks with disabled alternates. Includes media intake and verified handoff; editorial assembly remains owned by assembly-design.
---

For any Premiere access, follow [Premiere Agent startup and stage routing](../edit/references/premiere_start_here.md). Use the configured bridge or its CLI. When another session owns Premiere, coordinate the export through that owner; do not call the bridge, switch projects or compete for its lease. Existing saved exports can be processed entirely in Resolve.

# Premiere to Resolve

Create a source-linked, editable `.drp` alongside the original `.prproj`. Preserve editorial cuts, existing framing, camera enable states, audio and source ownership. A 9:16 timeline stays 9:16; disabled alternate angles remain editable on their existing tracks. A single-camera timeline follows the same path. Stacked tracks are supported; nested multicam source sequences require a separate compatibility test.

## Intake and export

→ Use skill: `footage-fetch` for Drive download and integrity checks.

Preserve the supplied project and work on a copy in the job's existing source/work/delivery directories. Follow the project scaffold convention for new jobs. Reuse exact available media paths; resolve missing media explicitly. A `.drp` references footage and does not package it. Identify every timeline and the main editor timelines; retain reference timelines and bins. Exporting a selected subset must be intentional and recorded.

Before Premiere access, read [capabilities](../edit/references/premiere_capabilities.md) and its identity/execution contract. Discover the installed connector. Export project-wide FCP7 XML, or every explicitly selected sequence, from the correct saved project. The active-sequence-only tool is not a whole-project export.

The native API is `app.project.exportFinalCutProXML(outputPath, suppressUI)`; guard exact project identity and retain its receipt. The tested UI fallback focuses the correct Project panel (Shift+1) and uses File → Export → Final Cut Pro XML. The dialog must say **Save Converted Project As**, not **Save Converted Sequence As**. Verify sequence inventory and translation log. Do not widen connector permissions to obtain the export.

## Convert and verify

Read [conversion.md](references/conversion.md) for the one-command handoff, runtime and tested boundaries. Use `scripts/handoff.py` in Resolve's scripting runtime with a fresh work directory, unique project name, nonexisting output, exact expected current project, saved `.prproj` and its actual native XML export. It prepares a v2 manifest, audits the native project, imports, verifies, exports and reopens the `.drp`. Do not invent XML source names, durations or timecodes.

The converter checks media identity, exact native timing, resolution, independent track/clip enable states, names, markers, source ranges, links and transported Motion/audio parameters. Custom track names omitted by XML are recovered from the bound native audit. A timing-only v1 audit cannot authorize conversion. Unknown graphs/effects, missing media and subframe timing loss stop the handoff.

Two required sizing details: use `centerCrop` for the tested native Premiere pixel-scale route, and freeze **each timeline's** custom resolution. This preserves already-designed 1080×1920 framing when landscape timelines are imported later. The skill does not choose or redesign a crop. Inspect actual pictures before extending the route to another sizing mode.

Resolve track visibility/name operations require the target timeline to be current. Keep whole-track visibility separate from individual-clip visibility; never flatten or bake alternates. The native audit rejects track visibility disagreement before import. Import adjustments restore only the audited flags/names and are recorded. Verification tests the flags again after DRP reopen.

State is checkpointed before imports and after each timeline. Any failure retains the project and receipts, including the failed phase; inspect them before choosing a recovery. Never blindly rerun imports, delete failed projects, or reuse work/output names.

## Review and delivery

Inspect representative rendered frames for each main timeline, including animated framing, boundaries and alternate-camera isolation. Audition audio and let the user open/edit the result. Structural verification, sampled pixels, listening and human acceptance are separate; until acceptance say **ready for review**.

Deliver original `.prproj`, native `.drp`, exact media dependencies and a concise report with Resolve version, test limits and any deliberately omitted sequences. Keep XML and detailed receipts in work or a labeled interchange folder. Supply XML as the older-version fallback without promising backward DRP compatibility. Do not upload or message the team merely because local conversion succeeded.

After assembly/design produces a saved Premiere handoff, → Use skill: `premiere-to-resolve`. Do not duplicate assembly or Drive logic here.
