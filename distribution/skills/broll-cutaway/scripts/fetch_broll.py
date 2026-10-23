#!/usr/bin/env python3
"""Source cinematic B-roll via yt-dlp -- search the catalog, then download a 4K video-only chunk.

THEN VERIFY BY EYE before using anything (premium/cinematic is a human call -- you cannot
automate it). Build a contact sheet and look:
  python3 __ACQ_SKILLS__/watch/scripts/contact_sheet.py <file> --n 16 --cols 4   # open the PNG

  fetch_broll.py --search "cinematic money cash b-roll 4k" --n 6        # list candidates
  fetch_broll.py --id ZJCLFhhzmts --sections "*0-90" --out money_src    # download a 4K chunk

Notes:
  - video-only (bv*) -- you don't need the source audio for a cutaway.
  - reject stocky / watermarked (Envato/Shutterstock/iStock) / low-res results on sight.
  - --sections "*START-END" (yt-dlp) keeps the download small; grab a generous window then trim
    the exact in-point later with insert_broll.py's `in=`.
"""
import argparse
import subprocess
import sys


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--search", help="search query (lists candidates: duration | title | id)")
    p.add_argument("--n", type=int, default=6)
    p.add_argument("--id", help="video id to download")
    p.add_argument("--sections", default="*0-90", help='yt-dlp download-sections, e.g. "*0-90"')
    p.add_argument("--out", default="broll_src", help="output basename (ext auto)")
    p.add_argument("--maxh", type=int, default=2160, help="max source height (default 4K)")
    a = p.parse_args()

    if a.search:
        subprocess.run(["yt-dlp", "--no-warnings", f"ytsearch{a.n}:{a.search}",
                        "--print", "%(duration)ss | %(title).70s | %(id)s", "--skip-download"])
    elif a.id:
        subprocess.run(["yt-dlp", "--no-warnings",
                        "-f", f"bv*[height<={a.maxh}]/bv*",
                        "--download-sections", a.sections,
                        "-o", f"{a.out}.%(ext)s", a.id])
    else:
        sys.exit("use --search QUERY or --id VIDEO_ID")


if __name__ == "__main__":
    main()
