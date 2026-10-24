# Editable opening hooks

`text-hook` owns copy, supporting passages, typography and placement; generated copy also uses `slop-detector`. The FilmCraft and Resolve adapters transport the owning helper's text origins, font metrics, rounded boxes and interval geometry into editable native graphics. Preview plates are review artifacts and are never placed on the native timeline.

Current executable scope includes **adding a hook to an already rendered FilmCraft or Resolve clip and removing a verified owned hook on a new native copy**. A replacement uses removal, a fresh native render and a newly measured owner recipe, as described below. Caption hiding and Premiere hook transport remain open. These are explicit repair tasks; they do not trigger raster substitution or another engine.

## Prepare

First finish the native cut, framing and captions and render through the toolkit. Inspect the complete clip, its current transcript, opening captions and protected picture regions. Save a project-owned `text-hook/v1` recipe according to the packaged owner's `references/handoff.md`. Its `source` must be the exact native export described by the base render receipt. Use `caption_strategy: preserve` and `existing_hook: none`. A native font must be installed under its exact family and face; the adapter does not install fonts or allow a silent family/style fallback. Font file hashes remain pinned. Broad font/script fidelity still needs rendered verification.

Run `native PROJECT_ID hooks PACKET.json` with:

```json
{
  "plan": "<project>/10_WORK/current-plan.json",
  "recipe": "<project>/10_WORK/text-hook.json",
  "recipeSha256": "<sha256>",
  "baseReceipt": "<project>/10_WORK/current-render-receipt.json",
  "baseReceiptSha256": "<sha256>",
  "output": "<project>/10_WORK/hook-preparation-01"
}
```

The output directory must be new. Preparation checks base media/native identity, transcript support through the owner, frame count and canvas, then creates the owner's preview and resolved recipe plus `plan.json`. The new plan pins that recipe, helper and entire prior editing plan. A later change to cuts, captions, framing or other plan fields invalidates this preparation. Re-examine the current cut instead of suppressing the check.

The distribution-only helper patch exposes coordinates already computed while drawing; it does not add a second font-fitting or placement policy. The source manifest preserves the canonical source hash and records the portable transformation. Install a fresh checkout for an updated local skill runtime; existing materializations are preserved.

## Add and render

Run `native PROJECT_ID revise PACKET.json` with:

```json
{
  "kind": "text-hook",
  "plan": "<project>/10_WORK/hook-preparation-01/plan.json",
  "nativeProject": "<project>/10_WORK/current/edit.fcproj",
  "expectedFingerprint": "<current native inspect fingerprint>",
  "inspectSession": "<project>/10_WORK/hook-01/inspect",
  "session": "<project>/10_WORK/hook-01/session",
  "reopenSession": "<project>/10_WORK/hook-01/reopen",
  "outputProject": "<project>/10_WORK/hook-01/edit.fcproj",
  "inspection": "<project>/10_WORK/hook-01/reopened.json"
}
```

Create the new work directory first. The base project must match the studied render receipt. The adapter inspects it, copies it to the new native output, adds one top video track, and creates one native graphic per stable placement interval. It saves and reopens, verifies text/shape properties and timing, and compares the entire pre-existing project state. Native graphic source reuse is allowed; source contents, original tracks, cuts, audio and manual changes are protected. The old project is never edited.

Use the returned fingerprint with the ordinary native render packet and this new plan. Include the actual `parentId` when publishing a revision. The render rechecks the native hook and records its owner/hash evidence. Publication and review use the existing immutable-version and fresh-review rules. This is a native revision operation, not a spoken recut.

Every hook covers frame zero through the first frame at or after five seconds, capped at clip duration. For 25 fps this is frames 0–125 inclusive; it clears at frame 126. Interval changes map to the first output frame at or after their supplied boundary. Adjacent intervals must cover the opening without gaps.

## Resolve construction and export

Preparation uses the same packet above and additionally pins the base render's native inspection. With that exact base timeline open in the project's selected Resolve host, run `native PROJECT_ID revise PACKET.json`:

```json
{
  "kind": "text-hook",
  "plan": "<project>/10_WORK/hook-preparation-01/plan.json",
  "expectedFingerprint": "<base native inspect fingerprint>",
  "title": "Opening hook revision 01",
  "nativeProject": "<project>/10_WORK/hook-01.drp",
  "inspection": "<project>/10_WORK/hook-01-inspection.json",
  "archiveDirectory": "<project>/10_WORK/hook-01-archive"
}
```

All output paths and the title must be new. This route is qualified only on **Resolve Studio 21.1.1 build 10**. It constructs a self-contained native Fusion Composition donor with editable Text+, rounded RectangleMasks, Backgrounds and Merges. Visibility uses explicit native per-frame BezierSpline keys with motion blur disabled. FontManager must resolve the exact measured font bytes and face; collection faces remain unsupported.

The adapter exports native parent/donor DRT archives and appends only the donor's independent top track to a new archive, preserving every original archive entry and all existing sequence bytes. It sets the owned generator's duration to the prepared opening range, imports a new timeline, and verifies its graph, placement, keys and original tracks. Original native properties, Fusion graphs, markers, flags, colors, take selections, names and source ranges are compared after import; only observed custom clip names are restored on the new copy if Resolve resets them. Both parent and revised timelines are rechecked before saving a new DRP. Failed intermediate timelines and files remain for reconciliation.

Use the returned fingerprint and new DRP with the ordinary native render packet and prepared plan. Export revalidates the hook and exact font, then requires the full inspected timeline fingerprint to remain unchanged. The selected editor performs final composition and export. Layout validation can invoke the configured shared Python for Pillow; it never invokes another editing engine.

Resolve's Text+ baseline/font-size conversion and rounded-mask mapping were measured on this host. Native text rasterization is not pixel-identical to the owner's Pillow preview: the qualified Arial Bold fixture's measured glyph bounds differed by up to three pixels, while remaining inside its fitted cards. Other fonts, scripts and host versions need rendered verification; matching a font name alone is insufficient.

## Removal, replacement and later finishing changes

Do not delete the hook contract to suppress stale-layout validation while leaving its native graphic in place. When the user requests a replacement or a finishing change that affects the current hook context, make a new plan identical to the existing plan except for removal of `hookContract`. Pin the existing plan and use `native PROJECT_ID revise PACKET.json`:

```json
{
  "kind": "text-hook-remove",
  "previousPlan": "<project>/10_WORK/current-hook-plan.json",
  "previousPlanSha256": "<exact previous plan SHA-256>",
  "plan": "<project>/10_WORK/hook-free-plan.json",
  "expectedFingerprint": "<current inspected native fingerprint>",
  "inspection": "<project>/10_WORK/hook-free-inspection.json"
}
```

For FilmCraft, add `nativeProject` for the inspected parent, a fresh `outputProject`, and fresh `inspectSession`, `session` and `reopenSession` paths. For Resolve, add a unique `title` and a fresh output `nativeProject` DRP path. These are the same backend path conventions as addition; removal needs no DRT archive directory.

The adapter first verifies the entire owned hook, its exact graph/graphics and interval timing, and refuses a locked track. FilmCraft removes that exact track through its native command on a saved/reopened copy. Resolve duplicates the inspected timeline and calls its native `DeleteTrack` API. All other inspected state, source/bin assets, cuts, captions, manual effects and metadata remain protected. The original project/timeline is rechecked; an unidentified or manually changed hook requires reconciliation, not broad title deletion. The removal plan cannot also change another field.

Within the same revision job:

1. Remove the identified hook using the operation above. Keep the old published version and feedback intact.
2. If requested, apply caption, framing or other finishing changes to this new hook-free checkpoint using their owning skills and supported native revision routes. A spoken recut still requires Assembly Design and the recut verification contract.
3. Render the updated hook-free result in the selected engine. Study the actual updated captions and protected picture regions. Use that render and receipt as the source for a fresh `text-hook` recipe; `existing_hook: none` now describes the actual result.
4. Add the freshly prepared hook and render the final version. Publish only that final result against the original submitted parent. Intermediate render receipts are work evidence, not review completion. If the request was only to remove the headline, the verified hook-free result can be the final version.

The job remains serialized through intermediate renders and returns to `editing` when the next native preparation, inspection or revision starts. A failure preserves its files and blocks publication/replay until reconciliation. Never reintroduce the old recipe by updating its hash, reuse its old placement after a layout change, or publish an intermediate without the requested replacement.

## Evidence and limits

A native synthetic fixture exercised two fitted rounded cards, two placement intervals, exact text/face/color, save/reopen, protected parent state and a 50-frame FilmCraft export. Its decoded audio matched the base byte for byte. The native render and owning preview were visually inspected.

A second six-second fixture exercised a unified two-line card. The card was present at frame 125 and absent at frame 126. All 24 native lossless frames after the hook matched the original composition pixel for pixel, and decoded audio was identical. Separately encoded H264 frames after the hook were **not** pixel-identical (54.60 dB PSNR); the native lossless comparison distinguishes unchanged composition from this encoded-output difference. The failed exact-H264 checker remains in local evidence.

These are mechanical fixtures, not real speech, editorial quality, reference fidelity, automatic-agent completion or human approval. No Premiere production project or global skill tree was modified. The first native diagnostic found an overly strict verifier assumption about new graphic-source allocation; the failed operation was retained and reconciled after terminal-process and protected-state inspection, then a fresh native revision passed.

A separate six-second Resolve fixture added two native fitted cards with two placement intervals, saved/closed/reopened the project and rendered 150 frames. The complete fingerprint stayed unchanged through reopen and export. Decoded audio matched the base byte for byte. All 24 native lossless frames after the hook matched the base pixel for pixel; sampled frames confirmed the card at 125 and its disappearance at 126. The original review project and page were restored after each test. This is direct native CLI evidence, not a review-room agent or human acceptance test.

The initial Resolve expression-based attempt completed its MP4 but correctly failed the post-render fingerprint guard when Resolve materialized an expression cache. That output has no success receipt and remains diagnostic evidence. The operation was reconciled after terminal-process/native-state inspection. Native visibility keys fixed the cause without weakening Fusion fingerprints or migrating existing approved work. A separate strict two-pixel preview comparison failed by one pixel; its evidence is retained, and the three-pixel typography difference is reported above rather than claimed as exact raster parity.

FilmCraft subsequently completed a six-second removal → body-caption wording revision → fresh layout preparation → replacement hook → native render sequence. The original checkpoint retained its hash, all four stages had byte-identical decoded audio, and the final sampled render visibly contained the new single-line hook and changed body caption. Exact saved-project comparisons protected everything outside the removed owned track. This was direct CLI execution, not the agent/review-room acceptance scenario.

Resolve also completed the six-second removal → caption revision → fresh measurement → replacement → native render sequence after the source-clock persistence fix described in `RESOLVE_STATE.md`. All three new exports decoded 150 frames; audio was byte-identical across the original, removed, caption-revised and replacement stages. Sampled final frames showed the changed caption, replacement headline, correct source-frame numbers at 0/49/50/125/126/149, and the headline clearing at frame 126. Every new timeline retained its complete snapshot and correct source clocks after loading again; the final also passed an explicit save/close/reopen. The original native checkpoint retained its hash and the prior review project was restored unchanged. This is direct native CLI evidence; agent/review-room execution and human copy/layout approval remain open.

Earlier attempts failed Fusion export because a duplicated Timeline MediaIn reopened one frame late. The initial complete snapshot happened to capture that already-shifted state, so its later stability and a successful still preview did not establish correct source timing. Controlled probes isolated the persistence failure; a read-only inspection change alone did not fix it. New copies explicitly persist verified source clocks, while shifted historical timelines are refused and preserved. A subsequent integration attempt stopped on the bridge's `None` return from `SetInput`; native readback now verifies the write. All failed journals/files remain retained and reconciled without success receipts or publication. No Fusion fingerprint rule was relaxed.

The later Codex/FilmCraft review-room scenario completed both real jobs with 150-frame immutable V1/V2, native removal/caption revision/fresh preparation/addition, and no intermediate publication. Independent checks preserved source/working/published hashes, native tracks/bin assets, exact decoded audio and protected caption regions. Browser V2 was unreviewed, retained previous feedback, and kept late feedback linked to read-only V1. See `LIVE_AGENT_LOOP.md` for the reproducible scenario and retained checker failures. The later Codex/Resolve browser scenario also passed with two immutable 150-frame versions and identical decoded audio. Both published native timelines matched archived snapshots, source-clock and owned-hook graph checks passed, and final save/close/reopen preserved the complete inspected state. Late feedback opened read-only V1; V2 remained unreviewed. Claude, Premiere, real footage and human approval remain open.
