# Assembly boundary execution

This is the active cutting contract for the editor's 16:9 assembly timeline.
The [full cutting playbook](CLIP_CUTTING_PLAYBOOK.md) is preserved for its seam,
word-tail, filler, and ASR-failure observations. Its older rendering, caption,
music, audit, provider, and fixed-padding recipes are not default assembly steps.
Its claims that RMS is phonetic ground truth or an automated audit certifies audible
words are superseded here. Low energy can contain a quiet consonant; ASR may restore
a clipped syllable from context. Neither alone proves an intact word.

Do not remove a leading connective by cutting at a forced-aligner's label inside
continuous speech. In phrases such as “and so I” or “like you,” inspect the intact
phrase before deciding that the connective can be removed. A millisecond-wide
minimum or zero crossing inside voiced energy is not a word boundary. Prefer the
minimum complete source phrase when its words are fused; record the restored source
IDs, then remap picture and captions and enhance the revised dialogue. Keep this a
construction decision before rendering, never a repeated post-render repair loop.

1. Pin the primary source media, rational frame rate, source clock, and one
   source-ordered word ledger. AssemblyAI words and times locate speech; none
   certify a cut frame. Keep disfluencies and adjacent omitted words visible.
2. Before selecting a promising interaction, inspect its complete words and
   targeted `candidate_performance.py` events: fillers, pauses, stretched labels,
   VAD/word conflicts, and relevant source audio or picture. The model decides
   the exact kept words, interior removals, question hook, and payoff. The probe
   cannot decide or silently rewrite those choices.
3. Compile the selected word IDs and read the literal joined playback. For the
   default 16:9 editor-review route, time the cut against **the audio track
   actually played on the timeline**. Reuse an AssemblyAI word map of that exact
   source clock when one exists; otherwise transcribe that dialogue feed once,
   preserving the raw response and word IDs. An alternate camera's transcript
   may guide word matching but its timestamps are not cut points for the played
   recorder. Map selected words onto the played-audio word IDs; unresolved
   matches are local problems, not permission to remove the passage.
4. Use `scripts/played_audio_edges.py` for initial source-frame proposals on
   that word map. For a positive label gap, start 70 ms before the selected
   word and end 100 ms after its final word when the gap affords it; use the
   midpoint for short gaps. The preferred head handle and millisecond margin are
   one budget, never additive padding. Quantize within the label-separated frame
   envelope: a head cannot move before the omitted previous word's end or after
   the kept word's start; an exclusive tail cannot move before the kept word's end
   or after the omitted next word's start. If no grid frame fits, report it; labels
   can be wrong and the conflict needs source inspection. The proposal helper allows
   reordered playback and separately flags actual source-frame intersections.
   Inspect every proposed head against the preceding excluded word and
   every tail against the following excluded word. Where either word's release
   overlaps the frame, inspect the short played-audio waveform/spectrogram and,
   when useful, obtain a second local AssemblyAI alignment. Shift only that
   picture edge on its frame grid, but resolve the played audio independently
   on its sample grid using [audio-precision.md](audio-precision.md). Preserve all selected
   words and the source-to-timeline sync offset; audio and picture need not end
   together. Do not apply a blanket pad after the local check or use low RMS alone
   as evidence that a consonant survived. If no frame cleanly separates fused
   speech, inspect an independent audio boundary before calling it fused; if no
   clean acoustic separation exists, mark it provisional rather than dropping words.
   Listening by the editor remains decisive; ASR, waveforms, and automated
   listening are advisory, not acoustic certification.
5. Preserve complete word tails and intentional nonverbal payoff performance.
   Check the resolved first/last word and source-linked V1/A1 ranges before
   handing the playable sequence to the editor. Mechanical readback does not
   certify listening quality or editorial approval.

For a precision recut, inspect every new join as **rendered played audio**, with
context on both sides and the selected source phrases available for comparison.
Check clipped consonants, lingering omitted syllables, doubled speech, unnatural
breath/cadence and clicks, including first/last clip edges. Review interior pauses
even when ASR boxes touch. A waveform/spectrogram or independent alignment narrows
the search; actual listening decides phonetic/cadence quality. Do not represent
ASR, a video contact sheet, tool execution, or a human-review link as listening.
Log source frames before/after, evidence path, what was inspected and remaining
uncertainty. Keep labels such as `PROPOSED`, `LOCALLY_INSPECTED`,
`LISTENED` (with actual reviewer/method), and `PROVISIONAL_SEAM` distinct.

Try a local frame adjustment first, then a source-native phrase boundary or a
deliberate paper-cut revision. Stop after two unsuccessful local repair attempts
at the same seam and expose that seam for editor review rather than looping or
silently dropping selected meaning. No blanket crossfade or fade-in may erase a
word onset/tail. Use source duration to clamp an unbounded last-word tail before
timeline placement. Save/reopen/readback verifies the chosen frames survived;
it does not certify how they sound.

When an incoming word is fused to the preceding word, moving to that word's ASR
onset can still remove its attack. Inspect the preceding phrase and retain the
smallest complete, source-supported phrase that makes the join intact and sensible.
Recompile the literal dialogue and source-word map, then resolve both join sides
again. Do not silently prepend a syllable or conceal an amputated word with a fade.
Keep the original meaning, speaker attribution and qualifications; if the needed
phrase changes the story, return to editorial design before downstream finishing.

For the default route, the editor reviews the timeline. No independent
editorial audit, scoring gate, or final PASS is required before placement.
