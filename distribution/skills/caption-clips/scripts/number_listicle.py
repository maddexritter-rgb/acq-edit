#!/usr/bin/env python3
"""Number the point-headings in a listicle clip's captions — LOCKED 2026-05-31.

When a clip is a listicle ("here are 4 things to do X", "3 signs she's into you",
"5 ways to..."), the caption that introduces each point gets a number prefix:
  "be direct"      → "1. be direct"
  "use her name"   → "2. use her name"
  "make the plan"  → "3. make the plan"
  "ask for a picture" → "4. ask for a picture"

This operates on the generated .ass (NOT the transcript) because the chunker
sometimes merges the previous sentence's tail word into the heading chunk
(e.g. "...like this. Be direct" → one chunk "this be direct"). When that
happens this script SPLITS the chunk so the number cleanly prefixes the heading.

Usage:
    python3 number_listicle.py <captions.ass> \
        --point "9.5:be:1." \
        --point "31.4:use:2." \
        --point "42.8:make:3." \
        --point "70.0:ask:4."

Each --point is "approx_start_sec:heading_first_word:number".
- approx_start_sec : where the heading is spoken (±1.5s tolerance)
- heading_first_word : first word of the point heading (lowercase, for matching)
- number : the prefix to prepend, e.g. "1." / "2." / "3." / "4."

The number is PREPENDED to the heading chunk's own words — never a full-text
replace (that would duplicate words when a point title spans two chunks, e.g.
"going ask for" + "a picture").

If the matched chunk contains leading words BEFORE heading_first_word (merged
prior-sentence tail), the chunk is split at the heading word: the prefix stays
as its own short caption, the numbered heading becomes a new caption.

Then re-burn the .ass onto the clip with burn_captions / batch_pro's ffmpeg step.
"""
from __future__ import annotations
import argparse, re, sys
from pathlib import Path


def t2s(ts: str) -> float:
    h, m, s = ts.split(':')
    return int(h) * 3600 + int(m) * 60 + float(s)


def s2t(s: float) -> str:
    h = int(s // 3600); m = int((s % 3600) // 60); sec = s - h * 3600 - m * 60
    return f"{h}:{m:02d}:{sec:05.2f}"


def lead_tags(text: str) -> str:
    """Return the leading {..}{..} override-tag groups (incl \\move, font)."""
    m = re.match(r'^((?:\{[^}]*\})+)(.*)$', text)
    return m.group(1) if m else ''


def strip_all_tags(text: str) -> str:
    return re.sub(r'\{[^}]*\}', '', text).strip().lower()


def word_count_before(vis_lower: str, heading_word: str) -> int:
    """How many words precede heading_word in the visible chunk text."""
    words = vis_lower.split()
    for i, w in enumerate(words):
        if w == heading_word:
            return i
    return -1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('ass', type=Path)
    ap.add_argument('--point', action='append', required=True,
                    help='"approx_start:heading_first_word:full_numbered_text"')
    ap.add_argument('--split-gap', type=float, default=0.30,
                    help='Seconds to give the split-off prefix word')
    ap.add_argument('--tolerance', type=float, default=1.5,
                    help='± seconds window to match a point by start time')
    args = ap.parse_args()

    points = []
    for p in args.point:
        approx, hword, num = p.split(':', 2)
        points.append({'approx': float(approx), 'hword': hword.lower().strip(),
                       'num': num.strip()})

    lines = args.ass.read_text().split('\n')
    out = []
    matched = 0
    for ln in lines:
        if not ln.startswith('Dialogue:'):
            out.append(ln); continue
        parts = ln.split(',', 9)
        start = t2s(parts[1])
        tags = lead_tags(parts[9])
        vis = strip_all_tags(parts[9])

        hit = None
        for pt in points:
            if abs(start - pt['approx']) <= args.tolerance and pt['hword'] in vis.split():
                hit = pt; break

        if not hit:
            out.append(ln); continue

        # PREPEND the number to the heading chunk's own words (never replace with
        # arbitrary text — that would duplicate words when the point title spans
        # two chunks, e.g. "going ask for" + "a picture").
        words = vis.split()
        n_before = word_count_before(vis, hit['hword'])
        if n_before <= 0:
            # Heading starts the chunk — simple prepend
            parts[9] = tags + f"{hit['num']} {vis}"
            out.append(','.join(parts))
            matched += 1
        else:
            # Merged prior-sentence tail — split it off, number the heading remainder
            prefix_words = ' '.join(words[:n_before])
            heading_words = ' '.join(words[n_before:])
            end = t2s(parts[2])
            split_t = max(start + 0.1, end - len(words[n_before:]) * 0.25)
            a = parts[:]; a[2] = s2t(split_t); a[9] = tags + prefix_words
            b = parts[:]; b[1] = s2t(split_t); b[9] = tags + f"{hit['num']} {heading_words}"
            out.append(','.join(a)); out.append(','.join(b))
            matched += 1
        points.remove(hit)

    args.ass.write_text('\n'.join(out))
    print(f'numbered {matched} point heading(s)')
    if points:
        print('UNMATCHED (check timing/word):')
        for pt in points:
            print(f"  ~{pt['approx']}s  {pt['hword']!r} → {pt['full']!r}")
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
