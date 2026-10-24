# Native camera panels

FilmCraft and Resolve construction accept `panel-layout` as a framing decision for a cut. In FilmCraft, each panel remains a native source-linked sequence; a native layout sequence composes them, and the master contains that layout for the exact cut interval. Dialogue stays on the master's original audio track. Captions and imported graphics remain outside the panel nests. There is no intermediate stacked movie or editor conversion.

Assembly Design owns camera choice, sync ranges and layout intervals. The packaged horizontal-to-vertical skill owns panel-specific crop/tracking and visual inspection; use its `references/native-split-setup.md` contract. The adapter consumes those decisions and never detects a subject or invents synchronization. Hashes prove which decisions were executed, not that camera sync or composition is editorially correct.

## Plan and camera receipt

The ordinary `acq-edit/framing-v1` receipt still pins the framing decision. A `shots[cutId]` entry can be:

```json
{
  "mode": "panel-layout",
  "cameraReceiptPath": "<project>/10_WORK/camera-decision.json",
  "cameraReceiptSha256": "<sha256>",
  "panels": [
    {
      "id": "top",
      "sourceRange": {"sourceId": "<camera-a>", "sha256": "<source-hash>", "inFrame": 50, "frames": 25},
      "rect": {"x": 0, "y": 0, "width": 360, "height": 320},
      "crop": {"mode": "fixed-crop", "sourceWidth": 640, "sourceHeight": 360, "x": 80, "y": 20, "width": 360, "height": 320}
    },
    {
      "id": "bottom",
      "sourceRange": {"sourceId": "<camera-b>", "sha256": "<source-hash>", "inFrame": 75, "frames": 25},
      "rect": {"x": 0, "y": 320, "width": 360, "height": 320},
      "crop": {"mode": "fixed-crop", "sourceWidth": 640, "sourceHeight": 360, "x": 120, "y": 20, "width": 360, "height": 320}
    }
  ]
}
```

This example targets a 360×640 output. The camera receipt has `schema: "acq-edit/camera-layout-v1"`, `owner: "assembly-design"`, the output `width`, `height`, `fps`, and `cutsSha256` from `common.fingerprint(spec['cuts'])`. Its `layouts[cutId]` is the exact ordered list of each panel's `id`, `sourceRange` and `rect` (excluding `crop`). This binds camera choices to the complete current assembly. The framing owner cannot change those choices by changing a crop receipt alone.

Each cut has two to four uniquely identified panels. Integer output rectangles must tile the whole frame without overlap or gaps. Each camera's range must have the cut's duration, a nonnegative source in-frame, a registered source hash and enough source frames. Indexed frame counts are used when available; otherwise frame counting runs once per source during that validation. Nominal and average source rates must match the timeline. These checks are not complete packet-level VFR certification.

Each panel crop must match its own rectangle's aspect ratio, not the master frame. It can use the existing fixed-crop contract or a source-bound `tracked-crop` curve. Tracking's source ID/hash/in-frame/count must match that panel camera, which can differ from the dialogue cut. Nested panel layouts, output gaps, border/shadow effects, arbitrary opacity and retiming are not supported by this construction path.

## FilmCraft construction and inspection

Each occurrence gets distinct `ACQ_Panel_<cut>_<panel>` sequences and its own `ACQ_Layout_<cut>` container. Panel sequences contain one original camera item and no audio. Their dimensions crop the source to the panel, and their parent nests use static native Motion to place them in the output. Tracking keys live inside each camera sequence at the camera's source clock. Separate occurrences do not share editable framing state.

The new master is initially assembled with its original linked sources. After creating the native nests, a typed saved-project construction step changes only each panel cut's picture reference/source-in to its generated layout and resets that new parent's Motion to identity. Existing master clip identities, record intervals, links, dialogue, captions and graphics remain. The project is reopened natively before use. This is new-project construction, never an in-place reconstruction of an inspected user project.

Saved-native verification checks the master and nested clocks, source paths, dimensions, panel rectangles, all tracking keys, unique nest identities, enabled tracks/clips, lack of nested audio, identity parent transforms and the supported effect stack. It refuses flattened replacements, unexpected masks, rotation, opacity, time-remap, track effects and shared occurrences. Render rechecks the plan and native graph before invoking FilmCraft's exporter.

Caption-only revisions retain and reverify the complete layout. `fixed-framing` and `tracking-framing` cannot edit a panel target. Panel-framing/layout revisions still need their own guarded native route; report that limitation rather than rebuilding the user's timeline or changing dialogue. Review text mentioning panels/layouts routes to both Assembly Design and horizontal-to-vertical without automatically requesting a spoken recut.

Premiere explicitly rejects this shared panel-layout transport before native mutation. Its native implementation remains required for the pilot. Do not substitute another engine, a converter or a flattened panel file.

## Resolve construction and inspection

Resolve Studio 21.1.1 build 10 constructs a Fusion composition directly on each selected picture cut. Each camera is a native MediaIn bound to its imported Media Pool ID and original file, with independent source trim and composition clocks. Fixed Crop/BetterResize nodes or the native horizontal Transform/XYPath/BezierSpline route frame each camera. Merge nodes position the panels over a transparent output-sized canvas. Captions follow the composite, and imported graphics remain separate timeline tracks. The original dialogue cuts and links remain unchanged; panel inputs add no timeline audio. No Premiere or FilmCraft process executes this route.

The adapter verifies source paths, persistent Media Pool IDs, native source dimensions, trim/global clocks, per-panel crop/tracking, connections, masks/bypass, output format, rectangles and the final caption/output chain. It removes only the unused default MediaIn in the newly created composition. Existing user graphs are never reconstructed. Construction writes the persistent native media identity and sets the output format after camera initialization, so save/close/reopen retains the complete fingerprint without weakening Fusion state checks.

Caption-only revisions duplicate and reverify the native layout. Fixed-framing requests targeting native panels are rejected before timeline duplication, even when the new plan incorrectly claims a single fixed crop. Panel-layout/framing revisions remain unsupported. The native calls use Blackmagic’s installed scripting interfaces and the [Fusion scripting reference](https://documents.blackmagicdesign.com/UserManuals/Fusion8_Scripting_Guide.pdf), including tool deletion and composition preferences; live behavior was verified on the stated Studio version.

## Observed mechanical evidence — 2026-10-23

FilmCraft built, saved/reopened and natively exported a 50-frame 360×640/25 fps fixture containing two generated camera sources: a tracked top panel, fixed bottom panel and later full-frame shot. Sampled first/middle/last panel frames and the full-frame boundary were viewed; both cameras and the master caption were visible with the expected crop. A native caption-only revision preserved every other project field except expected copy-derived document labels. Original checkpoint hashes were unchanged. Decoded audio was byte-identical across the single-camera baseline, panel render and caption revision.

A second 75-frame fixture used two independent split occurrences around a full-frame shot, nonzero camera source in-points and a later master record time. Native readback verified all panel source clocks and independent occurrences, and the native render passed frame count/geometry/full decode. Corruption checks refused disabled panel tracks, nested audio, shifted nest placement, changed opacity and shifted source clocks. Unit tests additionally cover missing camera receipts/binding, gap/overlap geometry, source duration/hash/rate changes, flattened/shared nests, masks and rotation.

Every decoded panel frame in both fixtures retained the intended camera color at all panel corners. The top source marker followed the supplied horizontal curve with at most 0.75 output-pixel edge error and fixed vertical bounds; the lower marker's rectangle remained fixed. Split entry/exit and repeated-occurrence contact-sheet frames were viewed. These measurements establish synthetic geometry transport, not human headroom or real-camera synchronization.

Resolve independently rendered a 75-frame 360×640/25 fps moving-marker fixture containing two split occurrences around a full-frame cut. Each camera used a different source clock; the top panel tracked horizontally and the bottom used a fixed crop. Save/close/reopen retained an identical complete native fingerprint. A caption-only revision rendered 75 frames, retaining the parent timeline/checkpoint and all inspected timeline fields after accounting for duplicated item identities. Exported Fusion graphs differed only in the requested caption wording and duplicate-specific Resolve cache paths.

Every panel frame in both Resolve versions passed camera-color and moving-marker checks. Maximum marker-edge error was 0.75 pixels in the top panel and 1.0 pixel in the lower panel. Sampled entry/exit, middle and repeated-occurrence frames were visually inspected. Decoded audio was not byte-identical: the difference measured −77.44 dB relative to signal. This remains an open audio qualification; no listening or audibility conclusion is inferred. These fixtures use simple test captions and do not qualify the production caption handoff on panel layouts.

This is direct native-adapter evidence with synthetic media. It does not establish real multicamera synchronization, headroom/phone composition, agent-driven panel planning/revision, both-agent acceptance, Premiere panel support or human approval.
