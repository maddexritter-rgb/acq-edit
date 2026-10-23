#!/usr/bin/env python3
"""clip_meta — resolve render-pipeline metadata for a delivered clip.

The audit gates (audit-visual / audit-audio / audit-captions) use this to become
seam-aware and music-aware without any brand-specific knowledge. Everything is
resolved from artifacts the render engine already emits:

  - clip.contract.json   (next to the delivered mp4)
  - manifest.json        (at the clip's project root)
  - 10_WORK/stages/cut/<hash>.meta.json  (segment boundaries on the output timeline)
  - 10_WORK/captions_work/*.ass          (the caption source that got burnt)

All fields degrade to None / [] when an artifact is missing, so a foreign clip
(no contract, no manifest) still audits — the gates just fall back to
content-only analysis.

Usage:
    from clip_meta import resolve
    meta = resolve("/path/to/20_DELIVER/v1/CLIP.mp4")
    meta["seam_times"]    # [9.46, 12.16, ...] cut boundaries, delivered timeline
    meta["music_path"]    # declared music bed, or None
"""

import json
import os
from pathlib import Path


def _load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None


def _find_project_dir(clip_path: Path, contract: dict | None) -> Path | None:
    """Project root = the folder holding manifest.json + 10_WORK for this clip."""
    if contract:
        pd = contract.get("source", {}).get("project_dir")
        if pd and Path(pd).is_dir():
            return Path(pd)
    # Walk up from the clip: 20_DELIVER/v1/clip.mp4 -> project root is 2-3 up
    for parent in list(clip_path.parents)[:4]:
        if (parent / "manifest.json").exists() and (parent / "10_WORK").is_dir():
            return parent
    return None


def _newest(paths):
    paths = [p for p in paths if p.exists()]
    return max(paths, key=lambda p: p.stat().st_mtime) if paths else None


def _resolve_segments(project_dir: Path | None, head_trim: float):
    """Segment spans on the DELIVERED timeline from the newest cut-stage meta.

    Returns (segments, fps) where segments = [{"start_s", "end_s"}, ...].
    The cut meta's in_frame/out_frame are output-timeline frame indices;
    cumulative duration_s is the authoritative seam clock. leadfix head_trim
    shifts everything earlier.
    """
    if not project_dir:
        return [], None
    cut_dir = project_dir / "10_WORK" / "stages" / "cut"
    meta_file = _newest(list(cut_dir.glob("*.meta.json"))) if cut_dir.is_dir() else None
    if not meta_file:
        return [], None
    data = _load_json(meta_file) or {}
    m = data.get("meta", {})
    segs_raw = m.get("segments", [])
    fps = m.get("fps")
    segments = []
    t = 0.0
    for s in segs_raw:
        d = float(s.get("duration_s", 0))
        start = max(0.0, t - head_trim)
        end = max(0.0, t + d - head_trim)
        if end > start:
            segments.append({"start_s": round(start, 3), "end_s": round(end, 3)})
        t += d
    return segments, fps


def _resolve_ass(clip_path: Path, project_dir: Path | None, manifest: dict | None):
    """Best-guess path to the .ass that was burnt onto this clip."""
    sidecar = clip_path.with_suffix(".ass")
    if sidecar.exists():
        return sidecar
    if project_dir:
        cw = project_dir / "10_WORK" / "captions_work"
        if cw.is_dir():
            preferred = cw / "subs.ass"
            if preferred.exists():
                return preferred
            newest = _newest(list(cw.glob("*.ass")))
            if newest:
                return newest
        newest = _newest(list((project_dir / "10_WORK").glob("*.ass")))
        if newest:
            return newest
    return None


def resolve(clip: str) -> dict:
    clip_path = Path(clip).resolve()
    contract = _load_json(clip_path.parent / "clip.contract.json")
    project_dir = _find_project_dir(clip_path, contract)
    manifest = _load_json(project_dir / "manifest.json") if project_dir else None

    stages = (manifest or {}).get("stages", {})
    head_trim = float(stages.get("leadfix", {}).get("head_trim", 0) or 0)

    music_path = stages.get("mix", {}).get("music")
    if not music_path and contract:
        music_path = (contract.get("declared", {}).get("music") or {}).get("path")

    mix = stages.get("mix", {})
    declared = (contract or {}).get("declared", {})

    segments, fps = _resolve_segments(project_dir, head_trim)
    seam_times = [s["start_s"] for s in segments[1:]]

    return {
        "clip": str(clip_path),
        "contract": contract,
        "project_dir": str(project_dir) if project_dir else None,
        "manifest": manifest,
        "segments": segments,
        "seam_times": seam_times,
        "fps": fps,
        "head_trim": head_trim,
        "music_path": music_path,
        "music_fade_out": float(mix.get("fade_out", 0) or 0),
        "voice_lufs": mix.get("voice_lufs"),
        "music_lufs": mix.get("music_lufs"),
        "speakers": declared.get("speakers"),
        "ass_path": str(_resolve_ass(clip_path, project_dir, manifest) or "") or None,
        "has_metadata": bool(contract or manifest or segments),
    }


if __name__ == "__main__":
    import sys
    print(json.dumps(resolve(sys.argv[1]), indent=2, default=str))
