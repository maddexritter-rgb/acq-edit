#!/usr/bin/env python3
"""revision_spec_from_notes.py — turn a structured revision NOTES file into a revision_verify SPEC, so the
self-check spec is AUTO-GENERATED from the cut list (never hand-forgotten or out-of-sync with the prompt).

Standard revision flow (the loop-closer that stops 18 round-trips):
  author notes.json (the cuts, derived from the client's review)  →  this script  →  spec.json
  →  revision_verify.py --prior <prior w_norm> --new <new w_norm> --spec spec.json  →  BLOCKS until every note applied.

notes.json:
  {
    "cuts": [
       {"remove": "phrase the note says to CUT"},                  // -> expect_gone (must be ABSENT after)
       {"remove": "members or", "expect": "the 3 core roles"},     // remove -> expect_gone; expect -> expect_present
       {"expect": "corrected wording that must APPEAR"}            // expect-only (a wording fix / restored line)
    ],
    "end_on": "the words the clip must END on (anything after = false ending)",
    "filler_guard": true
  }
->  spec.json: {expect_gone:[...], expect_present:[...], end_on, filler_guard}
Usage: revision_spec_from_notes.py --notes notes.json [--out spec.json]   (prints to stdout if no --out)
"""
import json, argparse
from pathlib import Path

def build(notes: dict) -> dict:
    cuts = notes.get("cuts", [])
    spec = {
        "expect_gone": [c["remove"] for c in cuts if c.get("remove")],
        "expect_present": [c["expect"] for c in cuts if c.get("expect")],
    }
    if notes.get("end_on"):
        spec["end_on"] = notes["end_on"]
    spec["filler_guard"] = bool(notes.get("filler_guard", True))
    return spec

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--notes", required=True)
    ap.add_argument("--out")
    a = ap.parse_args()
    spec = build(json.loads(Path(a.notes).read_text()))
    out = json.dumps(spec, indent=2)
    if a.out:
        Path(a.out).write_text(out)
        print(f"wrote {a.out}: {len(spec['expect_gone'])} expect_gone · {len(spec['expect_present'])} expect_present · "
              f"end_on={'set' if spec.get('end_on') else 'none'} · filler_guard={spec['filler_guard']}")
    else:
        print(out)

if __name__ == "__main__":
    main()
