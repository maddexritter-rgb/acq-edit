#!/usr/bin/env python3
"""qa_prebuild_audit — run the 6 pre-build gates on a Q&A clip's EDL BEFORE the 4K encode.

Catches the defect classes Maddex reviewed on the L1 batch (2026-06-14 → 06-16):
  G1 BOUNDARY-TAIL — seg_end clipping soft-consonant words (Whisper-end-label is 0.1-0.25s early)
  G2 GUEST-COMPLETION — cam-transitions that cut the previous speaker mid-completion (reads as muted mic)
  G3 PAYOFF-EXTENSION — closing seg ends before the natural button line in source
  G4 INTRO-BIZ-PLUS-PROBLEM — cold-viewer can answer "what's the business" AND "what's the problem"
  G5 MUSIC-INTRO-PROFILE — track has a slow build-up that needs --music-ss past the beat-drop
  G6 GUEST-EYE-POSITION — guest face center in upper third of panel (not lower-middle)
  G7 ENDING-COMPLETE — clip ends on a complete thought, not mid-clause / a trailing stammer (shared ending_check)

Usage:
  python3 qa_prebuild_audit.py <clip_project_dir> [--transcript <words.json>] [--sync <qa_sync.json>] [--music <path.mp3>]

Exit 0 = all gates pass. Exit 1 = at least one gate flagged. Prints a structured report.
"""
from __future__ import annotations
import argparse, json, os, re, subprocess, sys
from pathlib import Path

SOFT_TAIL = ("s","t","th","m","n","ng","tion","al","ful","ce","ze","x","f","sh","ch","d","l","r")
FILLER_OPENERS = {"and","so","but","or","um","uh","ah","mm","like","yeah","yep","well","okay","right","also"}

def load_words(path: Path):
    return json.loads(Path(path).read_text()).get("words", [])

def find_word_at(words, t, tol=0.01):
    """Return (idx, word) whose .end is within tol of t, or None."""
    for i, w in enumerate(words):
        if abs(w["end"] - t) <= tol or w["start"] <= t <= w["end"]:
            return (i, w)
    return None

def words_in_window(words, t0, t1):
    return [w for w in words if t0 <= w["start"] <= t1]

def soft_tail(word_text: str) -> str | None:
    bare = "".join(c for c in (word_text or "").lower() if c.isalpha())
    for s in sorted(SOFT_TAIL, key=len, reverse=True):
        if bare.endswith(s):
            return s
    return None

def gate_boundary_tail(edl, words):
    """G1: seg_end clipping soft-consonant words."""
    flags = []
    for i, seg in enumerate(edl["segments"]):
        end = seg["mic_end"]
        # find the word that ends at/just-before this segment end
        last_w = None
        for w in words:
            if w["end"] <= end + 0.005:
                last_w = w
            else:
                break
        if not last_w: continue
        gap = end - last_w["end"]
        # next word's start (ceiling for extension)
        next_w = next((w for w in words if w["start"] > last_w["end"]), None)
        gap_to_next = (next_w["start"] - end) if next_w else 99
        tail = soft_tail(last_w.get("word",""))
        # flag if soft-tail consonant AND gap-to-end is < 0.10s AND there's basically no room
        if tail and 0 <= gap < 0.10 and gap_to_next < 0.15:
            flags.append({
                "seg": i+1, "mic_end": end, "word": last_w.get("word","").strip(),
                "soft_tail": tail, "gap_to_label_end": round(gap, 3),
                "next_word_start": (next_w["start"] if next_w else None),
                "next_word": (next_w.get("word","").strip() if next_w else None),
                "suggested_fix": f"extend mic_end to {min(end+0.20, (next_w['start']-0.01) if next_w else end+0.20):.3f}" if next_w else f"extend mic_end to {end+0.20:.3f}",
            })
    return flags

def gate_guest_completion(edl, words):
    """G2: cam-transitions that cut the previous speaker mid-completion.

    Distinguishes natural-flow cut (defect — small source gap with prev speaker still talking)
    from extract-and-weld (intentional — large source jump across conversation phases)."""
    flags = []
    segs = edl["segments"]
    for i in range(len(segs)-1):
        cur, nxt = segs[i], segs[i+1]
        if cur["cam"] == nxt["cam"]: continue   # no cam-transition
        gap_words = [w for w in words if cur["mic_end"] < w["start"] < nxt["mic_start"]]
        if not gap_words: continue
        total_gap = nxt["mic_start"] - cur["mic_end"]
        # ONLY flag SHORT same-conversation gaps (< 5s). Larger = deliberate extract-and-weld.
        if total_gap > 5.0: continue
        # AND only when there's MEANINGFUL content (not just fillers/affirmations)
        gap_text = " ".join(w.get("word","").strip() for w in gap_words).strip()
        bare_words = [re.sub(r"[^a-z']","",w.get("word","").lower()) for w in gap_words]
        non_filler = [b for b in bare_words if b and b not in {"yeah","yes","ok","okay","mm","mhm","right","uh","um","cool"}]
        if len(non_filler) < 1: continue   # only fillers in gap → not a real cut
        flags.append({
            "seg_transition": f"{i+1}→{i+2}",
            "prev_speaker": cur.get("speaker"), "next_speaker": nxt.get("speaker"),
            "prev_cam": cur.get("cam"), "next_cam": nxt.get("cam"),
            "source_gap_s": round(total_gap, 2),
            "gap_words": gap_text[:120],
            "non_filler_words": non_filler[:8],
            "suggested_fix": f"consider extending seg{i+1} mic_end to ~{gap_words[-1]['end']:.3f} so {cur.get('speaker','prev')} finishes naturally before cam-switch (gap is only {total_gap:.1f}s — likely same-conversation, not weld)",
        })
    return flags

def gate_payoff_extension(edl, words):
    """G3: closing seg ends before the natural button line.

    Only flags when the next 1–6 words form a SHORT, IMPERATIVE/PUNCHY button (not a continuation thought)."""
    if not edl["segments"]: return []
    last = edl["segments"][-1]
    end = last["mic_end"]
    look_words = [w for w in words if end < w["start"] < end + 3.0]
    if len(look_words) < 2: return []
    # Find first period within the next 6 words
    for i, w in enumerate(look_words[:6]):
        if "." not in w.get("word",""): continue
        button = " ".join(x.get("word","").strip() for x in look_words[:i+1])
        bare = re.sub(r"[^a-zA-Z ]","",button).strip()
        wc = len(bare.split())
        if wc < 2 or wc > 7: continue   # too short or too long to be a punchy button
        # Punchy-button heuristic: starts with imperative ("Give", "Say", "Do", "Just") or "So <imperative>"
        first = bare.split()[0].lower()
        IMPERATIVE = {"give","say","do","stop","go","keep","take","make","ask","get","run","let","start","find","build","cut","drop","quit","sell","buy","write","trust","know","forget","never","always","just"}
        connector = first in {"so","and","but","because"} and len(bare.split()) > 1
        if first in IMPERATIVE or connector:
            button_end = look_words[i]["end"]
            return [{
                "current_end": end,
                "candidate_button": button,
                "button_ends_at": button_end,
                "suggested_fix": f"extend last seg mic_end {end:.2f}→{button_end+0.20:.2f} to include the button line",
            }]
        break  # found a period but not a punchy button — don't recommend extension
    return []

def gate_intro_business_plus_problem(edl, words, n_intro_segs=4):
    """G4: read first N segments — does the text answer 'what's the business' AND 'what's the problem'?"""
    intro_segs = edl["segments"][:n_intro_segs]
    intro_words = []
    for s in intro_segs:
        intro_words.extend([w.get("word","").strip() for w in words if s["mic_start"] <= w["start"] <= s["mic_end"]])
    intro_text = " ".join(intro_words).lower()
    # Heuristic business indicators: "sell", "I run", "we do", "company", revenue numbers
    biz_re = re.compile(r"\b(?:sell|run|own|do|we\s+(?:are|do|did|provide|make|sold)|provide|company|firm|business|service|practice|brand|cart|coffee|skin|cancer|portfolio|wealth|gym|insurance|million|thousand|\$|revenue|founders?|fitness|nutrition|sleep|investment|community|teach|broker|brokerage|advisor|advisory|sales|franchise|cafe|store|clinic|build|hiring|trainer|coach|consult|babies|overnight\s+care|daycare|childcare)\b", re.I)
    # Heuristic problem indicators: explicit problem words OR an implicit goal/gap (e.g. "want to get to $10M" reveals
    # a current vs target gap = the problem). The intro frames the problem either explicitly ("inventory issue")
    # or by stating a stretch goal vs current state (the doctor: "$250K → want $10M" → model needs to change).
    prob_re = re.compile(
        r"\b(?:"
        r"problem|issue|struggling|stuck|flat|can'?t|cannot|but |trying to|"
        r"too (?:much|heavy|hard|expensive)|underpriced|inventory|bottleneck|drowning|"
        r"drained|drains|hate|stale|losing|"
        # GOAL/GAP patterns (implicit problem):
        r"want(?:s|ed)? to (?:get|reach|grow|scale|go|hit|do|make|be)|"
        r"need to (?:get|reach|grow|scale|go|hit|do|make|be)|"
        r"looking to (?:get|reach|grow|scale|go|hit|do|make|be)|"
        r"trying to (?:get|reach|grow|scale|go|hit|do|make|be)|"
        r"hoping to|goal is|target is|aim(?:ing)? to|"
        r"plan(?:ning)? to (?:get|reach|grow|scale|go|hit|do|make|be)|"
        # Contradiction:
        r"on top of (?:that|this)|even though|despite|"
        # Job/situation friction (Maddex 2026-06-16: missed "full-time daytime job" pattern):
        r"full-time(?:\s+(?:daytime\s+)?job)?|day(?:time)?\s+job|side\s+(?:hustle|business)|"
        r"go pro|going pro|going full-time|"
        # Constraint/friction:
        r"only|less than|not enough|barely|fear|risk|afraid|worried|scaling|scale\b|behind|fix"
        r")\b", re.I
    )
    biz_hits = biz_re.findall(intro_text)
    prob_hits = prob_re.findall(intro_text)
    if biz_hits and prob_hits:
        return []
    return [{
        "intro_segments_examined": len(intro_segs),
        "intro_text": intro_text[:200],
        "biz_indicators_found": list(set(biz_hits)),
        "problem_indicators_found": list(set(prob_hits)),
        "missing": [] + (["business"] if not biz_hits else []) + (["problem"] if not prob_hits else []),
        "suggested_fix": "extend intro to include the guest's concrete problem statement (not just business+revenue). Consider welding in Alex's diagnostic callback ('you're sitting on product') as a clarifying beat.",
    }]

def gate_music_intro(music_path: str) -> list:
    """G5: profile music for slow intro buildup."""
    if not music_path or not Path(music_path).exists():
        return []
    cmd = ["ffmpeg","-hide_banner","-nostats","-i",music_path,"-t","30",
           "-af","astats=metadata=1:reset=1:length=1,ametadata=print:key=lavfi.astats.Overall.RMS_level",
           "-f","null","-"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    rms = []
    for ln in (r.stderr + r.stdout).splitlines():
        if "RMS_level=" in ln:
            try: rms.append(float(ln.rsplit("=",1)[-1]))
            except ValueError: rms.append(-99)
    # find first second where RMS > -25dB (substantial signal)
    beat_at = None
    for i, v in enumerate(rms[:30]):
        if v > -25.0:
            beat_at = i; break
    if beat_at and beat_at > 1:
        return [{
            "music": Path(music_path).name,
            "beat_drop_at_s": beat_at,
            "rms_curve_first_5s": rms[:5],
            "suggested_fix": f"pass --music-ss {beat_at}.0 to skip the build-up and start at the beat-drop",
        }]
    return []

def gate_ending_complete(edl, words):
    """G7: the clip must END on a COMPLETE thought (added 2026-06-18). Uses the shared canonical
    false-ending rule (_shared/ending_check.ends_complete) — the SAME rule reqc enforces post-render —
    so a false ending is caught BEFORE the 4K encode, not after. FAILS when the last kept word is
    mid-clause / a non-terminal word or stammer (and/but/that/that's/until…) OR the SAME speaker keeps
    going on the same clause in the SOURCE. Origin: StageQA/tyler shipped ending on '…a sales motion
    that's' while the raw continues 'That's, that's.' — G3 (payoff-extension) only looks FORWARD for a
    punchy button, it never checked the last word itself was terminal."""
    try:
        from ending_check import ends_complete
    except ImportError:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "_shared"))
        from ending_check import ends_complete
    if not edl.get("segments"): return []
    last = edl["segments"][-1]; end = last["mic_end"]
    last_w = None
    for w in words:
        if w["end"] <= end + 0.02: last_w = w
        elif w["start"] > end: break
    if not last_w: return []
    next_words = [w for w in words if w["start"] > last_w["end"]][:15]
    ok, reason = ends_complete(last_w.get("word",""), next_words)
    if ok: return []
    return [{
        "clip_ends_on": last_w.get("word","").strip(),
        "mic_end": round(end, 3),
        "reason": reason,
        "suggested_fix": "pull the last segment's mic_end back to the previous sentence-terminal word "
                         "(the last acoustically-complete payoff line); drop the trailing non-terminal "
                         "word / stammer. EAR-verify the new last word is whole (never trust ASR on a tail).",
    }]

def gate_guest_eye(sync: dict):
    """G6: guest panel eye position. Warn if eye > 0.30 (face center likely below upper third)."""
    gs = sync.get("guest_split", {})
    eye = gs.get("eye", 0.22)
    if eye > 0.30:
        return [{
            "current_eye": eye,
            "suggested_fix": f"lower guest_split.eye to ~0.15-0.20 (guest face will land too low in panel at eye={eye}). Render one test frame, measure where face center lands; if face_y > 0.35 of panel_height, lower further.",
        }]
    return []

CONNECTIVE_TISSUE = ["which is that", "so i could just be like", "what i was essentially asking",
                     "i guess what i'm asking", "i guess what im asking", "so basically what i'm saying",
                     "what i mean is", "i guess i'm just trying to", "if that makes sense"]

def gate_pacing(edl, words):
    """G8 PACING (ADVISORY — Oliver review 2026-06-22, calibration case_008): the #1 Q&A review note is
    'too loose.' Flag, BEFORE encode, the two things Oliver consistently trims: (a) intra-clip DEAD-AIR
    pauses (a gap > 0.6s between consecutive KEPT words inside a segment) and (b) leftover CONNECTIVE-TISSUE
    filler in the kept text. This is ADVISORY, not blocking and NOT an auto-cut: auto-trimming pauses on the
    single-cam answer re-opens the documented jump-cut regression, so the editor decides (and reqc's jump-cut
    gate is the backstop). It just makes the slack visible so we tighten toward Oliver pre-encode."""
    flags = []
    segs = edl.get("segments", [])
    kept = []
    for i, s in enumerate(segs):
        ms = float(s.get("mic_start", s.get("in", 0))); me = float(s.get("mic_end", s.get("out", 0)))
        seg_words = [w for w in words if w["start"] >= ms - 0.02 and w["end"] <= me + 0.02]
        kept.extend(seg_words)
        for a, b in zip(seg_words, seg_words[1:]):
            gap = b["start"] - a["end"]
            if gap > 0.6:
                flags.append({"type": "dead_air", "seg": i + 1, "at": round(a["end"], 2), "gap_s": round(gap, 2),
                              "between": f"…{a.get('word','').strip()} [gap] {b.get('word','').strip()}…",
                              "suggested_fix": f"tighten the {gap:.1f}s pause after '{a.get('word','').strip()}' (ear-verify; don't clip the word)"})
    text = " ".join(re.sub(r"[^a-z' ]", "", w.get("word", "").lower()) for w in kept)
    for phr in CONNECTIVE_TISSUE:
        if phr in text:
            flags.append({"type": "connective_tissue", "phrase": phr,
                          "suggested_fix": f"cut connective tissue '{phr}' — keep the substance on either side"})
    return flags

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project", help="path to clip project dir containing edl.json")
    ap.add_argument("--transcript", help="path to words.json (defaults to 10_WORK/_transcripts/alex_lav.words.json)")
    ap.add_argument("--sync", help="path to qa_sync.json (defaults to PROJECT/../qa_sync.json or 10_WORK/qa_sync.json)")
    ap.add_argument("--music", help="path to music track to profile")
    args = ap.parse_args()

    proj = Path(args.project).resolve()
    edl_path = proj / "edl.json"
    if not edl_path.exists():
        print(f"[setup] no edl.json at {edl_path} — gate skipped", file=sys.stderr); sys.exit(2)
    edl = json.loads(edl_path.read_text())

    # Resolve transcript
    tr = Path(args.transcript) if args.transcript else None
    if not tr or not tr.exists():
        for cand in [proj.parent.parent / "10_WORK/_transcripts/alex_lav.words.json",
                     proj.parent / "_transcripts/alex_lav.words.json"]:
            if cand.exists(): tr = cand; break
    if not tr or not tr.exists():
        print(f"[setup] no words.json found (tried {tr}) — gate skipped", file=sys.stderr); sys.exit(2)
    words = load_words(tr)

    # Resolve sync
    sy = Path(args.sync) if args.sync else None
    if not sy or not sy.exists():
        for cand in [proj.parent.parent / "10_WORK/qa_sync.json", proj.parent / "qa_sync.json"]:
            if cand.exists(): sy = cand; break
    sync = json.loads(sy.read_text()) if sy and sy.exists() else {}

    print(f"=== qa_prebuild_audit  {proj.name} ===")
    print(f"  edl: {edl_path}  ({len(edl['segments'])} segments)")
    print(f"  words: {tr}")
    print(f"  sync: {sy}")
    print(f"  music: {args.music or '(not provided — skipping G5)'}")

    issues = []
    for name, fn, args_ in [
        ("G1 BOUNDARY-TAIL",       gate_boundary_tail,       (edl, words)),
        ("G2 GUEST-COMPLETION",    gate_guest_completion,    (edl, words)),
        ("G3 PAYOFF-EXTENSION",    gate_payoff_extension,    (edl, words)),
        ("G4 INTRO-BIZ+PROBLEM",   gate_intro_business_plus_problem, (edl, words)),
        ("G5 MUSIC-INTRO-PROFILE", gate_music_intro,         (args.music,)),
        ("G6 GUEST-EYE-POSITION",  gate_guest_eye,           (sync,)),
        ("G7 ENDING-COMPLETE",     gate_ending_complete,     (edl, words)),
    ]:
        flags = fn(*args_)
        if flags:
            print(f"\n  ⚠️  {name}: {len(flags)} flag(s)")
            for f in flags:
                print(f"     " + json.dumps(f, indent=6).replace("\n", "\n     "))
            issues.extend([(name, f) for f in flags])
        else:
            print(f"  ✓  {name}")

    # G8 PACING — ADVISORY ONLY (does not block): surfaces loose dead-air + connective filler to tighten toward Oliver.
    pacing = gate_pacing(edl, words)
    if pacing:
        print(f"\n  ⓘ  G8 PACING (advisory, tighten toward Oliver — not blocking): {len(pacing)} flag(s)")
        for f in pacing:
            print(f"     " + json.dumps(f, indent=6).replace("\n", "\n     "))
    else:
        print(f"  ✓  G8 PACING (advisory)")

    print(f"\n=== verdict: {'BLOCK — fix flagged items before encode' if issues else 'ALL GATES PASS — clear to build'} ===")
    if pacing and not issues:
        print("    (G8 PACING advisories above are tighten-suggestions, not blockers.)")
    sys.exit(1 if issues else 0)

if __name__ == "__main__":
    main()
