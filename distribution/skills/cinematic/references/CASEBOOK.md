# CASEBOOK — how each rule in SKILL.md was learned

Every rule cost a rejected version. Read this when you are tempted to override one, or when a gate
fires and you want to know what it protects against. Origin: the 2026-08-08/09 session that
reverse-engineered the style from three reference reels.

---

## 1. The fabricated caption style (the worst one)

**What shipped:** captions in a cream→gold gradient with a warm glow covering 1.29× the glyph area.
Editor: *"where in the reference reels did you get this caption style? this looks absolutely
terrible."*

**Root cause:** the treatment was generalised from **ONE frame** — a payoff shot where warm
background light bled into the compression around white letters. It was never checked against the
rest of the reel.

**What the data actually said**, once every text-bearing frame was sampled (1,473 frames):
mean glyph RGB (238.1, 232.6, 232.2), R−B median +2.6, 79% neutral white. Even the warmest frame in
three reels is (253, 252, 207) — red and green both pinned, only blue down. The fabricated version
was (237, 187, 124).

**The clincher:** in one reference shot, `DO` renders white at 30.40s and `HARD` renders warm at
30.53s — same shot, two frames apart. The only difference is neutral background vs an orange wall
behind the strokes. **The type is white; the warmth is the shot.**

**Shadow test** ('RELENTLESS', white type over movie b-roll): ring luminance 3–9px = 149.8 (glyph
antialiasing), 9–17px = 88.7, far background = 84.1. No darkening anywhere → **no shadow, no glow.**

> **Rule: generalise from a distribution, never from one frame.** The canvas geometry survived this
> test (980×980 at 27 timestamps); the caption colour did not.

## 2. Watching vs sampling

Editor: *"that's why I told you to watch it at 15 frames per second… did you actually watch at least
one video at 15 fps?"* The honest answer was no — 11 sheets had been generated and 4 read, and the
colour call had used 3 hand-picked frames instead of the 15fps set at all.

**Why it went wrong mechanically:** contact sheets are 128–150px tiles. Useless for colour. So when
colour was needed, the sheets were abandoned for a few full-res grabs — the worst of both worlds.

> **Rule: sheets for STRUCTURE, full-res frames for COLOUR/SIZE.** Extract every frame at 15fps
> (~500–600 per reel) and analyse them all programmatically.

## 3. The measurement trap that nearly doubled caption width

The glyph detector is "bright pixel with dark neighbours". **A bright window with dark mullions
trips it.** Both the reference reel and our own A-roll have one behind the subject, so the
block-width aggregate was contaminated on BOTH sides — it reported reference 0.71 and ours 0.92, and
a chunk-length sweep "hit" 0.71 exactly at 6 words per chunk. The frames actually watched showed
1–3 words spanning 0.25–0.45.

> **Rule: measure our own captions from their ALPHA MASKS (exact). When an aggregate disagrees with
> what the frames plainly show, the frames win.**

## 4. Framing — the subject fell out of the card

A hardcoded centre crop (position 0.536) was used while the subject actually sat at cx 0.64–0.69 of
frame. Result: head jammed against the card's right edge, and on the wide shot only a desk and a
hand were visible. Face-tracking is the standing default and was simply skipped.

Then two sub-failures while fixing it:
- **Face picked by AREA** locked onto a wall fixture (score 0.60, cx 0.135) over the real face
  (score 0.93, cx 0.735). → pick by CONFIDENCE with a floor.
- **The fix still didn't land** because xmeml's horizontal centre is in FRAME-HEIGHT units:
  `premiere_x = 0.5 + xml_horiz × (H/W)`. Passing `(px − 0.5)` through landed the crop ~44% off.

## 5. Captions sitting on top of each other

`_line_metrics` used PIL's `font.getbbox()`, which is **origin-relative** — it returns ascent 0 for
every line. Baseline spacing collapsed to a constant and the `air` parameter became a silent no-op.
Fix: `getbbox(text, anchor="ls")`. A measured gate now clusters glyph rows per state and reports the
tightest inter-line gap.

## 6. Premiere / bridge failures

- **AV1.** 5 of 7 library clips were AV1; Premiere threw "unsupported compression type" and one
  imported with a bogus 2.75e-8 frame rate. **The MCP reported `imported: 4` while the rejection
  dialog was on screen** — a tool's success value is not proof.
- **Wrong project.** The active project silently switched back to an unrelated one and an
  un-guarded `importFiles` dropped a whole sequence and its media into it. It was unsaved, so disk
  was clean — recovery was "close without saving". Every call now carries the name guard.
- **Audio laydown destroyed the timeline twice.** `seq.audioTracks.addTracks` is not a function and
  fell through to Audio 1, overwriting the voice; then `audioTrack.overwriteClip(linkedAVitem, t)`
  dragged the linked VIDEO along and cut V1 from 24 clips to 3. `app.project.undo` is not exposed
  and re-opening does not revert (Premiere re-fronts the in-memory copy). Recovery = re-import the
  XML as a fresh sequence. **Put audio in the XML.** (Music on its own `<audio>` track imports fine —
  the "standalone audio defs are rejected" warning applies to defs without clipitems.)
- **Lumetri is unreachable** through this bridge (`list_available_effects` returns empty without QE).

## 7. Decorating instead of editing

The first build wrapped the card style around a RAW 33.65s window — no cut. Editor: *"You're still
editing the actual clip. You need to edit the clip where you cut out the arms, ums, pauses, and have
a good hook and a good ending."*

Running the `/edit` spine properly then found real defects the decoration had hidden: a 0.86s dead
beat inside a stretched word, and a filler + 1.54s pause immediately before the payoff.

> **Rule: `/edit` first, always. This skill owns the LOOK, not the CUT.**

## 8. Colour grade — handed back to the editor

Two grade attempts were rejected ("dog shit"). The reference plate is warm, moody and shallow-focus;
approximating background defocus with a radial matte inverted and blurred the subject's face. Real
background defocus needs subject matting (MatAnyone), not a radial approximation.

**Standing decision (2026-08-09): the editor does the colour grade and will teach the method.
Do not apply a grade.** When the method is taught, write it up as its own reference and have the
pipeline call it — never re-derive a look by guessing off reference frames again.
