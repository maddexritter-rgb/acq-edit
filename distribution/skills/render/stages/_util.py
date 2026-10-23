"""Shared helpers for render stages."""
from __future__ import annotations

import json, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
try:
    from fast_encode import encoder_args as _fe_args, probe_size as _fe_probe
except Exception:                                                   # pragma: no cover
    _fe_args = _fe_probe = None


def venc(bitrate: str, src=None, width=None, height=None):
    """Video-encoder args for a render stage, via _shared/fast_encode (2026-08-03).

    ACQ standing rule: never hand-write `-c:v`. Six stages used to inline
    `h264_videotoolbox -b:v <N>M` with divergent bitrates and NO libx264 fallback
    (broken on any non-VideoToolbox host). This routes every stage through the one
    owner while PRESERVING each stage's existing bitrate explicitly — so the codec
    decision + software fallback are centralized with zero change to output size
    (fast_encode's resolution tiers would jump 4K intermediates 20M->50M and blow up
    the stage cache, which is a known disk-fill risk here).
    """
    if _fe_args is None:
        return ["-c:v", "h264_videotoolbox", "-b:v", bitrate, "-tag:v", "avc1",
                "-pix_fmt", "yuv420p"]
    if width is None or height is None:
        width, height = (_fe_probe(str(src)) if src and _fe_probe else (1080, 1920))
    return _fe_args(width, height, "ffmpeg", bitrate=bitrate)


def run(cmd, **kw):
    cmd = [str(c) for c in cmd]
    print("  $", " ".join(cmd[:8]) + (" ..." if len(cmd) > 8 else ""), flush=True)
    return subprocess.run(cmd, check=True, **kw)


def resolve_path(p: str | Path, project: Path) -> Path:
    """Resolve a config path. Absolute -> as-is. Relative -> under project root."""
    p = Path(p)
    return p if p.is_absolute() else (project / p)


def ffprobe_duration(p: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(p)], capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def ffprobe_fps(p: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                          "-show_entries", "stream=r_frame_rate", "-of", "csv=p=0", str(p)],
                         capture_output=True, text=True, check=True)
    num, den = out.stdout.strip().split("/")
    return float(num) / float(den)
