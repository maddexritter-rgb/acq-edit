#!/usr/bin/env python3
"""Verify a multi-weight donor: every voice x weight x italic combination is real.

Decodes each donor Graphic out of a project file and checks that the profile's
nested run map addresses a run carrying the exact face it claims, that every rung
is a DISTINCT face (two rungs resolving to the same face is the flattening this
whole contract exists to prevent), and that fill, explicit size and the effect
graph around the text are unchanged.

Run it twice: on the offline donor, then on the file Premiere saved and reopened.
Passing both is still not a render proof -- only a rendered specimen shows that
Premiere used the faces rather than substituting them.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import premiere_native_cards as native
from native_graphics.decode_graphic_text import decode_runs

EXPECTED_EFFECTS = ("AE.ADBE Text",)


def verify(project: Path, profile: dict) -> dict:
    root = native.load(project)
    shared = native.pool(root)
    ids = native.objects(root)
    voices, problems = {}, []

    donors = profile.get("donors") or {}
    # A verifier that approves empty input approves anything. Each of these used to
    # produce zero voices / zero rungs / zero comparisons and still return the
    # STRUCTURALLY_VERIFIED status.
    if not donors:
        problems.append(
            "profile declares no 'donors' to verify"
            + (" (it carries 'donors_by_style'; verify a style donor with the style "
               "readback verifier, not this one)" if profile.get("donors_by_style")
               else ""))

    for voice, donor in donors.items():
        item = ids.get(donor["item_id"])
        if item is None:
            problems.append(f"{voice}: donor item {donor['item_id']} is absent")
            continue
        runs = decode_runs(native.payload(native.text_node(root, item), shared))
        declared_faces = donor.get("faces") or {}
        rungs, seen = {}, {}
        if not (donor.get("runs") or {}):
            problems.append(f"{voice}: donor declares no 'runs', so no rung was checked")
        for weight, mapping in (donor.get("runs") or {}).items():
            if not isinstance(mapping, dict):
                problems.append(f"{voice}/{weight}: legacy single-offset run, not upright+italic")
                continue
            for state in ("upright", "italic"):
                if state not in mapping:
                    problems.append(f"{voice}/{weight}: no {state} run declared")
                    continue
                index = mapping[state]
                if not isinstance(index, int) or not 0 <= index < len(runs):
                    problems.append(f"{voice}/{weight}/{state}: run index {index} out of range")
                    continue
                run = runs[index]
                face = run["font_postscript"]
                key = f"{weight}_italic" if state == "italic" else weight
                rungs[key] = dict(run_index=index, face=face, text=run["text"].strip(),
                                  size=run["font_size_raw"], fill=run["fill_rgb_explicit"])
                want = declared_faces.get(key)
                if not want:
                    # "Carries the exact face it claims" is meaningless when nothing
                    # is claimed; silently skipping the comparison passed the donor.
                    problems.append(f"{voice}/{key}: profile declares no face for this rung, "
                                    f"so the run's {face!r} cannot be verified")
                elif face != want:
                    problems.append(f"{voice}/{key}: run carries {face!r}, profile declares {want!r}")
                if face in seen:
                    problems.append(f"{voice}: {key} and {seen[face]} both resolve to {face!r} "
                                    f"-- rungs must be distinct faces, never flattened")
                seen[face] = key

        sizes = {r["size"] for r in rungs.values()}
        fills = {json.dumps(r["fill"]) for r in rungs.values()}
        if len(sizes) > 1:
            problems.append(f"{voice}: runs disagree on explicit font size {sorted(sizes)}")
        if len(fills) > 1:
            problems.append(f"{voice}: runs disagree on fill {sorted(fills)}")

        # The text component must still sit in its original effect chain, so shadow
        # and entrance animation are structurally intact.
        chain = ids[item.find("ClipTrackItem/ComponentOwner/Components").get("ObjectRef")]
        effects = [ids[r.get("ObjectRef")].findtext("MatchName")
                   for r in chain.findall("ComponentChain/Components/Component")]
        for required in EXPECTED_EFFECTS:
            if required not in effects:
                problems.append(f"{voice}: effect chain lost {required}")

        voices[voice] = dict(item_id=donor["item_id"], total_runs=len(runs),
                             rungs=rungs, distinct_faces=len(seen),
                             effect_chain=effects, color=donor.get("color"))

    return dict(
        status="DONOR_RUNS_VERIFIED_STRUCTURALLY_NOT_RENDER_PROVEN" if not problems
               else "DONOR_VERIFICATION_FAILED",
        project=str(project.resolve()),
        project_sha256=hashlib.sha256(project.read_bytes()).hexdigest(),
        profile_sha_matches=hashlib.sha256(project.read_bytes()).hexdigest()
                            == profile.get("project_sha256"),
        voices=voices, problems=problems,
        not_verified_here=["Premiere actually renders these faces",
                           "rungs are visually distinct on pixels",
                           "shadow and animation render unchanged"])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--project", required=True)
    ap.add_argument("--profile", required=True)
    ap.add_argument("--out")
    ap.add_argument("--expect-profile-hash", action="store_true",
                    help="also require the project hash to match the profile")
    a = ap.parse_args()
    profile = json.loads(Path(a.profile).read_text())
    result = verify(Path(a.project), profile)
    if a.expect_profile_hash and not result["profile_sha_matches"]:
        result["problems"].append("project hash does not match the profile")
        result["status"] = "DONOR_VERIFICATION_FAILED"
    text = json.dumps(result, indent=2)
    if a.out:
        Path(a.out).write_text(text + "\n")
    print(text)
    return 1 if result["problems"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
