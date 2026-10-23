"""cut — read cuts.json (list of {in, out}), cut each segment from source video + source audio,
concat with re-encode. Output: one 16:9 mp4 with segments back-to-back, no reframe, no captions.

Cuts.json format:
    {
      "segments": [{"in": 390.32, "out": 392.64}, ...]
    }
    (Extra keys like "text"/"label"/"n"/"cat" are preserved as meta but not used here.)

Config (manifest.stages.cut):
    {
      "source_video": "00_SOURCE/CAMA/master.mp4",
      "source_audio": "10_WORK/proxy_lav_720.mp4",
      "spec":         "10_WORK/cuts.json"
    }
"""
from __future__ import annotations

import json
from pathlib import Path

from _util import run as ff, resolve_path, ffprobe_fps, venc

import os as _os, sys as _sys
try:
    _SHARED = str(Path(__file__).resolve().parents[2] / "_shared")
    if _SHARED not in _sys.path:
        _sys.path.insert(0, _SHARED)
    import snap_silence as _snap
except Exception:
    _snap = None

VERSION = "1.4.0"  # 1.4.0: no_head_snap keeps segment-0 in-point exact (3-frames-before-hook); internal seams still snap
                   #        + 12ms fade-out per seam = clean splices BY DEFAULT (no mid-word cut/pop), not
                   #        just gated by audit-audio. Falls back to the raw boundary if snap fails/degenerate;
                   #        disable via config "snap_silence": false. (Janko159 → make the cutter safe, not just caught.)
# 1.2.0: per-segment source_video/source_audio override (multi-source supercut).
# 1.1.0: segment boundaries MEASURED per segment file (round(cum_t*fps) drifted
                   # vs ffmpeg's pts<t frame semantics — off-by-1 per seam, so reframe's tracker
                   # reset / split-section extraction landed a frame early; found 2026-06-12)


def run(work_dir, config, inputs, inputs_meta, project, manifest, out_path):
    src_v = resolve_path(config["source_video"], project)
    src_a = resolve_path(config["source_audio"], project)
    spec_path = resolve_path(config["spec"], project)
    spec = json.loads(spec_path.read_text())
    segments = spec["segments"]

    seg_dir = out_path.parent / f"{out_path.stem}_segments"
    seg_dir.mkdir(exist_ok=True)
    seg_files = []
    durs = []

    do_snap = config.get("snap_silence", True) and _snap is not None
    for i, s in enumerate(segments):
        in_t = float(s["in"]); out_t = float(s["out"])
        # Per-segment source override: a segment may name its OWN source_video/source_audio
        # (a different file) so one clip can assemble moments from several source files — e.g. a
        # supercut pulling moments from far-apart points of the same talk, each downloaded separately.
        # in/out are relative to THAT segment's source. Falls back to the stage-level source.
        seg_v = resolve_path(s["source_video"], project) if s.get("source_video") else src_v
        seg_a = resolve_path(s["source_audio"], project) if s.get("source_audio") else src_a
        # SNAP each boundary to inter-word SILENCE so splices land clean BY DEFAULT (no mid-word chop,
        # no pop) — not just caught by audit-audio after the fact. Acoustic-only (no transcript), fast
        # ffmpeg-seek. GUARDED: any failure or a degenerate (<0.1s) result keeps the raw boundary, so
        # this can never break a render — worst case it behaves exactly like before.
        # no_head_snap: keep the FIRST segment's in-point EXACT (don't snap it to a nearby silence).
        # The snap is great for internal seams, but on segment 0 it drifts the clip start into the
        # dead space before the hook (or past the hook words). When the in-point is hand-set to
        # "3 frames before the hook word", honor it verbatim. (2026-06-28)
        freeze_in = (i == 0 and config.get("no_head_snap"))
        if do_snap:
            try:
                a = str(seg_a)
                si = in_t if freeze_in else _snap.snap_in(a, in_t)
                so = _snap.snap_out(a, out_t)
                if so - si > 0.1:
                    in_t, out_t = si, so
            except Exception:
                pass
        dur = round(out_t - in_t, 3)
        # Fade IN at the seam + (post-snap) fade OUT in the trailing silence — kills clicks/pops at joins.
        # The fade-out is safe ONLY because the cut now lands in silence; a blind fade-out on a mid-word
        # boundary clips the word (the documented trap), which is why it pairs with the snap above.
        # ≥12ms both edges (playbook law: 6-8ms is too short and leaves clicks at seams;
        # raised from 0.008 on 2026-08-03 to match CLIP_CUTTING_PLAYBOOK / faded_trim_cut)
        fade = "afade=t=in:d=0.012"
        if dur > 0.05:
            fade += f",afade=t=out:st={max(0.0, dur - 0.012):.3f}:d=0.012"
        seg = seg_dir / f"seg_{i:02d}.mp4"
        ff(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-ss", f"{in_t:.3f}", "-i", str(seg_v),
            "-ss", f"{in_t:.3f}", "-i", str(seg_a),
            "-t", f"{dur:.3f}",
            "-map", "0:v", "-map", "1:a",
            *venc("25M", src=seg_v),
            "-c:a", "aac", "-b:a", "192k",
            "-af", fade,
            "-movflags", "+faststart", str(seg)])
        seg_files.append(seg)
        durs.append(dur)

    # Concat with re-encode (never -c copy across segments — keyframe alignment differs)
    fc_inputs = []
    fc_streams = []
    for i, f in enumerate(seg_files):
        fc_inputs += ["-i", str(f)]
        fc_streams.append(f"[{i}:v:0][{i}:a:0]")
    fc = "".join(fc_streams) + f"concat=n={len(seg_files)}:v=1:a=1[v][a]"
    ff(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        *fc_inputs, "-filter_complex", fc, "-map", "[v]", "-map", "[a]",
        *venc("20M", src=seg_files[0]),
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out_path)])

    fps = ffprobe_fps(out_path)
    # Boundaries from MEASURED per-segment frame counts, not round(cum_t*fps): ffmpeg's -t keeps
    # frames with pts < t (effectively ceil), so the arithmetic boundary drifts 1 frame per seam
    # and downstream consumers (reframe --cut-frames resets, split-section extraction) cut a frame
    # early. Counting each segment file is exact by construction.
    import subprocess as _sp
    boundaries = []
    cum_f = 0
    for d, f in zip(durs, seg_files):
        out = _sp.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames",
                       "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", str(f)],
                      capture_output=True, text=True, check=True)
        n = int(out.stdout.strip())
        boundaries.append({"in_frame": cum_f, "out_frame": cum_f + n, "duration_s": d})
        cum_f += n

    return {"out": str(out_path), "meta": {
        "fps": fps,
        "total_duration_s": round(sum(durs), 3),
        "segments": boundaries,
        "segments_dir": str(seg_dir),
        "segment_files": [str(f) for f in seg_files],
    }}
