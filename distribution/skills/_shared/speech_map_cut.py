#!/usr/bin/env python3
"""THE speech-map cut engine (v3, 2026-07-31, Maddex spec): "have the most
accurate frame measurement for when words start and end, and then don't make
cuts when there are words talking."

INVARIANT: every cut lands on a video frame whose cut-time sits fully inside a
Silero-confirmed NON-SPEECH gap, with margin on both sides:
    speech_end + END_MARGIN  <=  cut_time  <=  next_speech_start - LEAD_MARGIN
If no frame in the gap satisfies that, the boundary is REFUSED (verdict in the
report) — the fix is editorial (extend the span to the next real sentence gap
or route around), never a compromise cut on live speech.

Instruments, triangulated:
  Silero VAD  -> where speech physically is (breaths/noise = non-speech)
  RMS 5ms     -> quietest frame inside the legal window (avoid cutting a breath)
  AAI words   -> only WHICH gap a boundary belongs to, never WHERE it lands

  python3 speech_map_cut.py --source <src> --words <words.json> \
      --spans '[[t0,t1],...]' [--fps 30] [--report out.json]

Prints refined spans + per-boundary verdicts. Exit 2 if any boundary REFUSED.
"""
from __future__ import annotations
import argparse, json, subprocess, sys, tempfile
from fractions import Fraction
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from silero_vad import speech_spans

END_MARGIN = 0.025   # s of decay after speech before a cut may land
LEAD_MARGIN = 0.040  # s before the next speech onset a cut must clear
WIN_PAD = 1.6        # s of context extracted around each boundary


def parse_fps(value: str) -> float:
    """Accept an exact source rate such as 24000/1001, never a rounded 23.98."""
    try:
        fps = Fraction(value)
    except (ValueError, ZeroDivisionError) as exc:
        raise argparse.ArgumentTypeError('invalid frame rate') from exc
    if fps <= 0:
        raise argparse.ArgumentTypeError('frame rate must be positive')
    return float(fps)


def probe_fps(source: str) -> float:
    result = subprocess.run([
        'ffprobe', '-v', 'error', '-select_streams', 'v:0',
        '-show_entries', 'stream=avg_frame_rate,r_frame_rate',
        '-of', 'json', source,
    ], capture_output=True, text=True, check=True)
    streams = json.loads(result.stdout).get('streams', [])
    if not streams:
        raise ValueError('source has no video stream; specify --fps')
    stream = streams[0]
    for key in ('avg_frame_rate', 'r_frame_rate'):
        value = stream.get(key)
        if value and value != '0/0':
            return parse_fps(value)
    raise ValueError('source frame rate unavailable; specify --fps')


def extract_wav(src: str, t0: float, dur: float) -> str:
    f = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    f.close()
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-ss", f"{max(0, t0):.4f}", "-t", f"{dur:.4f}", "-i", src,
                    "-ac", "1", "-ar", "16000", f.name], check=True)
    return f.name


def rms_db_curve(wav: str) -> np.ndarray:
    """5ms-hop RMS dB curve of a wav file."""
    raw = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error",
                          "-i", wav, "-f", "f32le", "-"],
                         capture_output=True).stdout
    a = np.frombuffer(raw, dtype=np.float32)
    n = 80  # 5ms @16k
    k = len(a) // n
    w = a[: k * n].reshape(k, n)
    return 20 * np.log10(np.sqrt((w ** 2).mean(axis=1) + 1e-12))


HUG = 0.50  # search no further than this past the speech edge (pacing)


def boundary(fps, side, spans_abs, env, env_t0, env_t1, t_label):
    """Place one cut. side='end': after the speech span holding t_label;
    side='start': before it. Returns (frame_time|None, info).
    Placement HUGS the speech edge: earliest legal quiet frame after an end /
    latest before a start — a cut that wanders deep into a pause is a pacing
    bug even when it's silent."""
    if not spans_abs:
        return None, {"verdict": "REFUSED", "why": "no speech in window"}
    d = [(0 if s <= t_label <= e else min(abs(t_label - s), abs(t_label - e)), i)
         for i, (s, e) in enumerate(spans_abs)]
    _, idx = min(d)
    s, e = spans_abs[idx]
    if side == "end":
        if idx + 1 < len(spans_abs):
            gap_lo, gap_hi = e, spans_abs[idx + 1][0]
        elif env_t1 - e >= 0.6:      # window shows >=0.6s of silence after
            gap_lo, gap_hi = e, env_t1
        else:
            return None, {"verdict": "WIDEN", "why": "speech at window edge"}
        lo, hi = gap_lo + END_MARGIN, min(gap_hi - LEAD_MARGIN, gap_lo + HUG)
    else:
        if idx > 0:
            gap_lo, gap_hi = spans_abs[idx - 1][1], s
        elif s - env_t0 >= 0.6:
            gap_lo, gap_hi = env_t0, s
        else:
            return None, {"verdict": "WIDEN", "why": "speech at window edge"}
        lo, hi = max(gap_lo + END_MARGIN, gap_hi - HUG), gap_hi - LEAD_MARGIN
    gap_ms = round((gap_hi - gap_lo) * 1000)
    f_lo, f_hi = int(np.ceil(lo * fps)), int(np.floor(hi * fps))
    if f_hi < f_lo:
        return None, {"verdict": "REFUSED", "gap_ms": gap_ms,
                      "why": f"gap too small for a legal frame ({gap_ms}ms, "
                             f"need ~{int((END_MARGIN + LEAD_MARGIN) * 1000 + 33)}ms)"}

    def local_db(f):
        t = f / fps
        i0, i1 = int((t - 0.016 - env_t0) / 0.005), int((t + 0.016 - env_t0) / 0.005) + 1
        seg = env[max(0, i0):min(len(env), max(1, i1))]
        return float(seg.mean()) if len(seg) else None

    cand = range(f_lo, f_hi + 1) if side == "end" else range(f_hi, f_lo - 1, -1)
    dbs = {f: local_db(f) for f in cand}
    dbs = {f: v for f, v in dbs.items() if v is not None}
    if not dbs:
        return None, {"verdict": "REFUSED", "gap_ms": gap_ms, "why": "no measurable frame"}
    floor_db = min(dbs.values())
    for f in (sorted(dbs) if side == "end" else sorted(dbs, reverse=True)):
        if dbs[f] <= floor_db + 8.0:  # first edge-hugging frame that's truly quiet
            return f / fps, {"verdict": "OK", "gap_ms": gap_ms,
                             "cut_db": round(dbs[f], 1),
                             "speech_edge": round(e if side == "end" else s, 3)}
    return None, {"verdict": "REFUSED", "gap_ms": gap_ms, "why": "no quiet frame"}


def performance_boundary(fps, side, spans_abs, env, env_t0, env_t1, target):
    """Resolve OUTSIDE an explicit reviewed performance endpoint, never on speech."""
    if not spans_abs or not env_t0 <= target <= env_t1:
        return None, {'verdict': 'REFUSED', 'why': 'performance boundary lacks observed context'}
    gaps = list(zip([env_t0] + [e for s, e in spans_abs],
                    [s for s, e in spans_abs] + [env_t1]))
    for left, right in gaps:
        lo, hi = left + END_MARGIN, right - LEAD_MARGIN
        if side == 'end':
            lo, hi = max(lo, target), min(hi, target + HUG)
        else:
            lo, hi = max(lo, target - HUG), min(hi, target)
        first, last = int(np.ceil(lo*fps)), int(np.floor(hi*fps))
        candidates = {}
        for frame in range(first, last+1):
            t = frame/fps
            a = max(0, int((t-.016-env_t0)/.005))
            b = min(len(env), int((t+.016-env_t0)/.005)+1)
            if b > a:
                candidates[frame] = float(env[a:b].mean())
        if not candidates:
            continue
        floor = min(candidates.values())
        for frame in sorted(candidates, reverse=side == 'start'):
            if candidates[frame] <= floor+8:
                return frame/fps, {'verdict': 'OK', 'performance_endpoint': target,
                    'gap_ms': round((right-left)*1000), 'cut_db': round(candidates[frame],1),
                    'speech_edge': left if side == 'end' else right,
                    'why': 'reviewed performance preserved in verified nonspeech gap'}
    return None, {'verdict': 'REFUSED', 'why': 'no safe frame preserving performance endpoint'}


def micro_gap_boundary(fps, side, words, index, env, env_t0):
    """Find a quiet inter-word frame shorter than Silero's 100ms merge window.

    This is deliberately narrower than an onset snap: both neighboring word
    labels must leave room for a frame, and its 20ms RMS window must be quiet
    relative to the speech on both sides. It never accepts overlapping labels
    or a low-energy point inside either word.
    """
    left_i = index - 1 if side == 'start' else index
    right_i = index if side == 'start' else index + 1
    if left_i < 0 or right_i >= len(words):
        return None, {'verdict': 'REFUSED', 'why': 'no adjacent word for micro-gap'}
    left, right = words[left_i], words[right_i]
    gap = right['start'] - left['end']
    if not 0.065 <= gap <= 0.141:  # tolerate timestamp float representation of 140ms
        return None, {'verdict': 'REFUSED', 'why': 'word labels lack a short clean gap'}

    def db_window(a, b):
        i = max(0, int(np.floor((a - env_t0) / .005)))
        j = min(len(env), int(np.ceil((b - env_t0) / .005)))
        return env[i:j] if j > i else np.array([])

    before = db_window(left['end'] - .12, left['end'] - .03)
    after = db_window(right['start'] + .03, right['start'] + .12)
    if not len(before) or not len(after):
        return None, {'verdict': 'REFUSED', 'why': 'micro-gap speech context unavailable'}
    speech_floor = min(float(np.median(before)), float(np.median(after)))
    # Event microphones can keep a soft hesitation near the room floor. Require
    # a genuinely quiet absolute level as well as a drop from both speech sides.
    max_quiet_db = min(-36.0, speech_floor - 3.0)
    first = int(np.ceil((left['end'] + .025) * fps))
    last = int(np.floor((right['start'] - .025) * fps))
    candidates = []
    for frame in range(first, last + 1):
        t = frame / fps
        window = db_window(t - .010, t + .010)
        if len(window) >= 3 and float(window.max()) <= max_quiet_db + 3:
            candidates.append((float(window.mean()), frame))
    if not candidates:
        return None, {'verdict': 'REFUSED', 'why': 'no quiet micro-gap frame'}
    cut_db, frame = min(candidates)
    if cut_db > max_quiet_db:
        return None, {'verdict': 'REFUSED', 'why': 'micro-gap too loud'}
    return frame / fps, {
        'verdict': 'OK_MICRO_GAP', 'gap_ms': round(gap * 1000),
        'cut_db': round(cut_db, 1), 'speech_floor_db': round(speech_floor, 1),
        'preceding_word': left['word'], 'following_word': right['word'],
        'why': '20ms RMS-verified quiet frame between nonoverlapping word labels',
    }


def boundary_word_indices(words, span, selection=None):
    if selection is not None:
        from word_selection import select_indices
        ids = select_indices(words, selection)
        if not all(span[0] <= words[i]['start'] and words[i]['end'] <= span[1] for i in ids):
            raise ValueError('Indexed requested span does not contain selected word labels')
        return ids[0], ids[-1]
    return (next(i for i,w in enumerate(words) if w['start'] >= span[0] - .08),
            [i for i,w in enumerate(words) if w['end'] <= span[1] + .04][-1])


def excluded_neighbor(words, first, last, start, end, tolerance=.020):
    """Report an adjacent, unselected word reached by the resolved media range.

    Word boxes are only locators: no overlap is not proof of clean audio. An
    overlap is, however, enough to reject an obviously over-wide frame range.
    """
    if start is not None and first > 0 and words[first - 1]['end'] > start + tolerance:
        return 'start', first - 1
    if end is not None and last + 1 < len(words) and words[last + 1]['start'] < end - tolerance:
        return 'end', last + 1
    return None


def main():
    global END_MARGIN, LEAD_MARGIN
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True)
    ap.add_argument("--words", required=True)
    ap.add_argument("--spans", required=True)
    ap.add_argument("--fps", type=parse_fps,
                    help="Exact source frame rate (e.g. 24000/1001); default probes source")
    ap.add_argument("--report")
    ap.add_argument('--end-margin-ms', type=float, default=25.0,
                    help='Required clearance after speech; default 25 ms')
    ap.add_argument('--lead-margin-ms', type=float, default=40.0,
                    help='Required clearance before next speech; default 40 ms')
    ap.add_argument('--selection-spec', help='Pinned compiled cut_request JSON; exact boundary word identities')
    ap.add_argument('--performance', help='JSON list parallel to spans: null or reviewed [in,out] performance interval')
    ap.add_argument("--preserve-opener", action="store_true",
                    help="Preserve the first selected words for interior inserts or locked openings; refuse fused starts instead of stripping fillers or forcing an onset snap.")
    a = ap.parse_args()
    if not (0 <= a.end_margin_ms <= 250 and 0 <= a.lead_margin_ms <= 250):
        ap.error('speech margins must be between 0 and 250 ms')
    END_MARGIN, LEAD_MARGIN = a.end_margin_ms / 1000, a.lead_margin_ms / 1000
    if a.fps is None:
        try:
            a.fps = probe_fps(a.source)
        except (ValueError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
            ap.error(str(exc))
    raw_words = Path(a.words).read_bytes()
    transcript = json.loads(raw_words)
    W = transcript['words']
    spans = json.loads(a.spans)
    selections = [None]*len(spans)
    if a.selection_spec:
        from word_selection import validate_indexed_spec
        spec = json.loads(Path(a.selection_spec).read_text())
        if not a.preserve_opener:
            ap.error('Indexed selections require --preserve-opener')
        try:
            validate_indexed_spec(spec, transcript, raw_words, True)
            selections = spec['segments']
            if len(selections) != len(spans) or not all('source_words' in s for s in selections):
                raise ValueError('Indexed selections must cover every requested span')
            for span, selection in zip(spans, selections):
                boundary_word_indices(W, span, selection)
        except (ValueError, KeyError, TypeError) as exc:
            ap.error(str(exc))
    performance = json.loads(a.performance) if a.performance else [None]*len(spans)
    if len(performance) != len(spans):
        ap.error('performance intervals must match span count')
    for region, span in zip(performance, spans):
        if region is not None and not (isinstance(region, list) and len(region) == 2 and
                all(type(v) in (int,float) and np.isfinite(v) for v in region) and
                span[0] <= region[0] < region[1] <= span[1]):
            ap.error('performance must be a finite interval inside its requested span')
    out, report, refused = [], [], 0
    FILLER_OPENERS = {"all", "alright", "okay", "ok", "so", "uh", "um", "yeah",
                      "well", "and", "but", "like", "oh", "right", "anyways",
                      "anyway"}  # hi/hey/hello = editorial, not banned (question-read greetings can BE the hook)
    for n, (t0, t1) in enumerate(spans):
        i_first, i_last = boundary_word_indices(W, [t0,t1], selections[n])
        w_first, w_last = W[i_first], W[i_last]
        pad = WIN_PAD
        while True:  # widen until both boundary gaps are fully visible
            win0 = max(0, t0 - pad)
            dur = (t1 - t0) + 2 * pad
            wav = extract_wav(a.source, win0, dur)
            sp = speech_spans(wav, min_silence=0.10, speech_pad_ms=25)
            if sp is None:
                sys.exit("Silero unavailable — REFUSING to cut blind (no fallback).")
            spans_abs = [(s + win0, e + win0) for s, e in sp]
            env = rms_db_curve(wav)
            Path(wav).unlink(missing_ok=True)
            env_t1 = win0 + len(env) * 0.005
            s_t, s_info = boundary(a.fps, "start", spans_abs, env, win0,
                                   env_t1, w_first["start"])
            e_t, e_info = boundary(a.fps, "end", spans_abs, env, win0,
                                   env_t1, w_last["end"])
            if (s_info.get("verdict") != "WIDEN" and
                    e_info.get("verdict") != "WIDEN") or pad > 14:
                break
            pad *= 2.5
        # ADJACENCY: the legal gap must belong to the INTENDED word — a cut in
        # a legal-but-distant gap silently adds/drops words. > 0.35s drift from
        # the label = FUSED; report candidate boundary words instead of cutting.
        def cands(w_idx, direction):
            """Nearby words whose label-gap suggests a real pause (candidates
            for an alternative boundary, for the editorial layer to pick)."""
            found = []
            j = w_idx
            for _ in range(8):
                j += direction
                if not (0 <= j < len(W)):
                    break
                wj = W[j]
                nxt_gap = (W[j + 1]["start"] - wj["end"]) if j + 1 < len(W) else 9.9
                if direction > 0 and nxt_gap >= 0.15:
                    found.append(f"...{wj['word']} (+{wj['end']-W[w_idx]['end']:.1f}s)")
                prv_gap = (wj["start"] - W[j - 1]["end"]) if j > 0 else 9.9
                if direction < 0 and prv_gap >= 0.15:
                    found.append(f"{wj['word']}... ({wj['start']-W[w_idx]['start']:+.1f}s)")
                if len(found) >= 2:
                    break
            return found

        # FUSED = another WORD sits between the boundary word and the gap the
        # cut landed in. Trailing non-word vocalization (laugh, decay, breath
        # Silero counts as speech) with no intervening word label is fine —
        # extend through it. (2026-07-31: 'teenager.' + chuckle case.)
        def word_between(a_t, b_t):
            lo, hi = min(a_t, b_t), max(a_t, b_t)
            return any(lo + 0.02 < w["start"] < hi - 0.02 or
                       lo + 0.02 < w["end"] < hi - 0.02 for w in W)
        if s_t is not None and abs(s_info["speech_edge"] - w_first["start"]) > 0.35 \
                and word_between(s_info["speech_edge"], w_first["start"]):
            s_info = {"verdict": "FUSED", "why": f"speech runs into '{w_first['word']}' "
                      f"(edge {s_info['speech_edge']}); alt starts: {cands(i_first, -1) + cands(i_first, 1)}"}
            s_t = None
        if s_t is None:
            micro_t, micro_info = micro_gap_boundary(a.fps, 'start', W, i_first, env, win0)
            if micro_t is not None:
                s_t, s_info = micro_t, micro_info
        # ---- OPENER RULES (clip's first span only; Maddex 2026-07-31 "starts on
        # the hook, no filler before it") ----
        if n == 0 and not a.preserve_opener:
            import re as _re

            def _norm(x):
                return _re.sub(r"[^a-z']", "", x.lower())

            def onset_snap(w):
                d0 = int((w["start"] - 0.12 - win0) / 0.005)
                d1 = int((w["start"] + 0.02 - win0) / 0.005) + 1
                seg = env[max(0, d0):min(len(env), max(1, d1))]
                if not len(seg):
                    return None, None
                t_dip = win0 + (max(0, d0) + int(np.argmin(seg))) * 0.005
                return (np.round(t_dip * a.fps) / a.fps,
                        round(float(seg.min()), 1))

            # 1) engine-side filler strip: the intended opener is the first
            #    NON-FILLER word (merge-back is BANNED for openers)
            moved = []
            while _norm(w_first["word"]) in FILLER_OPENERS and i_first + 1 < len(W):
                moved.append(w_first["word"])
                i_first += 1
                w_first = W[i_first]
            # 2) fused opener → onset-snap at the hook word (never merge back)
            if s_t is None and s_info.get("verdict") in ("FUSED", "REFUSED"):
                s_t, db = onset_snap(w_first)
                if s_t is not None:
                    s_info = {"verdict": "ONSET_SNAP", "gap_ms": 0, "cut_db": db,
                              "why": "fused opener — snapped to hook-word onset dip"}
            # 3) ACTUAL-FIRST-WORD enforcement: whatever the verdict, if the cut
            #    would audibly open on anything before the hook word (stripped
            #    filler riding back in via a run-level gap), force the snap.
            if s_t is not None:
                actual_i = next((i for i, w in enumerate(W)
                                 if w["start"] >= s_t - 0.02), i_first)
                if actual_i < i_first:
                    s_t2, db = onset_snap(w_first)
                    if s_t2 is not None:
                        s_t = s_t2
                        s_info = {"verdict": "ONSET_SNAP", "gap_ms": 0, "cut_db": db,
                                  "why": f"forced: cut would have opened on "
                                         f"'{W[actual_i]['word']}…' before the hook"}
            if moved:
                s_info["stripped_fillers"] = moved
        if e_t is not None and abs(e_info["speech_edge"] - w_last["end"]) > 0.35 \
                and word_between(w_last["end"], e_info["speech_edge"]):
            e_info = {"verdict": "FUSED", "why": f"'{w_last['word']}' runs into next speech "
                      f"(edge {e_info['speech_edge']}); alt ends: {cands(i_last, 1) + cands(i_last, -1)}"}
            e_t = None
        if e_t is None:
            micro_t, micro_info = micro_gap_boundary(a.fps, 'end', W, i_last, env, win0)
            if micro_t is not None:
                e_t, e_info = micro_t, micro_info
        if performance[n] is not None:
            p0, p1 = performance[n]
            if s_t is None or s_t > p0:
                s_t, s_info = performance_boundary(a.fps, 'start', spans_abs, env, win0, env_t1, p0)
            if e_t is None or e_t < p1:
                e_t, e_info = performance_boundary(a.fps, 'end', spans_abs, env, win0, env_t1, p1)
        # Selection preservation applies even with --preserve-opener. The old
        # opener cleanup ran only without that flag, while indexed selections
        # required it; an early quiet frame could therefore include an excluded
        # "um" despite a perfectly correct selected first word.
        for _ in range(2):
            neighbor = excluded_neighbor(W, i_first, i_last, s_t, e_t)
            if neighbor is None:
                break
            side, excluded_i = neighbor
            candidate, info = micro_gap_boundary(a.fps, side, W,
                                                  i_first if side == 'start' else i_last,
                                                  env, win0)
            if candidate is not None and (
                    (side == 'start' and W[excluded_i]['end'] <= candidate + .020) or
                    (side == 'end' and W[excluded_i]['start'] >= candidate - .020)):
                if side == 'start':
                    s_t, s_info = candidate, info
                else:
                    e_t, e_info = candidate, info
            else:
                conflict = {'verdict': 'FUSED',
                            'why': f"resolved {side} would include excluded word "
                                   f"{excluded_i} ('{W[excluded_i]['word']}'); "
                                   'choose another source-native phrase or repair this boundary'}
                if side == 'start':
                    s_t, s_info = None, conflict
                else:
                    e_t, e_info = None, conflict
        rec = {"span": [t0, t1],
               "source_words": [i_first, i_last],
               "first_word": w_first["word"], "last_word": w_last["word"],
               "start": s_info, "end": e_info}
        # Preserve each successful edge even when the opposite edge refuses.
        # Review assembly may use that measured frame independently.
        if s_t is not None:
            rec['start']['cut_time'] = float(s_t)
        if e_t is not None:
            rec['end']['cut_time'] = float(e_t)
        if s_t is None or e_t is None:
            refused += 1
            rec["result"] = "REFUSED"
        else:
            rec["result"] = [round(s_t, 3), round(e_t, 3)]
            out.append([round(s_t, 3), round(e_t, 3)])
        report.append(rec)
        tag = rec["result"] if rec["result"] == "REFUSED" else \
            f"{rec['result'][0]:.3f}->{rec['result'][1]:.3f}"
        print(f"'{w_first['word']}'..'{w_last['word']}': {tag} | "
              f"start {s_info.get('verdict')} gap {s_info.get('gap_ms')}ms "
              f"cut@{s_info.get('cut_db')}dB | end {e_info.get('verdict')} "
              f"gap {e_info.get('gap_ms')}ms cut@{e_info.get('cut_db')}dB "
              f"{'| ' + e_info.get('why', '') if e_info.get('verdict')=='REFUSED' else ''}")
    if a.report:
        Path(a.report).write_text(json.dumps(report, indent=1))
    print("SPANS_JSON", json.dumps(out))
    return 2 if refused else 0


if __name__ == "__main__":
    sys.exit(main())
