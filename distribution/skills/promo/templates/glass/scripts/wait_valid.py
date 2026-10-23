#!/usr/bin/env python3
"""Wait for a media file to finish writing, then validate it (promo MODE B helper).

When a cut is still uploading / exporting (Drive sync, export-in-progress), its
size grows and the moov atom isn't written yet -> ffprobe says "moov atom not
found". Run this FIRST on any freshly-dropped cut before you touch it; it returns
only once the file size is stable AND ffprobe can read a duration.

  python3 wait_valid.py "/path/to/Cut.mp4" [max_seconds=900]
"""
import subprocess, sys, time, os

if len(sys.argv) < 2:
    print("usage: wait_valid.py <file> [max_seconds]"); sys.exit(1)
path = sys.argv[1]
deadline = time.time() + (float(sys.argv[2]) if len(sys.argv) > 2 else 900)

prev, stable = -1, 0
while time.time() < deadline:
    try:
        cur = os.path.getsize(path)
    except OSError:
        cur = 0
    stable = stable + 1 if (cur == prev and cur > 0) else 0
    prev = cur
    if stable >= 3:                              # ~9s of no growth
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                            "-of", "csv=p=0", path], capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            print(f"READY  size={cur} bytes  dur={r.stdout.strip()}s"); sys.exit(0)
    time.sleep(3)
print(f"TIMEOUT  last size={prev} bytes (still writing or unreadable)"); sys.exit(1)
