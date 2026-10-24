# Reference evidence extraction

Use the packaged `watch` owner for complete viewing/listening and reference comparison. This helper prepares local evidence; it does not watch, listen, infer a style, choose edits or certify fidelity. Keep the reference immutable and put outputs in a new project `10_WORK` directory.

For fast transitions, caption arrivals and detailed animation, extract every decoded frame at the source's native display size:

```sh
python3 scripts/reference_frames.py /absolute/reference.mp4 /absolute/project/10_WORK/reference-transition --start 2.1 --end 3.4 --all-frames --native-size
```

The half-open interval includes actual frame timestamps at or after `start` and before `end`. `--all-frames` preserves variable frame spacing without inventing duplicates. `--native-size` writes PNGs without the default 960-pixel resizing or JPEG compression. It preserves decoded display pixels, not the source's compressed bytes, color-management pipeline or arbitrary high-bit-depth format.

For an initial overview, omit `--all-frames` and choose `--fps 12` (the default). The helper selects the first available source frame in each sampling bin. It does not create a constant-rate video or pretend each sample occurred exactly on the bin boundary. A sparse overview can miss a fast event; use every-frame extraction for the relevant interval.

`index.json` uses `acq-edit/reference-frames-v2` and records:

- The source path/hash, selected streams, requested interval, sampling mode and image mode.
- Each image's actual decoded integer PTS, rational time base, normalized presentation time and hash. `seconds` remains available to readers of the earlier index format, but is now measured rather than calculated from image number.
- FFmpeg's input-start-normalized timestamp basis and the probed original container start. Do not treat these as an unrelated camera/source timecode.
- A separately hashed PCM audio excerpt with its requested interval, verified sample count/rate and channel count, or an explicit absence of source audio. Multiple audio streams require an explicitly selected reference mix first.
- `extracted-not-yet-viewed-or-listened`; audio retains its own not-listened status. Never promote these fields into viewing or human approval.

The helper refuses existing output directories, invalid/nonfinite bounds, unsupported stream ambiguity and sources changed during extraction. A failure after creating the output directory retains partial artifacts, `extraction.log` and an index with `status: failed`; inspect it and use a new destination for another attempt. An interval with no decoded frame does not become successful evidence.

After actual inspection, cite the relevant image/audio paths and normalized timestamps in `REFERENCE_RECIPE.schema.json`. Keep observed details separate from inferred techniques, record incomplete coverage and unsupported effects, and compare the selected editor's actual rendered result. Extraction alone must not set `fullVideoViewed` or `audioListened` to true. Native composition/export still belongs to the project's selected engine; Remotion supplies graphics through `NATIVE_MOTION.md`.

Actual FFmpeg regression fixtures cover irregular source PTS, a nonzero container start, exact native dimensions, sparse sampling, an explicit audio mix, silent footage, invalid intervals, empty intervals and preservation of existing artifacts. These establish extraction behavior, not a completed reference recreation or human assessment.

## Freeze a recipe for an edit

After the watch owner has actually completed inspection, keep its working recipe and cited reports, frames or audio evidence under `10_WORK`; keep the immutable reference media under `00_SOURCE`. A recipe must cover all nine categories, explicitly describe absent features, distinguish `observed` from `inferred`, cite evidence IDs for each observation and coverage claim, and list unsupported effects. `coverage.denseIntervals` is an explicit array of `{start,end,evidence}` entries; use an empty array only when no detailed interval was needed. Silent references require `audioAbsent: true` and `audioListened: false`. Preparation probes the source to check audio presence; the declared duration and viewing/listening remain owner-reported.

Write a packet with absolute project-owned paths:

```json
{
  "plan": "/project/10_WORK/designed-plan.json",
  "recipe": "/project/10_WORK/reference/recipe.json",
  "recipeSha256": "<working-recipe-sha256>",
  "source": {"path": "/project/00_SOURCE/reference.mp4", "sha256": "<source-sha256>"},
  "evidenceFiles": [{"id": "watch-report", "path": "/project/10_WORK/reference/watch-report.md", "sha256": "<report-sha256>"}],
  "snapshot": "/project/10_WORK/reference/frozen-v1.json",
  "output": "/project/10_WORK/reference-plan-v1.json"
}
```

Run `acq-edit native PROJECT_ID reference /project/10_WORK/reference-packet.json`. This shared preparation runs without loading an editor adapter. It validates the existing designed plan and creates two new files without overwriting earlier work: a full frozen recipe/evidence snapshot and a plan with `referenceStyle: {path,sha256}`. Continue construction using the returned plan. Existing cut, caption, framing and graphics decisions remain unchanged; this action records provenance and does not implement the recipe's effects. Route those decisions to their existing owners, explicitly retain unsupported effects, then inspect and compare the actual selected-engine render.

Each source/evidence pin is checked when the plan is consumed, after rendering and before publication. The native render receipt embeds the exact frozen snapshot, and publication archives that receipt beside the immutable version. Later edits to the working recipe do not rewrite the snapshot or earlier receipts. To adopt a new recipe, prepare a new snapshot and new plan; do not overwrite frozen files. Changes to a pinned source or inspection artifact stop the operation instead of substituting new content.

Every snapshot says `coverageStatus: reported-by-watch-owner` and `humanApproved: false`. Hashes establish which artifacts were used; they cannot establish that someone watched/listened, that a claim is correct, or that the output matches the reference. Real reference recreation and human fidelity review remain release gates.
