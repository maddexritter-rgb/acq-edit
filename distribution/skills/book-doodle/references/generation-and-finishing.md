# Generation and finishing

## Still: stable style, exact concept

Attach all three supplied `refs/*.png` to each still request unless the batch has an explicitly selected replacement reference pack. Use the available image-generation skill/tool; inspect references before editing. Adapt aspect ratio to the diagram, preserve generous blank space, and reserve caption space when placing it on the final 9:16 canvas.

The tested starting sizes were 2048x1152 landscape and 1024x1024 square. A square composition often fits a tall cutaway better; neither is a mandatory model capability. Use a supported size and avoid stretching it to fill the frame.

Reusable prompt prefix, followed by the exact approved beat:

> Match the reference images in drawing style: thick black felt-tip marker on plain white paper, hand-lettered ALL-CAPS text, simple stick figures, rough arrows, flat 2D, no shading, generous white space, no color except one green emphasis mark when useful. Draw a NEW illustration; do not copy the reference words, logos or brand identity. Draw:

Describe positions first, then objects/actions. Quote exact permitted labels in ALL CAPS; use only words actually spoken, except user-approved labels. End with “nothing else” when added labels/props would confuse the idea. Do not invent a number, claim or logo. Preserve a supplied product image when it is the subject; do not generate a look-alike cover.

Inspect the still for concept accuracy, readable letters, intended relationships and spare space. Approval of the moment allows this internal QC without another user stop. Repair a localized flaw using the available image-edit tool, or reroll that still; reject it before paying for animation. A material new metaphor goes back into the user proposal.

## Animation: blank first frame, accepted still last

The tested pairing used MiniMax H3 image-to-video, a requested six-second/2K job, **white start image plus the accepted still as end image**. Discover the current provider tools and schema; support and field names vary. A provider lacking end-frame control is not equivalent to this recipe. Do not silently substitute a mode that flashes the finished drawing at the start.

Create the blank white start image at exactly the still's dimensions. Use a standard image writer or FFmpeg for this solid-color utility asset. Keep any copied product image exception explicit in the prompt.

Reusable animation prefix:

> Flat 2D doodle on plain white paper. Locked camera, no zoom or parallax. Thick black marker lines with slight hand-drawn irregularity. No new objects, no text changes, no geometry changes. Ink appears by itself through a digital stroke reveal. No physical person, hand, arm, skin, pen or marker enters the image at any time. Every line is black except the approved emphasis mark and any supplied product image. Hold on the finished drawing.

Then specify the reveal order in the speaker's order: “First A, then B, then C, finally the green circle around X.” View the full animation at normal speed and inspect its ending; a contact sheet alone can miss a brief hand or text mutation. A failed hand/pen exclusion can be retried with stronger digital-mask language, but repeated failure calls for a simpler treatment, not unlimited generations.

Store request settings and job IDs before polling. Resume an existing job instead of resubmitting after an uncertain response. Save accepted and rejected revisions with reasons; do not overwrite an accepted animation during a retry. Preserve actual returned media properties: a six-second request can return a longer clip at another FPS.

## Conform picture plates

Probe actual decodable frames, FPS and dimensions. Match the destination timeline (30fps in a 30fps batch; retain 30000/1001 or other actual rates when applicable), not a hardcoded 23.976. Fit the whole drawing inside the planned diagram box without cropping labels or stretching its aspect ratio. White canvas fills the rest of the frame; captions occupy their own reserved area.

Use the helper for exact frame counts:

```bash
python3 scripts/make_plate.py --input <accepted-animation.mp4> \
  --output <project>/10_WORK/doodles/<moment>-plate.mov \
  --fps 30/1 --frames 90 --box 1000 800 40 260
```

The default is 1080x1920, ProRes 422 HQ. `--box` is width, height, x, y within that canvas. The helper computes a speed to fit the animation plus a short final hold; `--speed` and `--hold` allow intentional timing. If the reveal would become unreadably fast, simplify the illustration or revise the placement; don't hide the problem with a rapid flash. Dense diagrams need longer reading time, not a universal minimum/maximum percentage of the clip.

For a transparent alternative, add `--alpha-output <moment>-alpha.mov`. It keys white from the **same** accepted animation and exports ProRes 4444; the full-screen and alpha versions share geometry, timing and frame count. Inspect edge fringe, lost pale detail and black-ink contrast over the actual background. Alpha is optional and is not visually interchangeable with clean white full-screen cutaways. ProRes 422/422 HQ does not carry alpha; 4444 does.

## Integrate into the locked edit

Default: full-screen white cutaways only at approved moments, source speech continuous underneath, then back to the original picture. Time the first meaningful mark to the spoken cue, reveal in spoken order, allow a readable finished hold, and choose a clean cut or brief fade suited to that beat. Do not add transition time outside the approved interval or change the audio to match a generated duration.

**Premiere:** import plates as removable, retimable picture items above source footage and below the caption layer(s). Allocate tracks accordingly rather than assuming V2 is free. Keep source cuts, native reframing keys, separate voice/music lanes and their timing intact. Render only the final sequence; generated asset plates are permissible media, not flattened finished edits. Verify the imported clip's actual duration and alpha interpretation with a native frame test.

**Captions:** → Use the existing caption skill for the project's style and timing, including readable contrast over white. Keep captions above the illustrations. If the source has burned captions, reconstruct only the captions covered by the cutaway using the same spoken words and exact interval; do not duplicate captions outside it or guess missing words. Supply explicit caption-safe areas during drawings instead of deriving layout from an absent face.

**Explicit headless finishing:** this skill supplies the approved plates and intervals; use the selected renderer's real compositing path, with drawings after the footage grade and before captions. The current manifest render engine has no built-in doodle stage: adding a `doodles` key alone does nothing. If that engine is in use, implement and verify an actual composition stage/integration before claiming support; include plate contents and decision/placement changes in cache keys. Do not silently bypass the existing engine or change a Premiere-default batch to headless. Keep the source edit, picture, captions and audio independently reproducible even when the final output is a flattened MP4.

## Final checks and receipts

- Inspect each whole draw-on, the complete diagram, its legibility at phone size, and every cutaway entry/exit. No hands, pens, invented objects, altered labels, exposed old captions, or black seams.
- Verify exact clip length and frame count, full-file decode, and source-audio continuity/sync. Source metadata may overstate decodable picture frames; preserve complete speech and document any necessary last-picture hold. If compressed source audio causes native timing/level discontinuities, conform the same audio to PCM and recheck against source in several windows.
- Give auditors the explicit intentional illustration and hold intervals. A legitimate finished-drawing hold is different from an unexplained source freeze; retain all other checks.
- Match planned, approved and integrated moments one-for-one. Export through the normal edit review/delivery gates. Sampled checks must be described as sampled, not a claimed uninterrupted watch/listen.
- Keep prompts/reference hashes, actual provider/model/settings, generated asset revisions, measured durations, generation latency, revision reasons, estimated versus billed usage and plate/export QC beside the plan. No hardcoded failure rate, token count, turnaround or cost promise comes from a small test batch.
