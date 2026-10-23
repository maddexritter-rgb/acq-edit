#!/usr/bin/env python3
"""qa_calibration_score — score a Q&A cut against OLIVER'S ground-truth cut (2026-06-17).

The regression test for editorial TASTE. Pixel gates (audit-visual) and the editorial gate
(qa_editorial_score) measure a clip against rules; THIS measures a candidate cut against how
OLIVER actually cut the same raw footage — the closest thing to "cut like Oliver" we can score.

Use it two ways:
  1. After ANY change to the SOP / clipper_ai_prompt / cut-design: re-cut the corpus BLIND and
     confirm similarity went UP, not down (regression test for editorial taste).
  2. In a live session: produce a blind cut of a case's RAW, score it, read the divergences.

Each case file (edit/references/qa_calibration/case_NNN_*.json) holds:
  { RAW_full_interaction, OLIVER_published_cut, oliver_published_seconds, [MY_shipped_cut] }

Usage:
  qa_calibration_score.py --case <case.json> --candidate "<your blind cut transcript>"
  qa_calibration_score.py --case <case.json> --candidate-file <file.txt>
  qa_calibration_score.py --case <case.json> --score-shipped   # score the saved MY_shipped_cut
Exit 0 always (it's a measurement, not a gate); prints hook/payoff match + similarity + divergences.
"""
from __future__ import annotations
import argparse, json, re, subprocess, sys
from pathlib import Path

RUBRIC = """You are calibrating an AI Q&A editor against OLIVER, our master editor (the ground truth).
You are given the RAW interaction, OLIVER'S published cut of it, and a CANDIDATE cut. Score how close
the candidate is to Oliver's editorial choices — NOT whether it's "good" in the abstract, but whether
it picked the moment the way Oliver did.

Score these axes:
- HOOK: did the candidate open the way Oliver did — the CONTRAST HOOK (what they do, THEN the revenue),
  reaching back for the identity/credential if Oliver did, dropping host filler? match / close / miss.
- PAYOFF: did the candidate END on the SAME portable principle Oliver ended on (not a bare tactic /
  wind-down / earlier stopping point)? This is the highest-weight axis. match / close / miss.
- TENSION/BODY: did it keep the same core reasoning and cut the same tangents Oliver cut? match/close/miss.
- LENGTH: candidate seconds vs Oliver's seconds (a skeleton far shorter than Oliver = miss).
- SIMILARITY 0-100: overall structural closeness to Oliver's cut.

Output VALID JSON ONLY:
{"hook_match":"match|close|miss","payoff_match":"match|close|miss","body_match":"match|close|miss",
 "candidate_seconds_est":N,"oliver_seconds":N,"similarity_0_100":N,
 "divergences":[{"where":"hook|tension|payoff|length","what_oliver_did":"...","what_candidate_did":"...","lesson":"..."}],
 "verdict":"one-line: how close did the candidate land to Oliver, and the single biggest miss"}"""

def score(raw, oliver, oliver_sec, candidate):
    prompt = (f"{RUBRIC}\n\nRAW INTERACTION:\n\"\"\"\n{raw}\n\"\"\"\n\n"
              f"OLIVER'S PUBLISHED CUT ({oliver_sec}s):\n\"\"\"\n{oliver}\n\"\"\"\n\n"
              f"CANDIDATE CUT:\n\"\"\"\n{candidate}\n\"\"\"\n\nScore it. JSON only.")
    try:
        r = subprocess.run(["claude", "-p", "--model", "claude-opus-4-8", prompt],
                           capture_output=True, text=True, timeout=240)
        m = re.search(r"\{[\s\S]*\}", r.stdout)
        if not m:
            return {"error": f"no JSON from claude: {r.stdout[:200]} {r.stderr[:200]}"}
        return json.loads(m.group(0))
    except Exception as e:
        return {"error": str(e)}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", required=True)
    ap.add_argument("--candidate")
    ap.add_argument("--candidate-file")
    ap.add_argument("--score-shipped", action="store_true", help="score the saved MY_shipped_cut as the candidate")
    a = ap.parse_args()

    c = json.loads(Path(a.case).read_text())
    raw = c["RAW_full_interaction"]; oliver = c["OLIVER_published_cut"]
    oliver_sec = c.get("oliver_published_seconds", "?")
    if a.score_shipped:
        candidate = c.get("MY_shipped_cut", "")
        if not candidate: sys.exit("no MY_shipped_cut in case file")
    elif a.candidate_file:
        candidate = Path(a.candidate_file).read_text()
    elif a.candidate:
        candidate = a.candidate
    else:
        candidate = sys.stdin.read()

    r = score(raw, oliver, oliver_sec, candidate)
    if "error" in r:
        print("ERROR:", r["error"]); sys.exit(2)
    print(f"\n  case: {Path(a.case).name}")
    print(f"  hook={r.get('hook_match'):5}  payoff={r.get('payoff_match'):5}  body={r.get('body_match'):5}"
          f"  | ~{r.get('candidate_seconds_est')}s vs Oliver {r.get('oliver_seconds')}s"
          f"  | SIMILARITY {r.get('similarity_0_100')}/100")
    for d in r.get("divergences", []):
        print(f"   ✗ [{d.get('where')}] Oliver: {d.get('what_oliver_did')}")
        print(f"            cand: {d.get('what_candidate_did')}")
        print(f"          lesson: {d.get('lesson')}")
    print(f"\n  → {r.get('verdict')}\n")

if __name__ == "__main__":
    main()
