# Editable opening hooks

`text-hook` owns copy, supporting passages, typography and placement; generated copy also uses `slop-detector`. The FilmCraft adapter transports the owning helper's actual text origins, font metrics, rounded boxes and interval geometry into editable native text/shape layers. Preview plates are review artifacts and are never placed on the native timeline.

Current executable scope is **adding a first hook to an already rendered FilmCraft clip**, preserving its existing captions and all other layers. Caption hiding, replacement of an existing native hook, Premiere/Resolve hook transport and automatic hook recalculation after another finishing revision remain open. These are explicit repair tasks; they do not trigger raster substitution or another engine.

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

## Evidence and limits

A native synthetic fixture exercised two fitted rounded cards, two placement intervals, exact text/face/color, save/reopen, protected parent state and a 50-frame FilmCraft export. Its decoded audio matched the base byte for byte. The native render and owning preview were visually inspected.

A second six-second fixture exercised a unified two-line card. The card was present at frame 125 and absent at frame 126. All 24 native lossless frames after the hook matched the original composition pixel for pixel, and decoded audio was identical. Separately encoded H264 frames after the hook were **not** pixel-identical (54.60 dB PSNR); the native lossless comparison distinguishes unchanged composition from this encoded-output difference. The failed exact-H264 checker remains in local evidence.

These are mechanical fixtures, not real speech, editorial quality, reference fidelity, automatic-agent completion or human approval. No Premiere production project or global skill tree was modified. The first native diagnostic found an overly strict verifier assumption about new graphic-source allocation; the failed operation was retained and reconciled after terminal-process and protected-state inspection, then a fresh native revision passed.
