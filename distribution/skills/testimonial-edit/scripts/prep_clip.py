#!/usr/bin/env python3
"""prep_clip.py <workdir> — cutlist_v2.json + Groq clip_00.json -> a self-consistent
Premiere assembly plan where card beats are interleaved into the timeline BEFORE captions
are timed, so cuts / cards / captions all stay frame-aligned. Captions timed off the Groq
words (no re-transcription). Outputs premiere_plan.json + captions.srt into <workdir>.

premiere_plan.json.segments = ordered timeline segments, each:
  {"kind":"clip"|"card", "src_in","src_out","pos","dur"[, "card","lines"]}
Premiere assembly walks segments in order (insertClip from source at src_in/out); card
segments additionally get gaussian blur on V1 + the card PNG on V2 + muted audio.
"""
import glob, json, math, os, re, sys

FPS = 24000 / 1001
LEAD = 4 / FPS
MAX_HOLD = 1.2
CARD_DUR = 48 * 1001 / 24000  # exactly 48 frames ≈ 2.00s (editor-set, 2026-07-15)
Q_CARDS = [
    ("card1", ["HOW HAS YOUR BUSINESS BEEN", "SINCE YOUR LAST L3?"],
     ["business been since", "changed since", "how has", "since you", "since the last", "since i attended"]),
    ("card2", ["WHAT WERE THE CHALLENGES", "YOU WERE FACING BEFORE", "YOU CAME TO L3?"],
     ["challenge", "facing before", "problem", "struggling", "holding us back", "constraint", "stuck"]),
    ("card3", ["DID YOU HAVE DOUBTS AND FEARS", "AROUND SIGNING UP FOR L3?"],
     ["doubt", "fear", "worried", "nervous", "hesitat", "skeptic", "scared", "risk", "investment worth"]),
    ("card4", ["IF SOMEONE IN YOUR INDUSTRY", "IS ON THE FENCE ABOUT DOING L3...", "WHAT WOULD YOU TELL THEM?"],
     ["on the fence", "tell them", "advice", "someone else", "another business", "recommend", "worth it"]),
]

def q(t):
    return round(t * FPS) / FPS

def main(workdir):
    workdir = os.path.abspath(workdir)
    cutf = "cutlist_v3.json" if os.path.exists(f"{workdir}/cutlist_v3.json") else "cutlist_v2.json"
    cl = json.load(open(f"{workdir}/{cutf}"))
    if cl.get("empty"):
        print("EMPTY clip — skipping"); return
    words = json.load(open(f"{workdir}/clip_00.json"))["words"]

    # decide which cards fire, and before which span index (each card once, in order)
    # cards: prefer reverse-engineered cards.json ({"cards":[{span,lines}]}); else keyword fallback
    import hashlib
    card_for_span = {}
    cj = f"{workdir}/cards_final.json" if os.path.exists(f"{workdir}/cards_final.json") else f"{workdir}/cards.json"
    if os.path.exists(cj):
        for c in json.load(open(cj)).get("cards", []):
            if 0 <= c["span"] < len(cl["spans"]):
                card_for_span[c["span"]] = c["lines"]
    else:
        used = set()
        for cname, lines, kws in Q_CARDS:
            for si, sp in enumerate(cl["spans"]):
                if si in used: continue
                head = " ".join(w["word"].strip().lower() for w in words
                                if w["start"] >= sp["in"] - 0.05 and w["end"] <= sp["in"] + 6.0)
                if any(k in head for k in kws):
                    card_for_span[si] = lines; used.add(si); break

    def card_png(lines):
        h = hashlib.md5("|".join(lines).encode()).hexdigest()[:12]
        return f"qc_{h}.png"

    # build unified timeline (0.5s leader), interleaving card beats before their span
    segs, pos = [], 0.5
    for si, sp in enumerate(cl["spans"]):
        a, b = q(sp["in"]), q(sp["out"])
        if si in card_for_span:
            lines = card_for_span[si]
            # exactly 2s of blurred pre-answer footage; if not enough head, take the first 2s
            if a - CARD_DUR >= 0:
                beat_in, beat_out = q(a - CARD_DUR), a
            else:
                beat_in, beat_out = 0.0, q(CARD_DUR)
            segs.append({"kind": "card", "lines": lines, "card_png": card_png(lines),
                         "src_in": beat_in, "src_out": beat_out,
                         "pos": round(pos, 6), "dur": round(beat_out - beat_in, 6)})
            pos += beat_out - beat_in
        segs.append({"kind": "clip", "src_in": a, "src_out": b,
                     "pos": round(pos, 6), "dur": round(b - a, 6)})
        pos += b - a
    total = pos

    # card windows on the timeline (captions must avoid these)
    cardwins = [(s["pos"], s["pos"] + s["dur"]) for s in segs if s["kind"] == "card"]

    # captions: spice-ish chunk off Groq words, mapped onto each CLIP segment's timeline pos
    cues = []
    for seg in segs:
        if seg["kind"] != "clip": continue
        ws = [w for w in words if w["start"] >= seg["src_in"] - 0.05 and w["end"] <= seg["src_out"] + 0.05]
        cur = []
        for w in ws:
            if cur and (len(" ".join(x["word"].strip() for x in cur + [w])) > 26
                        or w["start"] - cur[-1]["end"] > 0.6):
                cues.append((cur, seg)); cur = []
            cur.append(w)
        if cur: cues.append((cur, seg))

    def fmt(t):
        h = int(t // 3600); m = int(t % 3600 // 60); s = int(t % 60); ms = int(round((t - int(t)) * 1000))
        if ms == 1000: ms = 0; s += 1
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    out, prev_end = [], 0.0
    for i, (cw, seg) in enumerate(cues):
        st = max(seg["pos"] + (cw[0]["start"] - seg["src_in"]) - LEAD, prev_end)
        en = seg["pos"] + min(cw[-1]["end"] - seg["src_in"] + 0.12, seg["dur"])
        nxt = None
        if i + 1 < len(cues):
            ncw, nseg = cues[i + 1]
            nxt = nseg["pos"] + (ncw[0]["start"] - nseg["src_in"]) - LEAD
        if nxt is not None and nxt - en <= MAX_HOLD and nxt > en:
            en = nxt  # butt-join, no gaps (within a clip run)
        for a, b in cardwins:  # never run under a question card
            if st < a < en: en = a
            if a <= st < b: st = b
        if en <= st: continue
        txt = re.sub(r"\s+", " ", re.sub(r"[^\w$%#&' ]+", "", " ".join(w["word"].strip() for w in cw))).strip().upper()
        if txt:
            out.append({"text": txt, "start": round(st, 3), "end": round(en, 3)})
            prev_end = en

    with open(f"{workdir}/captions.srt", "w") as f:
        for i, c in enumerate(out, 1):
            f.write(f"{i}\n{fmt(c['start'])} --> {fmt(c['end'])}\n{c['text']}\n\n")

    plan = {"person": cl["person"], "source": cl["source"], "fps": FPS,
            "super_line1": cl["super_line1"], "super_line2": cl["super_line2"],
            "segments": segs, "total": round(total, 3),
            "n_cards": len(cardwins), "n_captions": len(out),
            "srt": f"{workdir}/captions.srt", "disclaimer_out": 15.5}
    json.dump(plan, open(f"{workdir}/premiere_plan.json", "w"), indent=1)
    print(f"{cl['person']}: {sum(1 for s in segs if s['kind']=='clip')} clips + "
          f"{len(cardwins)} cards, {round(total)}s, {len(out)} captions")

if __name__ == "__main__":
    main(sys.argv[1])
