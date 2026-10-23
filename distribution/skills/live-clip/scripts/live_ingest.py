#!/usr/bin/env python3
"""/live-clip ingest loop — turn a running YouTube livestream (or a local file,
for dry runs) into a stream of closed, playable MPEG-TS chunks.

LIVE mode (the real thing):
  python3 live_ingest.py live <youtube-url> --work <dir> [--chunk 120]
    Resolves the live's from-start HLS manifest and segments it with ffmpeg.
    Primary path: yt-dlp -g for a muxed m3u8 + ffmpeg -live_start_index 0.
    Fallback (--pipe): yt-dlp --live-from-start -f b -o - piped into ffmpeg.
    Stays ~1 chunk behind the live edge by construction (a chunk is only read
    once the next one exists), so incomplete fragments are never touched.

SIMULATE mode (dry run against an already-downloaded stream):
  python3 live_ingest.py simulate <recording.mp4> --work <dir> [--speed 30] [--dur 600]
    Same segmenter, same output layout — ffmpeg -readrate <speed> replays the
    recording as if it were arriving live. Everything downstream is identical.

Writes: <work>/chunks/seg_%05d.ts, <work>/chunks/INGEST_DONE on clean end,
        <work>/ingest.log
Detached-friendly: run under nohup/caffeinate for a real live.
"""
from __future__ import annotations
import argparse, os, shlex, subprocess, sys
from pathlib import Path


def segment_cmd(inp: list[str], chunk: int, chunks_dir: Path) -> list[str]:
    return ["ffmpeg", "-hide_banner", "-loglevel", "warning", *inp,
            "-c", "copy", "-f", "segment",
            "-segment_time", str(chunk),
            "-reset_timestamps", "1",
            str(chunks_dir / "seg_%05d.ts")]


def resolve_hls(url: str) -> str | None:
    """Best muxed HLS manifest for the live (yt-dlp -g)."""
    for fmt in ("best[protocol*=m3u8][height<=1080]", "best[protocol*=m3u8]"):
        r = subprocess.run(["yt-dlp", "-g", "-f", fmt, url],
                           capture_output=True, text=True)
        line = r.stdout.strip().splitlines()
        if r.returncode == 0 and line and ".m3u8" in line[0]:
            return line[0]
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["live", "simulate"])
    ap.add_argument("source", help="YouTube live URL, or local recording for simulate")
    ap.add_argument("--work", required=True)
    ap.add_argument("--chunk", type=int, default=120, help="target chunk seconds")
    ap.add_argument("--speed", type=float, default=30.0, help="simulate: x realtime")
    ap.add_argument("--dur", type=float, default=0, help="simulate: only first N secs")
    ap.add_argument("--pipe", action="store_true",
                    help="live: force yt-dlp pipe fallback instead of direct HLS")
    a = ap.parse_args()

    work = Path(a.work).expanduser()
    chunks = work / "chunks"
    chunks.mkdir(parents=True, exist_ok=True)
    done_flag = chunks / "INGEST_DONE"
    if done_flag.exists():
        done_flag.unlink()

    log = open(work / "ingest.log", "a")

    if a.mode == "simulate":
        # NOTE: this ffmpeg build clamps -readrate to ~1x, so >1 speeds don't
        # accelerate. speed=0 -> unthrottled (mechanical dry runs); speed=1 ->
        # true realtime rehearsal.
        rate = [] if a.speed == 0 else ["-readrate", str(a.speed)]
        inp = [*rate, "-i", a.source]
        if a.dur:
            inp = [*rate, "-t", str(a.dur), "-i", a.source]
        cmd = segment_cmd(inp, a.chunk, chunks)
        print("SIMULATE:", " ".join(shlex.quote(c) for c in cmd))
        rc = subprocess.run(cmd, stdout=log, stderr=log).returncode
        done_flag.touch()
        return rc

    # LIVE
    if not a.pipe:
        hls = resolve_hls(a.source)
        if hls:
            print(f"HLS from-start: {hls[:90]}...")
            cmd = segment_cmd(
                ["-live_start_index", "0", "-rw_timeout", "30000000", "-i", hls],
                a.chunk, chunks)
            rc = subprocess.run(cmd, stdout=log, stderr=log).returncode
            done_flag.touch()
            return rc
        print("No muxed HLS manifest found; falling back to yt-dlp pipe.", file=sys.stderr)

    ytdlp = subprocess.Popen(
        ["yt-dlp", "--live-from-start", "-f", "b", "--no-part",
         "--quiet", "-o", "-", a.source],
        stdout=subprocess.PIPE, stderr=log)
    ff = subprocess.run(segment_cmd(["-i", "pipe:0"], a.chunk, chunks),
                        stdin=ytdlp.stdout, stdout=log, stderr=log)
    ytdlp.wait()
    done_flag.touch()
    return ff.returncode


if __name__ == "__main__":
    sys.exit(main())
