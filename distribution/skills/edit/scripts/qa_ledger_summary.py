#!/usr/bin/env python3
"""qa_ledger_summary.py — read the Q&A note ledger and show where we are on the road to one-shot:
coverage (% of note-categories with a prevention baked), the ENFORCEMENT gap (baked but not auto-run
pre-delivery = a human still has to catch it), and what to HARDEN next (open categories + recurring
partials). This is the dashboard for "use the notes as data."
Usage: qa_ledger_summary.py [path/to/qa_notes_ledger.json]
"""
import json, sys
from pathlib import Path

def main():
    p = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "references/qa_notes_ledger.json"
    cats = json.loads(p.read_text())["categories"]
    n = len(cats)
    baked = [c for c in cats if c["status"] == "baked"]
    partial = [c for c in cats if c["status"] == "partial"]
    open_ = [c for c in cats if c["status"] == "open"]
    enforced = [c for c in cats if c.get("enforced")]
    # baked/partial but NOT auto-run pre-delivery = the enforcement gap (notes that reach Maddex needlessly)
    enf_gap = [c for c in cats if c["status"] in ("baked", "partial") and not c.get("enforced")]
    total_recur = sum(c.get("recurrences", 1) for c in cats)

    print(f"=== Q&A NOTE LEDGER — {n} note-categories · {total_recur} total note-occurrences ===\n")
    print(f"COVERAGE:   baked {len(baked)}/{n} · partial {len(partial)} · open {len(open_)}")
    print(f"ENFORCED:   {len(enforced)}/{n} auto-run pre-delivery (caught before a human sees it)\n")

    print("🔴 OPEN — no prevention yet (each = a recurring round-trip until gated):")
    for c in open_ or [{"category": "(none)"}]:
        print(f"   • {c['category']}" + (f" — {c.get('gap','')}" if c.get('gap') else ""))

    print("\n🟠 ENFORCEMENT GAP — prevention EXISTS but isn't auto-run, so notes still leak to review:")
    for c in sorted(enf_gap, key=lambda x: -x.get("recurrences", 1)):
        print(f"   • {c['category']} (seen {c.get('recurrences',1)}x) — {c.get('prevention','?')}")
        if c.get("gap"): print(f"        gap: {c['gap']}")

    print("\n✅ BAKED + ENFORCED (these note-classes should NOT recur):")
    for c in sorted(baked, key=lambda x: -x.get("recurrences", 1)):
        if c.get("enforced"): print(f"   • {c['category']} (was seen {c.get('recurrences',1)}x)")

    # the headline number: of all note-occurrences, how many fall in categories we ALREADY prevent+enforce?
    covered_recur = sum(c.get("recurrences", 1) for c in cats if c["status"] == "baked" and c.get("enforced"))
    print(f"\n📊 {covered_recur}/{total_recur} note-occurrences are in categories we ALREADY prevent + auto-enforce.")
    print(f"   The rest are the work: {len(open_)} open + {len(enf_gap)} enforcement-gap categories.")
    print(f"   BIGGEST LEVER: run every existing gate in ONE pre-delivery gauntlet so the {len(enf_gap)} 'gap' "
          f"categories stop reaching review.")

if __name__ == "__main__":
    main()
