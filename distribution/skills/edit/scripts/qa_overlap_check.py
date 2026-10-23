#!/usr/bin/env python3
"""qa_overlap_check — PRE-RENDER gate for a Q&A assembly EDL.

Flags any two segments that share source time (>0.10s). Overlapping source ranges REPLAY the same
words in the render via mic bleed (both mics carry every line), producing audible duplications
("what do you charge?" x2, "one time" x3) that the transcript-reconstruction check CANNOT catch
(concatenated text looks like an intentional Q+echo). Run this on the EDL before rendering a
dialogue-heavy cut; then still whisper the actual render to HEAR any remaining dups.

Usage: qa_overlap_check.py EDL.json
Exit 0 = clean; exit 1 = overlaps found.
"""
import json, sys

def main(path):
    d = json.load(open(path))
    s = d["segments"]
    ov = 0
    for i in range(len(s)):
        for j in range(i + 1, len(s)):
            lo = max(s[i]["mic_start"], s[j]["mic_start"])
            hi = min(s[i]["mic_end"], s[j]["mic_end"])
            if hi - lo > 0.10:
                print(f"  OVERLAP seg{i} & seg{j}: {hi-lo:.2f}s shared source -> will replay audio")
                ov += 1
    print(f"{ov} overlapping pair(s) — FIX before rendering" if ov else "OK: zero source overlaps")
    return 1 if ov else 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
