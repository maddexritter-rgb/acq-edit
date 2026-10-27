# Caption-clips handoff to native graphics

The `captions` operation translates the packaged caption-clips owner's reviewed cards into an executable plan. It calls `filmcraft_caption_contract.prepare_cards` for display text, quote styling and speech holds, and `profile_caption_motion` for the selected arrival. FilmCraft uses `filmcraft_shadow.shadow_layer_props` for two shadows; Resolve uses an explicit native profile. It does not select words, infer quotations, measure faces, or decide where a caption belongs.

Production FilmCraft and Resolve plans containing body captions require this handoff. The previous single-text routes remain available only for explicit synthetic fixtures. Resolve executes the shared owner's text, holds and motion with native Fusion Text+ nodes and an explicit Resolve profile; it does not invoke FilmCraft. Premiere retains its native Graphics route and is refused by this transport. Complete caption quality across all engines remains a pilot gate.

## Prepare an executable plan

After source-word compilation and composition decisions, the owning caption skill writes a new project-local profile JSON and card handoff. Profiles, licensed fonts and per-brand decisions remain separate from reusable procedures. Copy the resolved profile into the project and pin its SHA-256; never reference a private workstation path.

The resolved profile must explicitly supply `allow_quote_italics`, `guest_turn_italics`, `caption_hold_through_seconds` and `caption_trailing_hold_seconds`. FilmCraft also requires `filmcraft_caption_motion` (`none` or `measured_fast_settle`); Resolve requires its own fields described below. Other profile data can remain in that file for the owning skill. This adapter consumes exact per-card typography and placement, not inferred defaults from the profile name.

FilmCraft example handoff:

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

Every card must explicitly classify `quote` and supply the mapped `speech_end` in timeline seconds. A real installed italic face is required when needed; a profile's approved quote-only synthetic italic treatment can instead be carried explicitly as `syntheticQuoteItalic: true` on that card. The native adapter checks the exact family/face against FilmCraft's font inventory. Guest styling does not infer quote punctuation. `elapsed_frames` advances the canonical entrance for a continuation without replaying it. The transport supports one ordered card stream. FilmCraft additionally supports reviewed semantic word emphasis through `style.emphasis`: ordered, nonoverlapping Unicode character ranges (`start`, `end`, exact `text`) in the final normalized display, with real `fontStyle`, `italicStyle`, `fontPostscript` and `italicPostscript` faces. It applies and verifies identical runs on foreground and both transparent shadow copies. Use `fontPostscript` and `italicPostscript` on the base style when changing its face. Width checks conservatively measure every requested face; measure native isolated ink again for final placement. Resolve currently rejects this extension explicitly. Overlapping speakers, arbitrary animations and scoped shadow overrides still need additional adapter support.

Profiles selecting `oliver_v2` now apply the owning capitalization rule during handoff preparation: lowercase body text, preserving I forms, known names and acronyms. Additional reviewed single-token names belong in profile `proper_names`. Emphasis offsets refer to the final normalized text, including quotation marks; stale ranges fail instead of silently targeting another word. Existing pinned plans remain on their original runtime until explicitly revised.

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

### Premiere Pro

Use the repository `caption-clips` native Graphics builder and guarded transfer.
`assets/native-captions` supplies closed generated-Graphics donor graphs; the
licensed font bundle is still required. `prepare_premiere_caption_template.py
graft` adds those donors to an offline copy of the saved target project. The
asset declares speaker-based or style-based donor selection. It never imports
historical source footage or timelines.

Build the reviewed manifest with `premiere_native_cards.py`, then bind its new
caption lane to two fresh native read surfaces with
`prepare_caption_transfer_structure.py`. Use `apply_native_captions.py` for the
scoped import, native structure checks and saved-file text/style verification.
Premiere paragraph returns are compared to shared line feeds without ignoring
words or removing line breaks. Save, close, reopen and verify again before
exporting through the Premiere adapter. Inspect every rendered caption state
and entrance; `sample_render.py --caption-entrances` extracts entrance evidence.

For comparisons using separate picture and mono dialogue, the bounded
`prepare_picture_dialogue.py` source-preparation route preserves compressed
picture packets and decoded audio. `prepare_native_variant.py` transports one
frozen contiguous selection to that verified source. Neither helper chooses
editorial content or substitutes another editor's render. Dense reviewed crop
curves use `apply_premiere_crop_plan.py` through the framing owner's native API.
These helpers currently support that bounded comparison workflow; they do not
qualify every multicamera, audio-layout or revision scenario.

### FilmCraft

FilmCraft places the wide shadow on V2, the tight shadow on V3 and the foreground on V4. Motion assets begin at V5. All three copies retain identical text, real faces, positions, intervals and animation. After creation, the adapter sets the reviewed text explicitly so FilmCraft's smart-quotes preference cannot rewrite an apostrophe. The source snapshot and global preferences are unchanged.

After saving and before export, verification reads the full typed native project. The quick `sequence_inspect` response has debug strings and keyframe counts, which cannot prove exact curves. Verification checks punctuation, quotation italics, every animation key, layer visibility, foreground color, shadow opacity/geometry, typography, timing and duplicate consistency. The native checkpoint remains bound to the live inspection fingerprint before and after rendering. Render receipts include caption-owner/helper provenance. These are construction checks, not human approval.

For a caption-only revision, prepare a new handoff and plan with the same source cuts. Pass that plan in the existing `caption-style` revision packet and target all three owned layers. Foreground colors must stay transparent on the shadow duplicates. The adapter preserves the parent project, checks native state before editing, verifies the revised caption contract, and refuses any cut change. Timing-changing captions need a separately supported replacement operation; do not force them through a property-only revision.

### Resolve Studio

Use the same handoff and preparation command with a Resolve plan. Supply `resolve_caption_motion` (`none` or `measured_fast_settle`) and `resolve_caption_shadows` in the pinned profile. The shadow object must contain an explicit `id` and exactly two entries, `wide` and `tight`. Each entry contains a two-number `offset`, two-number `softness`, and `opacity` from 0 to 1.

Offsets use normalized Fusion coordinates, positive Y upward. Softness uses native Text+ shading units, **not normalized coordinates**; the supported range is 0–100. These are measured per-profile inputs, not interchangeable FilmCraft shadow settings. An example from the small synthetic qualification fixture is:

```json
{
  "resolve_caption_motion": "measured_fast_settle",
  "resolve_caption_shadows": {
    "id": "resolve-two-shadow-qualification-v1",
    "wide": {"offset": [0.003, -0.003], "softness": [6, 6], "opacity": 1},
    "tight": {"offset": [0.006, -0.009], "softness": [2, 2], "opacity": 1}
  }
}
```

Each card's Resolve `style` contains `font`, `fontStyle`, optional real `italicStyle`, `fusionSize`, `center: [x, y]`, and `color`. Size is the native Text+ value; center uses normalized Fusion coordinates. The qualification fixture uses size 0.08 at center `[0.5, 0.425]` on 640×360. Those values are fixture evidence, not a delivery-resolution preset. FilmCraft pixel-position fields and synthetic italic are explicitly refused. Build, planned revision and render check the exact family/face in Resolve's font inventory to prevent silent substitution.

For each picture-cut overlap, the adapter constructs three Text+ nodes and three Merge nodes: wide black shadow, tight black shadow, then foreground. Exact owned names are `ACQ_Caption_<card-index>_<role>` and `ACQ_CaptionMerge_<card-index>_<role>`. The background comes from the source or existing owned framing resize. A native expression gates each card and transports the owner's piecewise linear position/opacity curve, compensating for source composition clocks and elapsed caption time across cuts. A continued card does not replay its entrance.

Before checkpoint/export, inspection verifies the owned node set, types, exact static inputs, expression text, source/merge/output connections, expression evaluation and picture timing. Complete parsed graph fingerprints protect the inspected state through export. These checks do not claim coverage of every unexposed native property or visual equivalence to another editor. See `RESOLVE_STATE.md` for schema v3 and explicit reconciliation of older receipts.

Caption-only revisions duplicate the native timeline. Supply a new pinned handoff/plan with unchanged cuts and property edits for every affected owned Text+ node. Wording changes update all three copies; foreground color changes target only the `text` role. The current property route supports wording, real face, size and color changes. Moving an expression-driven center, changing shadow geometry, timing or animation needs a separately supported operation; attempts must not silently discard the handoff. The old timeline and checkpoint remain available.

Only shared Python helpers are imported despite their historical `filmcraft_*` filenames. Resolve needs neither a FilmCraft executable nor a Premiere installation. Native text/input/expression APIs are documented in Blackmagic's [Fusion scripting guide](https://documents.blackmagicdesign.com/UserManuals/Fusion8_Scripting_Guide.pdf); this older guide is background, and the qualified host behavior is Studio 21.1.1 build 10.

## Recorded native evidence

On 2026-10-23, a synthetic white-background/tone fixture built three native cards with upright narration, a real italic quotation, straight-apostrophe preservation, short-pause holds and the measured fast-settle arrival. Save/reopen and native H264/AAC export passed: 75 frames, 640×360, 25 fps, full decode. Sampled rendered frames showed readable white captions and dark shadows on white.

A subsequent native caption-only revision changed wording and foreground color across the owned layers. It rendered another 75 frames, preserved every inspected cut range and the parent project's hash, and produced byte-identical decoded audio. This direct adapter execution does not establish real-speech accuracy, complete agent orchestration, delivery-resolution profile fidelity, reference matching or human approval. The regression fixture contains only synthetic native caption tracks, with media paths and project metadata removed.

On the same date, Resolve Studio 21.1.1 build 10 built and natively rendered the shared caption-owner handoff: three cards, a real italic quotation spanning a picture cut, two shadow copies, and the measured fast-settle arrival. Both the original and subsequent wording/yellow-color revision exported 75 frames at 640×360/25 fps with full decode passing. Sampled original and revised frames were viewed. The parent timeline, parent DRP hash and pre-existing review timeline were verified unchanged. This fixture used Resolve directly throughout; no FilmCraft engine or Premiere operation ran.

Decoded audio differed between Resolve versions at −72.31 dB difference RMS relative to the signal. This is retained as an open qualification, not rounded to equality or labeled inaudible. No real speech, complete agent-driven caption-owner workflow, reference recreation or human approval is established by this synthetic fixture. Unicode JSON and Fusion exports now read explicitly as UTF-8, including under ResolvePython's ASCII locale.


## Native caption visibility (FilmCraft and Resolve)

The caption owner can hide editable speech captions for explicit frame ranges while retaining the words, timing, arrival motion and both native shadow duplicates. This requires `captionContract` and a FilmCraft or qualified Resolve Studio 21.1.1 build 10 project. Premiere visibility remains unsupported. It never covers burned captions, changes cuts or invokes another engine.

Add this field to an otherwise identical plan:

```json
"captionVisibility": {
  "schema": "acq-edit/caption-visibility-v1",
  "owner": "caption-clips",
  "hiddenRanges": [{"startFrame": 0, "endFrame": 126}],
  "reason": "The opening headline replaces speech captions in this interval",
  "evidence": "Measured opening caption bounds and protected picture regions"
}
```

Ranges are ordered, nonoverlapping, half-open integer frames within the clip. The example hides frames 0 through 125. Remove the field in a new plan to restore the original caption visibility. The owner must reconsider these ranges after a spoken recut; see `NATIVE_RECUTS.md`.

Run `native PROJECT_ID revise PACKET.json` with:

```json
{
  "kind": "caption-visibility",
  "previousPlan": "<project>/10_WORK/current-plan.json",
  "previousPlanSha256": "<exact previous plan SHA-256>",
  "plan": "<project>/10_WORK/visibility-plan.json",
  "nativeProject": "<project>/10_WORK/current/edit.fcproj",
  "expectedFingerprint": "<current native inspect fingerprint>",
  "inspectSession": "<project>/10_WORK/visibility-01/inspect",
  "session": "<project>/10_WORK/visibility-01/session",
  "reopenSession": "<project>/10_WORK/visibility-01/reopen",
  "outputProject": "<project>/10_WORK/visibility-01/edit.fcproj",
  "inspection": "<project>/10_WORK/visibility-01/reopened.json"
}
```

Create the new work directory first. All output/session paths must be fresh. The FilmCraft adapter verifies the old owning contract and inspected fingerprint, changes only opacity on affected caption-owned layers in a native copy, saves/reopens, verifies exact new curves and compares all protected project state. Locked caption tracks, manual opacity changes, unrelated plan changes and no-op ranges are refused. Failed work remains for reconciliation; the original checkpoint stays unchanged.

For Resolve, use the same `kind`, pinned `previousPlan`, new `plan` and `expectedFingerprint`. Replace the FilmCraft path/session fields with a unique `title`, a fresh output `nativeProject` DRP path and a fresh `inspection` JSON path. The exact toolkit project and inspected parent timeline must already be selected. The adapter verifies native caption ownership, fonts and source clocks, then duplicates the timeline and pins its source clocks. It compares the complete inspected duplicate before changing only affected caption Merge `Blend` expressions. These expressions gate the owner's existing arrival curve on the timeline's frame grid; the foreground and both shadows use the same hidden ranges. Text, timing, Center motion, framing, graph connections, audio and inspected metadata stay protected. The parent is rechecked before saving/checkpointing the revised timeline. A locked primary picture track or another host version is refused. The existing Fusion fingerprint rules are unchanged.

Legacy projects containing a `hookContract` require their original pinned toolkit. Current builds do not add opening headlines. Caption visibility remains available for explicitly requested body-caption hiding/restoration.

A seven-second synthetic fixture completed base construction, hiding, restoration and replacement-hook rendering: four native 175-frame exports with identical decoded audio. Restored decoded video matched the base exactly. All 49 native lossless frames after the opening matched the base, including a caption spanning the cutoff. Sampled opening frames had no speech-caption or shadow remnants; inspected boundary frames showed the hook at 125 and the original caption at 126. Parent/source/checkpoint hashes stayed unchanged. This proves the tested direct adapter path. A subsequent fresh Codex/FilmCraft build and browser-submitted caption-hiding/hook revision passed with two immutable 175-frame versions, exact decoded audio, native ownership/protected-state checks and late feedback linked to read-only V1. See `LIVE_AGENT_LOOP.md`. Real footage, other engines/agents and human approval remain open.


Resolve Studio 21.1.1 build 10 subsequently passed a separate seven-second native fixture with the caption owner’s explicit Resolve profile. Base, hidden, restored and replacement-hook exports each decoded 175 frames with byte-identical audio. Restored decoded video matched the base exactly. Native stills verified foreground/shadow hiding, restoration, the headline at 125, and the original spanning caption at 126; every native frame from 126 through 174 matched the base. Each stage passed save/close/reopen with its complete inspected state unchanged. Original DRP hashes and the prior synthetic review project’s snapshot, render queue and page were preserved. No FilmCraft engine or Premiere integration was invoked.

The fixture initially supplied an incomplete timeline-reopening packet after the successful hide/restore renders. The existing precondition refused it before selecting a timeline; the failed packet and log remain retained. After recorded-process termination and actual host/checkpoint inspection, that operation was reconciled without replay. A new request used the hidden render receipt’s actual native project/database/timeline identity and succeeded. This was a fixture packet correction, with no weakened native guard. These were direct native tests. A later fresh Resolve-only Codex build and browser-submitted hiding/hook revision also passed: two immutable 175-frame versions, identical decoded audio, complete protected Fusion graphs/metadata, preserved checkpoints and late feedback opening read-only V1. See `LIVE_AGENT_LOOP.md`. That agent run’s stricter later-frame still check found differences of at most three RGB levels, initially seen between base and hidden timelines. Subsequent unchanged-checkpoint import and original-project reopening reproduced the later pixels before any edit; the visibility/duplication attribution is withdrawn. All 49 later native frames subsequently matched exactly after read-only reopening, with published state/files preserved. The earlier still-output variance remains unexplained; see `RESOLVE_STATE.md`. Other agents, real footage and human approval remain open.
