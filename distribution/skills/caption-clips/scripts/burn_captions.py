#!/usr/bin/env python3
"""Trim a single clip out of the source video and burn captions in one ffmpeg pass.

- Uses `-ss START -to END` AFTER `-i` for frame-accurate trim.
- Passes the skill's `fonts/` directory via `fontsdir=` so no system install needed.
- Re-encodes via ACQ fast-render standard (VideoToolbox HW; libx264 fallback). AAC audio.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parent.parent


def escape_for_filter(p: Path) -> str:
    """Escape path for use inside ffmpeg -vf. Colons and backslashes are trouble on some platforms."""
    s = str(p)
    # FFmpeg filter path escaping rules: escape backslash, single quote, and colons.
    s = s.replace("\\", "\\\\").replace("'", r"\'").replace(":", r"\:")
    return s


def find_ffmpeg_with_libass() -> str:
    """Return path to an ffmpeg binary that has the `subtitles` filter (libass).

    Delegates to the ONE shared resolver (_shared/ffmpeg_bin.py) so the libass rule lives in a
    single place; the block below is only a self-contained fallback if _shared is unavailable.
    """
    try:
        import sys as _s
        _s.path.insert(0, str(Path("__ACQ_SKILLS__/_shared")))
        from ffmpeg_bin import require_libass
        return require_libass("burn_captions")
    except SystemExit:
        raise
    except Exception:
        pass

    candidates: list[str] = []
    if os.environ.get("FFMPEG"):
        candidates.append(os.environ["FFMPEG"])
    if shutil.which("ffmpeg"):
        candidates.append(shutil.which("ffmpeg"))
    if shutil.which("ffmpeg-full"):
        candidates.append(shutil.which("ffmpeg-full"))
    # macOS Homebrew ffmpeg-full Cellar locations.
    import glob
    candidates.extend(sorted(glob.glob("/opt/homebrew/Cellar/ffmpeg-full/*/bin/ffmpeg")))
    candidates.extend(sorted(glob.glob("/usr/local/Cellar/ffmpeg-full/*/bin/ffmpeg")))

    seen = set()
    for c in candidates:
        if not c or c in seen:
            continue
        seen.add(c)
        try:
            out = subprocess.run([c, "-hide_banner", "-filters"],
                                 capture_output=True, text=True, timeout=10)
            if " subtitles " in out.stdout:
                return c
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue

    sys.stderr.write(
        "ERROR: no ffmpeg build with the `subtitles` filter (libass) was found.\n"
        "On macOS: `brew install ffmpeg-full` (or build ffmpeg with --enable-libass).\n"
        "You can also set FFMPEG=/path/to/ffmpeg to override.\n"
    )
    sys.exit(3)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path, help="Source video")
    ap.add_argument("subs", type=Path, help=".ass subtitle file")
    ap.add_argument("--start", type=float, required=True, help="Clip start in source (seconds)")
    ap.add_argument("--end", type=float, required=True, help="Clip end in source (seconds)")
    ap.add_argument("--out", type=Path, required=True, help="Output .mp4")
    ap.add_argument("--fonts-dir", type=Path, default=SKILL_ROOT / "fonts",
                    help="Directory containing font files referenced by the .ass styles")
    ap.add_argument("--crf", type=int, default=18)
    ap.add_argument("--preset", default="medium")
    args = ap.parse_args()

    for p, label in [(args.input, "input"), (args.subs, "subs")]:
        if not p.exists():
            print(f"{label} not found: {p}", file=sys.stderr)
            return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)

    ffmpeg_bin = find_ffmpeg_with_libass()
    sub_escaped = escape_for_filter(args.subs)
    fonts_escaped = escape_for_filter(args.fonts_dir)
    # setpts=PTS-STARTPTS resets video clock so ASS clip-local timestamps align
    # with output start (otherwise captions only render at absolute source time).
    vf = f"setpts=PTS-STARTPTS,subtitles=filename='{sub_escaped}':fontsdir='{fonts_escaped}'"

    # ACQ fast-render standard: hardware VideoToolbox encode (~4x faster on Apple Silicon).
    import os, sys
    sys.path.insert(0, os.path.expanduser("__ACQ_SKILLS__/_shared"))
    from fast_encode import encoder_args
    _ffprobe = ffmpeg_bin.replace("/ffmpeg", "/ffprobe")
    try:
        _parts = subprocess.run([_ffprobe, "-v", "error", "-select_streams", "v:0",
                                 "-show_entries", "stream=width,height", "-of", "csv=p=0",
                                 "-i", str(args.input)], capture_output=True, text=True).stdout.strip().split(",")
        _w, _h = int(_parts[0]), int(_parts[1])
    except Exception:
        _w, _h = 2160, 3840
    cmd = [
        ffmpeg_bin, "-y", "-hide_banner",
        "-ss", f"{args.start:.3f}",
        "-to", f"{args.end:.3f}",
        "-i", str(args.input),
        "-vf", vf,
        *encoder_args(_w, _h, ffmpeg_bin, tier="delivery", crf=args.crf),
        "-c:a", "aac",
        "-b:a", "192k",
        "-movflags", "+faststart",
        str(args.out),
    ]
    print("Running:", " ".join(cmd))
    proc = subprocess.run(cmd)
    if proc.returncode != 0:
        return proc.returncode
    print(f"\nWrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
