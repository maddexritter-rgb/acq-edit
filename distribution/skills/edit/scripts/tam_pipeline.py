#!/usr/bin/env python3
"""tam_pipeline — thin orchestrator: transcript -> segment -> select -> combined ranked picks.

Flow (all additive; reuses the existing tools, doesn't replace them):
  1. tam_segment.py  splits the long-form transcript into exchanges + carves filler.
  2. for each NON-filler exchange, slice the transcript to that exchange's [start,end] window and
     feed it to tam_select.py (the team TAM filter) — so each exchange is scored on its own.
  3. merge every exchange's candidates, re-rank globally by tam_score, write a combined
     <out>.picks.json + <out>.picks.md.

Why per-exchange instead of one giant tam_select pass: segmentation already isolated each guest, so
tam_select sees a clean single-exchange window (better hooks/boundaries) and we never lose a strong
moment to a neighbouring louder one. Filler exchanges are skipped entirely.

This calls the two scripts as subprocesses (python3 <script>) so their Claude-call logic, prompts,
and output schemas stay the single source of truth. No new dependency.

Usage:
  python3 tam_pipeline.py --transcript session.json --format hotline --top-per 3 --out ~/Downloads/sess
Outputs: <out>.segments.json/.md (from tam_segment) and <out>.picks.json/.md (combined ranked picks).
"""
from __future__ import annotations
import argparse, json, subprocess, sys, tempfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
SEGMENT = SCRIPTS / "tam_segment.py"
SELECT = SCRIPTS / "tam_select.py"


def run(cmd: list[str]):
    print(f"[pipe] $ {' '.join(str(c) for c in cmd)}", file=sys.stderr)
    p = subprocess.run([sys.executable, *[str(c) for c in cmd]], text=True)
    if p.returncode != 0:
        sys.exit(f"[pipe] step failed: {cmd[0]}")


def load_segments(p: Path) -> list[dict]:
    raw = json.loads(p.read_text())
    segs = raw.get("segments") or raw.get("transcript") or []
    return [s for s in segs if isinstance(s, dict)]


def slice_window(segments: list[dict], start: float, end: float) -> dict:
    """Build a {"segments":[...]} transcript covering only [start,end] (tam_select's input shape)."""
    out = []
    for s in segments:
        ss, se = float(s.get("start", 0) or 0), float(s.get("end", 0) or 0)
        if se <= start or ss >= end:
            continue
        out.append({"start": ss, "end": se, "text": str(s.get("text", "")).strip()})
    return {"segments": out}


def mmss_to_sec(v) -> float:
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str) and ":" in v:
        parts = [float(x) for x in v.split(":")]
        if len(parts) == 2:
            return parts[0] * 60 + parts[1]
        if len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
    try:
        return float(v)
    except Exception:
        return 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--transcript", required=True)
    ap.add_argument("--format", default="qa", choices=["qa", "hotline"])
    ap.add_argument("--window-min", type=float, default=28.0)
    ap.add_argument("--top-per", type=int, default=3, help="max candidates per exchange")
    ap.add_argument("--top", type=int, default=20, help="max combined picks to keep")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    tp = Path(a.transcript).expanduser()
    if not tp.exists():
        sys.exit(f"[pipe] transcript not found: {tp}")
    base = Path(a.out).expanduser()
    base.parent.mkdir(parents=True, exist_ok=True)

    # 1. segment ------------------------------------------------------------------------------
    run([SEGMENT, "--transcript", tp, "--format", a.format,
         "--window-min", a.window_min, "--out", base])
    seg_path = base.with_suffix(".segments.json")
    exchanges = json.loads(seg_path.read_text()).get("exchanges", [])
    content = [e for e in exchanges if not e.get("is_filler")]
    print(f"[pipe] {len(content)} content exchanges to select on "
          f"({len(exchanges)-len(content)} filler skipped)", file=sys.stderr)

    # source transcript segments (for slicing windows to feed tam_select)
    src_segments = load_segments(tp) if tp.suffix.lower() == ".json" else []

    # 2. select per exchange ------------------------------------------------------------------
    all_picks: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="tam_pipe_") as td:
        tdir = Path(td)
        for e in content:
            if src_segments:
                window = slice_window(src_segments, e["start"], e["end"])
            else:
                # No structured segments (plain-text transcript): hand the whole thing once.
                window = {"text": tp.read_text()}
            win_path = tdir / f"ex_{e['id']:03d}.json"
            win_path.write_text(json.dumps(window))
            out_stub = tdir / f"ex_{e['id']:03d}"
            run([SELECT, "--transcript", win_path, "--format", a.format,
                 "--top", a.top_per, "--out", out_stub])
            cand_file = out_stub.with_suffix(".tam.json")
            if not cand_file.exists():
                continue
            for c in json.loads(cand_file.read_text()).get("candidates", []):
                c["exchange_id"] = e["id"]
                c["exchange_title"] = e["title"]
                c["start_sec"] = mmss_to_sec(c.get("start"))
                c["end_sec"] = mmss_to_sec(c.get("end"))
                all_picks.append(c)
            if not src_segments:
                break  # plain-text path: one global tam_select pass is enough

    # 3. merge + global re-rank ----------------------------------------------------------------
    order = {"MINE": 0, "MAYBE": 1, "SKIP": 2}
    all_picks.sort(key=lambda c: (order.get(c.get("verdict"), 3), -(c.get("tam_score") or 0)))
    picks = all_picks[: a.top]
    for i, c in enumerate(picks, 1):
        c["rank"] = i

    pj = base.with_suffix(".picks.json")
    pm = base.with_suffix(".picks.md")
    pj.write_text(json.dumps({"format": a.format, "picks": picks}, indent=2))

    mine = sum(1 for c in picks if c.get("verdict") == "MINE")
    out = [f"# Combined TAM picks — {tp.name}", "",
           f"{len(picks)} picks ({mine} MINE) across {len(content)} exchanges", ""]
    for c in picks:
        out += [
            f"## [{c.get('verdict')}] {c.get('rank')}. {c.get('title')}  "
            f"({c.get('start')}–{c.get('end')}) · TAM {c.get('tam_score')}  ·  ex#{c.get('exchange_id')} {c.get('exchange_title')}",
            f"- hook: {c.get('hook')}",
            f"- issue: {c.get('issue')}",
            f"- solution: {c.get('solution')}",
            f"- tension: {c.get('tension')}",
            f"- why: {c.get('why')}",
            "",
        ]
    pm.write_text("\n".join(out))
    print(f"[pipe] {len(picks)} combined picks ({mine} MINE) → {pj}  +  {pm}")
    print(f"[pipe] segments → {seg_path}")


if __name__ == "__main__":
    main()
