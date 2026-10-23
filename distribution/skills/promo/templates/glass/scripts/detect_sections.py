#!/usr/bin/env python3
"""Map an assembly cut's chapters from its BLACK separators (promo MODE B helper).

The film's source cut separates chapters with long black gaps. This runs ffmpeg
blackdetect, treats every black >= MIN_SEP as a chapter separator, and prints the
CONTENT spans between them — ready to paste into assemble.py SECTIONS.

  python3 detect_sections.py /path/to/AssemblyCut.mp4 [min_sep_seconds=0.4]

Notes it prints:
  - Leading black (film starts after it).
  - SHORT blacks inside a span (< min_sep) are kept INSIDE that span — these are
    usually intentional in-chapter beats (e.g. a "snap to black" transition). Do
    NOT split on them.
  - Each content span as (start, end). Nudge ~+0.13 / -0.10 when pasting so you
    sit just inside the content (no black bleed). VERIFY by sampling a frame from
    each span, and CONFIRM the chapter's year with the user (dates are factual).
"""
import subprocess, sys, re

if len(sys.argv) < 2:
    print("usage: detect_sections.py <cut.mp4> [min_sep_seconds]"); sys.exit(1)
src = sys.argv[1]
min_sep = float(sys.argv[2]) if len(sys.argv) > 2 else 0.4

dur = float(subprocess.check_output(
    ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", src]).strip())
out = subprocess.run(
    ["ffmpeg", "-nostdin", "-hide_banner", "-i", src, "-vf", f"blackdetect=d={min_sep}:pix_th=0.10",
     "-an", "-f", "null", "-"], capture_output=True, text=True).stderr
blacks = [(float(m[0]), float(m[1])) for m in
          re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", out)]

print(f"\nsource: {src}\nduration: {dur:.2f}s   black separators (>= {min_sep}s): {len(blacks)}\n")
# content spans = gaps between consecutive separators (and head/tail)
cursor = 0.0
spans = []
for bs, be in blacks:
    if bs - cursor > 0.5:                      # a real content span before this black
        spans.append((cursor, bs))
    cursor = be
if dur - cursor > 0.5:
    spans.append((cursor, dur))

print("CONTENT SPANS (paste into assemble.py SECTIONS, then nudge +0.13 / -0.10):")
for i, (a, b) in enumerate(spans, 1):
    print(f"  S{i}:  ({a + 0.13:7.2f}, {b - 0.10:7.2f}, MUS / \"(1) Calm/<track>.mp3\", 0.17, {'True' if i == len(spans) else 'False'}),   # {b - a:.1f}s")
print(f"\n  ({len(spans)} chapters detected — sample a frame from each + confirm titles/years with the user.)")
