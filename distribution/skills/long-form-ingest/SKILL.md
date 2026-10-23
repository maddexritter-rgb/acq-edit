---
name: long-form-ingest
description: Transcribe long-form footage into evidence-preserving word, speaker, interaction, source-clock, and verification artifacts for editorial assembly. Use whenever new footage enters /edit and no current verified ingest package exists.
---

# Long-form ingest

Own source identity and editorially usable transcript evidence. Do not select clips,
write hooks, rank promises, or decide what should be cut. Those decisions belong to
`assembly-design`.

## Default assembly handoff

For a 16:9 assembly-cut request, transcribe the primary dialogue feed once and save the
raw provider result, source-ordered word list with stable indices, source media path,
and source clock/frame rate. Reuse existing current transcripts. Mark uncertain words
as uncertain; verify only words that affect a selected moment. Index complete Q&A
interactions so the question and actual answer remain available, but do not require
camera-by-camera transcription, exhaustive verification paperwork, or a completed
session-wide coverage ledger before the first timeline cut. The extended package below
is for specifically requested strict evidence mode.

## Canonical transcription route

Import `transcribe` and `AsrUnavailable` from `../_shared/asr.py` and call:

```python
transcribe(
    audio_path,
    use_cache=False,
    profile="editorial_ingest",
    prompt=neutral_source_description,
    keyterms=brand_vocabulary_loaded_by_path,
)
```

The editorial profile uses AssemblyAI Universal-3 Pro first with disfluencies and
speaker labels enabled. Groq Whisper and local MLX Whisper are availability fallbacks,
not equivalent evidence. Preserve the returned `engine`, `model`, `profile`, and
`evidence_status`. A `PARTIAL` transcript may support coverage and discovery, but
consequential words, speaker identity, fillers, and precision selections require
verification before assembly compilation.

AssemblyAI word times locate speech; they are not frame-certified edit points and the
provider does not inspect picture. Hand the same stable source-word IDs, disfluencies,
speaker turns, and source clock to `assembly-design`; it inspects selected performance
and resolves frame boundaries against the actual media in one assembly pass.

## Gemini delivery map (default, once per source)

After the AssemblyAI transcript, run the listener pass once per source on the same
played audio clock:

```bash
python3 scripts/delivery_map.py --words <raw_transcript.vN.json> --audio <played dialogue> \
  --out <10_WORK/ingest/delivery_map.vN.json> --cache-dir <10_WORK/ingest/gemini-cache>
```

It sends ~10-minute chunks with their numbered transcript through the Gemini fallback
chain (`gemini-4-argon`, then `gemini-3.8-flash`, then `gemini-3.1-pro-preview`; key:
`~/.config/assembly-design/gemini-paid-key`) and keeps tags keyed to **word indices**:
misheard, phantom or missing words, audible fillers, stumbles, swallowed words, emphasis,
energy drops, crosstalk, laughs, noise. Gemini timestamps are never used to place a tag.
Each misheard/phantom/missing tag gets a local-Whisper tiebreak vote recorded beside it;
the vote is evidence for the editor-model, never an automatic transcript rewrite.
Roughly $0.50–1 per source hour. Cached by audio + prompt, so reruns are free; one
retry, then a chunk is `UNAVAILABLE` and the run still succeeds. The map is listener
evidence: it selects nothing and approves nothing, and a missing or partial map never
blocks assembly. These are listener notes, not qualified acceptance; see the controls
record in `assembly-design/references/seam-audition.md` before treating any model as one.

## Extended ingest package (strict evidence mode)

Save versioned, create-only artifacts under the project's `10_WORK/ingest/`:

1. `raw_transcript.vN.json` — immutable complete provider result, including words,
   confidence, speaker labels, utterances, provider identity, source pin and clock.
2. `corrected_words.vN.json` — source-ordered words used by downstream plans. Never
   sort words by timestamp. Every textual change points to listening evidence in the
   verification record; contextual plausibility is not a correction.
3. `speaker_turns.vN.json` — exact word ranges for observed turns. Keep short or
   ambiguous replies `UNKNOWN`; do not infer identity from camera names or alternation.
4. `interaction_index.vN.json` — complete source units and handoffs, classified as
   `monologue`, `qa`, `l1_diagnosis`, `conversation_story`, `non_content`, or
   `unresolved`. This is navigation and coverage, not a candidate list.
5. `transcript_verification.vN.json` — raw/corrected/media/audio pins, checked ranges,
   source-clock mapping, correction evidence, gaps, and unresolved issues.
6. `meta.vN.json` — actual duration, rational frame rate, resolution, streams and audio
   channel identity from `ffprobe`.

For long sources, chunk extraction may be mechanical, but every artifact must retain
absolute source offsets and overlap reconciliation. Never derive absolute time from a
chunk number. Each independently recorded camera or audio file owns its own clock until
a measured sync map proves otherwise.

For a multicamera recording, choose the primary dialogue feed first. Transcribe it once
for interaction discovery and word selection. Inventory the other cameras as media and
clock sources; transcribe a camera's audio only when it contains otherwise missing speech,
resolves a selected passage, or is required to verify that selected camera's sync. Reuse
an existing current verified ingest package rather than re-running provider transcription.
Record which feeds were not transcribed and why; do not claim their unheard audio was
covered by the primary transcript.

## Interaction indexing

Read the complete transcript in bounded windows and account for the full source. An
interaction begins where a proposition, question or owner problem becomes identifiable
and ends only after its actual resolution and handoff.

- A pause, thanks, or first answer does not automatically end a Q&A.
- Continue through corrections, objections, reassurance, audience corroboration, host
  codas and follow-ups that change or complete the answer.
- A long talk may contain many monologue propositions; do not label the entire file one
  interaction merely because one person speaks.
- Preserve guest/audience speech. Missing picture coverage is not permission to remove
  the question or reply from the transcript.
- Record read ranges and honest coverage gaps. Never claim a complete ingest when a
  chunk, channel, tail or speaker is missing.

Each interaction row records its word range, speakers, kind, preceding/following handoff,
unresolved evidence and a neutral one-sentence description of what is discussed. It must
not propose a hook, payoff, viewer promise, title, score or recommended cut.

## Verification policy

Preserve raw ASR even when wrong. ASR agreement, diarization, confidence, forced
alignment, VAD and a plausible sentence are different evidence. Names, numbers, units,
negation, corrections, offer identity and speaker attribution block affected claims when
unresolved. Record `UNKNOWN`; never fabricate a listening receipt.

AssemblyAI disfluencies materially improve the faithful word map, but no recognizer
guarantees every filler, restart or acoustic edge. Suspicious long word boxes, compressed
phrases, zero-duration words, overlaps and unexplained gaps require source listening.

## Handoff

→ Use skill: `assembly-design` with the complete interaction index, corrected words,
speaker turns and verification package.

Assembly Design retains the same pinned words, source audio and clock mapping through
selection, boundary resolution, and timeline construction; no second skill selects or
silently substitutes another transcript.

Metadata and scene detection are supporting evidence. Scene cuts may help picture
analysis, but they are not required to understand the transcript and never define spoken
content units.
