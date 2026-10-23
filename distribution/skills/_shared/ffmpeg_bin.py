"""ffmpeg_bin — THE resolver for an ffmpeg/ffprobe binary, with a hard libass gate.

WHY THIS EXISTS (2026-08-18 outage)
-----------------------------------
Homebrew split ffmpeg into two formulae:
  * `ffmpeg`      — slim. Built WITHOUT --enable-libass. Has NO `ass` / `subtitles` filter.
  * `ffmpeg-full` — everything, including libass. But it is KEG-ONLY, so brew refuses to
                    put it on PATH by default.
A `brew upgrade` on 2026-08-13 linked slim ffmpeg 9.0.1 into /opt/homebrew/bin, so every
caption burn sitewide died with `Unknown filter 'ass'` / `No option name near '<path>'`.

That second error message is a RED HERRING and it cost a whole session: it looks like a
filter-graph QUOTING bug, so the instinct is to pin an old ffmpeg version. It is not.
When libass is missing, ffmpeg fails to parse `ass='<path>'` and reports a generic option
error. The `ass=` quoting is fine on every build that actually HAS libass (verified on 8.1.1).
=> Resolve on the CAPABILITY (does this binary have the `ass` filter?), NEVER on a version
   number. A version pin rots; a capability probe does not.

USE
---
    import sys; sys.path.insert(0, str(Path("__ACQ_SKILLS__/_shared")))
    from ffmpeg_bin import ffmpeg, ffprobe, require_libass

    FF  = ffmpeg()            # plain ffmpeg — PATH is fine, no libass needed
    FFP = ffprobe()
    FF  = require_libass()    # HARD GATE: an ffmpeg WITH libass, or exit 3 with a fix message

require_libass() never silently falls back to a build that cannot burn captions — a silent
fallback here ships a caption-less clip that looks "successful". It is a blocking gate.

Self-test:  python3 ffmpeg_bin.py
"""
from __future__ import annotations

import glob
import os
import re
import shutil
import subprocess
import sys

__all__ = ["ffmpeg", "ffprobe", "has_libass", "require_libass", "find_bin"]

_CELLARS = ("/opt/homebrew/Cellar", "/usr/local/Cellar")
_cache: dict = {}


def _vkey(path: str):
    """Sort key so 10.0.1 > 9.0.1 (a plain string sort gets this backwards)."""
    m = re.search(r"/Cellar/[^/]+/([^/]+)/", path)
    if not m:
        return (0,)
    return tuple(int(p) if p.isdigit() else 0 for p in re.split(r"[._-]", m.group(1)))


def _candidates(name: str) -> list:
    """Every plausible <name> binary, best-guess order. PATH first — if PATH is already
    correct we must use it, so a working machine never depends on Cellar layout."""
    out = []
    env = os.environ.get(name.upper())          # $FFMPEG / $FFPROBE hard override
    if env:
        out.append(env)
    w = shutil.which(name)
    if w:
        out.append(w)
    for cellar in _CELLARS:                     # libass-bearing formula, newest first
        out += sorted(glob.glob(f"{cellar}/ffmpeg-full/*/bin/{name}"), key=_vkey, reverse=True)
        out += sorted(glob.glob(f"{cellar}/ffmpeg/*/bin/{name}"), key=_vkey, reverse=True)
    seen, uniq = set(), []
    for c in out:
        if c and c not in seen and os.path.exists(c):
            seen.add(c)
            uniq.append(c)
    return uniq


def has_libass(binary: str) -> bool:
    """True iff this binary actually exposes the libass `ass` AND `subtitles` filters."""
    key = ("libass", binary)
    if key in _cache:
        return _cache[key]
    try:
        p = subprocess.run([binary, "-hide_banner", "-filters"],
                           capture_output=True, text=True, timeout=20)
        ok = bool(re.search(r"^ \S+ ass\s", p.stdout, re.M)) and \
             bool(re.search(r"^ \S+ subtitles\s", p.stdout, re.M))
    except (OSError, subprocess.SubprocessError):
        ok = False
    _cache[key] = ok
    return ok


def find_bin(name: str = "ffmpeg", libass: bool = False) -> str:
    """Resolve <name>. libass=True returns only a build with the ass/subtitles filters."""
    key = (name, libass)
    if key in _cache:
        return _cache[key]
    cands = _candidates(name)
    chosen = None
    if libass:
        probe = name if name == "ffmpeg" else name.replace("ffprobe", "ffmpeg")
        for c in cands:
            # probe the sibling ffmpeg when resolving a non-ffmpeg tool from the same keg
            test = c if name == "ffmpeg" else os.path.join(os.path.dirname(c), "ffmpeg")
            if has_libass(test):
                chosen = c
                break
    else:
        chosen = cands[0] if cands else None
    if chosen:
        _cache[key] = chosen
    return chosen or (shutil.which(name) or name)


def ffmpeg() -> str:
    return find_bin("ffmpeg")


def ffprobe() -> str:
    return find_bin("ffprobe")


def require_libass(label: str = "caption burn") -> str:
    """HARD GATE. Return an ffmpeg WITH libass, or exit 3 loudly. Never falls back silently."""
    b = find_bin("ffmpeg", libass=True)
    if b and has_libass(b):
        return b
    on_path = shutil.which("ffmpeg") or "(none)"
    sys.stderr.write(
        f"\n❌ {label}: NO ffmpeg with libass (the `ass`/`subtitles` filters) on this machine.\n"
        f"   ffmpeg on PATH: {on_path}\n"
        "   Homebrew's slim `ffmpeg` formula is built WITHOUT libass; `ffmpeg-full` has it\n"
        "   but is keg-only (brew will not put it on PATH by itself).\n"
        "   FIX:  brew install ffmpeg-full && brew unlink ffmpeg && brew link --force --overwrite ffmpeg-full\n"
        "   Verify:  ffmpeg -filters | grep -E ' (ass|subtitles) '\n"
        "   Override: FFMPEG=/path/to/ffmpeg-with-libass\n"
        "   (NOTE: `No option name near '<path>'` from an `ass=` filter means libass is MISSING,\n"
        "    not that the quoting is wrong. Do not 'fix' it by pinning an older ffmpeg.)\n\n")
    sys.exit(3)


if __name__ == "__main__":
    ff, fp = ffmpeg(), ffprobe()
    print(f"ffmpeg   : {ff}")
    print(f"ffprobe  : {fp}")
    print(f"libass   : {'YES' if has_libass(ff) else 'NO'}  (on the PATH/default pick)")
    g = find_bin("ffmpeg", libass=True)
    print(f"libass ff: {g if g and has_libass(g) else 'NONE FOUND'}")
    sys.exit(0 if g and has_libass(g) else 3)
