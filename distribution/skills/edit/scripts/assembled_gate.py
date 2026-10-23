#!/usr/bin/env python3
"""assembled_gate.py — BLOCKING gate on what a clip ACTUALLY SAYS, after every span change.

WHY THIS EXISTS (2026-08-08, L1QA0213/1018 batch — editor: "the cuts aren't really great,
especially on the intros and hooks… you must not read these in context"):
A session designed clips text-first, passed qa_editorial_score, then hit FUSED boundaries
from speech_map_cut. It then "repaired" the spans mechanically — snap-to-gap, expand
outward, repair loops — and shipped. Every repair silently REWROTE the clip: greetings
re-entered the head, payoffs ran on into wind-downs, endings became mid-sentence
cliffhangers. Durations and exit codes were checked after each pass. The WORDS never were.

So this gate reads the assembled text and blocks on the two things that pass every other
check: how the clip OPENS and how it ENDS.

🛑 THE RULE IT ENFORCES: the boundary engine tells you where you MAY cut. It NEVER gets to
   pick the opening line. If the only legal cut leaves a greeting in the head, the fix is a
   DIFFERENT opening (start on the syllable of the business/problem, or cold-open on a
   punchy host reaction whose next line is the context) — not shipping the greeting.
   (TEAM_ALEX_QA_HOTLINE_SOP §2/§6.)

Run it: at edit spine step 5 (after boundaries resolve), after ANY snap/repair/revision that
moves a span, and again at step 8b before delivery. Exit 0 = clean · 1 = BLOCK.

Usage:
  assembled_gate.py <clip_dir>...            # each dir needs assembled_final.txt
  assembled_gate.py --text "..." --name X
"""
import argparse, glob, os, re, sys

GREETING = re.compile(r"^\s*(hey|hi|hello|good (morning|afternoon)|what's up|how's it going|how are you)\b", re.I)
NAME_INTRO = re.compile(r"^\s*(my name is|my name's|i'm|i am)\s+[A-Z][a-z]+", re.I)
FILLER_OPEN = re.compile(r"^\s*(so|and|but|um|uh|ah|like|well|yeah|yes|okay|ok|right|also|anyway|anyways|cool|sure|alright|all right|i mean|you know|basically|actually|honestly|literally)\b[\s,]", re.I)
TRAIL_CONNECTIVE = re.compile(r"\b(so|and|but|because|which|that|the|a|an|to|of|is|are|it's|like|then|or|if|when|for|with|as|at|in|on|my|your|his|her|their|this|these|those)\s*[,.]?\s*$", re.I)
# Elliptical modal "…had to." / "…supposed to." is a COMPLETE terminal construction, not a
# trailing connective (2026-08-19: false-blocked "I've just been heartbroken when I had to.",
# a verified sentence-terminal ending followed by a turn change in source).
ELLIPTICAL_TO = re.compile(r"\b(had|have|has|need|needs|want|wants|going|supposed|used|trying|tried)\s+to\s*[,.]?\s*$", re.I)
# Wh-clause terminal copula ("…no one knows who you are.") is likewise a COMPLETE sentence,
# not a trailing connective (2026-08-19: false-blocked the S05 'biggest competitor is
# irrelevance' ending).
WH_COPULA = re.compile(r"\b(who|what|where|why|how) (you|it|they|we|i) (are|is|am|were|was)\s*[,.]?\s*$", re.I)
QUESTION_BACK = re.compile(r"(does that make sense|make sense|you know what i mean|is that right|right|helpful|okay|got it|cool)\s*[?.]?\s*$", re.I)
WIND_DOWN = re.compile(r"\b(thank you|thanks|appreciate it|you bet|no worries|that's it|awesome|perfect|cool|good luck|there you go)\s*[.!]?\s*$", re.I)


def sentences(t):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", t.strip()) if s.strip()]


def check(name, text, preface_s=None):
    fails, warns = [], []
    t = " ".join(text.split())
    if not t:
        return [f"{name}: EMPTY"], []

    head = " ".join(t.split()[:12])
    # Scan the OPENING WINDOW, not just offset 0 — "Alex. My name's Luke…" and
    # "All right. Hey, my name is…" both put the pleasantry a word or two in.
    win = " ".join(t.split()[:14])
    # ---- OPENER --------------------------------------------------------------
    # 🛑 A SELF-INTRO IS NOT A DEFECT. TEAM_ALEX_QA_HOTLINE_SOP §2 gives two valid hook
    # styles and the FIRST is "Short Preface (<=15s) — ideally a self-intro + the contrast
    # number". And qa_clip_patterns' "drop the name 92-100%" is measured on PODCAST/highlight
    # pairs; its own FORMAT NOTE says the L1-WORKSHOP diagnostic format STILL NEEDS the
    # business+problem intro so a cold viewer knows whose problem it is.
    # What is actually banned: GREETINGS/pleasantries, and PREFACE BLOAT (>15s of setup
    # before the host enters). Enforce those, not a blanket name ban.
    # (Corrected 2026-08-08 after this gate blocked a valid SOP hook style.)
    if GREETING.match(t) or re.search(r"\b(hey|hi|hello)[ ,]+(alex|there|man|guys)\b", win, re.I):
        fails.append(f"OPENER carries a GREETING/pleasantry — strip it; start on the syllable "
                     f"of the business/problem: “{head}…”")
    if re.search(r"\b(how's it going|how are you|nice to meet you|thank you for|thanks for having|"
                 r"i can't believe i'm|big fan)\b", win, re.I):
        fails.append(f"OPENER carries a pleasantry — strip it: “{head}…”")
    if FILLER_OPEN.match(t):
        # SOP counter-cost clause (edit SKILL 4PRE): a single leading connective in natural
        # cadence may STAY when removing it chops the opener — "trim it only when it's a true
        # verbal tic or it precedes the real hook word". So a lone And/So/But in front of a
        # substantive activity+number statement is a WARN, not a block. Everything else
        # (um/uh/yeah/okay/well/like/I mean/basically…) still blocks.
        m = re.match(r"^\s*(and|so|but)\b[\s,]+(.*)", t, re.I)
        rest = m.group(2) if m else ''
        first_sent = re.split(r"(?<=[.!?])\s", rest)[0] if rest else ''
        substantive = (len(first_sent.split()) >= 7 and
                       re.search(r"[$0-9]|\b(sell|run|own|do|make|help|teach|build)\b", first_sent, re.I))
        if m and substantive:
            warns.append(f"OPENER keeps a natural leading “{m.group(1)}” — allowed by the "
                         f"counter-cost clause; razor it by hand if you want it gone: “{head}…”")
        else:
            fails.append(f"OPENER starts on a filler/discourse marker: “{head}…”")
    if t[:1].islower() and not re.match(r"^\s*(and|so|but)\b", t, re.I):
        fails.append(f"OPENER begins mid-sentence (lowercase first word): “{head}…”")
    if re.match(r"^\s*[-—–]", t):
        fails.append(f"OPENER begins on a dash fragment: “{head}…”")

    # ---- ENDING --------------------------------------------------------------
    ss = sentences(t)
    last = ss[-1] if ss else t
    tail = " ".join(t.split()[-14:])
    if not re.search(r"[.!?]\s*$", t):
        fails.append(f"ENDING is not sentence-terminal — mid-sentence cliffhanger: “…{tail}”")
    if re.search(r"[-—–]\s*$", t):
        fails.append(f"ENDING trails on a dash — truncated thought: “…{tail}”")
    if TRAIL_CONNECTIVE.search(last.rstrip(".!?")) and not ELLIPTICAL_TO.search(last.rstrip(".!?")) and not WH_COPULA.search(last.rstrip(".!?")):
        fails.append(f"ENDING trails on a connective — extend to the principle: “…{tail}”")
    if QUESTION_BACK.search(last):
        fails.append(f"ENDING is a question back to the guest (wind-down class, 0.06x): “…{tail}”")
    if WIND_DOWN.search(last):
        fails.append(f"ENDING is a wind-down/pleasantry (THE deadliest ending): “…{tail}”")
    if len(last.split()) < 4:
        warns.append(f"ENDING is a very short fragment ({len(last.split())}w): “…{tail}”")

    # ---- PREFACE BLOAT / HOST ENTRY (SOP §2, the 5–15s host-entry rule) -------
    # The real hook defect is not a self-intro, it's SETUP THAT RUNS LONG before the host
    # enters. Caller passes the measured preface seconds; word-count proxy otherwise
    # (~200wpm for this format => 15s ~= 50 words).
    pre_s = preface_s
    if pre_s is not None:
        if pre_s > 15.0:
            fails.append(f"PREFACE BLOAT: {pre_s:.1f}s of setup before the host enters "
                         f"(hard rule 15s; target <5s) — compress the intro or cold-open "
                         f"on a host reaction")
        elif pre_s > 10.0:
            warns.append(f"guest setup {pre_s:.1f}s uninterrupted (>10s) — intersperse a host "
                         f"reaction/nod per SOP §2")

    # ---- SUBSTANCE -----------------------------------------------------------
    n = len(t.split())
    if n < 100:
        warns.append(f"SHORT CONTENT: {n} words — verify complete source value and reward "
                     f"through design evidence and editorial review; word count alone is not a defect")
    return fails, warns


def main():
    # The native handoff is a separate mode: text heuristics alone cannot certify it.
    if '--assembly-handoff' in sys.argv[1:]:
        from pathlib import Path
        import subprocess
        gate = Path(__file__).resolve().parents[2] / 'audit-script/scripts/assembly_handoff.py'
        args = [arg for arg in sys.argv[1:] if arg != '--assembly-handoff']
        return subprocess.run([sys.executable, str(gate), '--check', *args]).returncode
    ap = argparse.ArgumentParser()
    ap.add_argument('clipdirs', nargs='*')
    ap.add_argument('--text'); ap.add_argument('--name', default='clip')
    ap.add_argument('--file', default='assembled_final.txt')
    ap.add_argument('--preface-json', help='optional {clip: preface_seconds} map')
    a = ap.parse_args()

    items = []
    if a.text:
        items.append((a.name, a.text))
    for d in a.clipdirs:
        p = os.path.join(d, a.file)
        if not os.path.exists(p):
            cand = glob.glob(os.path.join(d, 'assembled*.txt'))
            if not cand:
                print(f"  [SKIP] {d}: no assembled text"); continue
            p = sorted(cand)[-1]
        items.append((os.path.basename(d.rstrip('/')), open(p).read()))

    pmap = {}
    if a.preface_json and os.path.exists(a.preface_json):
        import json as _j; pmap = _j.load(open(a.preface_json))

    bad = 0
    for name, text in items:
        fails, warns = check(name, text, pmap.get(name))
        if fails:
            bad += 1
            print(f"  [BLOCK] {name}")
            for f in fails: print(f"        ✗ {f}")
        else:
            print(f"  [OK]    {name}" + (f"  ({len(warns)} warn)" if warns else ""))
        for w in warns: print(f"        ⚠ {w}")
    print(f"\n{'🛑 BLOCK — fix the openers/endings before any render or import'
            if bad else '✅ all assembled texts open and end clean'}")
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
