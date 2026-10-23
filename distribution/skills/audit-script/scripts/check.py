#!/usr/bin/env python3
"""audit-script: independent editorial/script quality gate.

Transcribes the clip independently, then runs editorial checks:
cold viewer test, context-before-payoff, one-arc rule, hook quality,
payoff resolution, logical flow, brand safety, and length.

The heavy editorial checks (cold viewer, hook, flow) are best run by an
LLM sub-agent reading the transcript. This script handles the mechanical
checks (length, brand safety keywords) and prepares the transcript +
structured prompt for the LLM pass.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

WORDS_PER_SECOND = 3.5  # average speech rate

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
try:
    from asr import transcribe as _asr_transcribe, AsrUnavailable
except ImportError:
    _asr_transcribe, AsrUnavailable = None, RuntimeError


def transcribe_clip(clip_path: str) -> dict | None:
    """Transcribe via _shared/asr.py (Groq -> mlx fallback). None = no engine available."""
    if _asr_transcribe is None:
        return None
    try:
        return _asr_transcribe(clip_path)
    except AsrUnavailable as e:
        print(f"[transcribe] ASR UNAVAILABLE: {e}", file=sys.stderr)
        return None


def get_duration(clip_path: str) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", clip_path],
        capture_output=True, text=True,
    )
    return float(json.loads(r.stdout).get("format", {}).get("duration", 0))


def check_length(word_count: int, duration: float) -> dict:
    """Check clip length against category thresholds."""
    speech_duration = word_count / WORDS_PER_SECOND
    issues = []

    if speech_duration <= 40:
        category = "short"
    elif speech_duration <= 75:
        category = "mid"
    else:
        category = "long"

    if speech_duration > 90:
        issues.append({
            "severity": "error",
            "problem": f"speech duration ~{round(speech_duration)}s exceeds 90s hard cap",
        })
    elif speech_duration > 75 and category != "mid":
        issues.append({
            "severity": "warn",
            "problem": f"speech duration ~{round(speech_duration)}s — approaching 90s cap",
        })

    has_error = any(i["severity"] == "error" for i in issues)
    return {
        "pass": not has_error,
        "category": category,
        "speech_duration_s": round(speech_duration),
        "word_count": word_count,
        "issues": issues,
    }


def check_brand_safety(text: str, vocab_path: str | None = None) -> dict:
    """Check for brand safety violations using keyword matching."""
    issues = []
    text_lower = text.lower()

    # Profanity check (basic)
    profanity = ["fuck", "shit", "damn", "ass ", "bitch", "hell "]
    for word in profanity:
        if word in text_lower:
            # Find approximate position
            idx = text_lower.index(word)
            context = text[max(0, idx - 20):idx + 30]
            issues.append({
                "severity": "warn",
                "word": word.strip(),
                "context": context,
                "problem": f"profanity: '{word.strip()}'",
            })

    # Specific dollar amounts (often brand-restricted)
    dollar_matches = re.findall(r'\$[\d,]+(?:\.\d+)?', text)
    for dm in dollar_matches:
        # Clean and check magnitude
        amount_str = dm.replace("$", "").replace(",", "")
        try:
            amount = float(amount_str)
            if amount >= 100:  # Small amounts usually fine
                issues.append({
                    "severity": "warn",
                    "amount": dm,
                    "problem": f"specific dollar amount: {dm}",
                })
        except ValueError:
            pass

    # Load custom vocab if available
    if vocab_path and os.path.exists(vocab_path):
        with open(vocab_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("#") or not line:
                    continue
                if "BLOCK:" in line:
                    blocked = line.split("BLOCK:")[1].strip().lower()
                    if blocked in text_lower:
                        issues.append({
                            "severity": "error",
                            "problem": f"blocked term: '{blocked}'",
                        })

    has_error = any(i["severity"] == "error" for i in issues)
    return {"pass": not has_error, "issues": issues[:10]}


def check_opener(text: str) -> dict:
    """Check if the opener is clean (no filler words, no mid-conversation start)."""
    issues = []
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if not lines:
        return {"pass": True, "issues": []}

    first_line = lines[0].lower()

    # Filler openers
    fillers = ["yeah", "so", "um", "uh", "well", "okay so", "right so", "and", "but"]
    for filler in fillers:
        if first_line.startswith(filler + " ") or first_line == filler:
            issues.append({
                "severity": "warn",
                "problem": f"opens with filler: '{filler}'",
                "first_words": first_line[:50],
            })
            break

    # Mid-conversation start
    continuations = [
        "that's why", "that's what", "so basically", "the point is",
        "and that's", "which is why", "because of that",
    ]
    for cont in continuations:
        if first_line.startswith(cont):
            issues.append({
                "severity": "error",
                "problem": f"starts mid-conversation: '{cont}...'",
                "first_words": first_line[:60],
            })
            break

    has_error = any(i["severity"] == "error" for i in issues)
    return {"pass": not has_error, "issues": issues}


def check_dangling_references(text: str) -> dict:
    """Basic check for dangling references that need context not provided."""
    issues = []
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    # Common dangling patterns
    danglers = [
        (r"\bthat (?:thing|focus|approach|method|strategy)\b", "dangling 'that [noun]'"),
        (r"\bwhat (?:he|she|they) (?:said|mentioned|talked about)\b", "references prior speech"),
        (r"\bthe same (?:thing|way|approach)\b", "dangling 'the same [noun]'"),
        (r"\blike I (?:said|mentioned)\b", "self-reference to earlier speech"),
        (r"\bas I was saying\b", "mid-conversation continuation"),
    ]

    for i, line in enumerate(lines[:5]):  # Focus on early lines
        line_lower = line.lower()
        for pattern, desc in danglers:
            if re.search(pattern, line_lower):
                # Only flag if it's in the first 3 lines (later is usually fine)
                if i < 3:
                    issues.append({
                        "line": i + 1,
                        "text": line[:60],
                        "problem": desc,
                        "severity": "warn",
                    })

    return {"pass": True, "issues": issues}  # These are warnings — the LLM pass is authoritative


def prepare_llm_audit_prompt(transcript_text: str, checks_so_far: dict) -> str:
    """Prepare the structured prompt for the LLM editorial audit.

    This prompt is meant to be given to a Claude sub-agent to perform
    the subjective editorial checks (cold viewer, hook, flow, etc.).
    """
    return f"""You are an editorial auditor for short-form video clips. You receive ONLY the transcript of a rendered clip. You have ZERO context about what footage it came from, who edited it, or what the full conversation was about.

Read this transcript as if you just opened this video cold. You don't know the speaker. You don't know the show. You are a random person scrolling.

TRANSCRIPT:
---
{transcript_text}
---

Check EACH of the following and return a JSON object:

1. **cold_viewer** — Does every line make complete sense given ONLY the prior lines in this clip? Flag dangling references ("that thing", "what he said"), undefined jargon, mid-conversation continuations.

2. **context_payoff** — If this is Q&A: does the question appear before the answer? If advice: is the problem stated before the solution? If a story: is there setup before punchline?

3. **one_arc** — Does the clip cover exactly ONE topic/story/arc? Flag any topic changes or two separate Q&A pairs stitched together.

4. **hook_quality** — Would the first sentence make a stranger stop scrolling? Classify the hook type: contrarian / story / stat / confession / stakes / question / list / reveal / generic. Flag if generic or requires insider knowledge.

5. **payoff_lands** — Does the ending resolve the setup? Flag trails-off, introduces-new-idea, ends-on-question-without-answer.

6. **logical_flow** — Between each sentence, does it follow from the previous one? Flag missing connecting logic, pronouns without antecedent, cause-effect where cause was cut.

Return ONLY this JSON (no markdown, no explanation):
{{
  "cold_viewer": {{"pass": bool, "issues": []}},
  "context_payoff": {{"pass": bool, "issues": []}},
  "one_arc": {{"pass": bool, "issues": []}},
  "hook_quality": {{"pass": bool, "hook_type": "...", "hook_text": "first sentence", "issues": []}},
  "payoff_lands": {{"pass": bool, "issues": []}},
  "logical_flow": {{"pass": bool, "issues": []}}
}}

Each issue should have: {{"line": N, "text": "quoted text", "problem": "description", "severity": "error"|"warn"}}
Be strict. If in doubt, flag it as a warn."""


def main():
    parser = argparse.ArgumentParser(description="Audit editorial quality on a rendered clip")
    parser.add_argument("--clip", required=True, help="Path to rendered clip mp4")
    parser.add_argument("--out", required=True, help="Output JSON path")
    parser.add_argument("--vocab", help="Path to brand vocab.txt for brand safety")
    parser.add_argument("--llm-audit", action="store_true", help="Print LLM audit prompt to stdout for sub-agent")
    parser.add_argument("--llm-results", help="Path to JSON with the sub-agent's 6 editorial check results — merges them in so the verdict can be PASS")
    args = parser.parse_args()

    clip = args.clip
    if not os.path.exists(clip):
        print(f"ERROR: clip not found: {clip}", file=sys.stderr)
        sys.exit(1)

    duration = get_duration(clip)

    # Transcribe independently
    print("Transcribing clip independently...")
    transcript = transcribe_clip(clip)
    if transcript is None:
        # The ENTIRE gate is transcript-based — no engine = UNKNOWN report + exit 3, never PASS.
        fail = {"clip": os.path.basename(clip), "verdict": "UNKNOWN",
                "summary": "UNKNOWN: ASR unavailable — NO editorial checks ran "
                           "(fix Groq key / mlx_whisper; an unknown is NOT a pass)",
                "checks": {}}
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w") as f:
            json.dump(fail, f, indent=2)
        print("UNKNOWN: ASR unavailable — gate did not run", file=sys.stderr)
        sys.exit(3)
    full_text = transcript.get("text", "")

    if not full_text and "segments" in transcript:
        full_text = " ".join(s.get("text", "") for s in transcript["segments"])

    word_count = len(full_text.split())
    print(f"Transcribed: {word_count} words, ~{round(duration, 1)}s")

    results = {
        "clip": os.path.basename(clip),
        "transcript_word_count": word_count,
        "estimated_duration_s": round(duration, 1),
    }
    checks = {}

    # Mechanical checks (no LLM needed)
    print("Checking length...")
    checks["length"] = check_length(word_count, duration)

    print("Checking brand safety...")
    checks["brand_safety"] = check_brand_safety(full_text, args.vocab)

    print("Checking opener...")
    checks["opener"] = check_opener(full_text)

    print("Checking for dangling references...")
    checks["dangling_references"] = check_dangling_references(full_text)

    # LLM editorial checks — prepare prompt
    # These checks (cold_viewer, context_payoff, one_arc, hook_quality, payoff_lands, logical_flow)
    # require an LLM to evaluate. The prompt is either printed for a sub-agent or
    # placeholders are left in the output.
    llm_prompt = prepare_llm_audit_prompt(full_text, checks)

    if args.llm_audit:
        # Print the prompt for a sub-agent to process
        print("\n=== LLM AUDIT PROMPT ===")
        print(llm_prompt)
        print("=== END PROMPT ===\n")

    # The 6 editorial checks REQUIRE the LLM pass. Until 2026-08-03 these were
    # hardcoded {"pass": True} placeholders — the flagship checks of this gate never
    # ran and the gate rubber-stamped every clip. They are now honest UNKNOWNs
    # (pass: null) unless real results are merged in via --llm-results.
    LLM_CHECKS = ["cold_viewer", "context_payoff", "one_arc", "hook_quality", "payoff_lands", "logical_flow"]
    for check_name in LLM_CHECKS:
        checks[check_name] = {"pass": None, "issues": [],
                              "note": "NOT RUN — requires the LLM editorial pass "
                                      "(run the audit agent on llm_audit_prompt, then merge via --llm-results)"}
    if args.llm_results:
        try:
            with open(args.llm_results) as f:
                llm = json.load(f)
            merged = 0
            for check_name in LLM_CHECKS:
                if isinstance(llm.get(check_name), dict) and "pass" in llm[check_name]:
                    checks[check_name] = llm[check_name]
                    merged += 1
            print(f"Merged {merged}/{len(LLM_CHECKS)} LLM editorial results from {args.llm_results}")
        except Exception as e:
            print(f"ERROR: could not merge --llm-results ({e}) — editorial checks stay UNKNOWN",
                  file=sys.stderr)

    # Verdict: FAIL beats UNKNOWN beats PASS. PASS requires the editorial checks to have RUN.
    any_fail = any(c["pass"] is False for c in checks.values())
    any_unknown = any(c["pass"] is None for c in checks.values())
    results["verdict"] = "FAIL" if any_fail else ("UNKNOWN" if any_unknown else "PASS")
    results["checks"] = checks
    results["transcript"] = full_text
    results["llm_audit_prompt"] = llm_prompt

    failures = [k for k, v in checks.items() if v["pass"] is False]
    unknowns = [k for k, v in checks.items() if v["pass"] is None]
    if failures:
        first_fail = failures[0]
        first_issue = checks[first_fail]["issues"][0] if checks[first_fail]["issues"] else {}
        results["summary"] = f"FAIL: {', '.join(failures)}. {first_issue.get('problem', 'see details')}"
    elif unknowns:
        results["summary"] = (f"UNKNOWN: mechanical checks passed but the editorial checks did not run "
                              f"({', '.join(unknowns)}) — run the LLM pass and merge via --llm-results")
    else:
        results["summary"] = "All editorial + mechanical checks passed"

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n{results['verdict']}: {results['summary']}")
    print(f"Report: {args.out}")
    # exit codes: 0 PASS · 2 FAIL · 3 UNKNOWN — never 0 unless everything actually ran
    sys.exit(0 if results["verdict"] == "PASS" else (2 if results["verdict"] == "FAIL" else 3))


if __name__ == "__main__":
    main()
