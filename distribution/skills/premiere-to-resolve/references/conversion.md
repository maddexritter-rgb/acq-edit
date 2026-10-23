# Execution and tested boundaries

## Runtime and one-command handoff

Resolve must be running with local scripting available. Discover its version-matched Developer/Scripting docs. On the tested macOS Resolve 21.1+ installation:

`/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Applications/ResolvePython`

Probe `import DaVinciResolveScript as d; r=d.scriptapp('Resolve'); print(r.GetVersionString() if r else None)`. Other installations can use their configured Python or the in-app Console. Do not install another bridge or enable network scripting.

Read the current project name. Save/name an `Untitled Project` before running: its Save call opens a modal dialog. The converter checks the exact current name and saves it before creating a separate conversion project. It does not close or discard unrelated work.

```bash
'<ResolvePython>' '<skill>/scripts/handoff.py' \
  --project '<source>/project.prproj' --xml '<work>/native-export.xml' \
  --project-name '<unique-conversion-name>' \
  --expected-current-project '<exact-current-project-name>' \
  --work '<fresh-work>/handoff' --output '<delivery>/project.drp'
```

Use actual absolute paths. Optional `--path-map '<exact-mapping.json>'` maps original media paths to verified local paths; duplicate basenames are never sufficient identity. `handoff.py` does not open or control Premiere. Request a missing native export through the sole Premiere operator when another session owns the bridge.

For diagnosis, the same stages remain independently callable:

```bash
python3 '<skill>/scripts/prepare.py' '<work>/native-export.xml' '<fresh-work>/prepared'
python3 '<skill>/scripts/audit_prproj.py' '<source>/project.prproj' \
  '<fresh-work>/prepared/manifest.json' '<fresh-work>/native-audit.json'
'<ResolvePython>' '<skill>/scripts/convert.py' '<fresh-work>/prepared/manifest.json' \
  --native-audit '<fresh-work>/native-audit.json' \
  --project-name '<unique-name>' --expected-current-project '<exact-current-name>' \
  --work '<fresh-work>/conversion' --output '<delivery>/project.drp'
```

## State, identity and visibility

The v2 manifest stores per-track names and enable flags separately from per-clip flags. The native audit checks flat picture/audio timing in exact ticks, source identity, track inventory/visibility, frame rate and dimensions; it supplies native custom track names when XML omits them. Native per-clip flag serialization is not decoded: exported XML clip flags are checked against Resolve. Missing custom names default to Resolve's own track names, not invented camera labels.

Audit receipts bind the project, manifest and auditor code hashes. Input XML and prepared sequence hashes must still match; missing/size-changed media, v1 manifests and stale receipts stop before Resolve mutation. Source media are not fully hashed by this skill; use intake integrity verification where needed. Explicit selected-sequence exports record `native_sequences_not_in_export`; do not describe a subset as a full project.

Track flag restoration and verification always activate the exact timeline first. Resolve 21.1.1 returned false/failed for track operations against inactive timelines in the compatibility test. `track_adjustments` records any imported flag/name restoration. Picture edits, clip flags, scales and animated framing are not silently repaired: mismatches fail verification.

Native XML imports may add empty utility tracks. Missing declared tracks and unexpected populated tracks fail; extra empty Resolve tracks do not. Whole-track mute does not disable the underlying clips, remove alternate sources or flatten the timeline.

Use `centerCrop` with native Premiere pixel-scale Motion and `useCustomSettings=1` per timeline. `scaleToFit` adds a second scale, and inherited resolution settings can change earlier timelines after later imports. Do not refit an already-framed vertical edit.

Inspect `<work>/state.json` and `<work>/conversion/state.json` after failure. No automatic retry/resume is performed. The conversion and `__REOPEN_CHECK` names must both be unused; existing output/work names are refused. Retain failures until cleanup is authorized.

## Evidence and regression checks

Initial genuine export fixture: Premiere 26.3 → Resolve 21.1.1, eight flat timelines at 24000/1001 and 30 fps, including vertical and horizontal edits; 2,432 picture/audio items. Timing, source ranges, links, names, markers, static scale, animated anchor keys and DRP reopen were exercised. Listening and human acceptance remain separate.

Additional constructed compatibility tests used real source files/ranges: 133 spans across three cameras (399 picture items), whole-track disable, individual-clip disable, combined states, and 1080×1920 geometry. A native vertical edit with disabled alternate footage produced identical decoded pixels to its single-camera control at two sampled frames after DRP reopen. Importing landscape afterward did not change vertical dimensions. These controls do not establish a complete native multicam-project export, alternate lip-sync or arbitrary effect fidelity.

The original verifier's failure was reproduced by enabling a muted alternate and receiving a passing result. The maintained regression tests now require that wrong track state to fail, independently of clip flags. Run:

```bash
python3 -m unittest discover -s '<skill>/tests' -v
```

For live regression, use fresh project/work/output names and the real saved-project/native-XML pair. Run `handoff.py` without hand-editing manifests/audits or bypassing a failed audit. Check both verification receipts and sampled renders. Constructed XML tests can exercise `prepare.py`, `apply_track_settings()` and `snapshot()` in a clearly identified test project; they are not substitutes for a production native audit.

Resolve's `GetSourceStartFrame()`/`GetSourceEndFrame()` can truncate one frame low. Precise `GetLeftOffset(True)` and XML source-edge agreement are the tested route. Do not move cuts to compensate for accessor rounding.

## Bounded support

Stacked camera tracks and single-camera timelines are supported on the tested route. Nested multicam source sequences, other nests, transitions, non-unit retimes, mixed source/timeline rates within one sequence and missing media require investigation. Different rates between timelines are supported.

Unknown effects stop conversion. Native caption graphics/MOGRTs, plugins, complex color/audio routing, variable-speed ramps and Dynamic Link require their own compatibility test or explicitly approved rendered replacement. Do not flatten silently or imply full feature equivalence. Native frame-independent audio must pass exact tick comparison; if XML rounded speech edges, investigate native/AAF alternatives while preserving the Premiere original.

Keep original source metadata in genuine XML. Early constructed fixtures imported only after replacing guessed filenames/durations/timecodes with actual media metadata; which individual correction resolved matching was not isolated. Never synthesize guessed source metadata as a repair to a native export.

`.drp` portability depends on Resolve version and available media; relink exact originals on another workstation. XML is an alternative, not a promise that an older version supports every effect.

## References

- Adobe: [Export a project as Final Cut Pro XML](https://helpx.adobe.com/ca/premiere/desktop/render-and-export/export-files/export-a-project-as-a-final-cut-pro-xml-file.html).
- Blackmagic: installed `Developer/Scripting/README.md` and `DaVinciResolveScript.pyi`.
- Apple: [FCP XML interchange topics](https://developer.apple.com/library/archive/documentation/AppleApplications/Reference/FinalCutPro_XML/Topics/Topics.html).
