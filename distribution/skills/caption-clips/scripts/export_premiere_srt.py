#!/usr/bin/env python3
"""Export a review SRT from a verified native manifest or legacy spice ASS.

Native workflow (preferred for editable-graphics jobs):
    --manifest cards.json --receipt native.receipt.json --cuts cuts.json --out review.srt
    Checks exact native text/ticks and provided camera boundaries. Plain-text
    review/accessibility only; does not reproduce native graphics or spell-check.

Single-speaker output (default):
    One .srt with bold/italic/color markup per word.

Legacy split-speaker output (--split, explicit compatibility use only):
    Two files — <stem>_host.srt and <stem>_guest.srt — one per speaker.
    Separate subtitle files do not establish simultaneous Premiere visibility or
    styling fidelity. Use native graphics for editable styled captions.

Usage:
    python3 export_premiere_srt.py <subs_text.ass> [--out captions.srt] [--split]
"""
from __future__ import annotations
import argparse, re, sys, json, hashlib
from fractions import Fraction
from pathlib import Path


def ass_time_to_srt(t: str) -> str:
    """'H:MM:SS.cc' → 'HH:MM:SS,mmm'"""
    h, m, rest = t.split(":")
    s, cs = rest.split(".")
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int(cs) * 10:03d}"


def parse_color(color_str: str) -> str:
    """ASS &HAABBGGRR& hex → RRGGBB string."""
    c = color_str.upper()
    if len(c) == 8:   # AABBGGRR
        return c[6:8] + c[4:6] + c[2:4]
    if len(c) == 6:   # BBGGRR
        return c[4:6] + c[2:4] + c[0:2]
    return "FFFFFF"


def parse_word_tokens(text: str) -> list[tuple[str, bool, bool, str]]:
    """Parse ASS inline text → (word, is_bold, is_italic, rrggbb) tuples."""
    tokens = []
    for m in re.finditer(r"\{([^}]*)\}([^{]*)", text):
        tags, word_text = m.group(1), m.group(2).strip()
        if not word_text:
            continue
        fn_m   = re.search(r"\\fn([^\\}]+)", tags)
        font   = fn_m.group(1) if fn_m else "Proxima Nova Medium"
        fax_m  = re.search(r"\\fax(-?[\d.]+)", tags)
        fax    = float(fax_m.group(1)) if fax_m else 0.0
        col_m  = re.search(r"\\1c&H([0-9A-Fa-f]{6,8})&", tags)
        rrggbb = parse_color(col_m.group(1)) if col_m else "FFFFFF"
        tokens.append((word_text, any(w in font for w in ("Bold", "Extrabold", "Black")),
                       abs(fax) > 0.05, rrggbb))
    return tokens


def format_token(word: str, is_bold: bool, is_italic: bool, rrggbb: str,
                 strip_color: bool = False) -> str:
    text = word
    if is_bold:
        text = f"<b>{text}</b>"
    if is_italic:
        text = f"<i>{text}</i>"
    if not strip_color and rrggbb.upper() != "FFFFFF":
        text = f'<font color="#{rrggbb.upper()}">{text}</font>'
    return text


def cue_is_guest(tokens: list[tuple]) -> bool:
    """True if the majority of words in this cue are guest-colored (non-white)."""
    colored = sum(1 for _, _, _, rgb in tokens if rgb.upper() != "FFFFFF")
    return colored > len(tokens) / 2


def load_cues(ass_path: Path) -> list[tuple[str, str, list]]:
    cues = []
    for line in ass_path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.startswith("Dialogue:"):
            continue
        parts = line.split(",", 9)
        if len(parts) < 10:
            continue
        raw = re.sub(r"^\{[^}]*\}", "", parts[9])
        tokens = parse_word_tokens(raw)
        if tokens:
            cues.append((parts[1], parts[2], tokens))
    return cues


def write_srt(cues: list[tuple], out: Path, strip_color: bool = False) -> int:
    blocks = []
    for i, (st, en, tokens) in enumerate(cues, 1):
        text = " ".join(format_token(*t, strip_color=strip_color) for t in tokens)
        blocks.append(f"{i}\n{ass_time_to_srt(st)} --> {ass_time_to_srt(en)}\n{text}")
    out.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")
    return len(blocks)


TICKS = 254016000000


def srt_display_text(text):
    """Convert native explicit line separators only; never rewrap or normalize words."""
    if not isinstance(text, str):
        raise ValueError('Unsupported SRT text')
    normalized = text.replace('\r\n', '\n').replace('\r', '\n')
    if any(not line.strip() for line in normalized.split('\n')):
        raise ValueError('Empty lines are ambiguous SRT cue boundaries')
    return normalized


def timestamp(ms):
    hours, rem = divmod(ms, 3600000)
    minutes, rem = divmod(rem, 60000)
    seconds, milliseconds = divmod(rem, 1000)
    return f'{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}'


def encode_native_srt(manifest, receipt, cuts):
    rate = manifest['frame_rate']
    frame_seconds = Fraction(rate['denominator'], rate['numerator'])
    segments = manifest['render_segments']
    if len(segments) != len(receipt['cards']): raise ValueError('Native card count mismatch')
    blocks = []; previous_end = 0
    for index, (segment, native) in enumerate(zip(segments, receipt['cards']), 1):
        start, end = segment['start_frame'], segment['end_frame']
        if type(start) is not int or type(end) is not int or start < previous_end or end <= start:
            raise ValueError('Invalid/overlapping frame interval')
        if any(start < cut < end for cut in cuts): raise ValueError('Caption crosses camera cut')
        text = segment['text']
        # The builder writes a manifest '\n' into the native payload as '\r'
        # (Premiere's paragraph break) -- see premiere_native_cards.word_requests
        # and verify_style_readback.expected_run_texts. An exact comparison therefore
        # rejected EVERY two-line card as drift. Accept that one mapping and nothing
        # else: a manifest '\r' against a native '\n' is still a real mismatch.
        if text != native['text'] and text.replace('\n', '\r') != native['text']:
            raise ValueError('Native text mismatch')
        text = srt_display_text(text)
        for name, frame in [('start_ticks', start), ('end_ticks', end)]:
            if Fraction(int(native['timing'][name])) != frame * frame_seconds * TICKS:
                raise ValueError('Native timing mismatch')
        # The same floor mapping for starts/ends preserves adjacent cut boundaries.
        a, b = int(start * frame_seconds * 1000), int(end * frame_seconds * 1000)
        if b <= a: raise ValueError('Interval lost to SRT millisecond quantization')
        blocks.append(f'{index}\n{timestamp(a)} --> {timestamp(b)}\n{text}\n')
        previous_end = end
    return '\n'.join(blocks)


def write_native_sidecar(manifest_path, receipt_path, cuts_path, output):
    paths = [Path(p) for p in (manifest_path, receipt_path, cuts_path)]
    output = Path(output)
    evidence = output.with_suffix('.srt.receipt.json')
    if output.exists() or evidence.exists():
        raise FileExistsError('Preserve existing sidecar and receipt')
    manifest, receipt, cut_data = [json.loads(p.read_text()) for p in paths]
    cuts = [b['reference_frame'] for b in cut_data['hard_boundaries']
            if b['kind'] == 'camera_cut']
    if any(type(c) is not int or c < 0 for c in cuts):
        raise ValueError('Camera cut frames must be nonnegative integers')
    text = encode_native_srt(manifest, receipt, cuts)
    with output.open('x') as stream:
        stream.write(text)
    report = dict(status='NATIVE_SIDECAR_MATCH_NOT_SPELLCHECK_APPROVAL',
        cues=len(manifest['render_segments']), supplied_camera_boundaries=len(cuts),
        input_hashes={str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        srt_sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
        limitations=['Plain SRT does not preserve native typography or animation.',
                     'Provided cuts are checked; undetected cuts are not certified.',
                     'Native receipt equality is not fresh Premiere readback.',
                     'Accuracy and spelling still require source review.'])
    with evidence.open('x') as stream:
        json.dump(report, stream, indent=2)
    return report

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ass", nargs="?", help="Legacy subs_text.ass input")
    ap.add_argument("--manifest", type=Path, help="Resolved native caption manifest")
    ap.add_argument("--receipt", type=Path, help="Matching native build receipt")
    ap.add_argument("--cuts", type=Path, help="Reviewed hard_boundaries JSON; may explicitly contain no cuts")
    ap.add_argument("--out", help="output path (single-speaker mode)")
    ap.add_argument("--split", action="store_true",
                    help="Split into _host.srt + _guest.srt (Q&A / hotline)")
    a = ap.parse_args()

    if a.manifest:
        if a.ass or a.split or not all((a.receipt, a.cuts, a.out)):
            ap.error('Native mode requires --manifest --receipt --cuts --out; no ASS or --split')
        print(json.dumps(write_native_sidecar(a.manifest, a.receipt, a.cuts, a.out), indent=2))
        return 0
    if not a.ass or a.receipt or a.cuts:
        ap.error('Provide an ASS input, or the complete native manifest option set')

    ass_path = Path(a.ass).expanduser()
    if not ass_path.exists():
        sys.exit(f"ERROR: not found: {ass_path}")

    cues = load_cues(ass_path)
    if not cues:
        sys.exit(f"ERROR: no caption cues in {ass_path.name}")

    has_guest = any(cue_is_guest(toks) for _, _, toks in cues)

    if a.split and has_guest:
        stem = ass_path.with_suffix("")
        host_path  = Path(str(stem) + "_host.srt")
        guest_path = Path(str(stem) + "_guest.srt")
        host_cues  = [(st, en, t) for st, en, t in cues if not cue_is_guest(t)]
        guest_cues = [(st, en, t) for st, en, t in cues if     cue_is_guest(t)]
        n_host  = write_srt(host_cues,  host_path,  strip_color=True)
        n_guest = write_srt(guest_cues, guest_path, strip_color=True)
        print(f"export_premiere_srt: {n_host} host cues → {host_path.name}")
        print(f"export_premiere_srt: {n_guest} guest cues → {guest_path.name}")
    else:
        out = Path(a.out).expanduser() if a.out else ass_path.with_suffix(".srt")
        n = write_srt(cues, out)
        print(f"export_premiere_srt: {n} cues → {out.name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
