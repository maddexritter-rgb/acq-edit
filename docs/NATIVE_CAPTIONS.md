# Caption-clips handoff to native FilmCraft graphics

The `captions` operation translates the packaged caption-clips owner's reviewed cards into an executable plan. It calls `filmcraft_caption_contract.prepare_cards` for display text, quote styling and speech holds; `filmcraft_shadow.shadow_layer_props` for the two shadows; and `profile_caption_motion` for the selected native arrival. It does not select words, infer quotations, measure faces, or decide where a caption belongs.

Production FilmCraft plans containing body captions require this handoff. The previous single-text route remains available only for explicit synthetic fixtures. Resolve and Premiere retain their separate native routes; this handoff currently refuses those backends rather than dropping the requested styling or switching editors. Complete caption quality across all engines remains a pilot gate.

## Prepare an executable plan

After source-word compilation and composition decisions, the owning caption skill writes a new project-local profile JSON and card handoff. Profiles, licensed fonts and per-brand decisions remain separate from reusable procedures. Copy the resolved profile into the project and pin its SHA-256; never reference a private workstation path.

The resolved profile must explicitly supply `allow_quote_italics`, `guest_turn_italics`, `caption_hold_through_seconds`, `caption_trailing_hold_seconds`, and `filmcraft_caption_motion` (`none` or `measured_fast_settle`). Other profile data can remain in that file for the owning skill. This adapter consumes exact per-card typography and placement, not inferred defaults from the profile name.

Example handoff:

```json
{
  "schema": "acq-edit/caption-handoff-v1",
  "owner": "caption-clips",
  "projectId": "<project-id>",
  "clipId": "<clip-id>",
  "cutsFingerprint": "<common.fingerprint of the exact native cuts>",
  "profile": {"path": "<project>/10_WORK/caption-profile.json", "sha256": "<hash>"},
  "cards": [{
    "id": "semantic-card-1",
    "text": "The actual reviewed words",
    "start_frame": 0,
    "speech_end": 1.6,
    "quote": false,
    "elapsed_frames": 0,
    "style": {
      "font": "<installed family>",
      "fontStyle": "<installed upright face>",
      "italicStyle": "<installed italic face>",
      "size": 64,
      "renderedFontPx": 64,
      "position": [540, 960],
      "color": "#ffffff"
    }
  }],
  "omissions": []
}
```

`position` is the measured native point-text position, not a universal baseline or percentage. The caption owner must inspect composition and use the canonical foreground ink-bound helpers when centering is requested. `renderedFontPx` is the owner's measured glyph scale for shadow geometry. These numbers are not automatically established by copying the example. Actual reference fidelity, face clearance and delivery-resolution readability still need rendered inspection.

Every card must explicitly classify `quote` and supply the mapped `speech_end` in timeline seconds. A real installed italic face is required when needed; a profile's approved quote-only synthetic italic treatment can instead be carried explicitly as `syntheticQuoteItalic: true` on that card. The native adapter checks the exact family/face against FilmCraft's font inventory. Guest styling does not infer quote punctuation. `elapsed_frames` advances the canonical entrance for a continuation without replaying it. The current transport supports one ordered card stream with uniform typography per card; overlapping speakers, per-character emphasis, arbitrary animations and scoped shadow overrides require additional adapter support and are not silently discarded.

Display omissions use the owning skill's records with word, start/end seconds and reason. Its existing protection for quantities and negations applies. This translation does not establish source-word coverage or acoustic evidence; those remain the caption and assembly owners' responsibility.

Create a packet inside the project:

```json
{
  "plan": "<project>/10_WORK/compiled-plan-with-empty-captions.json",
  "handoff": "<project>/10_WORK/caption-handoff.json",
  "handoffSha256": "<hash>",
  "output": "<project>/10_WORK/finished-caption-plan.json"
}
```

```sh
acq-edit native PROJECT_ID captions /absolute/project/10_WORK/caption-packet.json
```

This uses the shared Python interpreter and does not start an editor. Output creation is exclusive. It pins the handoff and all three owning helper hashes, normalizes the exact cards, and adds `captionContract` to the new plan. Validation rederives those cards and refuses changed helper files, handoff/profile bytes or cut clocks. Recompiling a spoken recut therefore requires a newly mapped handoff.

## Native construction, inspection and revision

FilmCraft places the wide shadow on V2, the tight shadow on V3 and the foreground on V4. Motion assets begin at V5. All three copies retain identical text, real faces, positions, intervals and animation. After creation, the adapter sets the reviewed text explicitly so FilmCraft's smart-quotes preference cannot rewrite an apostrophe. The source snapshot and global preferences are unchanged.

After saving and before export, verification reads the full typed native project. The quick `sequence_inspect` response has debug strings and keyframe counts, which cannot prove exact curves. Verification checks punctuation, quotation italics, every animation key, layer visibility, foreground color, shadow opacity/geometry, typography, timing and duplicate consistency. The native checkpoint remains bound to the live inspection fingerprint before and after rendering. Render receipts include caption-owner/helper provenance. These are construction checks, not human approval.

For a caption-only revision, prepare a new handoff and plan with the same source cuts. Pass that plan in the existing `caption-style` revision packet and target all three owned layers. Foreground colors must stay transparent on the shadow duplicates. The adapter preserves the parent project, checks native state before editing, verifies the revised caption contract, and refuses any cut change. Timing-changing captions need a separately supported replacement operation; do not force them through a property-only revision.

## Recorded native evidence

On 2026-10-23, a synthetic white-background/tone fixture built three native cards with upright narration, a real italic quotation, straight-apostrophe preservation, short-pause holds and the measured fast-settle arrival. Save/reopen and native H264/AAC export passed: 75 frames, 640×360, 25 fps, full decode. Sampled rendered frames showed readable white captions and dark shadows on white.

A subsequent native caption-only revision changed wording and foreground color across the owned layers. It rendered another 75 frames, preserved every inspected cut range and the parent project's hash, and produced byte-identical decoded audio. This direct adapter execution does not establish real-speech accuracy, complete agent orchestration, delivery-resolution profile fidelity, reference matching or human approval. The regression fixture contains only synthetic native caption tracks, with media paths and project metadata removed.
