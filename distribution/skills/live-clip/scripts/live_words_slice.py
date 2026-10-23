#!/usr/bin/env python3
"""/live-clip words slicer — cut a per-segment word JSON out of the rolling
transcript, rebased to an extracted segment's media timebase, in the exact
format highlight_cut.py / qc tools expect ({"words":[{word,start,end}]}).

  python3 live_words_slice.py --work <dir> --t0 843.2 --t1 1290.5 \
      --media-start 720.0 --out SEG03_words.json [--text-out SEG03.txt]

--text-out also writes the plain text (for the banned-guest gate and the run
ledger). Prints the word-count and the first/last words as a sanity line.
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True)
    ap.add_argument("--t0", type=float, required=True)
    ap.add_argument("--t1", type=float, required=True)
    ap.add_argument("--media-start", type=float, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--text-out")
    a = ap.parse_args()

    rolling = json.loads((Path(a.work).expanduser() / "rolling_words.json").read_text())
    sel = [w for w in rolling if w["s"] >= a.t0 - 0.05 and w["e"] <= a.t1 + 0.05]
    if not sel:
        sys.exit(f"no words in [{a.t0}, {a.t1}]")
    words = [{"word": w["w"],
              "start": round(w["s"] - a.media_start, 3),
              "end": round(w["e"] - a.media_start, 3)} for w in sel]
    Path(a.out).write_text(json.dumps({"words": words}, indent=None))
    if a.text_out:
        Path(a.text_out).write_text(" ".join(w["word"] for w in words) + "\n")
    print(f"{len(words)} words | '{words[0]['word']}' ({words[0]['start']:.2f}s) "
          f"→ '{words[-1]['word']}' ({words[-1]['end']:.2f}s in media time)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
