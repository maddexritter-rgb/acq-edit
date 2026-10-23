"""Reduce dense tracker samples to editable, item-local Premiere Motion keys.

Input and output use the native motion-plan JSON contract (`records[].anchor_keys` as
`[relative_seconds, normalized_x, normalized_y]`). The simplifier preserves the
first/last samples and every point needed to stay within the requested normalized
Anchor Point error at each sample time under linear interpolation. Pixel error depends
on source dimensions and Motion scale. It never joins records across an edit.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def _distance(point, start, end) -> float:
    px, py = point[1], point[2]
    ax, ay = start[1], start[2]
    bx, by = end[1], end[2]
    dx, dy = bx - ax, by - ay
    u = (point[0] - start[0]) / (end[0] - start[0])
    return math.hypot(px - (ax + u * dx), py - (ay + u * dy))


def simplify(keys: list[list[float]], tolerance: float) -> list[list[float]]:
    if not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError("tolerance must be finite and non-negative")
    if any(len(k) != 3 or not all(math.isfinite(v) for v in k) for k in keys):
        raise ValueError("keys must contain finite time, x and y values")
    if any(b[0] <= a[0] for a, b in zip(keys, keys[1:])):
        raise ValueError("key times must be strictly increasing")
    if len(keys) <= 1:
        return keys[:]

    def recurse(first: int, last: int) -> list[int]:
        if last <= first + 1:
            return [first, last]
        distance, index = max(
            ((_distance(keys[i], keys[first], keys[last]), i) for i in range(first + 1, last)),
            default=(0.0, first),
        )
        if distance <= tolerance:
            return [first, last]
        return recurse(first, index)[:-1] + recurse(index, last)

    indices = recurse(0, len(keys) - 1)
    result = [keys[i] for i in indices]
    movement = max(math.hypot(k[1] - result[0][1], k[2] - result[0][2]) for k in keys)
    if movement <= tolerance:
        return [result[0]]
    return result


def simplify_plan(plan: dict, tolerance: float) -> dict:
    output = json.loads(json.dumps(plan))
    before = after = 0
    for record in output.get("records", []):
        keys = record.get("anchor_keys", [])
        before += len(keys)
        record["anchor_keys"] = simplify(keys, tolerance)
        record["keyframe_policy"] = {
            "scope": "individual_clip_item",
            "property": "Anchor Point",
            "tolerance_normalized": tolerance,
            "dense_samples": len(keys),
            "native_keys": len(record["anchor_keys"]),
            "error_metric": "time_aligned_linear_anchor_distance",
        }
        after += len(record["anchor_keys"])
    output["native_keyframe_summary"] = {
        "scope": "individual_clip_items_only",
        "property": "Anchor Point",
        "dense_samples": before,
        "native_keys": after,
        "tolerance_normalized": tolerance,
        "warning": "Render and verify every edit boundary; simplification does not certify framing or seam continuity.",
    }
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--tolerance", type=float, default=0.0012,
                        help="Maximum normalized Anchor Point error at sample times under linear interpolation")
    args = parser.parse_args()
    result = simplify_plan(json.loads(args.input.read_text()), args.tolerance)
    args.output.write_text(json.dumps(result, indent=2))
    print(json.dumps(result["native_keyframe_summary"], indent=2))


if __name__ == "__main__":
    main()
