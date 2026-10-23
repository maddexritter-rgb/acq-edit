#!/usr/bin/env python3
"""make_words.py — locked transcript -> cut/timeline_words.json, optionally lifting a 2nd speaker.

  python3 make_words.py <cut/locked_transcript.json> <out timeline_words.json>
  python3 make_words.py <locked> <out> --lift <word> --voice <VOICE_cut.wav> [--plan plan_v2.py]

🛑 ALWAYS build from locked_transcript.json, NEVER words_fmt.json — the formatted list silently
dropped a leading "If" on a shipped clip and the caption opened mid-sentence.

--lift removes a second speaker's interjection (a podcast host saying "Admission." reads terribly).
🛑 It does NOT trust the transcript's word boundaries — they were wrong by 300ms on a real clip
and the first cut removed a piece of the SUBJECT instead. It finds the silences that actually
bracket the interjection in the audio, and reports the span for you to apply to the media.
"""
import argparse, contextlib, json, subprocess, sys, wave
import numpy as np

SIL_DB = -55.0


def envelope(wav, t0, t1, hop=0.01):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t0:.3f}", "-t", f"{t1-t0:.3f}",
                    "-i", wav, "-ac", "1", "-ar", "16000", "/tmp/_env.wav"], check=True)
    with contextlib.closing(wave.open("/tmp/_env.wav")) as w:
        a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(float)
    n = int(16000 * hop)
    return [(t0 + k / 16000, 20 * np.log10((np.sqrt((a[k:k+n] ** 2).mean()) + 1e-9) / 32768))
            for k in range(0, max(len(a) - n, 0), n)]


def bracketing_silences(env, lo, hi):
    """The last silence before the loud block and the first silence after it, within [lo,hi]."""
    runs, cur = [], None
    for t, db in env:
        if db < SIL_DB:
            cur = [t, t] if cur is None else [cur[0], t]
        elif cur:
            runs.append(tuple(cur)); cur = None
    if cur: runs.append(tuple(cur))
    before = [r for r in runs if r[1] <= lo + 0.20]
    after = [r for r in runs if r[0] >= hi - 0.20]
    if not before or not after:
        return None
    return (sum(before[-1]) / 2, sum(after[0]) / 2)      # mid-silence on both sides


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("locked"); ap.add_argument("out")
    ap.add_argument("--lift"); ap.add_argument("--voice"); ap.add_argument("--pad", type=float, default=0.8)
    a = ap.parse_args()

    d = json.load(open(a.locked))
    ws = d if isinstance(d, list) else d.get("words", d)
    print(f"  {len(ws)} words from locked transcript")

    cin = cout = None
    if a.lift:
        if not a.voice: raise SystemExit("--lift needs --voice")
        hits = [w for w in ws if w["word"].strip(".,?!").lower() == a.lift.strip().lower()]
        if not hits: raise SystemExit(f"'{a.lift}' not in the transcript")
        h = hits[0]
        env = envelope(a.voice, max(0, h["start"] - a.pad), h["end"] + a.pad)
        span = bracketing_silences(env, h["start"], h["end"])
        if not span:
            print("  !! could not find silences bracketing it — cut by hand off the envelope", file=sys.stderr)
            for t, db in env: print(f"     {t:7.3f} {db:7.1f}", file=sys.stderr)
            raise SystemExit(2)
        cin, cout = span
        print(f"  '{a.lift}' transcript says {h['start']:.3f}-{h['end']:.3f}")
        print(f"  AUDIO says cut {cin:.3f} -> {cout:.3f}  ({cout-cin:.3f}s)   <- use THIS on the media")

    delta = (cout - cin) if cin is not None else 0.0
    def m(t): return t if cin is None or t <= cin else (cin if t < cout else round(t - delta, 3))

    out = []
    for w in ws:
        if a.lift and w["word"].strip(".,?!").lower() == a.lift.strip().lower():
            continue
        t0, t1 = m(w["start"]), m(w["end"])
        if t1 - t0 < 0.02: t1 = t0 + 0.04
        out.append({"word": w["word"], "t0": round(t0, 3), "t1": round(t1, 3)})
    json.dump(out, open(a.out, "w"), indent=1)

    print(f"  wrote {len(out)} words -> {a.out}")
    print(f"  opens: \"{' '.join(x['word'] for x in out[:9])}\"")
    if cin is not None:
        print(f"\n  NOW: cut {cin:.3f}->{cout:.3f} from AROLL_window.mp4 AND VOICE_cut.wav,")
        print(f"       remap every plan_v2 SHOT boundary the same way, and set DUR -= {delta:.3f}")


if __name__ == "__main__":
    main()
