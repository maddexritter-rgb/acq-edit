#!/usr/bin/env python3
"""Shared helpers for /live-clip: chunk manifest maintenance.

The ingest loop writes fixed-duration MPEG-TS chunks (seg_00000.ts, ...) into
<work>/chunks/. A chunk is CLOSED (safe to read) once the next-numbered chunk
exists, or once <work>/chunks/INGEST_DONE exists. The manifest maps each closed
chunk to its exact absolute stream-time span [t0, t1) via ffprobe duration —
segmenter cuts land on keyframes, so durations are NOT uniform and must be
measured, never assumed.
"""
from __future__ import annotations
import json, re, subprocess
from pathlib import Path

CHUNK_RE = re.compile(r"seg_(\d{5})\.ts$")


def ffprobe_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True).stdout.strip()
    return float(out)


def video_props(path: Path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height,r_frame_rate",
         "-of", "json", str(path)],
        capture_output=True, text=True, check=True).stdout
    s = json.loads(out)["streams"][0]
    num, den = s["r_frame_rate"].split("/")
    return {"width": s["width"], "height": s["height"],
            "fps": float(num) / float(den)}


def list_chunks(work: Path) -> list[Path]:
    return sorted((work / "chunks").glob("seg_*.ts"))


def closed_chunks(work: Path) -> list[Path]:
    chunks = list_chunks(work)
    if (work / "chunks" / "INGEST_DONE").exists():
        return chunks
    return chunks[:-1]  # last one may still be written


def load_manifest(work: Path) -> dict:
    mf = work / "manifest.json"
    if mf.exists():
        return json.loads(mf.read_text())
    return {"chunks": []}


def update_manifest(work: Path) -> dict:
    """Probe any newly-closed chunks, extend manifest, return it."""
    man = load_manifest(work)
    known = {c["file"] for c in man["chunks"]}
    t = man["chunks"][-1]["t1"] if man["chunks"] else 0.0
    for p in closed_chunks(work):
        if p.name in known:
            continue
        idx = int(CHUNK_RE.search(p.name).group(1))
        dur = ffprobe_duration(p)
        man["chunks"].append({"i": idx, "file": p.name,
                              "t0": round(t, 3), "t1": round(t + dur, 3)})
        t += dur
    (work / "manifest.json").write_text(json.dumps(man, indent=1))
    return man


def chunks_covering(man: dict, t0: float, t1: float) -> list[dict]:
    return [c for c in man["chunks"] if c["t1"] > t0 and c["t0"] < t1]
