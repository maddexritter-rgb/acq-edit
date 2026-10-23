# Independent audio boundaries

Assembly Design owns this stage. Preserve selected source-word IDs, playback order,
picture frames and source-to-timeline sync during an audio-only repair. A deliberate
word removal or pause compression needs a new compiled picture/audio revision.
Sample coordinates prove placement
precision, not that a chosen boundary sounds good.

## Default production method

Use the word transcript plus the actual played-source waveform together on every
new spoken assembly. Do not cut from word timestamps first and defer waveform
inspection until a bad render. Existing local triage, inspection, alignment,
paired-seam and audition helpers own this method; no second cutting pipeline.

Decode/cache the played signal once, prepare boundary evidence in batches, inspect
every selected head/tail and suspicious retained pause, and batch local alignment
for ambiguous contexts. Resolve the source-native phrase and both sides of the join
before construction. Reinspect boundaries introduced by a later editorial revision.
Reuse unchanged evidence by source/routing/settings identity; do not regenerate
source-wide waveforms or request remote analysis once per cut. Waveforms are local
signal data. Gemini is optional additional review, not the waveform generator.

The same decisions feed either execution backend. Follow
[Filmcraft execution](../../edit/references/filmcraft.md) for its separate PCM-WAV
route and native adapter; the PCM-in-MOV preparation below remains the Premiere
route. Use the verified played source/channel, not whichever container is convenient.

Preserve complete onsets, releases and meaningful cadence. Silence detection,
forced alignment, low amplitude and successful sample arithmetic cannot independently
prove a good cut. A fused word may require a deliberate phrase revision; never hide
an unwanted syllable with a fade or restore removed words to satisfy a helper.

The user-approved held-out batch supports adopting this workflow. Its exact media,
boundaries and approval belong in the project evidence; no timestamp, pause length,
frame rate, channel number, style or blanket perfect-cut claim is promoted here.

## Prepare the played source

For sample editing, use PCM at the sequence sample rate. Before ingest on new jobs:

```
python3 scripts/prepare_audio_precision.py --source SOURCE --output-dir NEW_WORK_DIR
```

The default is 48 kHz. This copies compressed picture without re-encoding, converts
one mono/stereo audio stream to PCM-in-MOV and compares every picture packet and
presentation time. Multiple streams, nonzero stream clocks and downmixing require
explicit routing. A failed preparation is unusable; partial files and the failure
receipt remain for inspection. Keep the original and the provenance receipt.

Use the derived media as the played clock for word timing and acoustic inspection.
For existing designs, create a deliberate source revision, preserve literal selected
words and run the compiled revision comparison. Never relink a reviewed sequence.

### Pin the channel that actually plays

Before alignment, waveform inspection or audition, record the played media identity,
audio stream, source channel indices, Premiere channel mapping, sequence sample rate,
and any gain/mix/processing. Channel numbering must say whether it is zero- or
one-based. A stereo source imported as mono may play only one source channel,
duplicated to both outputs. A diagnostic `-ac 1` downmix can combine different
microphones and create a different word tail. Never assume that mix is the timeline
signal. Preserve channels when decoding; select the verified channel explicitly.

Save the routing receipt beside the existing audio plan, with the native snapshot
and a rendered comparison that supports it. When routing cannot be established,
mark the acoustic decision unresolved. Correlation with the rendered source passage
can support a routing hypothesis; it cannot establish word integrity or certify
arbitrary effects. Do not bake one fixture's channel mapping into a general script.

A native test on compressed 44.1 kHz media in a 48 kHz sequence accepted exact geometry
but rendered a one-output-sample mapping discrepancy. Matched-rate PCM WAV and
PCM-in-MOV passed the same head/tail test with bit-identical retained interior audio.
This is bounded evidence, not a universal claim about every codec/version.

## Resolve and record audio edges

### Final picture continuity is a separate invariant

A J/L cut offsets picture and audio edit boundaries while preserving their shared
source clock. It does not require a hole in the picture or shifting the entire
linked picture out of sync. At unit speed, compare `video.start - video.inPoint`
with `audio.start - audio.inPoint`; different trimmed edges can still be in sync.
Link membership alone does not prove this relationship.

Picture timeline boundaries use the **sequence** frame grid. Source-frame clocks
and audio-sample clocks are separate, especially with mixed-rate footage. Do not
accumulate source-frame durations and assume they land on sequence frames. Retain
the inspected audio edges; a picture-only repair must not round or ripple them.
Resolve each shared picture boundary once, then apply the same tick to the outgoing
end and incoming start. Verify the resulting native source mapping and visible
frames; a source in-point need not have the same numeric phase as a timeline frame.

Run `scripts/compare_native_timing.py <current-snapshot.json> --audit-picture
<groups.json> --frame-ticks <exact-sequence-frame-ticks> --out <new-report.json>`.
The groups file is `[{"id":"<clip-id>","video_ids":["<native-node-id>"]}]`,
an explicit complete partition in current playback order. The audit checks all
picture items, including preserved and praised clips, for subframe gaps, overlaps,
off-grid timeline edges, source-duration conflicts and linked audio head-clock
offsets. Inter-clip review spacing is outside each group. An incomplete map fails.
Audio tail-clock conflicts are reported separately and block any claim of complete
AV/acoustic acceptance; do not rewrite audio to make that warning disappear.

Require both comparison with the intended plan **and** this independent invariant
check after construction/import/movement and after save/reopen. A gap shorter than
one output frame may not show black in one export; that does not make the geometry
valid. Never exempt protected clips or declare success merely because a flawed
plan was executed exactly. For fresh construction, fix the clock conversion before
import. For reviewed work, repair only explicitly authorized picture geometry,
preserve current audio bytes and metadata, and verify native readback and output.

### Fast local pre-build triage

Run local signal checks before timeline construction, not only after a bad export.
`played_audio_edges.py` has an acoustic mode that reuses the shared Silero engine:

```bash
python3 scripts/played_audio_edges.py --words WORDS.json --ranges RANGES.json \
  --fps 30 --acoustic-source PLAYED_MEDIA --stream 0 --channel 0 \
  --cache-dir PROJECT/10_WORK/acoustic-cache --out NEW_PROPOSALS.json
```

The numbers above are examples: use the verified played stream/channel and exact
source frame rate. This mode decodes the specified channel once and caches the
source-wide detector map by source file identity, routing, settings and detector
code. It does not call a remote model or generate plot pages. Source changes
invalidate the cache; uncertain routing still prevents acoustic acceptance.
For multi-channel mixes or processing, supply the verified rendered/conformed mix
as the played source; choosing one channel does not certify a stereo mix.

It intersects neighboring word-label gaps with padded detected non-speech, keeping
both selected and excluded words visible. A supported frame is only a proposal.
A conflict yields `PROVISIONAL_SEAM` and null `source_frames`, never a fallback cut
inside speech. Original timestamp frames remain diagnostic-only. Consumers must
handle null explicitly; they must not execute `timestamp_source_frames` instead.
Independent audio samples remain unresolved: feed inspected windows to the existing
paired-seam compiler rather than silently rounding audio onto these picture frames.
Legacy calls without `--acoustic-source` remain locator-only for replay.

Use a single local alignment batch for the ambiguous contexts, retaining their
complete dialogue and excluded neighbors. Cache successful alignment inputs and
outputs by source/channel, literal transcript, window, tool/model and normalization
identity. Compare token identity, neighboring occurrences and phoneme evidence
before promoting any times. Disagreements are investigation targets; do not average
ASR and alignment or automatically call either correct. Reuse the inspection and
paired-seam tools below. Generate waveform/spectrogram pages only where a decision
requires them; plots are displays of locally decoded audio, not a Gemini service.

This is a fast **triage** path, not an unattended precision-cut guarantee. A fused
phoneme may have no silence to cut on; local inspection or a deliberate source-word
revision remains necessary. Keep the final played-seam audit separate. A remote
listener is optional evidence and cannot rescue an unqualified boundary by voting
PASS. Do not claim this path has improved actual cuts without rendered comparison
and acceptance on development and held-out footage.

### Establish the right occurrence before tightening it

A precise timestamp can point to the wrong syllable or an earlier attempt. Before
replacing local word times, inspect the complete phrase between independently
supported words before and after it. Do not choose the alignment crop solely from
the timestamps under dispute: a crop that already omits the word's ending can force
the expected transcript onto the wrong sound. Widen to the intact clause, retaining
its literal fillers and restarts, and compare fresh locators with phoneme evidence.

Merge proposed times into a separate diagnostic map and inspect unchanged neighbors.
A later source word moving before its predecessor, a selected interior word falling
outside the kept phrase, or a large unexplained disagreement is an occurrence defect
to investigate, not permission to shift labels automatically. Overlapping speakers
and duplicate ASR hypotheses require source inspection rather than invented linear
timing. Use `scripts/validate_alignment_patch.py` on the normalized local word table
before promoting a repair; it checks identity, bounds and neighbor order, not sound.
Preserve the original map and correction evidence. A repaired tail must retain the
whole selected clause, including quieter interior words and the full final release.

When recompiling against a separate corrected word file, pass the explicit local
patch to `compare_assembly_revisions.py --timing-patch PATCH.json`. The comparison
checks pinned source hashes, unchanged word identities/media, original neighboring
words, and that every timing change exactly matches the geometrically validated
patch. It still flags the correction for review; neither this check nor an alignment
establishes acoustic correctness. An ordinary transcript change remains rejected.

Before refining a disputed word, obtain a literal observation of its intact source
context without supplying the expected kept sentence as the answer. Compare that
observation with the alignment input. An omitted filler or backchannel can make an
aligner assign an intended short word to the wrong sound, even when every selected
word passes interval containment. Correct the complete local alignment input, keep
its excluded speech visible, and establish the intended occurrence before trimming.
A number normalized into words the speaker did not say can produce the same drift.
Document uncertainty; neither a second aligner nor a model transcript proves the
final seam sounds intact. Preserve the source recording and original word map.

Treat fresh ASR as corroboration only. A recognizer can infer the intended phrase
even when the rendered audio has lost part of a word. Neither correct decoded text,
forced alignment nor feasible sample geometry establishes an intact audible join.
If a listening service misses known clipped-word controls, retain its observations
as unqualified diagnostics; do not count its PASS as acoustic completion. A usable
human-reviewed revision supports that revision, not a universal perfection claim.

### Paired-seam construction method (default)

Use this for new spoken assemblies and precision repairs, without waiting for a
complaint or another single-clip calibration. Human acceptance supports this workflow
as the default; it does not certify different footage or eliminate source inspection.
For new work, complete the paper cut and both tightening passes first. For repairs,
preserve the approved design unless the selected phrase itself prevents a clean join.

1. Keep the current deliberate source-word design. Decode the exact played PCM channel and
   include the intact surrounding speech, especially words being removed. Use a
   local forced word/phoneme alignment when transcript edges conflict with the sound.
   An available MFA `english_us_arpa` alignment is useful: provide the **complete
   literal local dialogue**, including fillers and abandoned starts, in the `.lab`
   beside the mono `.wav`. Record the source offset, channel, model/dictionary,
   command and normalization of numbers/contractions. Never align only the kept
   words against uncut audio; that can force excluded speech into retained words.
   Before constructing a linear alignment transcript, check for nonmonotonic word
   times, overlapping speakers, and duplicated filler hypotheses. A word-ID list
   can contain these even when its joined text looks plausible. Do not force that
   list into an invented sequential performance. Compare every selected boundary's
   occurrence with the independent word locators; large disagreements, implausibly
   long phones, or a word aligned to room tone require a shorter source inspection
   and local realignment. Preserve contradictory evidence. Do not change the source
   word artifact merely to make a timing validator pass. Unseparable overlap stays
   provisional unless a deliberate, source-faithful editorial revision resolves it.
2. Compare the alignment with waveform and, for quiet consonants or fused speech,
   a spectrogram. Preserve the full onset and release; exclude the next unwanted
   phoneme. A phoneme label can be late even on a 10 ms grid. Low amplitude or a
   nearby zero crossing can reduce a click **inside an already justified boundary
   window**; neither tells you which word is present. Conflicts remain provisional.
   Inspect all selected heads and tails, both sides of each omission, and retained
   spans with suspicious pauses or stretched labels. A complete word's release can
   extend beyond its ASR or phoneme end; the next excluded word can begin before its
   label. Widen the displayed context when ownership is unclear rather than adding
   a fixed handle. If connected sounds cannot be separated cleanly, reconsider the
   smallest source-native phrase and recompile the deliberate word change.
3. Design the outgoing and incoming edge **as one join**. Keep a short amount of
   original room/breath when the performance needs it; shorten excess pauses in
   picture and audio together. Do not generate silence between independently
   trimmed items. Do not restore unwanted syllables for a handle or fade them away.
4. Use `pair_audio_seams.py` to solve declared, locally inspected sample windows.
   It checks that `incoming_sample - outgoing_sample` equals an integer number of
   source picture frames. Both audio edges then share the same offset from their
   adjacent picture cut, preserving sync with no timeline hole or overlap. Windows
   are acoustic decisions supplied by the editor, never widened by this helper.
   An infeasible pair needs another local boundary or explicit unresolved status.
5. Execute the normal compiled selection/XML and audio plan. Verify exact ticks,
   source mapping, zero unintended gaps, and **native AV link membership**. Some
   independent audio extensions have removed native links while preserving exact
   geometry; restore only the previously verified pair, then read back membership.
   Save/reopen and compare a native export to the intended PCM. Listen to joins in
   phrase context and the complete clip; report unavailable listening honestly.

The helper consumes `edit.paired-seam-decisions/v1`: `fps`, `sample_rate`,
`span_count`, `first_source_frame`, `last_source_frame`, and one `joins` entry per
adjacent pair. Each entry supplies inclusive `out_window`/`in_window` sample bounds,
`preferred_out`/`preferred_in`, `reason`, `evidence`, and the actual `status`.
Run `python3 scripts/pair_audio_seams.py DECISIONS.json --selection SELECTION.json --clip-id CLIP --phonemes PHONEMES.json --out PAIRED.json`
using the exact pause-split selection matching the planned spans. Omit `--phonemes`
only when unavailable. The compiler binds selected words to audio intervals and
refuses a plan with a selected word wholly outside them; it saves rejected evidence
separately. Partial locator conflicts require local source inspection. Do not loosen
the selection, hide an excluded word or rewrite the ledger to pass containment.
If a locator is wrong, preserve the original and use the independently supported
timing correction procedure above. `LOCATORS_CONTAINED` still says nothing about
complete word releases, excluded-neighbor leakage or natural cadence. Legacy
geometry without a bound selection remains replayable, not a new handoff.
The output supplies source frames, source samples and continuous timeline samples
for the existing resolved assembly and audio-plan schemas; it is not a word selector
or an acoustic PASS. The current helper requires an integer number of samples per
picture frame and refuses unsupported grids rather than rounding away sync.
For an outer edge that would restore excluded speech when rounded to picture,
explicit `first_source_sample`/`last_source_sample` with `outer_edge_evidence` may
trim inside the enclosing first/last picture frame. The helper reports these outer
picture-only samples separately; this never permits an internal audio gap.

Preserve human feedback against exact project/sequence, word ranges, paired plan,
and native audio hash. Save identity-specific case evidence in the project/brain,
not in reusable skill code. Promote accepted behavior, not one clip's timestamps,
pause length, channel number or frame rate as defaults.

### Fast pre-render checks

Default to [pre-render construction](pre-render-construction.md). The independent-ASR
procedure below is optional targeted diagnosis for an unresolved source ambiguity,
not a whole-batch prerequisite. Reuse source-bound waveform evidence and inspect
uncertain regions before construction; no second transcription merely for a PASS.


Prepare a diagnostic PCM assembly from the resolved paired source/sample ranges,
then compare independently recognized speech with the selected words **before**
caption construction and video export. Use `scripts/spoken_preflight.py --words
ASSEMBLY_WORDS.json --source-pcm PLAYED.wav --paired PAIRED.json --channel CHANNEL
--audio NEW_ROUGH.wav --out NEW_PREFLIGHT.json`. This copies exact PCM intervals;
it does not render video or mutate the selected backend. With existing diagnostic
or native audio, omit `--source-pcm`, `--paired` and `--channel`.

A disagreement is a source-inspection queue, not an automatic replacement or a
failed editorial decision. Missing boundary words, negations, numbers and extra
neighbor words must be reconciled against intact source before finishing. Matching
text is not phonetic certification. Preserve raw and corrected locators separately;
never make expected words into the independent recognizer's prompt. `--observed`
replays saved evidence only, and cannot count as a new audio check.

The inspection helper ranks all edges and interior conflicts and includes broad
source windows for alignment requests. Read the whole contact sheet; spend detailed
inspection on disagreements, repeated occurrences, tight/overlapped edges and
speech/label conflicts. Do not infer approval from the priority label. For a suspect
alignment, independently transcribe the **actual complete decoded window first**,
then align that transcription and locate the intended occurrence through unchanged
neighbor words. Cropping audio and its forced text from the same bad ASR timestamps
can produce a confident but wrong alignment. Expand context when the target touches
the crop boundary or its neighbors fail to match; never keep retrying the same
cropped labels for agreement.

→ Use skill: `horizontal-to-vertical` for geometry-bound tracking caches. Cutting
changes invalidate only dependent source-range results and derived timelines;
finishing must consume the current complete list, not an old positional zip.

### Prepare the inspection evidence

`scripts/inspect_cut_boundaries.py` generalizes the source-waveform inspection used
for the accepted workflow. Supply the existing v2 selection and one clip ID, a
routing JSON with `media`, zero-based audio `stream` and `channel`, `sample_rate`,
and `evidence: {path, sha256}` pointing to the verified native routing comparison.
The helper checks this binding; it does not independently certify that receipt.
An optional phoneme JSON uses absolute source times in `words` keyed by word index,
with `aligned_start`, `aligned_end` and optional `phones`. An optional performance
map uses the existing candidate-performance `events`. Preserve the original maps.

```
python3 scripts/inspect_cut_boundaries.py --selection SELECTION.json --clip-id CLIP \
  --routing ROUTING.json --phonemes PHONEMES.json --performance PERFORMANCE.json \
  --spectrogram --out NEW_INSPECTION_DIR
```

Read the generated pages and index before declaring local inspection complete.
The helper includes excluded neighboring words, both transcript and phoneme locators,
every selected edge and suspicious interior events. Context width and pause-locator
threshold only control diagnostic display; neither chooses a cut, changes a word,
marks a region listened, or creates an approval. Missing phonemes leave transcript
locators visible and uncertain. Use another intact source context if it is wider
than the selection's interaction. Re-run on the current revision after word changes;
do not let an older plot stand in for newly introduced boundaries.

`played_audio_edges.py --audio-sample-rate 48000` retains compatible picture-frame
proposals and emits independent `head.audio` and `tail.audio` candidates. Fused
labels yield an unresolved sample candidate. Sample feasibility is not a clean-seam
verdict: labels can omit consonants, release tails or reverberation.

Inspect outgoing and incoming sounds separately, with the omitted neighbors visible.
Compare the joined played audio against intact source context. Preserve complete
onsets/releases and intentional cadence. Do not use blanket padding, low RMS, an
ASR transcript or an automated reviewer preference as acoustic certification.
Finer timing cannot separate truly overlapping speech. Return lexical changes to
the existing designer, rather than silently restoring or deleting words.

### Decide what kind of repair is needed

- **Retained word clipped:** compare the intact source onset/release against the
  native join. Inspect quiet consonants and breath carrying the final phoneme, then
  choose the smallest supported boundary change. Check the omitted neighbor again:
  extending a tail can restore a filler or part of the following word.
- **Wrong occurrence or untranscribed restart:** compare the complete local take.
  A selected word may align to the first attempt rather than the fluent occurrence.
  Preserve raw ASR, save an evidence-backed timing correction separately, recompile
  and compare revisions. A plausible replacement timestamp is not sufficient proof.
- **Unwanted word belongs to the selected text:** fix the paper cut deliberately.
  Do not shave phonemes from a word that should be removed whole. An isolated
  connective from a discarded take may need removal before a later complete take;
  this is not a rule to remove all connectives. Record the changed word IDs and why
  the revised joined dialogue still preserves the source meaning.
- **Pause too long:** choose the intended cadence from both phrases, then shorten
  the planned picture and audio interval together through a recompiled revision.
  An audio-only trim leaves the picture's pause in place. Subframe audio offsets
  remain useful for word releases; they are not a substitute for deliberate ripple.

Keep approved hooks, reasoning and payoffs during seam work unless the actual
word choice is the defect. A rejected seam is not permission for a batch redesign.
Never add a fixed number of frames everywhere, mute retained phonemes, or use a
fade to disguise an unwanted word. Meaningful breath and performance still count.

Save a plan using zero-based indices into the base XML expected receipt. Source
sample ranges are half-open; status is the actual review performed:

```json
{"schema":"edit.assembly-audio-edges/v1","expected_sha256":"<base expected receipt SHA256>","sample_rate":48000,"cuts":[{"assembly_item_index":0,"source_samples":[480001,719999],"reason":"Source-backed boundary decision","evidence":"<source and joined-audio evidence path>","status":"LOCALLY_INSPECTED"}]}
```

Valid statuses are PROPOSED, LOCALLY_INSPECTED, LISTENED and EDITOR_APPROVED. They are
not interchangeable. A filename alone does not establish listening or approval.
No automatic ripple, time stretch or blanket fades. Deliberate overlapping audio
requires a separately designed transition; the current operation refuses overlap.

### Damaged recordings and enhancement artifacts

Before committing to a payoff with suspected distortion/dropout, compare the exact
untreated recorder and synchronized camera audio with the enhanced version. RMS and
export integrity do not prove intelligibility; a gain boost cannot repair damaged
phonemes. Keep a short source-versus-processed listening comparison for the affected
phrase. When the editor selects an untreated source, send those exact bytes to the
requested enhancement service; do not silently normalize, denoise or reuse a prior
processed variant. Record the input hash and returned settings. Enhance speech without
music; match the replacement phrase's sound and timing before restoring the bed.
If the same defect survives a targeted repair, return to the spoken design rather
than repeatedly exporting variants. With recut authorization, compare an earlier
complete example or another source-supported payoff; preserve essential qualifications.
No synthetic words, missing phonemes hidden by fades, or claim of listening from metrics.

### Review the complete played result

For explicitly requested strict listening evaluation, use the [executable seam audition loop](seam-audition.md). Ordinary runs do not invoke this loop; claim acoustic completion only from actual listening evidence.
It builds source/played evidence and rejects incomplete or contradictory review
records. It supplements acoustic judgment; it cannot establish that a listener is
correct. Fixed offsets around phoneme labels remain proposals, including when their
frame/sample geometry is feasible.

Inspect every seam, outer edge and suspicious interior pause across the assembly;
do not depend on the user supplying bad-cut timestamps. Use intact source context
and the actual native output. For ambiguous alternatives, build one indexed A/B
WAV with clearly separated versions and a sidecar mapping each interval to its
candidate and source ranges. Multiple separately attached files have produced
false "identical" model judgments; a single reel reduces that ambiguity without
making the reviewer infallible.

Record the exact audio hash, reviewed ranges, reviewer/method, observations and
remaining uncertainty. Listen in phrase context and at normal speed, including the
whole clip after local repairs. Keep contradictory model observations; do not reroll
unchanged audio for a PASS or count a failed listening call as review. If audition is
unavailable, save the playable evidence and state that limitation honestly.

## Execute through the existing native importer

Pass `--audio-plan PLAN.json` to `scripts/apply_native_assembly.py` on the default
Premiere Agent profile and exact-project assembly scope. The shared launcher includes
the Assembly-owned `lab_apply_assembly_audio_edges` tool through `precision_bridge.mjs`,
using the existing guard, queue, transport and journal. Research can explicitly select
the disposable Lab profile; production inputs require exact file authorization.

The original v2 selection/compiler/XML chain still governs initial placement.
`apply_audio_edges.py` binds the sample plan to imported native IDs, applies exact
source and timeline ticks, preserves every other item/sequence and native AV link
membership, and saves a chained handoff. Use the final `precision-result.json` and
its stage handoff downstream; the earlier base `result.json` is historical.
The frame-aligned route stays compatible when no audio plan is supplied, but it
must not be described as completed sample-precision execution.

`native_audio_edges.mjs` checks PCM codec/rate, sequence sample grid, stale geometry,
retiming, effect automation, duplicates, sync offsets, bounded changes and collisions.
Every requested tick must match; one frame of tolerance is unacceptable. Failed or
uncertain writes stop dependent work. Inspect the original job and actual state;
never auto-replay a failed mutation or silently change connectors.

The reusable implementations are `prepare_audio_precision.py` (conform/provenance),
`played_audio_edges.py` (candidate edges), `apply_native_assembly.py` (compiled
placement), `apply_audio_edges.py` with `precision_bridge.mjs` and
`native_audio_edges.mjs` (guarded independent audio edges), and
`compare_assembly_revisions.py` (intentional word/source changes). Discover their
current arguments rather than copying a project-specific command or hardcoding a
Lab installation path. Local plotting, audition and rendered-comparison scripts
remain evidence helpers until generalized and tested; they are not a second cutter.

Verify again after any move, ranking or merge, not only immediately after precise
placement. Compare source in/out, durations and relative AV timing in integer ticks;
a pure relocation must preserve them. A timeline can still look frame-aligned while
its audio edges have changed. Keep the pre-move snapshot and distinguish an observed
geometry change from an unproven claim about which operation caused it.

Save/reopen and export affected audio. Verify source mapping and protected picture,
sync and unaffected audio. Actual joined listening decides word integrity/cadence.
Premiere 26.3 fixture success establishes bounded native sample placement, not
unattended acoustic selection or general production acceptance. Treat user-rejected
seams as development regressions and use additional held-out footage under
[evaluation.md](evaluation.md); do not call tuned examples independent validation.
