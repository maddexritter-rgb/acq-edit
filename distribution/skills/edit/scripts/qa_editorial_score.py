#!/usr/bin/env python3
"""qa_editorial_score — the EDITORIAL transcript gate for Q&A clips (2026-06-17).

Turns the 250-pair winner-vs-loser analysis (qa_clip_patterns.md → "TRANSCRIPT EDITORIAL
TRANSFORM") into an enforced gate. Scores a clip's spoken transcript on the 5 dimensions that
separate top10 from bottom25, and BLOCKS the editorial patterns that land bottom-25:

  1. HOOK CLASS      — plain_statement opener = 0.23x DEATH hook → FAIL. Want confession /
                       vivid_image / contrarian_claim. (number/question = neutral WARN.)
  2. PAYOFF CLASS    — ending on wind_down (0.06x) / bare tactic (0.11x) / cta (0x) = FAIL.
                       Want principle / story_button / number_reframe / tough_love.
  3. PORTABILITY     — the #1 predictor (2.89x). Read hook+payoff cold: do both stand alone? FAIL if no.
  4. ONE ARC         — two competing threads = WARN.
  5. OPENER CLEAN    — mid-fragment / lowercase / hedge open = FAIL (never open mid-thought).

Uses the local `claude` CLI for the judgment (it's authed; same pattern as tam_select). Falls
back to heuristics if the CLI is unavailable. Run at edit Step 4 (after designing keep-spans,
BEFORE render) and again as a pre-render gate on the delivered transcript.

Usage:
  qa_editorial_score.py --transcript-json <file>   # {name: {title, transcript}} → scores each
  qa_editorial_score.py --text "<clip transcript>"  # score one
  echo '<transcript>' | qa_editorial_score.py -
Exit 0 = all PASS. Exit 1 = ≥1 FAIL.
"""
from __future__ import annotations
import argparse, json, os, re, subprocess, sys
from pathlib import Path

RULESET = """You are the EDITORIAL gate for an Alex Hormozi Q&A short, scoring its TRANSCRIPT against
Oliver's team SOP (the CLIPPER AI PROMPT), confirmed by 250 perf-tiered raw→final pairs. Score ONLY the text.

HOOK (the first sentence) — the CONTRAST HOOK is the standard (Alex's own directive):
  WIN = activity/what-they-do FIRST, then the revenue ("I sell property in the UAE and we do $6M" /
    "I print stickers and make $1.5M") — the mundane-activity + big-number contrast = the "holy shit" magnet.
    Also winning: confession (raw admission), vivid_image, contrarian_claim, an immediate attention-grabber
    ("well, that's a racket", "$10M but our profit is shit").
  ACCEPTABLE — DO NOT FAIL (Oliver ships these): an activity→revenue opener that names WHAT they do + the
    number ("we do business coaching for PT practices, $2.1M last year") even if it's not a "holy shit"
    contrast. It IS the contrast-hook form. Prefer a punchier line if one genuinely exists in the raw, but a
    clear activity→revenue opener PASSES — WARN at most, never FAIL. (Many real guests have no punchy hook.)
  DEATH (FAIL only these): a truly flat declarative with NO number AND no activity-identity AND no stakes;
    OR revenue-FIRST bragging with no activity ("we do $6M" alone); OR a mid-sentence lowercase fragment;
    OR a GREETING / NAME-INTRO opener ("my name is…", "hi, I'm X with the Y team", "hey") — that's the
    pleasantry Oliver always cuts; drop it and OPEN on what they do + the number (the Dominique/ThreeFunctions
    clip opened on "my name is Dominique, I'm with the Deep Pockets team" and buried the $20M six seconds in).
  PREFACE BLOAT (Oliver's #1 underperformance cause): the opener must satisfy the HOOK FILTER — either a
    short preface (≤15s of setup) OR an attention-grabber. Long setup + delayed grab = FAIL.

PAYOFF (the last sentence):
  WINNING: principle (portable universal maxim — 74% of winners), belief-breaker, Alex's professional opinion,
    story_button, number_reframe, tough_love. Must be CONCRETE and understandable without extra context.
  DEATH: wind_down (trailing off / guest reaction / "land the plane" — 0.06x, deadliest), a NICHE tactic that
    only helps this one guest (0.11x — a widely-applicable actionable step is fine; a guest-specific one is not),
    cta (sales pitch — 0x), cliffhanger / dangling question.

PORTABILITY (#1 predictor, 2.89x): read ONLY the first line + last line as a cold viewer with zero context.
  Does the hook intrigue AND the payoff resolve it, standalone? Niche diagnostics that need the whole case = NOT portable.

ONE ARC: a single Problem → Solution loop (the "One-Hit" model — The Lesson, not The Journey). Two distinct
  PROBLEMS being solved = FAIL (split into separate clips). BUT a supporting story / example / anecdote — even
  Alex's own (e.g. his "6 gyms to 0 in gym launch" sell-off) — that REINFORCES the single principle is NOT a
  second arc; KEEP it. The test is "two problems being solved?", not "more than one example used."

REASONING LADDER (calibration case_001, 2026-06-17 — the one verified under-trim failure): when the payoff
  is a REFRAME or a NUMBER, keep the diagnosis→WHY ladder that EARNS it (the concrete figures, the mechanism,
  the ROI/value logic), and end on the portable PRINCIPLE — never amputate the middle so the clip jumps
  hook→tactic→done. A reframe/number payoff with its reasoning stripped to bookends = WARN "restore the why
  that makes the payoff land for a cold viewer." (Surgeon clip: the "$4M practice → 70% from this → I did $3M
  doing this → teach the business part → incremental value / direct ROI" ladder is what earns the price
  reframe; cutting straight from "underpriced" to "25K + 5K/yr" strips it.)
  COUNTER-COST (do NOT overcorrect into going long): this is not a license to pad. Duration does NOT separate
  tiers (winner median ≈35s; many winners <30s; duration↔views r≈0.09). Trim hard — cut tangents, side-quests,
  logistics, the 2nd thread — just don't cut the spine that makes the payoff make sense. Keep the WHY, not the length.

NO-DETOUR / OVER-LENGTH (cold-start validation 2026-06-17 — the #1 cold-session failure: cuts ran ~2x Oliver):
  once the answer/diagnosis is REACHED, DELETE the remaining diagnostic back-and-forth. Flag (WARN) any cut that
  keeps Socratic Q&A, logistics, or "still figuring it out" exchanges AFTER the payoff logic has landed — Oliver
  cuts almost straight from the stakes to the answer. (Tanya cold cut 128s vs Oliver 80s; Trey 128s vs 68s — both
  kept a diagnostic middle Oliver removed.) The arc is hook → minimum WHY → answer; extra rounds of diagnosis = cut.

CONTEXT-FIRST HOOK (cold-start miss — pelvic-floor): the opener must establish the GUEST's business + problem,
  NOT open cold on Alex's rhetorical question ("how many gyms do you think I had?"). If the winning context line
  sits earlier in the raw, HUNT BACKWARD for it and open there. Opening on Alex's question with no guest setup = a
  hook MISS (a cold viewer doesn't know who the advice is for).

NO-RESTATEMENT ENDING (cold-start miss — Trey): ending on a conceptual LABEL or a restatement of the problem
  ("that's how you generate leads", "it's a lead-gen campaign") = a wind-down, FAIL. End one beat FORWARD on the
  CONCRETE quantified result/principle ("you'll probably sell more than a hundred carts"). When Oliver had numbers,
  he ended on the numbers — prefer the concrete result over the abstract label.

BRAND / CLIENT-PULL SAFETY: flag (WARN) exact price points ("my price is $X"), "I fired [name]", or other
  specific/sensitive details a client could want pulled. Revenue/profit framing only.

VERDICT: FAIL if hook is plain_statement/revenue-first/none/Preface-Bloat, OR payoff is wind_down/niche-tactic/
  cta/cliffhanger, OR not portable, OR two competing arcs, OR opener is a mid-sentence fragment. WARN for
  neutral hooks, client-pull risks, or minor issues. PASS only if the hook is a contrast/winning class, the
  payoff is a portable principle/concrete advice, it's ONE arc, and it passes the cold test.

Output VALID JSON ONLY:
{"hook_class": "...", "hook_first_words": "...", "contrast_hook": true/false, "payoff_class": "...",
 "payoff_last_words": "...", "portable": true/false, "one_arc": true/false, "opener_clean": true/false,
 "client_pull_risk": true/false, "verdict": "PASS|WARN|FAIL", "failures": ["..."], "fix": "one concrete instruction"}"""

def score_with_claude(name, transcript):
    prompt = f"{RULESET}\n\nCLIP: {name}\nTRANSCRIPT:\n\"\"\"\n{transcript}\n\"\"\"\n\nScore it. JSON only."
    try:
        r = subprocess.run(["claude", "-p", "--model", "claude-opus-4-7", prompt],
                           capture_output=True, text=True, timeout=180)
        if r.returncode != 0:
            return {"error": f"claude exit {r.returncode}: {r.stderr[:150]}"}
        m = re.search(r"\{[\s\S]*\}", r.stdout)
        if not m:
            return {"error": f"no JSON: {r.stdout[:150]}"}
        return json.loads(m.group(0))
    except Exception as e:
        return {"error": str(e)}

DEATH_TACTIC_TAILS = re.compile(r"\b(just (say|do|run|use|add)|you (could|should|want to)|register here|link in bio|acquisition\.com|free gift|i would recommend|that.?ll probably|give the \w+ one away)\b", re.I)
WINDDOWN_TAILS = re.compile(r"\b(thank you|thanks|appreciate it|good luck|land the plane|you got this|that.?s it|anyway)\b\.?\s*$", re.I)

def heuristic(name, transcript):
    """Fast non-LLM fallback: catches the loudest death signals."""
    t = transcript.strip()
    first = t.split(".")[0] if t else ""
    last = t.rstrip().split(".")[-2] if t.count(".") >= 1 else t
    fails = []
    opener_clean = bool(re.match(r"^[A-Z\"']", t)) and first.split()[0:1] != []
    if not opener_clean:
        fails.append("opener starts mid-fragment / lowercase")
    if t.rstrip().endswith("?"):
        fails.append("ends on a dangling question (cliffhanger)")
    if WINDDOWN_TAILS.search(t[-60:]):
        fails.append("ends on a wind-down / sign-off")
    if DEATH_TACTIC_TAILS.search(t[-120:]):
        fails.append("ends on a bare tactic / CTA")
    verdict = "FAIL" if fails else "WARN"   # heuristic can't confirm PASS (needs LLM for hook/portability)
    return {"hook_first_words": " ".join(first.split()[:8]), "payoff_last_words": last.strip()[-80:],
            "verdict": verdict, "failures": fails, "fix": "run with claude CLI for full hook/portability scoring",
            "heuristic_only": True}

def score_transcript(name, tx, no_llm=False):
    """Full editorial score for ONE transcript: LLM (or heuristic) + the substance floor.
    Returns the verdict dict {verdict, failures, fix, word_count, ...}. Importable by cut_design.py."""
    r = (heuristic if no_llm else score_with_claude)(name, tx)
    if "error" in r and not no_llm:
        r = heuristic(name, tx); r["llm_error"] = True
    # SUBSTANCE FLOOR (250-pair data: winner median 148 words ≈ 57s; p25 ≈ 100 words).
    # A cut under ~100 words is a hook→principle SKELETON that strips Alex's reasoning — never shipped.
    nwords = len((tx or "").split())
    r["word_count"] = nwords; r["approx_seconds"] = round(nwords / 2.6)
    if nwords < 100:
        r.setdefault("failures", []).append(
            f"TOO THIN: {nwords} words (~{round(nwords/2.6)}s). Winners are ~130–160 words / ~50–65s. "
            f"You stripped Alex's reasoning chain to bookends — keep the diagnosis + the WHY, not just hook+principle.")
        r["verdict"] = "FAIL"
    return r

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--transcript-json")
    ap.add_argument("--text")
    ap.add_argument("--no-llm", action="store_true", help="heuristics only (fast, no PASS verdicts)")
    ap.add_argument("stdin", nargs="?")
    a = ap.parse_args()

    items = {}
    if a.transcript_json:
        d = json.loads(Path(a.transcript_json).read_text())
        for k, v in d.items():
            items[k] = v.get("transcript", v) if isinstance(v, dict) else v
    elif a.text:
        items["clip"] = a.text
    else:
        items["clip"] = sys.stdin.read()

    results, any_fail = {}, False
    for name, tx in items.items():
        r = score_transcript(name, tx, no_llm=a.no_llm)
        results[name] = r
        v = r.get("verdict", "?")
        if v == "FAIL": any_fail = True
        hk = r.get("hook_class", "?"); pf = r.get("payoff_class", "?")
        print(f"  [{v:4}] {name:34s} hook={hk:16s} payoff={pf:14s} portable={r.get('portable','?')}")
        for f in r.get("failures", []): print(f"          ✗ {f}")
        if r.get("fix") and v != "PASS": print(f"          → {r['fix']}")
    print(f"\n{'BLOCK — fix FAILs before render' if any_fail else 'ALL PASS'}")
    sys.exit(1 if any_fail else 0)

if __name__ == "__main__":
    main()
