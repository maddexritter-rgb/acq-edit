#!/usr/bin/env python3
"""Fail closed unless every caption font is installed under its exact PostScript name."""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


DEFAULT_REQUIRED = (
    "ProximaNova-Medium",
    "ProximaNova-MediumIt",
    "ProximaNova-Extrabld",
    "ProximaNova-ExtrabldIt",
)
LOCAL_FONT_ROOTS = (
    Path.home() / "Library/Fonts",
    Path("/Library/Fonts"),
    Path("/System/Library/Fonts"),
)
ADOBE_CACHE = Path.home() / "Library/Application Support/Adobe/CoreSync/plugins/livetype"


def scan_fonts(path: Path) -> list[str]:
    try:
        result = subprocess.run(
            ["fc-scan", "--format", "%{postscriptname}\\n", str(path)],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return []
    return [name for name in result.stdout.splitlines() if name]


def fonts_from_manifest(path: Path) -> set[str]:
    data = json.loads(path.read_text())
    found: set[str] = set()
    for track in data.get("tracks", []):
        for card in track.get("cards", []):
            found.update(card.get("fonts", []))
    for card in data.get("render_segments", data.get("cards", [])):
        for word in card.get("words", []):
            if word.get("font_postscript"):
                found.add(word["font_postscript"])
    return found


def fonts_from_profile(path: Path) -> set[str]:
    """The faces a native donor profile declares it uses.

    Only a profile with an explicit per-donor `faces` map (or `font_replacements`
    for a style donor) can answer this. A legacy profile's weight NAMES must not be
    used to guess: under the old two-weight contract `strong` meant Extrabold, on the
    full ladder it means Bold. Refuse instead of checking the wrong faces.
    """
    data = json.loads(path.read_text())
    replacements = {f for f in (data.get("font_replacements") or {}).values() if f}
    donors = {**(data.get("donors") or {}), **(data.get("donors_by_style") or {})}
    if not donors and not replacements:
        raise SystemExit(
            f"{path}: profile declares neither 'donors' nor 'donors_by_style'/"
            "'font_replacements', so the faces it uses are unknown. Name them with "
            "`--font <PostScriptName>`, or regenerate the profile with "
            "prepare_native_donor.py, which records them.")
    undeclared = [name for name, donor in donors.items()
                  if not (donor.get("faces") or {}) and not replacements]
    if undeclared:
        raise SystemExit(
            f"{path}: donor(s) {undeclared} declare no 'faces' map, so the exact faces "
            "they use are unknown. Re-run with `--font <PostScriptName>` per face, or "
            "regenerate the profile with prepare_native_donor.py, which records them.")
    return replacements | {f for donor in donors.values()
                           for f in (donor.get("faces") or {}).values() if f}


def _name_file_rows(argv: list[str]) -> list[tuple[str, str]]:
    """Run a fontconfig query printing "<postscript name>\t<file>" per line.

    Scanning font files ONE AT A TIME costs ~12 seconds on a machine with a normal
    font library, and everything that measures caption width pays it on import --
    it turned this skill's test suite from sub-second into minutes. fc-list (whole
    system) and fc-scan (one directory) answer the same question in one call.
    """
    try:
        result = subprocess.run(argv, check=True, capture_output=True, text=True)
    except (OSError, subprocess.CalledProcessError):
        return []
    rows = []
    for line in result.stdout.splitlines():
        name, _, path = line.partition("\t")
        if name.strip() and path.strip():
            rows.append((name.strip(), path.strip()))
    return rows


def _under(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _register(target: dict[str, list[str]], rows) -> None:
    for name, path in rows:
        paths = target.setdefault(name, [])
        if path not in paths:
            paths.append(path)


def installed_faces() -> dict[str, list[str]]:
    """Faces backed by a real font FILE in a local font root."""
    found: dict[str, list[str]] = {}
    _register(found, [(name, path) for name, path in
                      _name_file_rows(["fc-list", "--format", "%{postscriptname}\t%{file}\n"])
                      if any(_under(Path(path), root) for root in LOCAL_FONT_ROOTS)])
    if found:
        return found
    for root in LOCAL_FONT_ROOTS:                      # fontconfig unavailable
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.suffix.lower() in {".otf", ".ttf", ".ttc"}:
                _register(found, [(n, str(path)) for n in scan_fonts(path)])
    return found


def cached_faces() -> dict[str, list[str]]:
    """Faces present ONLY in Adobe's CoreSync cache -- which is a FAIL here.

    Scanned separately from installed_faces because fontconfig does not index the
    CoreSync cache at all. Folding both into one fc-list returns an empty cached
    set, and a cache-only face then reports as `missing` rather than `cache_only`:
    the same refusal, but the wrong reason, pointing the operator at installing a
    file when the real problem is that Premiere would silently substitute.
    """
    if not ADOBE_CACHE.exists():
        return {}
    found: dict[str, list[str]] = {}
    _register(found, _name_file_rows(
        ["fc-scan", "--format", "%{postscriptname}\t%{file}\n", str(ADOBE_CACHE)]))
    if found:
        return found
    for path in ADOBE_CACHE.rglob("*.otf"):            # fontconfig unavailable
        _register(found, [(n, str(path)) for n in scan_fonts(path)])
    return found


def inventory() -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    return installed_faces(), cached_faces()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--native-graphics", type=Path)
    ap.add_argument("--font", action="append", default=[])
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    required = set(args.font)
    if args.native_graphics:
        required.update(fonts_from_manifest(args.native_graphics))
    if not required:
        required.update(DEFAULT_REQUIRED)
    installed, cached = inventory()
    rows = []
    failed = False
    for name in sorted(required):
        if name in installed:
            status = "installed"
            paths = installed[name]
        elif name in cached:
            status = "cache_only"
            paths = cached[name]
            failed = True
        else:
            status = "missing"
            paths = []
            failed = True
        rows.append({"postscript_name": name, "status": status, "paths": paths})
    payload = {"ok": not failed, "fonts": rows}
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        for row in rows:
            print(f"{row['status']:10} {row['postscript_name']}" + (f" -> {row['paths'][0]}" if row["paths"] else ""))
        print("PASS: exact caption fonts are locally installed" if not failed else "FAIL: cached-only/missing fonts may substitute; do not render or train")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
