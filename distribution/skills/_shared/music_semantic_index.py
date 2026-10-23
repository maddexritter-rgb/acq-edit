#!/usr/bin/env python3
"""Compatibility shim. Canonical implementation: music/scripts/music_semantic_index.py."""
import runpy
from pathlib import Path
TARGET = Path("__ACQ_SKILLS__/music/scripts/music_semantic_index.py")
runpy.run_path(str(TARGET), run_name="__main__" if __name__ == "__main__" else "music_semantic_index")
