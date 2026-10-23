#!/usr/bin/env python3
"""Add sentence-ending punctuation back to a word-level transcript.

Whisper's word-level mode (-ml 1) strips punctuation. Without it, the chunker
can't detect sentence boundaries and ends up merging the last word of one
sentence with the first words of the next ("...beating people you win by..."),
which looks visually wrong.

This script uses whisper's regular (sentence-level) output AS the source of
truth for punctuation, then maps the periods/?/! back to the word-level entries
by sequential word matching. No API call required.

Usage:
    python3 punctuate_transcript.py \\
        --word-level transcript.json \\
        --sentence-level transcript_sentences.txt \\
        --out transcript_punct.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


WORD_RE = re.compile(r"([A-Za-z']+)([.!?]?)")


def tokenize_sentences(text: str) -> list[tuple[str, str]]:
    """Yield (word_lowercase, terminal_punct_or_empty) tuples from a sentence-punctuated text."""
    out = []
    for m in WORD_RE.finditer(text):
        word = m.group(1).lower().strip("'")
        punct = m.group(2)
        if word:
            out.append((word, punct))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--word-level", type=Path, required=True)
    ap.add_argument("--sentence-level", type=Path, required=True,
                    help="Plain-text whisper output (no --ml flag) — has natural punctuation")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    data = json.loads(args.word_level.read_text())
    words = data["words"]

    sent_text = args.sentence_level.read_text()
    sent_tokens = tokenize_sentences(sent_text)

    if not words or not sent_tokens:
        print("Empty input(s)", file=sys.stderr)
        return 1

    # Walk in parallel; advance sentence cursor each time we find a word match.
    # Robust to extra/missing words on either side: only advance sentence cursor
    # when the current word-level word matches the next sentence token.
    s = 0
    marked = 0
    for w in words:
        wclean = w["word"].lower().strip(" '.,?!\"")
        # Search forward in sentence tokens for a match (allow up to 5 ahead for resilience)
        for offset in range(min(5, len(sent_tokens) - s)):
            stok_word, stok_punct = sent_tokens[s + offset]
            if stok_word == wclean:
                # Match — advance to here, apply terminal punct if any
                s += offset + 1
                if stok_punct:
                    w["word"] = w["word"].rstrip(".,?!") + stok_punct
                    marked += 1
                    print(f"  marked '{w['word']}' as sentence-end")
                break
        # If no match found, leave word as-is and try again on next iteration

    args.out.write_text(json.dumps({"words": words}, indent=2))
    print(f"\nMarked {marked} sentence-end words. Wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
