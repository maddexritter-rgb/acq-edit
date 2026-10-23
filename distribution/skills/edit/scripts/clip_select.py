#!/usr/bin/env python3
"""clip_select — pick clip-worthy moments out of a long-form MONOLOGUE / podcast / talk.

The CLIPS-lane selector (bucket 1). NOT for Q&A / hotline — that's tam_select.py, untouched.

THREE stages:
  1. PROPOSE (LLM, prompts/clip_select.md): candidate windows + open/exit/structure tags + the
     exact open/exit lines, grounded in the 602-pair lift study.
  2. LIFT SCORE (deterministic, config/clip_lift.json): a coarse empirical prior on the tags
     (0.35*open + 0.40*exit + 0.25*structure). Good recall, coarse ranking (many candidates tie).
  3. JUDGE (LLM, prompts/clip_judge.md): a content-reading clip-worthiness re-rank of every proposed candidate
     lift candidates — the tie-breaker that reads the ACTUAL open/exit language (hook punch,
     cold-viewer self-containment, payoff landing). Phase-5 validation showed stage 2 alone
     ranks the human's moment well into the list but rarely #1; the judge is what fixes that.

Final order = all candidates judged by quality desc (lift tiebreak); incomplete review fails.
verdict (judged): MINE >= 70 · MAYBE >= 50 · PASS < 50.  Disable the judge with --no-judge.

Input  : transcript JSON ({"segments":[{start,end,text}]}) or plain .txt
Output : <out>.clips.json (ranked, scored) + <out>.clips.md (readable)
Auth   : ANTHROPIC_API_KEY (env / ~/.zshrc) else the `claude -p` CLI.
Usage  : python3 clip_select.py --transcript pod.json --top 12 --out 10_WORK/pod
"""
from __future__ import annotations
import argparse, json, os, re, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROMPT_PATH = HERE.parent / "prompts" / "clip_select.md"
JUDGE_PROMPT_PATH = HERE.parent / "prompts" / "clip_judge.md"
RULES_PATH = HERE.parent / "config" / "clip_lift.json"
W_OPEN, W_EXIT, W_STRUCT = 0.35, 0.40, 0.25


def load_transcript(p: Path) -> str:
    raw = p.read_text()
    if p.suffix.lower() != ".json":
        return raw
    d = json.loads(raw)
    rows = d if isinstance(d, list) else d.get("segments") or d.get("words") or d.get("transcript")
    if isinstance(rows, list) and rows:
        return "\n".join(
            f"[{float(x.get('start', 0)):.3f}-{float(x.get('end', 0)):.3f} "
            f"speaker={x.get('spk', x.get('speaker', 'unknown'))}] "
            f"{str(x.get('text', x.get('word', ''))).strip()}" for x in rows)
    if isinstance(d, dict) and isinstance(d.get("text"), str):
        return d['text']
    raise ValueError("Unsupported or empty transcript; provide segments or words with source seconds")


def proposal_prompt(rules):
    return PROMPT_PATH.read_text() + "\n\nACTIVE EMPIRICAL PRIORS (not acceptance rules):\n" + json.dumps(rules)


def get_key():
    k = os.environ.get("ANTHROPIC_API_KEY")
    if k:
        return k
    try:
        m = re.search(r"sk-ant-[A-Za-z0-9_\-]+", (Path.home() / ".zshrc").read_text())
        if m:
            return m.group(0)
    except Exception:
        pass
    return None


def call_claude(system: str, user: str) -> str:
    key = get_key()
    if key:
        try:
            import anthropic
            c = anthropic.Anthropic(api_key=key)
            r = c.messages.create(model="claude-sonnet-4-6", max_tokens=8192, temperature=0,
                                  system=system, messages=[{"role": "user", "content": user}])
            return r.content[0].text
        except Exception as e:
            print(f"[clip_select] SDK failed ({e}); trying claude CLI", file=sys.stderr)
    proc = subprocess.run(["claude", "-p", f"{system}\n\n---INPUT---\n{user}"],
                          capture_output=True, text=True, timeout=600)
    if proc.returncode != 0:
        sys.exit(f"[clip_select] claude CLI failed: {proc.stderr[:300]}")
    return proc.stdout


def parse_json(text: str) -> dict:
    t = re.sub(r"^```(?:json)?\s*", "", text.strip()).replace("```", "").strip()
    i = t.find("{")
    if i > 0:
        t = t[i:]
    j = t.rfind("}")
    if j != -1:
        t = t[:j + 1]
    return json.loads(t)


def lift_of(table: dict, tag) -> float:
    if not tag:
        return 1.0
    e = table.get(str(tag).strip().lower())
    return float(e["lift"]) if e and "lift" in e else 1.0


def _nk(s):
    return re.sub(r"[^a-z0-9 ]", "", " ".join((s or "").lower().split()))


def judge_rerank(transcript: str, cands: list, top_k=None) -> list:
    """Review all proposed candidates. A missing/failed judge cannot retain a MINE verdict."""
    if not cands:
        return cands
    items = [{**c, "candidate_id": str(i)} for i, c in enumerate(cands)]
    user = ("CANDIDATES:\n" + json.dumps(items, indent=2)
            + f"\n\nSOURCE TRANSCRIPT:\n{transcript}")
    ranked = parse_json(call_claude(JUDGE_PROMPT_PATH.read_text(), user)).get("ranked", [])
    if not isinstance(ranked, list) or len(ranked) != len(cands):
        raise ValueError("UNKNOWN: incomplete editorial judge coverage")
    by_id = {r.get("candidate_id"): r for r in ranked}
    if set(by_id) != {str(i) for i in range(len(cands))}:
        raise ValueError("UNKNOWN: duplicate or unmatched editorial judge IDs")
    result = []
    for i, candidate in enumerate(cands):
        r = by_id[str(i)]
        q = r.get("quality")
        if type(q) not in (int, float) or not 0 <= q <= 100:
            raise ValueError("UNKNOWN: invalid editorial judge quality")
        c = dict(candidate)
        c["quality"] = q
        c["judge"] = {k: r.get(k) for k in ("hook", "cold", "payoff", "vehicle", "tight", "verdict")}
        c["verdict"] = "MINE" if q >= 70 else ("MAYBE" if q >= 50 else "PASS")
        result.append(c)
    return sorted(result, key=lambda c: (-c['quality'], -c.get('lift_score', 0)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--transcript", required=True)
    ap.add_argument("--top", type=int, default=12)
    ap.add_argument("--out", default=None)
    ap.add_argument("--rules", default=str(RULES_PATH))
    ap.add_argument("--no-judge", dest="judge", action="store_false", help="skip the stage-3 quality judge")
    a = ap.parse_args()

    tp = Path(a.transcript).expanduser()
    if not tp.exists():
        sys.exit(f"[clip_select] transcript not found: {tp}")
    rules = json.loads(Path(a.rules).read_text())
    open_t, exit_t, struct_t = rules["open_type_lift"], rules["exit_type_lift"], rules["structure_lift"]

    transcript = load_transcript(tp)
    out = parse_json(call_claude(proposal_prompt(rules), f"Return up to {a.top} candidates.\n\nTRANSCRIPT:\n{transcript}"))
    cands = out.get("candidates", [])
    if not isinstance(cands, list) or any(not isinstance(c, dict) for c in cands):
        raise ValueError("Invalid candidates schema")
    cands = cands[:a.top]

    # stage 2: lift score + coarse sort
    for c in cands:
        ol, xl, sl = lift_of(open_t, c.get("open_type")), lift_of(exit_t, c.get("exit_type")), lift_of(struct_t, c.get("structure"))
        c["lift_breakdown"] = {"open": ol, "exit": xl, "structure": sl}
        c["lift_score"] = round(W_OPEN * ol + W_EXIT * xl + W_STRUCT * sl, 3)
        c["verdict"] = "MINE" if c["lift_score"] >= 1.25 else ("MAYBE" if c["lift_score"] >= 1.0 else "PASS")
    cands.sort(key=lambda c: -c.get("lift_score", 0))

    # stage 3: quality judge re-rank (the tie-breaker)
    if a.judge:
        cands = judge_rerank(transcript, cands)
    else:
        for c in cands:
            c["verdict"] = "UNREVIEWED"
    for i, c in enumerate(cands, 1):
        c["rank"] = i
    cands = cands[: a.top]

    base = Path(a.out).expanduser() if a.out else tp.with_suffix("")
    js, md = base.with_suffix(".clips.json"), base.with_suffix(".clips.md")
    js.write_text(json.dumps({"candidates": cands, "scoring": {
        "weights": {"open": W_OPEN, "exit": W_EXIT, "structure": W_STRUCT},
        "judge": a.judge, "rules_subset": rules.get("subset"), "n_pairs": rules.get("n_pairs")}}, indent=2))

    lines = [f"# CLIP selection — {tp.name}", "",
             f"{len(cands)} candidates · lift prior + {'quality judge' if a.judge else 'lift only'} ({rules.get('n_pairs')} pairs) · best first", ""]
    for c in cands:
        q = f" · quality {c['quality']}" if c.get("quality") is not None else ""
        lines += [
            f"## [{c['verdict']}] {c['rank']}. {c.get('title_idea','')}  "
            f"({c.get('start')}–{c.get('end')}) · lift {c.get('lift_score')}{q}",
            f"- open ({c.get('open_type')}): \"{c.get('open_line','')}\"",
            f"- exit ({c.get('exit_type')}): \"{c.get('exit_line','')}\"",
            f"- structure ({c.get('structure')}) · reach_back={c.get('reach_back')}",
            f"- keep: {c.get('keep_vehicle','')}",
            f"- cut: {', '.join(c.get('cut_list', []) or [])}"]
        if c.get("judge"):
            lines.append(f"- judge: {c['judge'].get('verdict','')}")
        lines += [f"- why: {c.get('why','')}", ""]
    md.write_text("\n".join(lines))

    mine = sum(1 for c in cands if c["verdict"] == "MINE")
    print(f"[clip_select] {len(cands)} candidates ({mine} MINE){' +judge' if a.judge else ''} → {js}  +  {md}")


if __name__ == "__main__":
    main()
