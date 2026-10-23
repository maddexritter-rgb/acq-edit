# Premiere assembly via MCP bridge (proven pattern, 2026-07-14)

1. `open_project` the job's .prproj (Premiere may have another project fronted — always open explicitly).
2. `import_media` the source into 00_RAW bin.
3. First span: `set_item_in_out` (frame-exact seconds) → `create_sequence_from_clips` (sequence inherits source settings; in/out carries).
4. Remaining spans in ONE `execute_extendscript` call (4 sequential tool calls per span is fragile; batch it):

```javascript
var seq = app.project.activeSequence;            // verify seq.name first!
var item = __findProjectItem("<source name>");
var spans = [[srcIn, srcOut, timelinePos], ...]; // frame-exact: floor(t*fps)/fps (+0.002 guard)
for (var i = 0; i < spans.length; i++) {
  item.setInPoint(spans[i][0], 4);
  item.setOutPoint(spans[i][1], 4);
  var t = new Time(); t.seconds = spans[i][2];
  seq.insertClip(item, t, 0, 0);
}
```

Gotchas:
- Playhead does NOT advance after insertClip — compute positions cumulatively (frame counts, not float sums).
- `set_playhead_position` does not clamp to sequence end.
- Timeline starts at 0.5s (leader) per THE CUT RULES. create_sequence_from_clips places
  the first clip at 0 — shift it with `videoTracks[0].clips[0].move(0.5)` (plain number
  works in v25; Time-object fallback), THEN insert the rest at positions that already
  include the 0.5 offset. Verified 2026-07-14 across 3 sequences.
- `add_text_overlay` errors ("Illegal Parameter type") in bridge v25.0 — do NOT use; overlay
  pre-rendered transparent PNGs on V2 instead (import_media → Track.overwriteClip → set clip.end).
- `export_frame` errors ("seq.exportFramePNG is not a function") in bridge v25.0 — verify via
  timeline data + editor scrub, or AME-export a short range.
- Premiere switches fronted projects between sessions — ALWAYS open_project + verify seq name
  before any ExtendScript mutation.
- SRT captions: `import_media` the .srt → `create_caption_track {item_id, format subtitle}` (stage 2 only).
- Verify at the end: last clip's `end.ticks` must equal computed total (frame-exact).

## Proven end-to-end flow (2026-07-14, 4 sequences)
1. Frame-quantize spans in python: fa=floor(in*fps), fb=floor(out*fps); pass fa/fps+0.002;
   positions = 0.5 + cumulative_frames/fps. Probe fps per source — never assume.
2. Sanity-gate every cutlist before assembly: spans strictly increasing, in<out,
   monotonic, total within runtime target.
3. After the insert loop, verify last clip end.ticks == computed total, then app.project.save().
4. Cut-only preview render for the review gate: ffmpeg select/aselect with the same
   frame numbers, scale to 1080p, NO gfx/captions/loudnorm — the editor reviews the CUT.


## CARD BLUR — must be a SEPARATE TIME-MATCHED PASS (bug fixed 2026-07-15)
The inline blur in the build loop SILENTLY FAILS two ways, and ffmpeg verify-burns HIDE it
(ffmpeg applies its own blur, so the burn looks right while the Premiere sequence is flat):
1. `qe track.getItemAt(j)` is NOT aligned to DOM `videoTracks[0].clips[j]` — the 0.5s leader
   and inter-clip slots appear as empty QE items, so blur lands on the wrong clip or none.
   FIX: build `real[]` = QE item indices whose `.name` is valid (wrap in try/catch); its length
   equals DOM clip count and `real[d]` is the QE item for DOM clip d.
2. Setting `Blurriness` immediately after `addVideoEffect` in the same script DOESN'T COMMIT
   (reads back 0). FIX: TWO passes in SEPARATE execute_extendscript calls — Pass A adds
   `getVideoEffectByName("Gaussian Blur")` to each card beat (matched by start time to plan
   card positions, via real[d]); Pass B sets Blurriness=220 (+Repeat Edge Pixels=true) on each
   card beat's DOM component. Then a 3rd read-back pass MUST confirm getValue()==220 on every
   card beat (objective proof — you cannot screenshot the native sequence: export_frame and
   AME export are both broken in bridge v25).
Card beat = the guest's live listening footage before the answer, so blur gives the moving
blurred background under the question text (the approved Stetson look).


## CARD DURATION + MUTE (editor 2026-07-15)
- Cards are a SET 2.0s (48 frames @23.976; prep_clip CARD_DUR). Not variable — uniform pacing.
  Beat = 2s of blurred pre-answer footage; if the answer starts <2s into the source, take the
  first 2s instead (still blurred). Fixes "some cards too fast".
- MUTE the card beat's AUDIO — no room noise under the question. Same index trap as blur:
  a.clips[j] by segment index is WRONG (leader + sweep desync the audio track). Do it as a
  time-matched pass: disable each audio clip whose start ≈ a card position. Verify by read-back
  (a.clips[i].disabled === true on every card-position audio clip).


## OPENING FRAMEWORK + SNAP + FLAT REVIEW (approved 2026-07-15)
- Opening = "Stetson style": clip OPENS on the guest's spoken BUSINESS intro (name NOT spoken,
  it's in the super), then card→answer×N → payoff. Per clip an agent (opening.json:
  keep|replace|prepend) finds the business-intro line from the source (usually the name/business
  Q&A — which may be LATE in the source, e.g. TC at 1458s); drop "my name is X", keep the
  business sentence. build_final.py applies it: replace=swap span0, prepend=insert span0 +
  bump cards_final span refs +1. Spans need NOT be increasing in source time (timeline order =
  span-list order; NEVER add a strictly-increasing guard — it corrupts prepended-late intros).
- SNAP every boundary OUTWARD ONLY (in moves earlier into preceding silence, out moves later
  into following silence; ≤0.06s inward tolerance). Inward/nearest snapping CLIPS leading/
  trailing words (proven: dropped "Marketing", "My business", "I'm"). silencedetect floor =
  mean−6dB. Some agent intros still need a hand-tighten (fused name+business, sparse intros) —
  eyeball the first-span text after build.
- FLAT review sequence (editor pref 2026-07-15): NOT nested — lay every clip/card/super directly
  on ALL_L3_REVIEW (review_flat_plan.json: V1 all clips contiguous, V2 cards, V3 supers) so the
  editor trims in place. Then blur+mute the V1 card beats by timeline position.
