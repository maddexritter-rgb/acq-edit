#!/usr/bin/env python3
"""Compatibility shim. Canonical implementation: music/scripts/pick_music.py."""
import runpy
from pathlib import Path
TARGET = Path("__ACQ_SKILLS__/music/scripts/pick_music.py")
if __name__ == "__main__":
    runpy.run_path(str(TARGET), run_name="__main__")
else:
    globals().update({k: v for k, v in runpy.run_path(str(TARGET)).items() if not k.startswith("__")})
