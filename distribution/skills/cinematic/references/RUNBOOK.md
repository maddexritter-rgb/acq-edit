# RUNBOOK — one cinematic-card clip, start to finish

**THE ONE operational recipe.** `SKILL.md` holds the *rules and why*; this holds the *sequence*.
Two clips shipped through it (BlackDotRoom 2026-08-09, UnreasonableToFail 2026-08-09). Everything
below was actually run — no step is aspirational.

Roughly **40–60 min** per clip, most of it the two ~4-minute renders.

---

## 0 · PREREQS — check before starting

```bash
ls __ACQ_SKILLS__/cinematic/scripts/          # engine (see §ENGINE FILES)
ls __ACQ_ASSETS__/assets/broll_lib/pp/      # b-roll, ALWAYS pp/ (H.264) never raw/ (AV1 → Premiere rejects)
ls __ACQ_ASSETS__/assets/fonts/             # OpenSauceSans family + Akira Expanded
```

🛑 **DO NOT RE-MINE A SOURCE `/edit` HAS ALREADY MINED.** Check first — it costs minutes and the
cut is usually already locked:
```bash
ls <source_project>/10_WORK/clips/                       # per-clip folders with cut_spans.json
python3 -c "import json;d=json.load(open('<src>/10_WORK/candidates_final.json'))['candidates'];\
print(len(d));[print(c['quality'],round(c['end_sec']-c['start_sec'],1),c['slug'],c['open_line'][:60]) \
for c in sorted(d,key=lambda x:-x['quality'])[:15]]"
```
**Pick on merit, not vibes.** Both shipped clips were q87–88 and 24–32s. Wanted: a `bold_claim` or
`direct_address` open, a real punchline exit, self-contained, and — critically — **a metaphor that
maps to ONE film** (white room → *The Matrix*; volume until failure is unreasonable → *Whiplash*).

---

## 1 · SCAFFOLD
```bash
bash __ACQ_ASSETS__/scripts/new_project.sh alex <ShortName>
```
→ `~/Downloads/alex/<YYYY-MM-DD>_<ShortName>/{00_SOURCE,10_WORK,20_DELIVER}`. Copy the engine in:
```bash
S=__ACQ_SKILLS__/cinematic/scripts; W=<project>/10_WORK
cp $S/{plate.py,gen_captions.py,face_frame.py} $W/
cp $S/caption_type.py   $W/caption_v2.py     # gen_captions imports it as caption_v2 locally
cp $S/chunk_captions.py $W/make_groups.py
cp $S/preview.py        $W/preview_fast.py
mkdir -p $W/cut $W/premiere/assets $W/build
cp <source_project>/10_WORK/clips/<Slug>/*.json $W/cut/
```

## 2 · MEDIA — one command
```bash
python3 make_media.py MASTER.mp4 cut/cut_spans.json <project>/10_WORK
```
Builds `AROLL_window.mp4` + `VOICE_cut.wav` from the spans and writes `media_offsets.json` into
**both** `cut/` and `premiere/assets/` (face_frame reads one, plate.py the other — a missing copy
makes the dark-flip silently default every word to white). It prints the `DUR` to put in the plan.

## 3 · WORDS — one command
```bash
python3 make_words.py cut/locked_transcript.json cut/timeline_words.json
```
Always from `locked_transcript.json`, never `words_fmt.json` — the formatted list silently dropped
a leading *"If"* on a shipped clip. The script prints the opening words; **read them against what
he actually says** before going further.

### 3b · SECOND SPEAKER? LIFT THEM OUT
```bash
python3 make_words.py cut/locked_transcript.json cut/timeline_words.json \
        --lift "Admission" --voice premiere/assets/VOICE_cut.wav
```
🛑 It finds the cut span from the **audio envelope**, not the transcript. On a real clip the
transcript's boundaries were wrong by 300ms and cutting to them removed a piece of the SUBJECT
instead of the host. The script prints both so you can see them disagree, then tells you the span
to apply to the media and how far to shift `DUR` and the shot boundaries. Verify after with ASR.

## 4 · CHUNK (before the shot plan — cuts must land on cue boundaries)
Retarget the **two clip-specific lines** at the top of `make_groups.py`:
`EMPH_PHRASES` (multi-word beats; must swallow any word too short to render alone) and `EMPH`
(rare single beats, ~10% of lines). Then:
```bash
python3 make_groups.py          # → generated_groups.py
```
Expect **~33–38 cues, 2.5–3.1 words/cue**. Print the cue boundary list — it's the grid the shot
plan must snap to.

## 5 · PLAN the shots
🛑 **COPY THE TEMPLATE — DO NOT WRITE IT FROM SCRATCH.**
```bash
cp __ACQ_SKILLS__/cinematic/templates/plan.example.py <project>/10_WORK/plan_v2.py
```
It already carries **cropdetect-measured `CROP` values for the whole b-roll library**. Writing a
plan by hand instead is exactly how the letterboxed-b-roll bug shipped — the correct numbers were
sitting in the template the whole time. If you add a NEW film source, measure it and add it back:
```bash
ffmpeg -hide_banner -ss 12 -i clip.mp4 -t 6 -vf cropdetect=24:2:0 -f null - 2>&1 | grep cropdetect | tail -1
```

🛑 **Pick b-roll timestamps by LOOKING** — build a contact sheet, don't guess. Skip anything
off-brand (on-screen profanity, graphic imagery).

Targets: **18–28 shots · 6.8–7.4 cuts/10s · median shot 1.2–1.5s.** Raise the cut rate with
b-roll cutaways, never by splitting A-roll. **Every `t0` must equal a cue boundary.**

## 6 · FRAME the A-roll
```bash
python3 face_frame.py premiere/assets/AROLL_window.mp4 plan_v2.py cut/media_offsets.json \
        cut/aroll_framing.json 0.58 0.28        # face_x  face_frac
```
`face_frac` drives scale. **Compute the fill floor = `980 / source_height` (90.7% for 1080) and
compare** — anything far above it is real zoom. Print the table and eyeball it: a shot disagreeing
with its neighbours by >15% is a tracker failure, not a creative choice.

## 7 · CAPTIONS
```bash
python3 gen_captions.py
```
Three gates must all print PASS, and the summary must look like:
`base/strong/emph/peak` all present · `fill` overwhelmingly white · glyph height med ≈ 60–70
(reference p25 49 / p50 70 / p75 97) · card-bounds PASS · luma-straddle PASS.

If luma-straddle fails it names the cue and cut — **move the CUT to the cue edge**, never recolour.

## 8 · MUSIC — the `/edit` 4-step chain
1. Classify the clip's vibe → lane. Cinematic → `(3) ViralREELS` (74 Notion tracks, vibe-tagged).
2. `_shared/pick_music.py --folder <lane> --used "<prior tracks>"`.
   🛑 **It ranks by distance to the `_APPROVED.txt` centroid.** That centroid is calm/low-energy,
   so it returns melancholy no matter the lane. **If the brief is upbeat, ignore the ranking and
   select on measured `energy`/`tempo` plus the Notion vibe tags** (Engaging · Hard · Sigma ·
   Phonk · Gym). Upbeat means energy **0.29–0.49**, not 0.10–0.13.
3. Vocals fight a monologue. **ASR cannot detect sung/rapped vocals over a beat** — it returns "🎵"
   and called *Not Like Us* instrumental. Use genre instead: phonk is reliably instrumental.
4. **The ear decides.** Build auditions by remuxing the finished picture — seconds, not a re-render:
   ```bash
   ffmpeg -y -i build/V<n>_preview.mp4 -i premiere/assets/VOICE_cut.wav -stream_loop -1 -i TRACK.mp3 \
     -filter_complex "[1:a]highpass=f=80,loudnorm=I=-16:TP=-1.5:LRA=11[vo];\
   [2:a]volume=0.22,afade=t=in:st=0:d=0.8,afade=t=out:st=<total-1.2>:d=1.2[mu];\
   [vo][mu]amix=inputs=2:duration=first,loudnorm=I=-14:TP=-1.0:LRA=11[a]" \
     -map 0:v -map "[a]" -c:v copy -c:a aac -b:a 192k -t <total> out.mp4
   ```
   Winner → append to `_APPROVED.txt`. **This is what stops the centroid drifting.**
   Then write the path into `10_WORK/MUSIC_BED.txt` (the renderer refuses to run without it).

## 8b · VALIDATE — before spending four minutes on a render
```bash
python3 check_plan.py <project>/10_WORK      # exits non-zero on any blocker
```
Checks all five things that have actually shipped broken: cuts off cue boundaries, gaps/coverage,
`CROP` vs cropdetect, cut-rate band, punctuation in cues. **Run it every time.**

## 9 · RENDER
```bash
python3 preview_fast.py          # ~4 min, auto-increments V<n>
```
`repaired N black boundary frames` should be a **handful**. If N is near a shot's frame count, the
repair pass ate that shot.

## 🛑 THE TAIL — 0.15s, NOT 1.7s (editor, 2026-08-12)
Set `TAIL = 0.15` in the plan. The 1.6–1.9s black tail in `STYLE_SPEC.md` was measured off the
ORIGINAL reference reels; **every delivered ACQ build ends with 0.00–0.20s of black**, two of them
on a live frame with none. A 1.70s tail shipped once and came straight back: *"it kind of cuts to
black abruptly and then has like a second of black."*

Three things move together, and fixing only the first leaves an ending that still reads wrong:
1. `TAIL = 0.15`.
2. The **final cue holds to picture-out** — every other cue is held until its successor takes over,
   so the last one was the only cue clipped to its own last word, and the payoff word vanished
   before the picture did. Fixed in `gen_captions.py`.
3. The **music fade is derived from TAIL** (`max(0.40, min(1.5, TAIL+0.35))`). The hardcoded 1.5s
   was invisible inside a 1.7s black tail; with a short tail it ducks the bed across the entire
   payoff line. Fixed in `preview_matted.py`.

> **A number measured off the reference is not automatically the number we ship.** Check the
> builds the editor already approved before trusting a spec row.

## 9b · INK GATE — BLOCKING, on the DELIVERED pixels
```bash
python3 ink_gate.py .            # exit 0 required, every render including a re-render
```
Measures every caption word's ink under its own alpha mask **in the rendered frame** and checks it
against the fill the manifest declared. Exists because the overlay blend silently recoloured black
ink to white on a white card — a 1.08s "FUTURE IS A STRANGER" beat rendered as a white-on-white
outline **while all three `gen_captions` gates printed PASS**, because those gates read the
declared fill and never look at a pixel. Validated on the known-bad build: it names the 4 words at
ink luma 252 on a plate of 229.

> **A gate on what we ASKED FOR is not a gate on what we SHIPPED.** Any layer applied after the
> caption PNGs are written (blend, matte, grade) can invalidate a decision the caption gates
> approved, and only an observed-pixel check can see it.

## 10 · VERIFY before sending
- Contact sheet of card crops (`crop((50,470,1030,1450))`), 8 frames, ~490px — **look at it**.
- b-roll fills the card: luma of a thin strip inside the top and bottom card edges is not near-black
  (excluding intentional `card` shots).
- ASR the audio at any edit seam.
- Zero punctuation across all cues.

---

## 🛑 THE MATTED VARIANT USES A DIFFERENT CAPTION ENGINE (2026-08-12)
`scripts/` holds BOTH, and copying the wrong one in as `caption_v2.py` is silent for two clips out
of five and a hard crash for the other three:

| variant | copy in as `caption_v2.py` | face | ladder |
|---|---|---|---|
| **matted** (the shipped look) | **`caption_matted.py`** | Europa Grotesk | graduated 108/118/132/150 + the `lead` lockup |
| house | `caption_type.py` | OpenSauceSans | flat 96 |

A batch built from `caption_type.py` died on `KeyError: 'lead'` for the three clips whose chunker
produced a two-line lockup, and rendered the other two **in the wrong font and a flat size ladder**
with every gate printing PASS — the captions were internally consistent, just not the approved look.
`caption_matted.py` lived only inside project folders until this was hit; it is in the skill now.

> **Two engines for the same slot is a trap that no gate can see.** When a variant needs its own
> file, the file has to live in the skill and the RUNBOOK has to name it.

## 🛑 TWO SPEAKERS: THE FACE TRACKER WILL FRAME THE WRONG MAN (2026-08-12)
Rule 5 (pick by CONFIDENCE, never by area) fixed choosing a wall fixture over a face. It does
nothing when there are **two real faces**. On a wide two-shot the host is often more front-facing
than the subject (who is in profile), so the host wins on confidence — and the shot gets framed on
him, at a plausible-looking scale, silently.

Measured on a real clip: three shots at cx 0.31-0.43 with 268-348px faces, and one at **cx 0.697
with a 153px face and scale clamped to 185%**. That is the host.

`face_frame.py` now REFUSES the run when a shot's face centre deviates >0.18 from the median cx, or
its face is under 55% of the median height — the subject is the person present in EVERY shot, so the
median is the subject's side. It also prints the per-shot scale/px/py/cx/face table on success.

**The fix is in the PLAN, not the tracker:** a wide two-shot is a poor 980-square card anyway, so
make that span b-roll. Map where the camera actually sits before planning:
```bash
# all faces per frame, every 1s: reveals exactly where the two-shot starts and ends
```

## ⚠️ A SHOT AT THE FILL FLOOR MAKES THE VERTICAL CLAMP DEGENERATE
When a face is large enough that `face_frac/fh` falls below the fill floor, `S` clamps to exactly
`CARD/SRC_H` and the vertical clamp window `[lo,hi]` collapses to a single point — then float error
on the re-check raises `AssertionError: vertical gap at the card edge` on framing that is correct to
within a billionth of a pixel. Now carries a 0.5px tolerance and reports the actual numbers
(face cx/cy/height, scale vs fill floor, and the legal max `face_x`) instead of a bare assert.

## ENGINE FILES — what each one owns
| file | owns |
|---|---|
| `chunk_captions.py` | cue boundaries · weight ladder · `show()` punctuation strip |
| `caption_type.py` | faces, sizes, tracking, `WHITE_PLATE`, fill · renders one word PNG |
| `gen_captions.py` | per-word items + manifest + **the three gates** |
| `plate.py` | reconstructs card content at time *t* (for the dark-flip) |
| `face_frame.py` | per-shot A-roll scale/position (YuNet, confidence-picked) |
| `preview_fast.py` | segments → captions → motion blur → mix → mp4 |
| `make_media.py` | spans → AROLL_window + VOICE_cut + both offset files |
| `make_words.py` | locked transcript → timeline_words · second-speaker lift |
| `check_plan.py` | **the pre-render gate** — 5 blockers, exits non-zero |
| `ink_gate.py` | **the post-render gate** — declared fill vs the ink actually rendered, exits non-zero |
| `plan_v2.py` | **per clip** — copy `templates/plan.example.py`, then DUR/SHOTS/FLASH |
| `caption_matted.py` | the MATTED variant's caption engine — copy in as `caption_v2.py` |
| `mine_emotional.py` | emotional-charge mining (stakes/loss/fear), NOT teaching arcs |

**Per-clip, everything else is reusable:** `plan_v2.py` entirely, and the two vocabulary lines in
`chunk_captions.py`. Nothing else should need editing.

## THE TRAPS, in the order they bit
| symptom | cause | fix |
|---|---|---|
| captions overlap on top of each other | per-WORD minimum duration pushed words past the cue end | a cue is atomic; pull short words **earlier** |
| glitchy / jumping | size, direction and magnitude varying per WORD | those are per-CUE; only **weight** is per-word |
| "too fast to read" | chunks capped at 3 words | 2–4 words → fewer, longer cues |
| b-roll letterboxed in the card | assumed 16:9 | `cropdetect` |
| Alex too zoomed | `face_frac` too high | compare against the fill floor |
| a beat vanished | repair pass ate the black card | protect `card`/`dot` frames |
| word invisible | 0.02s word alone in its cue | put it in an `EMPH_PHRASES` beat |
| captions read wrong on every shot | pinned to a corner | **centre them** (X/Y median 0.50) |
| gold/glow captions appear | `render()` default fill | always pass `fill` |
| a white-card beat is a faint outline, gates all PASS | the OVERLAY blend recolours beat words toward the plate; on a near-255 plate it returns white whatever the source, so BLACK ink is erased | overlay must skip `fill=="black"` (it is fixed in `preview_matted.py`); `ink_gate.py` blocks it |
| captions read as a ticker on a repeated phrase | an anaphora run ("you don't have the X") split mid-unit because the repeated subject was not a clause boundary | `"you"` is in `CLAUSE_OPEN` |
| a bare connective flashes on its own | `MIN_PHRASE 3` let "as long as" satisfy the clause-close test and ship as a 0.28s cue | `MIN_PHRASE = 4` |
| `check_plan` says crops are ✓ but b-roll is letterboxed | it hardcoded `pp/` while the matted plan links `pp5/`, so every crop was SKIPPED behind a green tick — and its `-ss 12` probe returned nothing on any clip shorter than 12s | reads `P.LIB`, probes at 25% of each clip's own duration, and FAILS when cropdetect returns nothing |

---

## 🎵 MUSIC — THE BAR IS **CHILLS** (locked 2026-08-10)

> *"The music has to be very emotional, very energetic. We have to give people the chills, make
> them feel a certain emotion with the music and the clip. And a lot of that's clip selection."*

The target is a physical reaction, not a track that "matches the vibe". A correct-but-flat pick
fails even if the measured picker ranks it top.

**🛑 THIS STYLE ALLOWS A VOCAL TRACK — the house "instrumental only" rule does NOT apply here.**
The strongest device found so far is the opposite of a neutral bed:

> a VOCAL hook whose **lyric restates the clip's argument**, timed to land in the opening seconds,
> mixed loud enough to actually be heard (~**−3 dB vs the VO**, decaying to a normal bed after).

Worked example (DreamsWillDie, shipped + posted): argument *"someone's dreams will die — yours or
theirs"* against the lyric *"a white blank page / and a swelling rage"* at 0.3s. The lyric states
the feeling before the first sentence lands. That is the mechanism — not the track being nice.

**Read the clip's THESIS first, then hunt for a lyric that says the same thing.**

### ⚠️ TWO DIFFERENT BED SHAPES — pick one deliberately
The lyric-hook shape (loud at the open, decaying to a bed) is for a track whose WORDS carry the
argument. For an instrumental or a slow-builder the shape is the opposite: **place the in-point so
the track's own rise happens across the clip's window, converge the level on the PAYOFF (≈−5 dB vs
VO), and let the open sit quiet (−11 to −13 dB).** Applying the opening lift to a build gives
loud→quiet→loud, which fights the track.

🛑 **Choose the in-point by measuring the rise ACROSS THE CLIP'S OWN WINDOW, not in the track.**
A lift detector run over the isolated track picked an in-point whose level *fell* 1.5 dB across the
clip — right answer to the wrong question. Sweep candidate in-points and maximise
`level(clip t 14–22) − level(clip t 0.5–5)`.

🛑 **Do NOT print a lyric transcript to find an in-point.** Reproducing song lyrics is off-limits,
and the search itself is unnecessary: the **energy envelope** gives the in-point directly, and it is
already the documented fallback for tracks ASR cannot read. Name the track, not its words.

→ Full method, approved tracks and the exact in-point/level recipe:
  `__ACQ_ASSETS__/assets/music_approved/_APPROVED.md`
→ Global music-selection logic (TikTok folder, picker, blacklist) is unchanged and still governs
  the house short-form bed: memory `reference_music_selection_2026-06-06`.

**CLIP SELECTION IS HALF OF IT.** Music can only amplify a charge already in the moment. A purely
informational moment cannot be scored into chills — for cinematic pieces select for stakes, loss,
defiance or warning, not just for a clean argument.

---

## 🛑 THE CUT COMES FIRST — VERIFY IT BEFORE ANY FANCY EDITING (batch of 5, 2026-08-11)

> *"You still have to edit these clips. The cut has to be very good, and then you do the fancy
> editing on top of it."*

**The loop, per clip, before touching b-roll/captions/music:**
1. Cut the spans.
2. **Re-transcribe the CUT AUDIO** (`faster_whisper` on `VOICE_cut.wav`) and READ it back.
3. Any clipped or phantom word -> **measure the RMS envelope at that boundary** and move the cut
   into the silence trough. Repeat until the read-back is clean.

On a 5-clip batch this caught **4 defects in 5 clips** that the transcript's own word times hid:

| defect | cause |
|---|---|
| opened on "*was* afraid" — the "I" gone | cut landed ON the word's start; the attack needs ~0.10s of lead |
| ended "risk *a verse*" | transcript end-time cut 0.33s off "aversion" mid-release |
| phantom leading "of" | entry sat mid-phrase with NO silence near it (best trough −36 dB) |
| trailing "And" bleeding in | next word starts exactly at the transcript's end time |

**🛑 A transcript word-time is not an acoustic boundary.** It is reliably off by 50–300ms, and
`start`/`end` of adjacent words frequently overlap. Cut on the ENVELOPE, always.
**And if a phrase has no silence around it, do not cut there — re-open the clip on a line that
does.** That usually improves the writing too.

### `make_plan.py` — shot plans derived FROM the cues
Shot boundaries must equal caption cue boundaries (check_plan enforces it), so generate the shot
list from the cues rather than round numbers. Cinematic variant targets ~3.0s shots (2–3 cuts/10s).

### `mux_music.py` — lyric-timed beds, auto-levelled
Re-muxes the bed onto an already-rendered clip (never re-render for an audio change), converging
the opening lift onto **−3 dB vs the VO** by measuring the music stem against the loudnorm'd VO
stem. Beds are chosen by LYRIC, matched to the clip's argument.
⚠️ Whisper hallucinates on heavily-reverbed music ("Thanks for watching!"). When ASR is unreliable,
find the vocal entry from the ENERGY ENVELOPE instead and say so.

### Selective captions (`chunk_accumulate.drop_noise` + `keep` map)
Stutters and filler ("the, the boy", "I mean") are dropped from the CAPTION while the audio keeps
its natural delivery — the reel study's "captions are selective, not a transcript". Each group
records `keep`, the source-word index of every shown word, so gen_captions times word k from the
word it actually came from; without it every drop pulls the rest of the phrase early.

---

## 🎬 ROUTE 8C — EDITOR OWNS THE CUT (Premiere assembly handoff, 2026-08-11)

> *"We'll just do the 16:9 assembly cuts, and then just import XML that I can edit and extend,
> because I noticed a lot of them were just too short. I'll give you the cuts of the clip that I
> want, and then you can add on the fancy edits."*

**Inverts the pipeline.** The machine mines and proposes; the EDITOR sets the final in/out; the
machine then applies the cinematic layer to THEIR cut. Use this whenever cut length or cut taste
is the sticking point — it is faster than iterating renders.

    mine moments -> build_assembly_xml.py -> editor extends/trims in Premiere
      -> read the sequence back over the MCP -> cinematic 9:16 treatment on their cut

**`build_assembly_xml.py` — the handoff artifact**
· 16:9 xmeml, one clipitem per moment, video+audio LINKED so trimming picture takes sound.
· 🛑 Each moment points at a **1080p H.264 proxy window with a 60s handle each side**, NOT the
  master. Our master is 4K AV1 and Premiere scrubs it miserably; more importantly, trimming
  OUTWARD is the whole point and the handle is the room to do it.
· `assembly_moments.json` records each window's `win_start` in master time, so the editor's final
  in/out maps straight back with `master_t = win_start + timeline_in`.
· A multi-span moment is laid as ADJACENT clipitems so the interior seam stays trimmable.
· A named marker per moment puts the slug on the timeline.

**Validate before handing over** (a broken XML wastes the editor's time, not ours): parse it and
assert — every referenced file id is defined exactly once, every pathurl exists on disk, `out-in`
== `end-start` for every clipitem (else something got retimed), no negative in-points.

**Reading their cut back:** `premiere_agent.py inspect get_full_sequence_info` through the shared startup route gives every clipitem's
in/out/start/end. Map through `win_start` to master time, then feed those spans into the normal
cut -> verify -> cinematic pipeline. **The RMS/re-transcribe verify loop still applies** — the
editor trimming by eye can still leave a clipped attack.

🛑 **Do not import into whatever project happens to be open.** Ask first — an unrelated job's
project should not collect our sequences and bins.

### 🛑 PREMIERE MCP GOTCHAS (measured 2026-08-11, Premiere 25.0.0)
1. **`import_fcp_xml` fails with "Not Enough Parameters".** Use **`import_media`** with the .xml
   path instead — it imports the sequence correctly.
2. **Give every `<file>` an explicit `<duration>`.** Without it Premiere stretched the LAST video
   clipitem to the full media length — 108.98s of video against 48.97s of audio, silently out of
   sync. It only showed up because the sequence was read back and video/audio durations compared.
   **Always read the sequence back after import and assert `vdur == adur` per clip.**
3. **A contiguous assembly cannot be extended** — dragging an out-point outward collides with the
   next clip. Leave `GAP_S = 20.0` between moments (spans *within* one moment stay butted; that
   seam is the cut).
4. **Sequence deletion is not reliably exposed** — `delete_sequence` reports "Sequence not found"
   even with the exact id from `list_sequences`, and `projectItem.deleteBin()` is a no-op on a
   sequence. Superseded sequences have to be cleared by hand in the Project panel.

### 🛑 FRAMING — `Py` MUST BE COMPUTED FROM THE FACE (bug found 2026-08-11)
`face_frame.py` hardcoded `Py = 0.5` while computing `Px` properly from the detected face. That is
invisible at fill scale — a 16:9 source scaled to cover a 980 card has NO vertical freedom, so 0.5
is the only legal value — but the moment a shot punches in (Alex leaning back makes the face small,
so S climbs to ~1.44) vertical centring shoves his head off the TOP of the card. Two shipped clips
came back with "Alex is cropped pretty weirdly."

Py is now `(CARD_Y + face_y*CARD - (cy - SRC_H/2)*S) / H` with `face_y = 0.34` (head in the top
half, matching the horizontal rule), clamped so the card stays covered.

**The general lesson: a default that is provably correct in the common case can still be a bug in
the uncommon one.** 0.5 was right for every fill-scale shot we had ever rendered, which is exactly
why it survived so long. When a value is only ever exercised at one extreme, test the other.

**Check framing BEFORE rendering.** Recreating the card crop from `aroll_framing.json` with a
single ffmpeg `scale`+`crop` costs a second and catches this; a render costs ten minutes.

### ✅ B-ROLL METHOD — CONFIRMED (editor, 2026-08-11: *"exceptionally done well"*)
What produced it, in order of importance:
1. **ONE film per clip, chosen for the ARGUMENT** — not a vibe match. Rocky for fear-then-go,
   Oppenheimer for the dream that became the nightmare, Creed for "someone in your corner",
   Whiplash for the lonely cost of exceptional.
2. **Duration-aware planning.** The library is mostly 1.4–7.0s clips; a shot longer than its
   source freezes on the last frame. `make_plan.py` matches each slot to a clip that covers it.
3. **A forced reuse starts at a DIFFERENT offset** so identical frames never play twice.
4. **Eyeball the candidates on one contact sheet before planning** — that is what caught the
   misfiled Matrix/Alex footage and the watermarked Rocky clip sitting in the library.

### 🛑 DEAD AIR IS INVISIBLE IN A TRANSCRIPT — RUN THE GATE (batch rejected 2026-08-11)
8 assembly cuts were proposed; 7 were rejected outright — *"the cuts were terrible."* The
boundaries were RMS-verified to the millisecond and every clip had been re-transcribed and read
cold. **The interiors were never measured.** They carried **6–34% dead air**, worst a **5.86s
silence in the middle of a clip**.

**A transcript cannot show you a pause.** Every word is correct and in the right order; the clip
still crawls. Reading is necessary and NOT sufficient — the envelope is the only witness.

**Proof it was the cause:** on the single clip the editor kept, his own edit removed exactly the
2.74s silence at 7.6s that the gate would have flagged. He hand-fixed the defect.

**Now mandatory before ANY cut is shown to the editor:**
```bash
python3 scripts/tighten.py <slug>          # maps silences in the CUT audio back to master time
```
· silences >= 0.50s inside a clip are cut to 0.22s of breath
· head/tail are left to the boundary work
· report % dead on the DELIVERED file; a shippable cut is ~0 pauses >= 0.3s
· a removal seam in a talking head can jump-cut — place it under a b-roll cut where the shot
  changes anyway, which the cinematic style is already doing every ~3s

**The general failure mode: verifying one dimension exhaustively and never checking another.**
Boundaries were measured to 10ms while a six-second hole sat in the middle. When a whole batch is
rejected, suspect an UNMEASURED dimension before re-tuning a measured one.
