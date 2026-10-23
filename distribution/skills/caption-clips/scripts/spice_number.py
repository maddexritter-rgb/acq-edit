#!/usr/bin/env python3
"""Listicle numbering / category tabs for SPICE captions. Two modes:

  --above  (PREFERRED, Maddex SOP 2026-06-04): the number sits on its OWN LINE ABOVE the caption
           line and PERSISTS for the whole tactic — "#1" holds through every caption of tactic 1,
           then "#2" pops up and holds through tactic 2, etc. One persistent cue per item spanning
           [item_start, next_item_start] (last → --clip-end). The caption layer is untouched.
           OPTIONAL category tab: a point of "start:#N:CATEGORY" adds a white pill (black bold-italic
           category, e.g. OFFER / PRICING / FOCUS) ABOVE the number — the viral "tab" look (2026-06-05).

  (inline, legacy) prepend "#N " into each item's heading cue, SPICE-aware (preserves the per-word
           \\fn/\\1c/\\fax/\\fscx tags — unlike number_listicle.py which flattens the cue).

Numbers are white (color = voice; never yellow), Black weight, with the spice stroke/shadow.

ABOVE :  spice_number.py <ass> --above --clip-end 56.15 \
             --point "12.60:#1:OFFER" --point "17.24:#2:MARKETING" ... [--num-y 1070] [--tab-y 975]
INLINE:  spice_number.py <ass> --point "12.60:have:#1" --point "17.24:no:#2" ...
"""
import argparse, re
from pathlib import Path


def t2s(ts):
    h, m, s = ts.split(':'); return int(h) * 3600 + int(m) * 60 + float(s)


def s2t(x):
    x = max(0.0, x); h = int(x // 3600); x -= h * 3600; m = int(x // 60); x -= m * 60
    s = int(x); cs = int(round((x - s) * 100))
    if cs == 100: s += 1; cs = 0
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def strip_tags(t):
    return re.sub(r'\{[^}]*\}', '', t).strip().lower()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('ass', type=Path)
    ap.add_argument('--point', action='append', required=True)
    ap.add_argument('--above', action='store_true', help='persistent number on its own line above captions')
    ap.add_argument('--clip-end', type=float, default=None, help='(--above) clip duration, for the last number span')
    ap.add_argument('--num-y', type=int, default=1070, help='(--above) Y of the number line; default sits just above the y=60%% caption line')
    ap.add_argument('--num-size', type=int, default=85)
    ap.add_argument('--num-weight', default='Proxima Nova Black')
    ap.add_argument('--num-color', default='FFFFFF')
    ap.add_argument('--tab-y', type=int, default=None, help='(--above) Y of the category pill; default = num_y - 95')
    ap.add_argument('--tab-size', type=int, default=66)
    ap.add_argument('--tab-weight', default='Proxima Nova Black Italic')
    ap.add_argument('--tolerance', type=float, default=1.5, help='(inline) start-time match window')
    ap.add_argument('--out', type=Path, default=None)
    a = ap.parse_args()

    hx = a.num_color.lstrip('#')
    col = f"&H00{hx[4:6]}{hx[2:4]}{hx[0:2]}&".upper()
    lines = a.ass.read_text().split('\n')

    # ---------- ABOVE / PERSISTENT mode ----------
    if a.above:
        if a.clip_end is None:
            raise SystemExit("--above needs --clip-end")
        pts = []
        for p in a.point:
            bits = p.split(':')
            st = float(bits[0]); lbl = bits[1].strip()
            cat = bits[2].strip().upper() if len(bits) > 2 and bits[2].strip() else None
            pts.append((st, lbl, cat))
        pts.sort(key=lambda x: x[0])
        spans = [(st, (pts[i + 1][0] if i + 1 < len(pts) else a.clip_end), lbl, cat)
                 for i, (st, lbl, cat) in enumerate(pts)]
        tab_y = a.tab_y if a.tab_y is not None else a.num_y - 95
        num_style = (f"Style: SpiceNum,{a.num_weight},{a.num_size},&H00FFFFFF,&H00FFFFFF,"
                     f"&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,7,0,5,40,40,0,1")
        # category pill: black bold-italic text on an opaque WHITE box (BorderStyle 3)
        tab_style = (f"Style: SpiceTab,{a.tab_weight},{a.tab_size},&H00000000,&H00000000,"
                     f"&H00FFFFFF,&H00FFFFFF,0,0,0,0,100,100,0,0,3,14,0,5,40,40,0,1")
        Y = a.num_y
        cues = []
        for st, en, lbl, cat in spans:
            ntag = (f"{{\\an5\\move(540,{Y - 8},540,{Y},0,200)\\fad(100,0)"
                    f"\\shad8\\blur9\\4c&H000000&\\4a&H00&\\3c&H000000&\\1c{col}}}")
            cues.append(f"Dialogue: 1,{s2t(st)},{s2t(en)},SpiceNum,,0,0,0,,{ntag}{lbl}")
            if cat:
                ttag = f"{{\\an5\\pos(540,{tab_y})\\fad(120,0)}}"
                cues.append(f"Dialogue: 1,{s2t(st)},{s2t(en)},SpiceTab,,0,0,0,,{ttag}{cat}")
        out = []
        for ln in lines:
            out.append(ln)
            if ln.startswith('Style: Spice') and not ln.startswith('Style: SpiceNum') and not ln.startswith('Style: SpiceTab'):
                out.append(num_style)
                out.append(tab_style)
            if ln.startswith('Format: Layer, Start'):
                out.extend(cues)
        (a.out or a.ass).write_text('\n'.join(out))
        n_tabs = sum(1 for s in spans if s[3])
        print(f"above-mode: {len(spans)} numbers @ y={Y}" + (f", {n_tabs} category tabs @ y={tab_y}" if n_tabs else ""))
        for st, en, lbl, cat in spans:
            print(f"  {lbl:>4} {('['+cat+']') if cat else '':<12} {st:6.2f} -> {en:6.2f}")
        return

    # ---------- INLINE mode (legacy) ----------
    points = []
    for p in a.point:
        approx, hw, lbl = p.split(':', 2)
        points.append({'approx': float(approx), 'hw': hw.lower().strip(), 'lbl': lbl.strip()})
    out = []
    matched = 0
    for ln in lines:
        if not ln.startswith('Dialogue:'):
            out.append(ln); continue
        parts = ln.split(',', 9)
        start = t2s(parts[1])
        vis = strip_tags(parts[9]).split()
        first = vis[0] if vis else ''
        hit = next((pt for pt in points if abs(start - pt['approx']) <= a.tolerance and first == pt['hw']), None)
        if not hit:
            out.append(ln); continue
        m = re.match(r'^(\{[^}]*\})(.*)$', parts[9])
        numtok = f"{{\\fn{a.num_weight}\\b0\\i0\\fax0\\1c{col}}}{hit['lbl']} "
        parts[9] = (m.group(1) + numtok + m.group(2)) if m else (numtok + parts[9])
        out.append(','.join(parts)); matched += 1; points.remove(hit)
    (a.out or a.ass).write_text('\n'.join(out))
    print(f"inline-mode: numbered {matched} heading(s)" + (f"; UNMATCHED {[p['hw'] for p in points]}" if points else ""))


if __name__ == '__main__':
    main()
