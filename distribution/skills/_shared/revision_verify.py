#!/usr/bin/env python3
"""revision_verify.py — BLOCK a revision that didn't apply the notes or REGRESSED vs the prior cut.

WHY THIS EXISTS (ThreeFunctions V4, 2026-06-22): a revision shipped with 2 skipped notes, a garbled payoff,
a 'so I' false ending, and re-introduced filler — because the downstream session NEVER checked its own output
against the notes. A reviewer caught it, costing a full round-trip. This is the deterministic self-check a
revision MUST pass BEFORE delivery, so "did it actually do the notes?" is answered by a tool, not the next
human review. It needs no video — it diffs the new cut's transcript against the prior cut's + a notes spec.

Usage:
  revision_verify.py --prior PRIOR(.json w_norm | .txt) --new NEW(.json w_norm | .txt) --spec spec.json
spec.json:
  {
    "expect_gone":    ["phrases that MUST be absent in the new cut (the things the notes said to cut)"],
    "expect_present": ["phrases that MUST be present (e.g. a corrected wording / a tightened line)"],
    "end_on":         "the exact words the clip must END on — anything after = a leaked/false ending",
    "filler_guard":   true
  }
Exit 0 = PASS · 1 = at least one FAIL (BLOCK delivery, fix before shipping).
"""
import sys, json, re, argparse
from collections import Counter
from pathlib import Path

# Tics/stammers that should NEVER increase in a tightening revision -> increase = FAIL (a re-cut-from-source tell).
STAMMER_HARD = {"um", "uh", "uhh", "erm", "sorry", "mhm"}
TIC_HARD = {"right", "basically", "literally"}
# Softer fillers (noisier in ASR) -> increase = WARN, not block.
TIC_SOFT = {"like", "kinda", "sorta", "actually", "honestly"}

def norm_tokens(s):
    return re.sub(r"[^a-z0-9' ]", " ", s.lower()).split()

def load_text(path):
    p = Path(path)
    if p.suffix == ".json":
        d = json.loads(p.read_text())
        w = d.get("words", d) if isinstance(d, dict) else d
        return " ".join((x["word"] if isinstance(x, dict) else x) for x in w)
    return p.read_text()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prior", help="prior cut transcript (w_norm.json or .txt) — needed for filler-regression diff")
    ap.add_argument("--new", required=True, help="new cut transcript (w_norm.json or .txt)")
    ap.add_argument("--spec", required=True, help="notes spec JSON")
    a = ap.parse_args()
    spec = json.loads(Path(a.spec).read_text())
    new = " ".join(norm_tokens(load_text(a.new)))
    prior = " ".join(norm_tokens(load_text(a.prior))) if a.prior else ""

    fails, warns = [], []

    for ph in spec.get("expect_gone", []):
        if " ".join(norm_tokens(ph)) in new:
            fails.append(f"NOTE NOT APPLIED — '{ph}' is STILL in the cut (was supposed to be removed)")
    for ph in spec.get("expect_present", []):
        if " ".join(norm_tokens(ph)) not in new:
            fails.append(f"NOTE NOT APPLIED — '{ph}' is MISSING (was supposed to be present)")

    eo = spec.get("end_on")
    if eo:
        eo_n = " ".join(norm_tokens(eo))
        if eo_n not in new:
            fails.append(f"END phrase not found at all — clip must end on '{eo}'")
        elif not new.endswith(eo_n):
            trail = new[new.rfind(eo_n) + len(eo_n):].strip()
            fails.append(f"FALSE ENDING — clip must hard-end on '{eo}', but it leaks: '...{trail}' after it")

    if spec.get("filler_guard") and prior:
        pc, nc = Counter(prior.split()), Counter(new.split())
        for tok in sorted(STAMMER_HARD | TIC_HARD):
            if nc[tok] > pc[tok]:
                fails.append(f"FILLER REGRESSION — '{tok}' appears {nc[tok]}x in new vs {pc[tok]}x in prior "
                             f"(+{nc[tok]-pc[tok]}): a tightening revision must not ADD filler (re-cut-from-source tell)")
        for tok in sorted(TIC_SOFT):
            if nc[tok] > pc[tok]:
                warns.append(f"possible filler regression — '{tok}' {pc[tok]}->{nc[tok]} (verify by ear)")
    elif spec.get("filler_guard"):
        warns.append("filler_guard requested but no --prior given; skipped the regression diff")

    print("=== revision_verify ===")
    for f in fails: print(f"  ✗ {f}")
    for w in warns: print(f"  ⚠ {w}")
    if not fails and not warns: print("  ✓ all notes applied · clean ending · no filler regression")
    print(f"\n{'BLOCK — revision incomplete or regressed; fix before delivery' if fails else ('PASS (review warnings)' if warns else 'PASS')}")
    sys.exit(1 if fails else 0)

if __name__ == "__main__":
    main()
