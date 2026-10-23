> Optional strict listening evaluation only when requested. Normal `/edit` and
> assembly-design runs use [pre-render construction](pre-render-construction.md),
> targeted source inspection and one export. This document does not create a default
> audit or automatic repair loop.

# Executable seam audition and repair

Use for every completed spoken assembly and for seam-only revisions. Preserve the
selected moments and ranking unless a particular spoken construction cannot be
joined cleanly. This stage belongs to Assembly Design. General audio finishing and
caption audits do not substitute for it.

## Local audio-review credentials

The audio-review runner uses `~/.config/assembly-design/gemini-paid-key` by default.
The existing environment/shared ASR credential remains available as `--credential legacy`;
`~/.config/assembly-design/gemini-fallback-key` is available as `--credential fallback`.
Credential files use mode `0600`. Never print their values or copy them into skill
files, project artifacts, prompts or invocation logs. Existing shared credentials
are preserved; this preference applies to Assembly Design audio review only.
If the selected credential cannot authenticate or has unavailable quota, a configured
alternative may be tried once. The runner does not silently retry, change model or
cycle credentials. Do not retry an unchanged quota failure repeatedly.
Keys on the same provider project can share quota; another key does not establish
available billing or capacity. Report the actual response. Changing credentials
does not qualify a listener or waive the sensitivity controls below.

## Model choice and visible failures

Use `scripts/review_audio.py` for reusable Gemini audio-review calls. The preferred
evaluation model is `gemini-3.1-pro-preview`, which accepts actual audio and returns
text observations. This is a quality-first candidate, not a claim of superior
splice detection or a qualified acceptance authority. A prior
`gemini-3-flash-preview`/prompt configuration missed controlled speech damage;
do not silently downgrade to it or treat intelligible transcription as intact sound.
The model remains configurable with `--model`. Compare current supported candidates
on the same blind intact/damaged evidence when a materially better model becomes
available; promote based on detection, localization and false alarms on this task,
not provider tier, price, model name or general benchmark rank. Record exact model,
prompt, audio hashes, raw response and token usage. Qualify again after model or
prompt changes. A model change never transfers another model's qualification.

Controls record (7 blind paired controls, `audio_listener_controls.v2`): as of
2026-10-15 no model qualified. `gemini-3.1-pro-preview` missed 1, false-alarmed 1,
mislocalized 1; `gemini-3.8-flash` missed 1; `gemini-4-argon` missed 2 and invented one
onset defect, with no false alarms on identical controls. Every model missed the clipped
word ending (C01). Consequence for the default route: word endings and onsets are judged
by `scripts/join_check.py` measurement; Gemini output is listener notes (positive
findings only), never acceptance. Receipts sit beside each model's controls run.

Surface workflow defects and model/service limitations as soon as they affect
quality: name the actual provider/model, failure, affected editing stage, and
concrete remedy. Distinguish connectivity, listening quality and native execution.
Do not claim that purchasing credits guarantees better cuts or a particular number
of reviews; record actual usage and evaluate before scaling.

```bash
python3 scripts/review_audio.py --audio /absolute/control.wav \
  --prompt-file /absolute/blind-prompt.txt --out /absolute/new-evidence-directory
```

## Run the loop

1. Freeze the current native source/timeline ranges, played channel/routing, and
   actual exported PCM. Compare the export to its source map. For an unchanged
   revision, an existing mapped native export is reusable; document that provenance.
2. Prepare every internal join, both outer edges, and full-clip audio with the
   command below. Include intact source context on each side, including omitted
   speech. Detect missing/overlapping sample ranges before auditory review.
3. Check the listening method on an accepted reference and controlled damage before
   relying on it for a rejected batch or after changing models/prompts. Record the
   untouched reference, perturbation recipe, audio hashes and original responses.
   A synthetic perturbation is a sensitivity probe, not human-rated ground truth.
   Quiet releases, intrusive syllables and unnatural cadence need separate cases.
   A listener that misses clear damage or repeatedly invents damage is not a batch
   acceptance authority. Do not retry unchanged evidence until it gets a PASS.
4. Review the played join against its two intact source contexts at normal speed.
   Separately judge retained speech, excluded speech, cadence and clicks. A quiet
   release or breath can carry a final consonant; energy thresholds and labels
   cannot decide its ownership. A complete word may still have an unnatural join.
5. For a rejected seam, inspect source audio/phones/spectrogram, then propose a small
   set of source-supported alternatives. Do not apply a fixed padding policy.
   Compare alternatives in one indexed, neutrally labeled audition reel, retaining
   the current cut as a baseline. Do not show the listener the preferred answer.
   Reuse `pair_audio_seams.py` only to solve the inspected windows. If no clean
   pair exists, revise the smallest local phrase from original source words and
   recompile; preserve the hook, argument, payoff and surrounding accepted cuts.
6. Apply the chosen geometry using the existing native execution contract. Keep
   picture/audio sync and links; shorten pauses in both when intended. No synthetic
   silence, time stretch, or fades disguising excluded syllables. Save/reopen and
   export/read back. Replay the full clip after local repair.
7. Run `check` on the final packet and observations. Every region needs completed
   listening and the exact current hashes. Any failed/uncertain check or reported
   issue remains actionable even when a model's overall verdict says PASS. Record
   contradictory observations rather than silently dropping them. Mechanical
   evidence completion does not establish listener correctness or human approval.

If listening fails, retain the playable work and mark all uncovered regions
incomplete. A provisional review timeline may still be shown when requested; it is
not a completed acoustic batch. Do not single out only a few visibly risky joins
while implying the remaining unlistened joins passed. Source alignment can triage
work during an outage; it does not finish the audit.

## Prepare source-versus-played evidence

```bash
python3 scripts/seam_audition.py prepare --manifest INPUT.json --out NEW_PACKET_DIR
python3 scripts/seam_audition.py check --packet NEW_PACKET_DIR/packet.json \
  --reviews REVIEWS.json --out NEW_GATE.json
```

Use absolute paths. The tool creates output exclusively and does not modify media
or Premiere. `INPUT.json` is `edit.seam-audition-input/v1` with `clips`:

- `id`: stable clip ID.
- `audio`, `geometry`, `routing`: each `{path, sha256}`. Audio is the entire actual
  played clip as PCM WAV; geometry is current native readback; routing identifies
  the export/source comparison and verified source channel. Do not fabricate the
  mapping receipt or claim a source reconstruction is a native export.
- `segments`: ordered actual audio items, with `media`, zero-based audio `stream`
  and `channel`, integer `source_in`, `source_out`, `timeline_in`, `timeline_out`.
  Coordinates are half-open samples at the WAV/source rate; timeline is clip-local.
  Retiming and intended overlap require an explicit adapter, not rounded ranges.

Each packet has head, numbered joins, tail and full regions. Individual played
contexts and original outgoing/incoming contexts have hashes and sample offsets.
The full region uses the complete clip. Widen context when four seconds cannot
resolve an occurrence or the phrase's meaning; the extraction default is not a
boundary-selection policy.

`REVIEWS.json` is `edit.seam-audition-reviews/v1`, with `packet_sha256` and `regions`.
Each observation contains `clip_id`, `region_id`, `status: LISTENED`, `reviewer`,
`method: human_listening|audio_model`, `played_sha256`, `source_sha256s`,
`response: {path, sha256}` pointing to the original response, `observation`,
`checks: {retained_speech, excluded_speech, cadence, clicks}`, and `issues`.
Audio-model observations also require `qualification: {path, sha256}`. That receipt
pins `controls` and the original `response`, identifies the exact `reviewer`
(model plus prompt revision), reports `missed_defects`, `false_alarms`, and
`localization_errors`, and may say `QUALIFIED_ON_RECORDED_CONTROLS` only when all
three are zero on the documented sensitivity set. Include unchanged negative
controls and clearly damaged positive controls; inspect uncertain perturbations
rather than assigning invented human labels. Record scope/limitations. This small
qualification is a minimum sensitivity check, not a universal quality claim.
A missing or failed qualification cannot authorize model-only batch completion.

Each check is `pass`, `fail` or `uncertain`. A response file and self-reported status
alone do not authenticate listening. Retain the actual audio request/invocation
and make the adapter preserve all issues from the original response. Never convert
an overall PASS into four passes when its detailed observations disagree.

A changed audio/geometry/routing hash invalidates the affected packet. Rebuild and
review the current revision. Keep the prior packet and rejected observations.
`INCOMPLETE` and `REPAIR_REQUIRED` exit nonzero. `REVIEW_EVIDENCE_COMPLETE` means
coverage/identity checks passed; it is deliberately not named audio-perfect.

Keep accepted and rejected calibration cases in project evidence and the existing
editorial brain, linked to exact revisions. Store generalized cutting behavior in
this skill, and source-specific times only with the corresponding project.
