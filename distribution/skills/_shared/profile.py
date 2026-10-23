#!/usr/bin/env python3
"""ACQ PIPELINE PROFILER — stage-level wall-time tracking (locked 2026-06-06).

Why this exists: without per-stage timings we're guessing where time goes. The north star
("Drive link -> finished clips in 10 minutes") is meaningless unless we can answer
"which step is slow?" Real numbers > intuition.

Enable globally:   export ACQ_PROFILE=1
Disable:           unset ACQ_PROFILE  (or leave unset — profiling is OFF by default)
Log location:      ~/.claude/profile_log.jsonl  (override via ACQ_PROFILE_LOG=<path>)

How to use in any skill:
    from profile import stage
    with stage("reframe", clip="clip01.mp4"):
        run_reframe(...)
    with stage("captions", clip="clip01.mp4", note="spice dual-color"):
        burn_captions(...)

Every entry is JSONL with: ts, pid, stage, duration_s, status, clip?, skill?, note?, **kwargs.

Encode jobs are AUTO-profiled — parallel.run_commands(kind="encode") wraps each ffmpeg call
in `stage("encode")` automatically when ACQ_PROFILE=1, so existing skills get free coverage.

Read the data:
    python3 __ACQ_SKILLS__/_shared/profile.py report          # human-readable summary
    python3 __ACQ_SKILLS__/_shared/profile.py report --json   # machine-readable
    python3 __ACQ_SKILLS__/_shared/profile.py report --since 1h
    python3 __ACQ_SKILLS__/_shared/profile.py clear           # wipe the log (with backup)
"""
import json
import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path

DEFAULT_LOG = Path.home() / ".config" / "acq-edit" / "profile.jsonl"
LOG_PATH = Path(os.environ.get("ACQ_PROFILE_LOG", str(DEFAULT_LOG)))


def _enabled() -> bool:
    return os.environ.get("ACQ_PROFILE") in ("1", "true", "TRUE", "yes", "on")


def _detect_skill() -> str:
    """Best-effort: figure out which skill is calling us, by walking up the call stack
    looking for a path under __ACQ_SKILLS__/<name>/ or __ACQ_SKILLS__/<name>/. Used for the optional `skill` field."""
    try:
        import inspect
        frame = inspect.currentframe()
        # Shared by both agents: a caller may live under either skills root.
        skills_roots = [str(Path.home() / r / "skills") + os.sep for r in (".agents", ".claude")]
        while frame:
            fname = frame.f_code.co_filename
            for skills_root in skills_roots:
                if skills_root in fname:
                    rest = fname.split(skills_root, 1)[1]
                    return rest.split(os.sep, 1)[0]
            frame = frame.f_back
    except Exception:
        pass
    return ""


def _write(entry: dict):
    """Append one JSON line. Best-effort — never raise into the user's pipeline."""
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_PATH, "a") as f:
            f.write(json.dumps(entry, default=str) + "\n")
    except Exception:
        pass


@contextmanager
def stage(name: str, **fields):
    """Time a section of work. If ACQ_PROFILE is off, this is a near-zero overhead no-op
    (no log writes, no skill detection). Always usable — never breaks the pipeline.

    Optional fields go straight into the JSONL entry: clip, in_path, out_path, note, etc.
    """
    if not _enabled():
        yield
        return

    t0 = time.monotonic()
    status = "ok"
    skill = fields.pop("skill", None) or _detect_skill()
    try:
        yield
    except BaseException as e:
        status = f"error:{type(e).__name__}"
        raise
    finally:
        dt = time.monotonic() - t0
        entry = {
            "ts": time.time(),
            "pid": os.getpid(),
            "stage": name,
            "duration_s": round(dt, 3),
            "status": status,
        }
        if skill:
            entry["skill"] = skill
        entry.update(fields)
        _write(entry)


# ----------------------------------------------------------------------------
# `report` CLI — quick aggregations over the JSONL log.
# ----------------------------------------------------------------------------
def _parse_since(s: str) -> float:
    """Parse '1h', '30m', '2d' into seconds-ago. Returns 0.0 (= no filter) on parse error."""
    if not s:
        return 0.0
    try:
        unit = s[-1].lower()
        n = float(s[:-1])
        mult = {"s": 1, "m": 60, "h": 3600, "d": 86400}.get(unit)
        return time.time() - n * mult if mult else 0.0
    except Exception:
        return 0.0


def _load(since_ts: float = 0.0):
    if not LOG_PATH.exists():
        return []
    rows = []
    with open(LOG_PATH) as f:
        for line in f:
            try:
                r = json.loads(line)
            except Exception:
                continue
            if since_ts and r.get("ts", 0) < since_ts:
                continue
            rows.append(r)
    return rows


def _summary(rows):
    """Group by stage (and skill if present): count, total_s, mean_s, p50, p95, fail%."""
    from statistics import median
    buckets = {}
    for r in rows:
        key = (r.get("skill", "?"), r.get("stage", "?"))
        b = buckets.setdefault(key, {"n": 0, "total": 0.0, "durs": [], "fails": 0})
        b["n"] += 1
        b["total"] += r.get("duration_s", 0)
        b["durs"].append(r.get("duration_s", 0))
        if not r.get("status", "ok").startswith("ok"):
            b["fails"] += 1
    out = []
    for (skill, stage_name), b in buckets.items():
        durs = sorted(b["durs"])
        out.append({
            "skill": skill, "stage": stage_name, "count": b["n"],
            "total_s": round(b["total"], 2),
            "mean_s": round(b["total"] / max(1, b["n"]), 3),
            "p50_s": round(median(durs), 3) if durs else 0.0,
            "p95_s": round(durs[int(len(durs) * 0.95)] if len(durs) > 1 else durs[0], 3) if durs else 0.0,
            "fail_pct": round(100.0 * b["fails"] / max(1, b["n"]), 1),
        })
    out.sort(key=lambda x: x["total_s"], reverse=True)
    return out


def main(argv=None):
    import argparse
    p = argparse.ArgumentParser(prog="profile")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("report", help="Aggregate stage timings")
    r.add_argument("--since", default="", help="Limit to last N (e.g. 1h, 30m, 2d).")
    r.add_argument("--json", action="store_true", help="Machine-readable output.")
    sub.add_parser("clear", help="Wipe the log (with .bak backup).")
    sub.add_parser("path", help="Print the log path.")
    a = p.parse_args(argv)

    if a.cmd == "path":
        print(LOG_PATH); return 0
    if a.cmd == "clear":
        if LOG_PATH.exists():
            bak = LOG_PATH.with_suffix(LOG_PATH.suffix + ".bak")
            LOG_PATH.rename(bak); print(f"backed up -> {bak}")
        else:
            print("(log was empty)")
        return 0
    # report
    rows = _load(_parse_since(a.since))
    summ = _summary(rows)
    if a.json:
        print(json.dumps({"total_rows": len(rows), "stages": summ}, indent=2)); return 0
    if not rows:
        print(f"no entries in {LOG_PATH}.  Set ACQ_PROFILE=1 in your pipeline shell.")
        return 0
    print(f"\n📊 ACQ profile report  ({len(rows)} entries from {LOG_PATH})\n")
    header = f"{'skill':<22} {'stage':<22} {'n':>4} {'total':>9} {'mean':>8} {'p50':>8} {'p95':>8} {'fail%':>6}"
    print(header); print("-" * len(header))
    for s in summ:
        print(f"{s['skill']:<22.22} {s['stage']:<22.22} {s['count']:>4} "
              f"{s['total_s']:>8.2f}s {s['mean_s']:>7.3f}s {s['p50_s']:>7.3f}s "
              f"{s['p95_s']:>7.3f}s {s['fail_pct']:>5}%")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
