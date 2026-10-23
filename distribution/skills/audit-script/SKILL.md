---
name: audit-script
description: >
  Quick content check: review a supplied post, carousel, script, video or Premiere cut
  against the creator's hook-retain-reward, goodwill and value-compression framework.
  Use for "check this content", "would Alex like this", "review this against the content
  framework", or an explicit audit-script invocation. Returns a concise verdict and exact
  fixes using a fresh reviewer. Also owns optional strict editorial review and the
  post-render script audit in edit step 9. Review only unless
  changes are requested; does not claim the creator's personal approval.
---

# audit-script — editorial-only quality gate

For any Premiere access, follow [Premiere Agent startup and advanced stage routing](../edit/references/premiere_start_here.md). Use the configured new bridge by default; if MCP tools are missing in this chat, use its CLI. Keep this skill’s existing creative scope and read-only limits.


## Quick check — default for a standalone invocation

Invoke with `$audit-script check this` and attach/paste the content or identify the existing artifact in the session. A direct request to check whether the creator would like a piece routes here, unless the task explicitly calls for the `/edit` assembly handoff or final audit. This mode works without a clip project, Premiere connection, or the full editing pipeline.

1. Resolve the actual piece from the user's attachment, pasted copy, file/link, or clearly identified current-session artifact. Read it in full and identify the version. If no piece is available or several candidates are equally plausible, ask only which piece to check. Do not review the earlier discussion about a piece as though it were the piece itself.
2. Read [references/content_unit_review.md](references/content_unit_review.md), **Context and scope** and all seven **Review criteria**. Those criteria are the single source of truth. For this quick mode, omit the assembly-only packet, Premiere readback, JSON receipts and handoff gates. For written content use paragraph/line references; for carousels inspect every supplied slide in order; for video obtain the actual spoken transcript with timestamps and inspect visuals when available. State any unavailable modality or incomplete access rather than pretending to have reviewed it. A pasted script can receive a script verdict without the finished video.
3. Spawn a fresh subagent (`fork_turns="none"` or equivalent) with the exact piece/evidence, intended audience/platform if established, this skill path, and the shared rubric path. Request **quick mode**, all seven criteria, and the compact response below. Do not supply the builder's reasoning, praise, prior verdict or full session history. The reviewer must not recursively delegate. If delegation is unavailable, disclose that independent review could not run; a clearly labeled provisional self-check is permitted but must not be called an independent pass.
4. Return **Fits the framework / Needs changes / Cannot assess**, one sentence explaining why, the strongest element, and up to three highest-impact fixes with exact line/slide/time references. If there are additional material blockers, mention their count and location. Finish with a proposed opening or tighter structure only if useful, clearly labeled as a suggestion. Judge whether the length is earned; don't impose the legacy post-render duration caps. Use the shared framework as the creator's editorial lens, never assert what the actual person privately thinks.
5. Keep the response in chat by default. Review is read-only: do not recut, rewrite the saved artifact, publish, or run the full `/edit` pipeline unless requested. A quick-check verdict cannot substitute for `/edit`'s native assembly gate or audiovisual audits. If fixes are requested later, preserve source meaning and re-review the changed piece.

## Assembly review mode

Read [references/content_unit_review.md](references/content_unit_review.md) in full. New
v4 assembly jobs use one `final_editorial` review after Assembly Design's frame
resolution and word reconciliation and reuse it
when native readback proves the words/order are identical. Do not repeat the editorial
audit merely because those same words entered Premiere. Changed words/order invalidate it.
Historical v1-v3 native assembly handoffs retain their existing fresh-review contract.
Existing post-render checks still run at delivery.

## Post-render mode — existing delivery audit

The remaining sections apply to the rendered-file mode. For assembly review, the reference above owns the criteria, including earned length; do not import the generic duration caps below into that mode.

> Fresh-context agent. Receives ONLY the transcript text of the rendered clip.
> No video, no audio, no editing context. Tests whether the WORDS make sense
> to a cold viewer who just opened this video.

## How to run

```bash
python3 __ACQ_SKILLS__/audit-script/scripts/check.py \
    --clip 20_DELIVER/v1/clip.mp4 \
    --out 10_WORK/audit_script.json
```

The script transcribes the clip independently (Groq), then runs all editorial checks
on the text. It does NOT read any prior transcript or mining results.

## What it checks

### 1. COLD VIEWER TEST — does every line make sense with zero context?
- Read the transcript as if you just opened this video with no prior knowledge
- For each line, ask: "Does this make complete sense given ONLY the lines before it?"
- Flag: dangling references ("that focus", "what he said", "the same thing", "her ex")
  where the referent was never stated in this clip
- Flag: jargon or terms used without definition ("one avatar", "grand slam offer",
  "the funnel") that a cold viewer wouldn't understand
- Flag: mid-conversation continuations ("...and that's why", "so basically", "the point is")
  that assume the viewer heard something they didn't
- **FAIL** if any line requires context the clip doesn't provide

### 2. CONTEXT BEFORE PAYOFF — is the setup present?
- If this is a Q&A/commentary clip: does the QUESTION appear before the ANSWER?
- If this is a story clip: is there a setup before the punchline?
- If this is advice: is the PROBLEM stated before the SOLUTION?
- The viewer should understand WHY the speaker is saying what they're saying
- **FAIL** if payoff arrives without setup

### 3. ONE-ARC RULE — one topic, one story, one payoff?
- The clip should cover ONE thing. Not two half-stories stitched together.
- Flag: topic changes mid-clip ("...anyway, on a different note", or an abrupt shift
  from pricing to hiring to marketing)
- Flag: two separate Q&A pairs merged into one clip
- **FAIL** if the clip contains more than one distinct topic/arc

### 4. HOOK QUALITY — would a stranger stop scrolling?
- The first sentence must be compelling on its own
- Rate the hook: would a stranger who doesn't know the speaker stop scrolling?
- Check against hooks taxonomy (contrarian, story, stat, confession, stakes, question, list, reveal)
- Flag: hooks that are generic ("today we're going to talk about...")
- Flag: hooks that require insider knowledge to be interesting
- **WARN** if hook is weak (not a hard fail — subjective)

### 5. PAYOFF LANDS — does the ending resolve the setup?
- The last sentence should deliver a clear conclusion, lesson, or punchline
- Flag: trails off ("so yeah, that's kind of the thing...")
- Flag: introduces a new idea in the last line (no resolution)
- Flag: ends on a question without an answer (unless that's the hook structure)
- **FAIL** if the ending doesn't resolve the setup

### 6. LOGICAL FLOW — are there jumps in logic?
- Between each sentence, check: does this follow from the previous one?
- Flag: missing connecting logic where a cut removed a bridging sentence
- Flag: pronouns with no clear antecedent
- Flag: cause-and-effect claims where the cause was cut
- **WARN** if flow feels choppy (some choppiness is intentional for pacing)

### 7. BRAND SAFETY — does this comply with SOPs?
- No specific dollar amounts (unless the content type allows it)
- No competitor names
- No profanity (unless the brand allows it)
- No claims that could create legal liability
- Respects the brand's content guardrails (loaded from vocab/brand config if available)
- **FAIL** if any brand safety rule is violated

### 8. LENGTH APPROPRIATENESS
- Shorts: 25–40s of speech
- Mids: 60–75s of speech
- Hard cap: 90s
- Flag: clip is >90s of speech
- Flag: clip feels padded (could deliver the same point in half the time)
- **WARN** if over-length or padded

## Output format

```json
{
  "clip": "clip.mp4",
  "verdict": "FAIL",
  "transcript_word_count": 187,
  "estimated_duration_s": 52,
  "checks": {
    "cold_viewer": {"pass": false, "issues": [
      {"line": 3, "text": "that's why I always say focus on the avatar", "problem": "dangling reference: 'the avatar' never defined in this clip"}
    ]},
    "context_payoff": {"pass": true},
    "one_arc": {"pass": true},
    "hook_quality": {"pass": true, "hook_type": "contrarian", "hook_text": "Most people think revenue is the goal"},
    "payoff_lands": {"pass": true},
    "logical_flow": {"pass": true},
    "brand_safety": {"pass": true},
    "length": {"pass": true, "category": "short"}
  },
  "summary": "FAIL: cold viewer test — 'the avatar' referenced at line 3 but never defined in this clip"
}
```

## Fix instructions on failure

- Cold viewer issue → either add the missing context line to `cuts.json` (extend the clip)
  or rewrite/remove the line that references it
- Missing context/setup → extend the clip start in `cuts.json` to include the question/setup
- Multiple arcs → split into two clips, or trim one arc out in `cuts.json`
- Weak hook → consider starting the clip later at a stronger opening line
- Trailing payoff → trim the end in `cuts.json` to end on the strongest beat
- Brand safety → remove the offending line in `cuts.json`

## SOPs this agent should have loaded

When running as a sub-agent, load these references for the editorial checks:
- `__ACQ_SKILLS__/assembly-design/references/CLIP_CUTTING_PLAYBOOK.md` — preserved cutting playbook
- `edit/references/hooks_taxonomy.md` — hook classification
- `edit/TEAM_ALEX_QA_HOTLINE_SOP.md` — Q&A/Hotline specific rules (if Q&A content)
- The brand's `vocab.txt` if available (for jargon validation)
