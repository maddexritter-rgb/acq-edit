#!/usr/bin/env python3
"""ACQ FAST-RENDER STANDARD — single source of truth for video encoder args (locked 2026-06-05).

Apple Silicon has dedicated hardware video encoders (VideoToolbox). On Maddex's M3 Max,
`h264_videotoolbox` benchmarked ~4x faster than `libx264 -crf12 -preset slow` at 4K
(13.1s -> 3.0s for 8s of 2160x3840) at comparable file size — and it runs on the media
engine instead of pinning the CPU, which also frees cores for parallelism. USE IT for every
delivery / intermediate / proxy render. Reserve libx264 ONLY for a final archival master
where max quality-per-bit matters (tier='master').

Any video skill should call encoder_args() instead of hand-writing '-c:v libx264 ...':

    import sys, os; sys.path.insert(0, os.path.expanduser("__ACQ_SKILLS__/_shared"))
    from fast_encode import encoder_args
    cmd = [ffmpeg, ..., *encoder_args(width, height, ffmpeg, tier="delivery"), "-c:a","aac", out]

Env overrides (flip behaviour without code edits):
    ACQ_ENCODER=x264   force software libx264 everywhere
    ACQ_ENCODER=vt     force VideoToolbox everywhere (even master)
    ACQ_FAST=0         alias for ACQ_ENCODER=x264
"""
import os
import subprocess
from functools import lru_cache


@lru_cache(maxsize=8)
def _has_vt(ffmpeg: str) -> bool:
    try:
        out = subprocess.run([ffmpeg, "-hide_banner", "-encoders"],
                             capture_output=True, text=True, timeout=15).stdout
        return "h264_videotoolbox" in out
    except Exception:
        return False


def _bitrate_for(width: int, height: int) -> str:
    """Resolution-aware VBR target. Generous on purpose — most of these are intermediates
    that get re-encoded downstream, so we protect against generational loss."""
    px = int(width) * int(height)
    if px >= 7_000_000:   # 4K (2160x3840 / 3840x2160)
        return "50M"
    if px >= 3_000_000:   # ~1440
        return "24M"
    if px >= 1_500_000:   # 1080x1920 / 1920x1080
        return "14M"
    return "8M"


@lru_cache(maxsize=64)
def probe_size(path: str, ffmpeg: str = "ffmpeg") -> tuple[int, int]:
    """Return (width, height) of the first video stream in path, or (1080, 1920) as a
    sensible 9:16 short-form fallback if probing fails. Cached per path."""
    # Derive ffprobe from the BASENAME only. A global str-replace would corrupt a parent
    # dir like ".../ffmpeg-full/.../bin/ffmpeg" into a bogus ".../ffprobe-full/...",
    # silently breaking the probe -> falling back to 1080p bitrate even for 4K sources.
    _b = os.path.basename(ffmpeg)
    if "ffmpeg" in _b:
        ffprobe = os.path.join(os.path.dirname(ffmpeg), _b.replace("ffmpeg", "ffprobe"))
    else:
        ffprobe = "ffprobe"
    try:
        out = subprocess.run([ffprobe, "-v", "error", "-select_streams", "v:0",
                              "-show_entries", "stream=width,height",
                              "-of", "csv=s=x:p=0", path],
                             capture_output=True, text=True, timeout=15).stdout.strip()
        w, h = out.split("x")[:2]
        return int(w), int(h)
    except Exception:
        return (1080, 1920)


def encoder_args_for(input_path: str, ffmpeg: str = "ffmpeg", *, tier="delivery",
                      crf=18, bitrate=None):
    """encoder_args() but auto-probe width/height from input_path. Convenience for callers
    that don't already know the output dimensions (most common case)."""
    w, h = probe_size(input_path, ffmpeg)
    return encoder_args(w, h, ffmpeg, tier=tier, crf=crf, bitrate=bitrate)


def encoder_args(width, height, ffmpeg, *, tier="delivery", crf=18, bitrate=None):
    """ffmpeg video-codec args for an output.

    tier: 'delivery' | 'intermediate' | 'proxy'  -> VideoToolbox (hardware, ~4x faster)
          'master'                                -> libx264 (slow, max quality-per-bit)
    Honors ACQ_ENCODER / ACQ_FAST env overrides; falls back to libx264 if VideoToolbox absent.
    """
    force = os.environ.get("ACQ_ENCODER", "").lower()
    if os.environ.get("ACQ_FAST") == "0":
        force = "x264"
    want_vt = (force == "vt") or (tier != "master" and force != "x264")
    if want_vt and _has_vt(ffmpeg):
        br = bitrate or _bitrate_for(width, height)
        return ["-c:v", "h264_videotoolbox", "-b:v", br, "-tag:v", "avc1", "-pix_fmt", "yuv420p"]
    preset = "slow" if tier == "master" else "medium"
    return ["-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-pix_fmt", "yuv420p"]
