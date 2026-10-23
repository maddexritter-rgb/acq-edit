#!/usr/bin/env python3
"""EXPERIMENTAL: build a donor carrying every weight/italic run, from an approved donor.

Status: UNPROVEN until a rendered specimen, taken after a Premiere save/reopen,
shows every rung distinct. It rewrites a binary Source Text payload, which is a
diagnostic-grade mechanism upstream -- so this script refuses to describe its own
output as approved, and `verify_native_donor.py` is what promotes it.

What it does. A donor Graphic's styled-run vector is rebuilt so it physically
contains one independently addressable run per (weight, italic state):

    0 base/upright      1 base/italic
    2 strong/upright    3 strong/italic
    4 emphasis/upright  5 emphasis/italic
    6 payoff/upright    7 payoff/italic

Each run is a separate clone of an approved donor run, and the document's font
vector is extended so every run's font_index addresses its own exact PostScript
face. Faces are therefore real per-run faces, not a synthesised slant. Fill
colour, explicit font size, shadow, entrance animation, position and the
surrounding effect graph all come from the donor and are never touched: only the
text component's payload changes.

Fonts are referenced by exact Adobe PostScript name. Nothing is bundled or
renamed, and a face this machine cannot resolve is an error, not a fallback.
"""
from __future__ import annotations

import argparse
import base64
import copy
import gzip
import hashlib
import json
import struct
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

import premiere_native_cards as native
from native_graphics.decode_graphic_text import decode_runs

# Ladder order is the run order. Index = 2*rung + (1 if italic).
LADDER = ("base", "strong", "emphasis", "payoff")
FACES = {
    "base": ("ProximaNova-Medium", "ProximaNova-MediumIt"),
    "strong": ("ProximaNova-Bold", "ProximaNova-BoldIt"),
    "emphasis": ("ProximaNova-Extrabld", "ProximaNova-ExtrabldIt"),
    "payoff": ("ProximaNova-Black", "ProximaNova-BlackIt"),
}
# Each run carries its own rung name, so the donor doubles as a labelled specimen.
LABELS = {(w, i): f"{w}{'-italic' if i else ''}" for w in LADDER for i in (False, True)}


def run_plan():
    """[(run_index, weight, italic, face, label)] in physical run order."""
    plan = []
    for rung, weight in enumerate(LADDER):
        for italic in (False, True):
            plan.append((2 * rung + int(italic), weight, italic,
                         FACES[weight][int(italic)], LABELS[(weight, italic)]))
    return plan


def _ptr(buf, offset):
    return offset + struct.unpack_from("<I", buf, offset)[0]


def _field(buf, table, index):
    vt = table - struct.unpack_from("<i", buf, table)[0]
    rel = struct.unpack_from("<H", buf, vt + 4 + index * 2)[0]
    if not rel:
        raise ValueError(f"required table field {index} is absent")
    return table + rel


def _explicit_font_run(buf: bytes, donors) -> int:
    """Index of a donor run whose style table has an explicit font_index slot."""
    for run in donors:
        style = run["style_table_offset"]
        vt = style - struct.unpack_from("<i", buf, style)[0]
        size = struct.unpack_from("<H", buf, vt)[0]
        if size >= 6 and struct.unpack_from("<H", buf, vt + 4)[0]:
            return run["index"]
    raise ValueError(
        "No donor run carries an explicit font_index slot, so per-run faces cannot be "
        "addressed. Prepare a donor whose text uses at least two different faces.")


def _append_string(out: bytearray, text: str) -> int:
    out.extend(b"\x00" * ((-len(out)) % 4))
    at = len(out)
    encoded = text.encode("utf-8")
    out.extend(struct.pack("<I", len(encoded)) + encoded + b"\x00")
    return at


def rebuild_with_faces(payload: bytes, plan) -> bytes:
    """One independently addressable run per plan entry, each with its exact face.

    The font vector is DOCUMENT level, not per run: decode_runs resolves every
    run's font_index against the one top-level vector. So per-run faces are not
    achieved by rewriting identifiers inside a cloned run (that vector is never
    read) -- the document's font vector is extended to hold every required face,
    and each run's font_index is repointed at its own entry.

    Run topology comes from the proven clone path, so each run keeps the donor's
    explicit font size, fill and style-table shape; only font_index changes.
    """
    from native_graphics.native_run_topology_probe import rebuild_runs

    donors = decode_runs(payload)
    if not 1 <= len(plan) <= 256:
        raise ValueError("Donor run plan must be 1-256 runs")

    # Clone from a run whose style table carries an EXPLICIT font_index slot. A run
    # using font_index 0 usually omits the field entirely (flatbuffers drop
    # defaults), leaving nothing to repoint; the donor's emphasis run has the slot
    # because its index is non-zero. Everything else about the style -- size, fill,
    # italic field -- comes along with the clone either way.
    source = _explicit_font_run(payload, donors)

    # 1. Stage the topology: one clone per entry, all carrying that run's style.
    staged = rebuild_runs(payload, [(source, (" " if i else "") + label)
                                    for i, (_, _, _, _, label) in enumerate(plan)])
    out = bytearray(staged)

    # 2. Extend the document font vector with every face this donor must offer.
    document = _ptr(out, _field(out, _ptr(out, 12), 0))
    fonts_field = _field(out, document, 1)
    old_vector = _ptr(out, fonts_field)
    old_count = struct.unpack_from("<I", out, old_vector)[0]
    existing = []
    for i in range(old_count):
        at = _ptr(out, old_vector + 4 + i * 4)
        length = struct.unpack_from("<I", out, at)[0]
        existing.append(out[at + 4:at + 4 + length].decode("utf-8"))

    faces = [face for _, _, _, face, _ in plan]
    names = existing + [f for f in dict.fromkeys(faces) if f not in existing]
    index_of = {name: i for i, name in enumerate(names)}

    # Every pointer in this format is a FORWARD offset, so the vector is reserved
    # first and its strings are appended after it, then the entries are patched.
    out.extend(b"\x00" * ((-len(out)) % 4))
    new_vector = len(out)
    out.extend(struct.pack("<I", len(names)) + b"\x00" * (4 * len(names)))
    for i, name in enumerate(names):
        at = _append_string(out, name)
        entry = new_vector + 4 + i * 4
        struct.pack_into("<I", out, entry, at - entry)
    struct.pack_into("<I", out, fonts_field, new_vector - fonts_field)

    # 3. Repoint each run's font_index at its own face.
    run_vector = _ptr(out, _field(out, document, 0))
    if struct.unpack_from("<I", out, run_vector)[0] != len(plan):
        raise ValueError("staged run count does not match the plan")
    for i, face in enumerate(faces):
        table = _ptr(out, run_vector + 4 + i * 4)
        style = _ptr(out, _field(out, table, 1))
        struct.pack_into("<I", out, _field(out, style, 0), index_of[face])

    struct.pack_into("<I", out, 0, len(out) - 12)
    result = bytes(out)

    decoded = decode_runs(result)
    if len(decoded) != len(plan):
        raise ValueError(f"rebuilt {len(decoded)} runs, expected {len(plan)}")
    for run, (_, weight, italic, face, label) in zip(decoded, plan):
        if run["font_postscript"] != face:
            raise ValueError(f"run for {weight}/{'italic' if italic else 'upright'} carries "
                             f"{run['font_postscript']!r}, expected {face!r}")
        if run["text"].strip() != label:
            raise ValueError(f"run label {run['text']!r} does not match {label!r}")
        if run["font_size_raw"] != donors[source]["font_size_raw"]:
            raise ValueError("a rebuilt run lost the donor's explicit font size")
        if run["fill_rgb_explicit"] != donors[source]["fill_rgb_explicit"]:
            raise ValueError("a rebuilt run lost the donor's fill")
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--project", required=True, help="the approved donor project to read")
    ap.add_argument("--profile", required=True, help="its matching hash-bound profile")
    ap.add_argument("--output", required=True, help="the NEW donor project (never overwritten)")
    ap.add_argument("--out-profile", required=True, help="the NEW nested-run profile")
    a = ap.parse_args()

    output, out_profile = Path(a.output), Path(a.out_profile)
    for path in (output, out_profile):
        if path.exists():
            raise FileExistsError(path)

    project = Path(a.project)
    profile = json.loads(Path(a.profile).read_text())
    if hashlib.sha256(project.read_bytes()).hexdigest() != profile["project_sha256"]:
        raise ValueError("Profile does not match this donor project")

    root = native.load(project)
    shared = native.pool(root)
    ids = native.objects(root)
    plan = run_plan()

    donors_out, report = {}, {}
    for voice, donor in profile["donors"].items():
        item = ids[donor["item_id"]]
        node = native.text_node(root, item)
        before = decode_runs(native.payload(node, shared))
        rebuilt = rebuild_with_faces(native.payload(node, shared), plan)
        # Replace only the text payload. The effect graph around it -- shadow,
        # entrance animation, transform -- is untouched by construction.
        node.set("Encoding", "base64")
        node.set("BinaryHash", str(uuid.uuid4()))
        node.text = base64.b64encode(rebuilt).decode()

        decoded = decode_runs(rebuilt)
        donors_out[voice] = dict(
            item_id=donor["item_id"],
            runs={w: {"upright": 2 * r, "italic": 2 * r + 1} for r, w in enumerate(LADDER)},
            faces={f"{w}{'_italic' if i else ''}": f for _, w, i, f, _ in plan
                   for f in [FACES[w][int(i)]]},
            color=donor["color"],
            italic_source_run_state="per_run_face",
        )
        report[voice] = dict(
            donor_item=donor["item_id"],
            runs_before=len(before), runs_after=len(decoded),
            faces_before=sorted({r["font_postscript"] for r in before}),
            faces_after=[r["font_postscript"] for r in decoded],
            labels=[r["text"].strip() for r in decoded],
            fill=decoded[0]["fill_rgb_explicit"],
            font_size=decoded[0]["font_size_raw"],
        )

    with output.open("xb") as f:
        f.write(gzip.compress(ET.tostring(root, encoding="utf-8", xml_declaration=True), mtime=0))

    new_profile = copy.deepcopy(profile)
    new_profile.update(
        project_sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
        donors=donors_out,
        run_schema="nested_weight_italic",
        prepared_from=str(project.resolve()),
        status="EXPERIMENTAL_DONOR_REQUIRES_PREMIERE_RENDER_CERTIFICATION",
    )
    out_profile.write_text(json.dumps(new_profile, indent=2) + "\n")

    print(json.dumps(dict(
        status="EXPERIMENTAL_DONOR_BUILT_NOT_YET_PROVEN",
        donor=str(output.resolve()), profile=str(out_profile.resolve()),
        voices=report,
        next_step="verify_native_donor.py, then a Premiere save/reopen and a rendered specimen",
    ), indent=2))


if __name__ == "__main__":
    main()
