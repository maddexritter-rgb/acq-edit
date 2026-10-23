#!/usr/bin/env python3
"""/live-clip segment extraction — pull one completed interaction out of the
chunk stream as a standalone media file for Premiere.

  python3 live_extract.py --work <dir> --t0 843.2 --t1 1290.5 \
      --slug PricingCaller --out-dir <proj>/10_WORK/live_segments

Whole covering chunks are concatenated with stream copy (no re-encode, no -ss),
so the extracted file's absolute start time is EXACTLY the first chunk's t0 —
frame math stays honest and the extra head/tail (< one chunk) is simply media
Premiere never uses. Emits <slug>.mp4 + <slug>.json {media_start, t0, t1}.
"""
from __future__ import annotations
import argparse, json, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from live_common import update_manifest, chunks_covering


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True)
    ap.add_argument("--t0", type=float, required=True)
    ap.add_argument("--t1", type=float, required=True)
    ap.add_argument("--slug", required=True)
    ap.add_argument("--out-dir", required=True)
    a = ap.parse_args()
    work = Path(a.work).expanduser()
    out_dir = Path(a.out_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)

    man = update_manifest(work)
    cover = chunks_covering(man, a.t0, a.t1)
    if not cover:
        sys.exit(f"no chunks cover [{a.t0}, {a.t1}]")
    if cover[-1]["t1"] < a.t1:
        sys.exit(f"range end {a.t1:.1f}s not fully ingested yet "
                 f"(have up to {cover[-1]['t1']:.1f}s) — segment still too "
                 f"close to the live edge, retry next cycle")

    lst = out_dir / f"{a.slug}.concat.txt"
    lst.write_text("".join(f"file '{work / 'chunks' / c['file']}'\n"
                           for c in cover))
    out_mp4 = out_dir / f"{a.slug}.mp4"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-c", "copy", "-movflags", "+faststart", str(out_mp4)],
                   check=True)
    lst.unlink()

    meta = {"media_start": cover[0]["t0"], "t0": a.t0, "t1": a.t1,
            "chunks": [c["file"] for c in cover]}
    (out_dir / f"{a.slug}.json").write_text(json.dumps(meta, indent=1))
    print(json.dumps({"media": str(out_mp4), **meta}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
