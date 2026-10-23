#!/usr/bin/env python3
"""Convert generated ASS captions into the shared caption-card manifest."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

SCHEMA = "spice.caption-cards/v1"
TAG = re.compile(r"\{([^}]*)\}([^{}]*)")


def ass_seconds(value: str) -> float:
    h, m, rest = value.split(":")
    s, cs = rest.split(".")
    return int(h) * 3600 + int(m) * 60 + int(s) + int(cs) / 100


def color_rrggbb(tags: str) -> str:
    m = re.search(r"\\1c&H([0-9A-Fa-f]{6,8})&", tags)
    if not m:
        return "FFFFFF"
    raw = m.group(1)[-6:].upper()
    return raw[4:6] + raw[2:4] + raw[0:2]


def word_style(tags: str, text: str) -> dict:
    font = re.search(r"\\fn([^\\}]+)", tags)
    family = font.group(1) if font else "Proxima Nova Medium"
    scale = re.search(r"\\fscx(-?[\d.]+)", tags)
    fax = re.search(r"\\fax(-?[\d.]+)", tags)
    if "Black" in family:
        weight = "peak"
    elif "Extrabold" in family:
        weight = "strong"
    elif "Bold" in family:
        weight = "bold"
    else:
        weight = "base"
    return {
        "text": text.strip(),
        "color": color_rrggbb(tags),
        "weight": weight,
        "font": family,
        "scale": int(round(float(scale.group(1)))) if scale else 100,
        "italic": bool(fax and abs(float(fax.group(1))) > 0.05),
    }


def parse_ass(path: Path) -> dict:
    cards = []
    play_x = play_y = None
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("PlayResX:"):
            play_x = int(line.split(":", 1)[1])
        elif line.startswith("PlayResY:"):
            play_y = int(line.split(":", 1)[1])
        elif line.startswith("Dialogue:"):
            fields = line.split(",", 9)
            if len(fields) < 10 or fields[0] != "Dialogue: 1":
                continue
            start, end, payload = ass_seconds(fields[1]), ass_seconds(fields[2]), fields[9]
            words = []
            for tags, text in TAG.findall(payload):
                clean = text.replace(r"\N", " ").strip()
                if clean:
                    words.append(word_style(tags, clean))
            if not words:
                continue
            pos = re.search(r"\\pos\([^,]+,([\d.]+)\)", payload)
            y = float(pos.group(1)) if pos else (play_y or 1920) / 2
            colors = {w["color"] for w in words}
            cards.append({
                "id": f"card-{len(cards)+1:04d}",
                "start": round(start, 6),
                "end": round(end, 6),
                "y_pct": round(y / (play_y or 1920) * 100, 4),
                "speaker": "guest" if colors != {"FFFFFF"} else "host",
                "text": " ".join(w["text"] for w in words),
                "words": words,
                "gloss": None,
                "boundary": {"camera_cut": False, "speaker_change": False},
            })
    manifest = {
        "schema": SCHEMA,
        "source": {"kind": "ass", "path": str(path.resolve())},
        "video": {"width": play_x, "height": play_y, "fps": None},
        "cards": cards,
    }
    validate(manifest)
    return manifest


def validate(data: dict) -> None:
    if data.get("schema") != SCHEMA:
        raise ValueError(f"unsupported schema: {data.get('schema')}")
    prior_end = -1.0
    for card in data.get("cards", []):
        if not 0 <= float(card["start"]) < float(card["end"]):
            raise ValueError(f"invalid card duration: {card.get('id')}")
        if float(card["start"]) < prior_end - 0.001:
            raise ValueError(f"overlapping cards: {card.get('id')}")
        if not 1 <= len(card.get("words", [])) <= 4:
            raise ValueError(f"card must contain 1-4 word slots: {card.get('id')}")
        if card.get("text") != " ".join(w["text"] for w in card["words"]):
            raise ValueError(f"card text/word mismatch: {card.get('id')}")
        prior_end = float(card["end"])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("ass", type=Path)
    ap.add_argument("out", type=Path)
    args = ap.parse_args()
    data = parse_ass(args.ass)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(data, indent=2) + "\n")
    print(f"caption_manifest: {len(data['cards'])} cards -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
