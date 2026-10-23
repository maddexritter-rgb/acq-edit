#!/usr/bin/env python3
"""/live-clip watcher — poll a channel until it goes live, then run the whole
autonomous pipeline: scaffold project → ingest → rolling transcribe → spawn the
Claude supervisor session (AUTOPILOT.md) → restart pieces that die.

  python3 live_watch.py --channel https://www.youtube.com/@AlexHormozi \
      [--brand alex] [--poll 60] [--until 22:00] [--supervisor-cmd claude]

Run it under caffeinate, detached (see start_liveclip_autopilot.sh). Exits after
one live stream has been fully processed, or at --until.
"""
from __future__ import annotations
import argparse, datetime, json, re, subprocess, sys, time
from pathlib import Path

SKILL = Path(__file__).parent
AUTOPILOT = SKILL.parent / "AUTOPILOT.md"


def log(msg: str) -> None:
    print(f"[{datetime.datetime.now():%H:%M:%S}] {msg}", flush=True)


def probe_live(channel: str) -> dict | None:
    """Return {url, id, title} if the channel is live right now, else None."""
    r = subprocess.run(
        ["yt-dlp", "--no-warnings", "--playlist-items", "1",
         "--print", "%(is_live)s\t%(webpage_url)s\t%(id)s\t%(title)s",
         f"{channel.rstrip('/')}/live"],
        capture_output=True, text=True, timeout=90)
    line = (r.stdout or "").strip().splitlines()
    if not line:
        return None
    parts = line[0].split("\t")
    if len(parts) == 4 and parts[0] == "True":
        return {"url": parts[1], "id": parts[2], "title": parts[3]}
    return None


def spawn(cmd: list[str], logfile: Path) -> subprocess.Popen:
    f = open(logfile, "a")
    return subprocess.Popen(cmd, stdout=f, stderr=f)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", required=True)
    ap.add_argument("--brand", default="alex")
    ap.add_argument("--poll", type=int, default=60)
    ap.add_argument("--until", default="22:00", help="give up at HH:MM local")
    ap.add_argument("--supervisor-cmd", default="claude")
    a = ap.parse_args()

    stop_h, stop_m = map(int, a.until.split(":"))
    log(f"watching {a.channel} for a live (until {a.until})")
    live = None
    while live is None:
        now = datetime.datetime.now()
        if (now.hour, now.minute) >= (stop_h, stop_m):
            log("hit --until with no live; exiting")
            return 1
        try:
            live = probe_live(a.channel)
        except Exception as e:
            log(f"probe error (will retry): {e}")
        if live is None:
            time.sleep(a.poll)

    slug = "Live" + re.sub(r"[^A-Za-z0-9]", "", live["title"])[:24]
    log(f"LIVE: {live['title']} ({live['url']}) → scaffolding {a.brand}/{slug}")
    r = subprocess.run(
        ["bash", str(Path("__ACQ_ASSETS__/scripts/new_project.sh")),
         a.brand, slug], capture_output=True, text=True)
    m = re.search(r"(/[^\s]+/\d{4}-\d{2}-\d{2}_[^\s/]+)", r.stdout + r.stderr)
    proj = Path(m.group(1)) if m else \
        Path.home() / "Downloads" / a.brand / f"{datetime.date.today()}_{slug}"
    work = proj / "10_WORK" / "live"
    work.mkdir(parents=True, exist_ok=True)
    (work / "live_info.json").write_text(json.dumps(
        {**live, "proj": str(proj)}, indent=1))
    log(f"project: {proj}")

    ingest = spawn(["python3", str(SKILL / "live_ingest.py"), "live",
                    live["url"], "--work", str(work)], work / "watch_ingest.log")
    transcribe = spawn(["python3", str(SKILL / "live_transcribe.py"),
                        "--work", str(work), "--watch"],
                       work / "watch_transcribe.log")

    prompt = (f"Read {AUTOPILOT} and follow it exactly. WORK={work} PROJ={proj} "
              f"LIVE_URL={live['url']}. Loop until INGEST_DONE exists and every "
              f"detected segment is built or held, then finish per the doc.")
    restarts = 0
    while True:
        log(f"spawning supervisor (attempt {restarts + 1})")
        sup = subprocess.run(
            [a.supervisor_cmd, "-p", prompt, "--dangerously-skip-permissions"],
            cwd=str(proj), capture_output=True, text=True)
        (work / f"supervisor_{restarts}.log").write_text(
            sup.stdout[-200000:] + "\n--- STDERR ---\n" + sup.stderr[-20000:])
        done = (work / "chunks" / "INGEST_DONE").exists()
        segs = work / "segments.json"
        pending = False
        if segs.exists():
            try:
                pending = any(s.get("status") == "detected"
                              for s in json.loads(segs.read_text()).get("segments", []))
            except Exception:
                pending = True
        if done and not pending:
            log("stream processed; watcher done")
            break
        restarts += 1
        if restarts > 6:
            log("supervisor kept dying (6 restarts) — giving up, footage is safe in chunks/")
            break
        time.sleep(30)

    for p in (ingest, transcribe):
        if p.poll() is None:
            p.wait(timeout=600)
    return 0


if __name__ == "__main__":
    sys.exit(main())
