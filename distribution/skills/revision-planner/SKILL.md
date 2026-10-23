---
name: revision-planner
description: >
  Solo-operator clip revision engine. Takes a v1 render + its audit report + ACQ feedback
  (free-form text from Slack/Drive comments), classifies each issue by category (subtitle /
  audio / video-timing / visual / hook / re-cut), auto-patches safe fixes with ffmpeg
  (lowercase typos, trim black frames, normalize audio peak, add 3-frame lead, fix audio
  clipping, reburn captions), re-runs mozi-sf-audit on the patched clip, and updates the
  clip-review-tracker. For complex fixes that can't be auto-patched (hook changes, re-cuts,
  wrong takes) produces a concrete edit brief with timestamps. Triggers: "revise clip",
  "apply feedback", "plan revisions", "patch this clip", "ACQ said X fix it", "run revisions",
  "auto-patch", "v2 this clip".
---

# Revision Planner

→ Load [scoped production policy](../edit/references/scoped-brand-policy.md), including direct revisions; consume the relevant construction and delivery stages.
Account for every previous-version note in the existing revision ledger, keep version stacks, and persist session-wide exclusions/global corrections at their stated scope.
Use the user's selected backend and owning stage for the patch; scoped guidance adds no automatic audit, rejection, or approval loop.

The loop closer. Turns ACQ feedback into either (a) an automatically-patched v2 that re-passes audit, or (b) a focused edit brief for the user to execute by hand.

Designed for **solo operator** workflow — no editor briefs to generate; just fix the thing if it's fixable.

Read `references/patch-recipes.md` for the full list of auto-patchable issues.

---

## When to run

Every time a clip in the tracker enters `needs-revision` state (ACQ left feedback). Most common entry points:

- User pastes feedback in chat: "the reviewer said the hook is too quiet and there's a black frame at the end"
- User runs `tracker.py feedback <clip-slug> --text "..."`
- Periodic: `revision-planner run-all-pending` processes every clip in `needs-revision`

---

## Inputs

1. **Clip slug** — from `vault/deliveries/<brand>/<slug>.md`
2. **Brand** — inferred from tracker if unambiguous, else required (default `alex`)
3. **Feedback** — one of:
   - Inline `--text "..."`
   - A file `--file feedback.txt`
   - Already stored in tracker (from a prior `tracker.py feedback` call)
4. **Auto-patch mode** (default: `safe`):
   - `safe` — only patches with well-defined ffmpeg recipes
   - `aggressive` — also attempts caption rewording, timing shifts (experimental)
   - `plan-only` — classifies + writes edit brief, doesn't patch

---

## The 6 issue categories

| Category | Auto-patchable? | Recipe |
|---|---|---|
| **subtitle-text** (typo, case, missing word, double word) | ✅ yes (safe) | edit `.ass` → caption-burner reburn |
| **subtitle-timing** (gap, too long, too short) | ✅ yes (safe) | edit `.ass` timing → reburn |
| **subtitle-style** (color, position, font) | ⚠️ partial | edit `.ass` style block → reburn (safe for color/position, not font) |
| **audio-levels** (too quiet, clipping, pumping) | ✅ yes (safe) | ffmpeg loudnorm / volume / dynaudnorm |
| **video-timing** (black frames, too-short/long lead, dead space) | ✅ yes (safe) | ffmpeg trim / concat silent frames |
| **video-content** (wrong hook, re-cut needed, wrong take) | ❌ no | produce edit brief |

See `references/patch-recipes.md` for the exact ffmpeg commands per category.

---

## Phase 1 — Load context

Pull everything needed:

```
record = clip-review-tracker.load(client, clip_slug)
  - clip_path                         (mp4)
  - subtitle_file                     (ass)
  - audit_reports[-1]                 (latest audit .md + .json)
  - feedback_files[-1]                (latest ACQ feedback .txt)
```

If any of these is missing, STOP and report what's missing. Don't guess.

---

## Phase 2 — Parse the feedback

Feedback can be structured (if pasted from Frame.io-like tool) or free-form. Parser handles both.

### Structured pattern
```
[00:08] subtitle "Awesome" should be lowercase
[00:23] there's a black frame after I say "exactly"
audio is too quiet overall
```

### Free-form example
```
Hey Maddex — the hook at the start is too quiet and there's a weird black flash around the 40-second mark, also I spotted a typo "Their" should be "There" at like 15 seconds in. Otherwise looks good!
```

Both produce the same internal representation: a list of `Issue` objects with `{timestamp?, category, description, suggested_fix?, auto_patchable}`.

---

## Phase 3 — Classify each issue

For each parsed issue, pick the most-likely category using these signals:

**subtitle-text** — keywords: "caption", "subtitle", "typo", "spelling", "word", "uppercase", "lowercase", "cap", "missing", "double"
**subtitle-timing** — "gap", "subtitle too fast", "stays too long", "caption timing"
**subtitle-style** — "color", "font", "size", "position", "below face", "above face"
**audio-levels** — "quiet", "loud", "clipping", "popped", "volume", "level", "compressed"
**video-timing** — "black frame", "black flash", "cut off", "trim", "fade", "lead", "starts too early"
**video-content** — "wrong hook", "re-cut", "wrong take", "different clip", "change the X", "move the Y"

Ambiguous → default to `video-content` (forces manual review) — don't auto-patch when in doubt.

Each issue gets tagged with a confidence score. Below 0.7 confidence → plan-only, don't patch.

---

## Phase 4 — Generate → Evaluate → Repair (per issue)

**The loop that replaces "patch everything → re-audit → hope" with surgical repair.**
Each issue runs through three small phases instead of one big patch pass. The point:
when the audit fails, you know **which patch** failed (and why) instead of re-rendering
blind. (Pattern from the Anthropic prompting playbook — generator/evaluator/repair
beats single-shot by 60%+ tokens and dramatically reduces V3 revisions.)

### 4a. Generate — patch candidate with declared expectation

For each `auto_patchable=true` issue, produce a JSON patch spec:

```json
{
  "issue_id": "issue-3",
  "category": "audio-levels",
  "recipe": "loudnorm",
  "params": {"i": -16, "tp": -1.5, "lra": 11},
  "expect": {
    "metric": "audio.integrated_lufs",
    "tolerance": [-17.0, -15.0]
  }
}
```

`expect` is the load-bearing field. It states what the patch is SUPPOSED to achieve in
a measurable way — the evaluator checks ONLY this, not the whole clip. Every recipe in
`references/patch-recipes.md` MUST declare its expect; recipes without an expect cannot
be auto-applied.

### 4b. Apply — execute the patch

**Patch execution order** (some patches stack):

1. Subtitle edits first (modify `.ass` text/timing)
2. Re-burn captions on the updated `.ass`
3. Video-timing edits next (trim black, add lead) on the re-captioned output
4. Audio normalization LAST (so it applies to the final mix)

All intermediate files go into a `_patching/` subdir. Final output = `<clip-stem>.v2.mp4`.
If any patch shells out and errors, log it + skip + continue.

### 4c. Evaluate — verify each patch hit its declared expectation

For each applied patch, measure the declared `expect.metric` on the v2 output. **Evidence
must be a number, not a verdict.** Examples:

- `audio.integrated_lufs` → `ffmpeg -af ebur128 -f null -` → parse `I:` field
- `video.black_frames_in_range` → `ffmpeg -vf blackdetect` → count entries in [tA, tB]
- `subtitle.text_at_time` → grep `.ass` Dialogue lines, check the new text is present
- `video.duration_at_least` → `ffprobe` format duration

Write the evaluation as `{issue_id, metric, observed, expected, met: bool, evidence}`
to `_patching/eval.json`.

### 4d. Repair — ONE targeted retry, then escalate

For each `met: false`:
- Try ONE alternative recipe (e.g. loudnorm I=-16 → -14, or volume-only fallback).
- Re-evaluate ONLY that metric on the second-try output.
- If still `met: false` after the retry → flip the issue to `auto_patchable=false`
  and route it to the edit brief at Phase 6. **Do not silently ship a clip where a
  declared expectation failed.**

The repair budget per issue is exactly ONE retry. This caps the blast radius — a
patch that needs three tries is structurally wrong and belongs in the edit brief.

---

## Phase 5 — Whole-clip re-audit (regression check)

After every per-issue evaluation passes, run a FULL `mozi-sf-audit` on the v2 — this
catches regressions where Phase 4 fixed the targeted issue but broke something else
(e.g. trimming black frames shortened the clip below the duration minimum):

```bash
python3 __ACQ_SKILLS__/mozi-sf-audit/scripts/audit.py \
  --clip <path>.v2.mp4 \
  --subtitles <path>.v2.ass \
  --platform instagram \
  --out ~/Downloads/audits/<slug>-v2.audit.md
```

**Phase 4 is per-issue and surgical; Phase 5 is whole-clip and adversarial.** Both must
pass to ship.

---

## Phase 6 — Update tracker

Based on audit v2 verdict:

- **SHIP (exit 0)**: `tracker.py transition <slug> audited-v2-pass` + attach audit v2 artifact
- **REVISE (exit 2)**: `tracker.py transition <slug> audited-v2-fail` — user sees on next dashboard run

For issues that were NOT auto-patchable AT INPUT *and* issues that **failed Phase 4d's
expectation evaluation after one retry**, write an edit brief to `<slug>-v2.edit-brief.md`
and link it into the tracker record. Transition to `audited-v2-fail` with a note pointing
to the brief. The brief MUST include the evaluator's evidence (observed metric vs declared
expectation) for any patch-and-retry failure — so the human knows exactly what the recipe
couldn't deliver, not just that "something went wrong."

---

## Phase 7 — Output report

```
REVISION PLAN — alex/example-clip (v1 → v2)

Feedback parsed: 4 issues
  ✅ [00:08]  subtitle-text        "Awesome" → "awesome"              auto-patched
  ✅ [00:23]  video-timing         black frame trimmed                  auto-patched
  ✅ [all]    audio-levels         normalized peak -12.5dB → -6.0dB     auto-patched
  ⚠️ [00:05]  video-content        "change hook to something punchier"  EDIT BRIEF (can't auto-patch)

v2 audit verdict: ❌ REVISE (1 remaining issue needs human)

Edit brief written: ~/Downloads/audits/example-clip-v2.edit-brief.md
Tracker: audited-v2-fail → see dashboard

Next step: address hook rewrite manually, re-render, run `tracker.py transition <slug> patching`.
```

If ALL issues were auto-patched and v2 audit passes:

```
REVISION PLAN — alex/example-clip (v1 → v2)

Feedback parsed: 3 issues
  ✅ [00:08]  subtitle-text        "Awesome" → "awesome"            auto-patched
  ✅ [00:23]  video-timing         black frame trimmed              auto-patched
  ✅ [all]    audio-levels         normalized peak -12.5dB → -6.0   auto-patched

v2 audit verdict: ✅ SHIP

Tracker: audited-v2-pass → ready to re-deliver to ACQ
v2 clip: ~/Downloads/clips-captioned/example-clip.v2.mp4
```

---

## Invocation

```bash
# Plan + auto-patch
python3 __ACQ_SKILLS__/revision-planner/scripts/planner.py \
  --clip-slug example-clip \
  --client alex \
  --mode safe

# Plan-only (don't patch, just write edit brief)
python3 ... --mode plan-only

# Feed inline text instead of tracker's stored feedback
python3 ... --text "hook too quiet, trim black frame at end"

# Run every clip in `needs-revision` state
python3 ... run-all-pending
```

---

## Quick reference card

```
INPUT     → clip in `needs-revision` state + feedback text
PHASE 1   → load context from tracker + audit report
PHASE 2   → parse feedback (structured or free-form)
PHASE 3   → classify each issue into 6 categories
PHASE 4   → per-issue Generate→Evaluate→Repair loop (declare expect → apply → measure → 1 retry → escalate)
PHASE 5   → whole-clip regression audit via mozi-sf-audit on v2
PHASE 6   → tracker transition to audited-v2-pass / audited-v2-fail
PHASE 7   → print report; write edit brief for non-auto-patchable issues

SAFE patches:      subtitle text + timing, audio normalize, black-frame trim, lead fix
NOT SAFE:          hook change, re-cut, wrong-take → edit brief
ALWAYS:            re-audit after patching / update tracker / link artifacts
NEVER:             auto-patch if confidence <0.7 / skip re-audit / overwrite v1 clip
```
