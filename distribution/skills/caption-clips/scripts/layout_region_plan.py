#!/usr/bin/env python3
"""Pure helpers for the camera-stage -> caption-layout region contract."""

from __future__ import annotations

import json
from pathlib import Path


SPLIT_LAYOUTS = {"split", "split_screen", "stacked"}


def load_regions(path: str | None, total_frames: int) -> list[dict]:
    if not path:
        return []
    payload = json.loads(Path(path).read_text())
    regions = payload.get("segments", payload) if isinstance(payload, dict) else payload
    if not isinstance(regions, list):
        raise ValueError("region plan must contain a segments array")
    normalized = []
    for raw in regions:
        if not all(k in raw for k in ("start_i", "end_i", "layout")):
            raise ValueError("each planned region requires start_i, end_i, and layout")
        start = int(raw["start_i"])
        end = int(raw["end_i"])
        if start < 0 or end < start or end >= total_frames:
            raise ValueError(f"invalid planned region: {raw}")
        normalized.append({**raw, "start_i": start, "end_i": end,
                           "layout": str(raw["layout"]).lower()})
    normalized.sort(key=lambda r: (r["start_i"], r["end_i"]))
    for left, right in zip(normalized, normalized[1:]):
        if right["start_i"] <= left["end_i"]:
            raise ValueError(f"overlapping planned regions: {left} / {right}")
    return normalized


def bounds_with_regions(cuts: list[int], regions: list[dict], total_frames: int) -> list[int]:
    region_bounds = []
    for region in regions:
        region_bounds.extend([region["start_i"], region["end_i"] + 1])
    return sorted(set([0, total_frames]
                      + [c for c in cuts if 0 < c < total_frames]
                      + [b for b in region_bounds if 0 < b < total_frames]))


def layout_for_region(regions: list[dict], lo_i: int, hi_i: int) -> str | None:
    midpoint = (lo_i + hi_i - 1) // 2
    matches = [r for r in regions if r["start_i"] <= midpoint <= r["end_i"]]
    if len(matches) > 1:
        raise ValueError(f"overlapping planned regions at frame {midpoint}")
    return matches[0]["layout"] if matches else None


def is_split(layout: str | None) -> bool:
    return bool(layout and layout.lower() in SPLIT_LAYOUTS)
