#!/usr/bin/env python3
"""Validate a workshop/event organic-to-paid plan before modifying approved edits."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path


def load(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path}: root must be an object")
    return value


def close(a: object, b: object, tolerance: float = 1e-3) -> bool:
    try:
        return math.isclose(float(a), float(b), abs_tol=tolerance)
    except (TypeError, ValueError):
        return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("plan", type=Path)
    parser.add_argument("--profile", type=Path, required=True)
    args = parser.parse_args()

    plan = load(args.plan)
    profile = load(args.profile)
    routes = profile.get("offer_routes", {})
    expected_transition = profile.get("transition", {})
    expected_overlay = profile.get("brand_overlay", {})
    clips = plan.get("clips")
    errors: list[str] = []

    if not isinstance(clips, list) or not clips:
        errors.append("clips must be a non-empty list")
        clips = []

    seen: set[str] = set()
    for index, clip in enumerate(clips, 1):
        label = str(clip.get("id", index))
        prefix = f"clip {label}:"
        if label in seen:
            errors.append(f"{prefix} duplicate id")
        seen.add(label)

        lane = clip.get("content_lane")
        expected_offer = routes.get(lane)
        if expected_offer is None:
            errors.append(f"{prefix} unsupported content_lane {lane!r}")
        elif clip.get("cta_offer") != expected_offer:
            errors.append(
                f"{prefix} CTA offer {clip.get('cta_offer')!r} does not match "
                f"{lane!r} route {expected_offer!r}"
            )

        if clip.get("cta_status") != "approved":
            errors.append(f"{prefix} CTA is not currently approved")
        if clip.get("cta_claims_preceding_participation") and not clip.get(
            "cta_speaker_appears_in_organic"
        ):
            errors.append(f"{prefix} CTA makes a false preceding-participation claim")

        organic_end = clip.get("organic_end")
        cta_start = clip.get("cta_start")
        watermark_end = clip.get("watermark_end")
        if not close(organic_end, cta_start, tolerance=0.05):
            errors.append(f"{prefix} CTA does not start at the approved organic endpoint")
        try:
            if float(watermark_end) > float(cta_start) + 1e-3:
                errors.append(f"{prefix} watermark bleeds into CTA")
        except (TypeError, ValueError):
            errors.append(f"{prefix} invalid watermark_end or cta_start")

        transition = clip.get("transition", {})
        for key, expected in expected_transition.items():
            actual = transition.get(key)
            matches = close(actual, expected) if isinstance(expected, (int, float)) else actual == expected
            if not matches:
                errors.append(f"{prefix} transition {key}={actual!r}; expected {expected!r}")

        overlay = clip.get("brand_overlay", {})
        if overlay.get("stroke") != expected_overlay.get("stroke"):
            errors.append(f"{prefix} overlay stroke does not match profile")
        if expected_overlay.get("asset") and overlay.get("asset") != expected_overlay.get("asset"):
            errors.append(f"{prefix} wrong brand overlay asset")
        expected_shadows = expected_overlay.get("shadows", [])
        actual_shadows = overlay.get("shadows", [])
        if len(actual_shadows) != len(expected_shadows):
            errors.append(f"{prefix} wrong number of overlay shadows")
        else:
            for shadow_index, (actual, expected) in enumerate(zip(actual_shadows, expected_shadows), 1):
                for key, expected_value in expected.items():
                    actual_value = actual.get(key)
                    matches = close(actual_value, expected_value) if isinstance(expected_value, (int, float)) else actual_value == expected_value
                    if not matches:
                        errors.append(
                            f"{prefix} shadow {shadow_index} {key}={actual_value!r}; "
                            f"expected {expected_value!r}"
                        )

    result = {"status": "PASS" if not errors else "FAIL", "clips": len(clips), "errors": errors}
    print(json.dumps(result, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
