#!/usr/bin/env python3
"""caption_qc.py — STRUCTURAL gate proving a caption render is the LOCKED spice version.

THE BUG THIS CATCHES
--------------------
Multiple pipelines burn captions. The locked, approved one is `generate_spice.py --burn` with a
spice preset: it composites the TWO-LAYER gblur Premiere drop shadow, is resolution-adaptive, and
applies per-word color. A SECOND path (render/stages/captions.py, pre-fix) did a plain ffmpeg
`subtitles=` burn of a static .ass — no gblur, wrong/placeholder style — which shipped the
"horrendous" captions in /edit. This gate makes that impossible: it asserts the structural
fingerprints that are TRUE iff the render came from generate_spice --burn with a spice preset,
and FALSE for a plain subtitles= burn. Callers run it after burning and ABORT (non-zero) on failure.

Checks (all deterministic, no API):
  1. PRESET-IS-SPICE: the preset JSON has a premiere/gblur shadow block (sigma/border/intensity).
     pro.json / pro_locked.json / alex_canon.json lack it -> FAIL (a flat-pro preset can't be used).
  2. GBLUR-SIDECARS: generate_spice --burn writes <ass>_text.ass / _shadow.ass / _shadow2.ass next
     to the output .ass (the two-layer composite inputs). A plain subtitles= burn writes none -> FAIL.

CLI:  caption_qc.py <captions.ass> --preset <spice*.json>   (exit 0 = spice render; 3 = WRONG version)
Bypass (emergency only): ACQ_CAPTION_GATE=0
"""
from __future__ import annotations
import argparse, json, os, sys
from pathlib import Path


def evaluate(ass_path, preset_path):
    """Return (ok: bool, reasons: list[str]). ok=False => NOT the locked spice render; abort."""
    reasons = []
    ass = Path(ass_path)
    preset = Path(preset_path) if preset_path else None

    # 1) preset must carry the premiere/gblur shadow block (the spice fingerprint)
    spice_preset = False
    if preset and preset.exists():
        try:
            # resolve `extends` so THINNED variants (2026-08-03) still expose the
            # inherited shadow block — otherwise every variant fails this gate
            import sys as _s
            _s.path.insert(0, str(Path(__file__).resolve().parent))
            from generate_spice import load_preset as _lp
            P = _lp(preset)
            sh = P.get("shadow", {})
            spice_preset = (sh.get("mode") == "premiere"
                            and any(k in sh for k in ("premiere_sigma", "premiere_border", "premiere_intensity")))
        except Exception as e:
            reasons.append(f"preset unreadable ({e})")
    if not spice_preset:
        reasons.append(f"preset '{preset.name if preset else None}' is NOT a spice/premiere-gblur preset "
                       f"(pro/pro_locked/alex_canon lack the gblur shadow block) — flat captions would ship")

    # 2) the two-layer gblur composite writes these sidecars; a plain subtitles= burn writes none
    stem = ass.with_suffix("")
    sidecars = {s: (Path(f"{stem}_{s}.ass").exists()) for s in ("text", "shadow", "shadow2")}
    missing = [s for s, ok in sidecars.items() if not ok]
    if missing:
        reasons.append(f"gblur sidecar .ass missing {missing} next to {ass.name} — the two-layer shadow "
                       f"composite did not run (a plain subtitles= burn, i.e. the WRONG caption path)")

    return (len(reasons) == 0), reasons


def check_or_die(ass_path, preset_path, label="caption_qc"):
    """Convenience for callers: raise SystemExit(3) with a clear message if not the spice render."""
    if os.environ.get("ACQ_CAPTION_GATE", "1") == "0":
        print(f"  {label}: gate DISABLED (ACQ_CAPTION_GATE=0)", flush=True)
        return
    ok, reasons = evaluate(ass_path, preset_path)
    if ok:
        print(f"  {label}: OK — locked spice render (gblur shadow + spice preset)", flush=True)
        return
    msg = ("✗ CAPTION QC FAILED — output is NOT the locked spice version (the 'horrendous' wrong path):\n  - "
           + "\n  - ".join(reasons)
           + "\n  => refusing to ship. Captions MUST be burned via generate_spice.py --burn with a spice "
             "preset. (ACQ_CAPTION_GATE=0 bypasses in an emergency.)")
    print(msg, file=sys.stderr)
    raise SystemExit(3)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ass")
    ap.add_argument("--preset", required=True)
    a = ap.parse_args()
    ok, reasons = evaluate(a.ass, a.preset)
    if ok:
        print(f"caption_qc: OK (spice render) — {a.ass}")
        sys.exit(0)
    print("caption_qc: FAIL — " + "; ".join(reasons))
    sys.exit(3)


if __name__ == "__main__":
    main()
