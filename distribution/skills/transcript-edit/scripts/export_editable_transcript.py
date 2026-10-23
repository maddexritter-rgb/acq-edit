#!/usr/bin/env python3
"""Export a clip's transcript in two human-editable formats:

  <name>_transcript.txt          prose format, easy to scan
  <name>_transcript_edit.txt     [timestamp] word per line, for precision

User edits either file (deletes words/lines). Round-trip via
apply_transcript_edit.py — aligns edits back to original word list and
renders a new clip with only the kept segments.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def build_prose(words: list[dict]) -> str:
    """Join words into paragraphs on . ! ? boundaries. Each sentence on new line."""
    out = []
    sent = []
    for w in words:
        sent.append(w["word"])
        if w["word"].rstrip().endswith((".", "!", "?")):
            out.append(" ".join(sent).strip())
            sent = []
    if sent:
        out.append(" ".join(sent).strip())
    return "\n\n".join(out)


def build_per_line(words: list[dict]) -> str:
    """One word per line: [start]  word"""
    lines = []
    lines.append("# Transcript for precision editing")
    lines.append("# Delete lines for words you want cut.")
    lines.append("# Keep the format: [start]  word")
    lines.append("")
    for w in words:
        lines.append(f"[{w['start']:7.3f}]  {w['word']}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--transcript", type=Path, required=True,
                    help="Word-level transcript JSON from transcribe_groq.py")
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--name", required=True, help="Base name for output files")
    args = ap.parse_args()

    tr = json.loads(args.transcript.read_text())
    words = tr.get("words", [])
    if not words:
        raise SystemExit("transcript has no words")

    args.out_dir.mkdir(parents=True, exist_ok=True)

    prose = build_prose(words)
    per_line = build_per_line(words)

    # Prose with intro header
    prose_text = (
        f"# {args.name} — clip transcript (prose)\n"
        f"# Edit this file: delete words/sentences you want cut.\n"
        f"# Keep everything else as-is. Re-run apply_transcript_edit.py.\n"
        f"#\n"
        f"# Total: {len(words)} words · {words[-1]['end']:.1f}s\n\n"
        + prose + "\n"
    )
    (args.out_dir / f"{args.name}_transcript.txt").write_text(prose_text)
    (args.out_dir / f"{args.name}_transcript_edit.txt").write_text(per_line)

    # Also copy the raw JSON alongside so apply_transcript_edit.py can read it
    import shutil
    shutil.copy2(args.transcript, args.out_dir / f"{args.name}_transcript_ORIGINAL.json")

    print(f"Wrote:")
    print(f"  {args.out_dir / f'{args.name}_transcript.txt'}")
    print(f"  {args.out_dir / f'{args.name}_transcript_edit.txt'}")
    print(f"  {args.out_dir / f'{args.name}_transcript_ORIGINAL.json'}")


if __name__ == "__main__":
    main()
