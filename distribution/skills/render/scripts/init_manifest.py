#!/usr/bin/env python3
"""init_manifest — scaffold a manifest.json + empty source files for a project.

Looks at the project's 00_SOURCE/ and 10_WORK/ to guess defaults, writes a manifest.json + an
empty cuts.json template, and (optionally) a captions.ass placeholder. Idempotent: refuses to
overwrite an existing manifest.json unless --force.

Usage:
    python3 init_manifest.py <project_dir> --pipeline listicle [--title slug] [--force]
"""
from __future__ import annotations

import argparse, json, sys
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parent.parent
PIPELINES_DIR = SKILL_DIR / "pipelines"


def find_master(source_dir: Path) -> Path | None:
    """Find the biggest .mp4 / .mov under 00_SOURCE/, preferring CAMA/UHD-named files."""
    cands = []
    for p in source_dir.rglob("*"):
        if p.suffix.lower() not in (".mp4", ".mov", ".mxf"): continue
        score = p.stat().st_size
        name = p.name.upper()
        if "UHD" in name or "4K" in name or "CAMA" in name: score *= 10
        cands.append((score, p))
    if not cands: return None
    return sorted(cands)[-1][1]


def find_proxy(work_dir: Path) -> Path | None:
    for name in ("proxy_lav_720.mp4", "proxy.mp4", "proxy_1080.mp4"):
        p = work_dir / name
        if p.exists(): return p
    return None


def relpath(p: Path, base: Path) -> str:
    try: return str(p.relative_to(base))
    except ValueError: return str(p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project", type=Path, help="Project root (must contain 00_SOURCE/)")
    ap.add_argument("--pipeline", default="listicle", help=f"Pipeline name from {PIPELINES_DIR.name}/")
    ap.add_argument("--title", default=None, help="Title slug (defaults to project folder name slug)")
    ap.add_argument("--force", action="store_true", help="Overwrite an existing manifest.json")
    a = ap.parse_args()

    project = a.project.resolve()
    if not project.exists() or not project.is_dir():
        sys.exit(f"ERROR: {project} is not a directory")

    manifest_path = project / "manifest.json"
    if manifest_path.exists() and not a.force:
        sys.exit(f"ERROR: manifest.json exists at {manifest_path} (use --force to overwrite)")

    pipeline_path = PIPELINES_DIR / f"{a.pipeline}.json"
    if not pipeline_path.exists():
        sys.exit(f"ERROR: no pipeline {a.pipeline} at {pipeline_path}")

    source_dir = project / "00_SOURCE"
    work_dir = project / "10_WORK"
    source_dir.mkdir(exist_ok=True)
    work_dir.mkdir(exist_ok=True)

    master = find_master(source_dir)
    proxy = find_proxy(work_dir)

    title = a.title or project.name.split("_", 1)[-1] if "_" in project.name else project.name

    # Per-pipeline manifest skeletons. Keep these minimal; user fills in specifics.
    if a.pipeline in ("listicle", "single"):
        preset = "alex-listicle"
    elif a.pipeline == "qa":
        preset = "alex-stage"
    else:
        preset = "alex-listicle"

    # LOCKED 2026-06-11 (StayInAGreatMood) — single-cam Alex desk/talking-head defaults so a clip
    # comes out right the FIRST time. Q&A/multicam keeps the per-angle layout analyzer ON.
    ALEX_SPICE58 = str(SKILL_DIR.parent / "caption-clips" / "presets" / "spice_alex58.json")
    single_cam = a.pipeline in ("listicle", "single")
    if single_cam:
        reframe_cfg  = {"preset": preset, "zoom": 1.4, "eye_y": 0.30, "res": "4k"}
        captions_cfg = {"preset": ALEX_SPICE58, "no_layout": True}  # static y≈58 (tank-top/mic line); see edit/SKILL.md locked recipe
        leadfix_cfg  = {"head_trim": 0.0}   # cut starts on the word; bump ~0.08 only if a lead beat
    else:  # qa / multicam
        reframe_cfg  = {"preset": preset, "zoom": 1.6, "res": "4k"}
        captions_cfg = {"context": None}    # layout analyzer ON (per-angle height); set "context" for guest-color hint
        leadfix_cfg  = {"head_trim": 0.063605}

    manifest = {
        "title": title,
        "pipeline": a.pipeline,
        "stages": {
            "cut": {
                "source_video": relpath(master, project) if master else "00_SOURCE/<MASTER>.mp4",
                "source_audio": relpath(proxy, project) if proxy else "10_WORK/proxy_lav_720.mp4",
                "spec":         "10_WORK/cuts.json",
            },
            "reframe": reframe_cfg,
            "grade": {"filter": "eq=contrast=1.06:saturation=1.08:gamma=0.98,colorbalance=rm=0.015:gm=-0.022:bm=-0.035"},
            "captions": captions_cfg,  # spice via spice_caption (re-transcribes cut audio); IGNORES any .ass — caption Y comes from the preset
            "mix": {
                "music":      "<music skill winner — approved-only, clip brief + semantic/acoustic match>",
                "voice_lufs": -16, "music_lufs": -30,
                "fade_in":     1.0, "fade_out": 1.5, "limiter": 0.45,
            },
            "leadfix": leadfix_cfg,
        },
        "output": {"name": f"<ACQ_NAME>_{title}_Maddex_<YYYYMMDD>_V1.mp4", "dir": "20_DELIVER"},
    }
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print(f"wrote {manifest_path}")

    cuts_path = work_dir / "cuts.json"
    if not cuts_path.exists():
        cuts_path.write_text(json.dumps({"segments": [
            {"in": 0.0, "out": 0.0, "text": "fill me in", "label": "hook"}
        ]}, indent=2))
        print(f"wrote {cuts_path} (empty template — fill segments)")

    # NOTE: no captions.ass is scaffolded anymore. Captions are GENERATED from the cut clip's own
    # audio at render time by the captions stage (spice_caption.py -> generate_spice --burn: the locked
    # two-layer gblur spice shadow + per-word color). The old hand-styled placeholder .ass was the
    # source of the wrong, shadow-less captions in /edit — removed so it can't be burned by mistake.

    print()
    print("Next steps:")
    print(f"  1. Edit {cuts_path.name} — fill segments[] with hand-picked in/out times")
    print(f"  2. (captions auto-generate from the cut's audio — locked spice style; "
          f"set stages.captions.context for a Q&A guest-color hint)")
    print(f"  3. Set music path + output.name in manifest.json")
    print(f"  4. Render:  python3 __ACQ_SKILLS__/render/engine.py {project}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
