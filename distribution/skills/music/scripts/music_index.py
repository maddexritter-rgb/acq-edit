#!/usr/bin/env python3
"""music_index.py — librosa vibe-feature index for a music library, so beds are picked by MEASURED
sound, not filename guessing. Per track: tempo(BPM), energy(RMS), brightness(spectral centroid Hz),
perc_ratio(groove vs atmospheric), onset_density(busy vs sparse), mode(major/minor) -> a coarse vibe
bucket. Honors <root>/_BLACKLIST.txt (marks banned=true). Brand-agnostic; reusable.

Usage: music_index.py <music_folder> [--out <index.json>] [--seconds 45] [--workers N]
Output JSON keyed by filename: {path, folder, banned, vibe, tempo, energy, brightness, perc_ratio,
onset_density, mode, major_corr, minor_corr, duration}.
"""
import sys, json, os, argparse
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
import numpy as np

# Krumhansl-Schmuckler key profiles (for a rough major/minor = brighter/sadder read)
MAJ = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
MIN = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])


def _features(y, sr):
    import librosa
    tempo = float(np.atleast_1d(librosa.beat.beat_track(y=y, sr=sr)[0])[0])
    rms = float(np.mean(librosa.feature.rms(y=y)))
    cent = float(np.mean(librosa.feature.spectral_centroid(y=y, sr=sr)))
    yh, yp = librosa.effects.hpss(y)
    pr = float((np.mean(np.abs(yp)) + 1e-9) / (np.mean(np.abs(yh)) + np.mean(np.abs(yp)) + 1e-9))
    od = float(np.mean(librosa.onset.onset_strength(y=y, sr=sr)))
    ch = np.mean(librosa.feature.chroma_cqt(y=y, sr=sr), axis=1)
    cmaj = max(np.corrcoef(np.roll(MAJ, i), ch)[0, 1] for i in range(12))
    cmin = max(np.corrcoef(np.roll(MIN, i), ch)[0, 1] for i in range(12))
    return dict(tempo=round(tempo, 1), energy=round(rms, 4), brightness=round(cent),
                perc_ratio=round(pr, 3), onset_density=round(od, 3),
                mode="major" if cmaj >= cmin else "minor",
                major_corr=round(float(cmaj), 3), minor_corr=round(float(cmin), 3))


def analyze(path, seconds=24):
    import librosa
    try:
        dur = librosa.get_duration(path=path)
        window = min(seconds, max(8, dur))
        starts = sorted(set(round(max(0, min(dur-window, x)), 2)
                            for x in (0, dur*.22, dur*.48, dur*.72)))
        segments = []
        for start in starts:
            y, sr = librosa.load(path, sr=22050, mono=True, offset=start, duration=window)
            if len(y) >= sr * 2:
                segments.append({"start": start, **_features(y, sr)})
        if not segments:
            return {"error": "too short"}
        middle = segments[len(segments)//2]
        return {**{k:v for k,v in middle.items() if k != "start"},
                "duration": round(dur, 1), "segments": segments}
    except Exception as e:
        return {"error": str(e)[:140]}


def vibe(f):
    """Coarse bucket from features. CALIBRATE thresholds against the user's approve/reject over time;
    the 'sad-sparse' lane (slow + sparse + minor) is the one to avoid for Alex reflective clips."""
    if not f or "error" in f:
        return "unknown"
    t, e, b, pr, od, m = (f["tempo"], f["energy"], f["brightness"],
                          f["perc_ratio"], f["onset_density"], f["mode"])
    slow = t < 95
    sparse = (od < 1.4) or (e < 0.025)
    groovy = pr > 0.42 and od > 1.8
    if slow and sparse and m == "minor":
        return "sad-sparse"                 # AVOID lane for Alex
    if slow and sparse:
        return "reflective-calm"
    if t >= 115 and od > 2.3:
        return "uplifting-driving" if m == "major" else "confident-dark"
    if groovy:
        return "chill-groove"
    if m == "major" and not slow:
        return "warm-bright"
    return "warm-melodic"


def _job(args):
    path, seconds = args
    return path, analyze(path, seconds)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--out", default=None)
    ap.add_argument("--seconds", type=int, default=24)
    ap.add_argument("--workers", type=int, default=0)
    a = ap.parse_args()
    root = Path(a.folder).expanduser()
    out = Path(a.out) if a.out else root / "_music_index.json"
    bl = root / "_BLACKLIST.txt"
    blast = []
    if bl.exists():
        blast = [l.strip() for l in bl.read_text().splitlines()
                 if l.strip() and not l.strip().startswith("#")]
    mp3s = [p for p in root.rglob("*.mp3") if not p.name.startswith("._")]
    print(f"{len(mp3s)} tracks under {root}", flush=True)
    workers = a.workers or max(2, (os.cpu_count() or 4) - 1)
    index = {}
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(_job, (str(p), a.seconds)): p for p in mp3s}
        done = 0
        for fut in as_completed(futs):
            path, f = fut.result(); p = Path(path); done += 1
            # Relative paths are stable and collision-free. Filename-only keys silently
            # overwrote same-named tracks in different lanes.
            index[str(p.relative_to(root))] = {"path": str(p), "folder": p.parent.name,
                             "banned": any(b.lower() in p.name.lower() for b in blast),
                             "vibe": vibe(f), **(f or {})}
            if done % 25 == 0:
                print(f"  {done}/{len(mp3s)}", flush=True)
    json.dump(index, open(out, "w"), indent=1)
    from collections import Counter
    ok = {k: v for k, v in index.items() if "error" not in v}
    print("VIBES:", dict(Counter(v["vibe"] for v in ok.values())), flush=True)
    print(f"errors: {len(index)-len(ok)}  wrote {out}", flush=True)


if __name__ == "__main__":
    main()
