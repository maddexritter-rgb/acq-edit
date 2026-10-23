#!/usr/bin/env python3
"""Prepare source evidence for an editor; never select cuts or certify listening."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess


def pin(path):
    path = Path(path).resolve()
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def load(path):
    return json.loads(Path(path).read_text())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def number(value):
    require(isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and value >= 0, "Invalid source time")
    return float(value)


def word_text(w):
    return str(w.get("word", w.get("text", "")))


def word_times(w):
    start, end = number(w["start"]), number(w["end"])
    require(end >= start, "Reversed word locator")
    return start, end


def routing_binding(routing, media):
    require(Path(routing["media"]).resolve() == Path(media).resolve(), "Routing media mismatch")
    for key in ("stream", "channel", "sample_rate"):
        require(type(routing[key]) is int and routing[key] >= 0, "Explicit integer routing required")
    require(routing["sample_rate"] > 0, "Invalid sample rate")
    evidence = routing["evidence"]
    require(pin(evidence["path"]) == evidence, "Routing evidence path/hash mismatch")


def make_rows(clip, words, phonemes=None, performance=None, context=.6, pause=.45):
    require(context > 0 and pause > 0, "Positive diagnostic context/threshold required")
    require(clip.get("kept_word_ranges"), "Explicit current kept_word_ranges required")
    wm = {w.get("word_index", i): w for i, w in enumerate(words)}
    pm = (phonemes or {}).get("words", {})
    a, b = clip["interaction_word_range"]
    require(a <= b and all(i in wm for i in range(a, b + 1)), "Incomplete interaction word map")
    for key, value in pm.items():
        idx = int(key)
        if idx not in wm:
            continue
        require(value.get("word_index", idx) == idx, "Phoneme word identity mismatch")
        normalize = lambda s: re.sub(r"\W", "", s.casefold())
        require(normalize(word_text(value)) == normalize(word_text(wm[idx])), "Phoneme text mismatch")
        start, end = number(value["aligned_start"]), number(value["aligned_end"])
        require(end >= start, "Reversed phoneme locator")
    rows = []
    kept = set()
    def add(label, idx, start, end, kind):
        rows.append({"id": label, "word_index": idx, "kind": kind,
                     "start": max(0, start - context), "end": end + context,
                     "status": "DIAGNOSTIC_ONLY_NOT_INSPECTED"})
    for n, (first, last) in enumerate(clip["kept_word_ranges"]):
        require(a <= first <= last <= b, "Kept range outside interaction")
        kept.update(range(first, last + 1))
        for edge, idx, component in (("head", first, 0), ("tail", last, 1)):
            loc = word_times(wm[idx])[component]
            aligned = pm.get(str(idx), {}).get("aligned_start" if component == 0 else "aligned_end", loc)
            add(f"span-{n:03d}-{edge}", idx, min(loc, aligned), max(loc, aligned), edge)
        for idx in range(first, last):
            left, right = word_times(wm[idx])[1], word_times(wm[idx + 1])[0]
            if right - left > pause:
                add(f"gap-{idx}-{idx+1}", idx, left, right, "pause_locator")
    for event in (performance or {}).get("events", []):
        if event.get("kind") not in {"stretched_word", "vad_word_conflict", "filler_word"}:
            continue
        indices = event.get('word_indices', [event.get('word_index')])
        if indices == [None] and event.get('kind') in ('stretched_word','filler_word'):
            match = re.fullmatch(r'(?:word|filler)_(\d+)', event.get('id',''))
            indices = [int(match.group(1))] if match else []
        for idx in indices:
            if idx not in kept:
                continue
            st, en = word_times(wm[idx]); p = pm.get(str(idx), {})
            add(f"event-{event['id']}-{idx}", idx, min(st, p.get("aligned_start", st)),
                max(en, p.get("aligned_end", en)), event["kind"])
    return prioritize(rows, wm, pm), wm, pm


def alignment_context(words, index, guard=2.0):
    """Plan a broad re-transcription window, never a label-forced alignment corpus."""
    st,en=word_times(words[index]);lo=max(0,st-guard);hi=en+guard
    ids=[i for i,w in enumerate(words) if word_times(w)[1]>=lo and word_times(w)[0]<=hi]
    lo=max(0,min(word_times(words[i])[0] for i in ids)-.35)
    hi=max(word_times(words[i])[1] for i in ids)+.35
    return {'source_window':[lo,hi],'target_word_index':index,'neighbor_word_ids':ids,
            'instruction':'Independently transcribe this entire decoded window before forced alignment. Align its actual transcript, not a cropped slice of old ASR labels. Map target occurrence using unchanged left/right words; disagreement stays unresolved.'}


def prioritize(rows, wm, pm):
    """Order inspection, not certify phonemes. Every row remains in the packet."""
    words=[wm[i] for i in sorted(wm)]
    for row in rows:
        idx=row['word_index'];w=wm[idx];p=pm.get(str(idx));reasons=[]
        if row['kind'] in ('vad_word_conflict','stretched_word'):reasons.append('INTERIOR_TIMING_CONFLICT')
        if not p:reasons.append('NO_INDEPENDENT_ALIGNMENT')
        else:
            delta=max(abs(w['start']-p['aligned_start']),abs(w['end']-p['aligned_end']))
            row['max_locator_disagreement_seconds']=delta
            if delta>.08:reasons.append('LOCATOR_DISAGREEMENT')
        for neighbor in (idx-1,idx+1):
            if neighbor in wm and word_text(wm[neighbor]).casefold()==word_text(w).casefold():reasons.append('REPEATED_WORD_OCCURRENCE')
        if idx-1 in wm and w['start']-wm[idx-1]['end']<.08 and row['kind']=='head':reasons.append('TIGHT_OR_OVERLAPPED_HEAD')
        if idx+1 in wm and wm[idx+1]['start']-w['end']<.08 and row['kind']=='tail':reasons.append('TIGHT_OR_OVERLAPPED_TAIL')
        row['priority']='FOCUSED_REVIEW' if reasons else 'BATCH_REVIEW'
        row['reasons']=sorted(set(reasons));row['acoustic_approved']=False
        if reasons:
            local=sorted(wm).index(idx);ctx=alignment_context(words,local)
            ctx['target_word_index']=idx;ctx['neighbor_word_ids']=[sorted(wm)[i] for i in ctx['neighbor_word_ids']]
            row['alignment_context']=ctx
            if 'LOCATOR_DISAGREEMENT' in reasons:
                row['start']=min(row['start'],ctx['source_window'][0]);row['end']=max(row['end'],ctx['source_window'][1])
    return rows


def prepare(selection, clip_id, routing_path, out, phonemes_path=None,
            performance_path=None, context=.6, pause=.45, spectrogram=False):
    import numpy as np
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from scipy.io import wavfile
    selection, out = Path(selection).resolve(), Path(out).resolve()
    doc = load(selection)
    require(doc.get("schema") == "edit.assembly-selection/v2", "Current v2 source-word selection required")
    clips = [c for c in doc["clips"] if c["id"] == clip_id]
    require(len(clips) == 1, "Clip ID missing or ambiguous")
    clip = clips[0]; media = Path(clip["media"]).resolve()
    require(media.is_file(), "Media missing")
    words_path = Path(clip["source_words"]).resolve()
    require(pin(words_path)["sha256"] == clip["source_words_sha256"], "Source words changed")
    words = load(words_path)["words"]
    routing = load(routing_path); routing_binding(routing, media)
    rows, wm, pm = make_rows(clip, words, load(phonemes_path) if phonemes_path else None,
                            load(performance_path) if performance_path else None, context, pause)
    rows.sort(key=lambda r:(r['priority']!='FOCUSED_REVIEW',r['start'],r['id']))
    probe = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "a",
        "-show_entries", "stream=sample_rate,channels,codec_name", "-of", "json", str(media)]))
    require(routing["stream"] < len(probe["streams"]), "Audio stream unavailable")
    stream = probe["streams"][routing["stream"]]
    require(routing["channel"] < stream["channels"], "Audio channel unavailable")
    require(int(stream["sample_rate"]) == routing["sample_rate"], "Played rate mismatch; do not resample diagnostics")
    require(stream["codec_name"].startswith("pcm_"), "Prepare verified played PCM before precision inspection")
    a, b = clip["interaction_word_range"]
    start = max(0, math.floor(min([word_times(wm[i])[0] for i in range(a,b+1)] + [r["start"] for r in rows]) - context))
    end = math.ceil(max([word_times(wm[i])[1] for i in range(a,b+1)] + [r["end"] for r in rows]) + context)
    out.mkdir(parents=True, exist_ok=False)
    wav = out / "played-source-channel.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-n", "-ss", str(start), "-i", str(media),
        "-t", str(end-start), "-map", f"0:a:{routing['stream']}", "-vn", "-af",
        f"pan=mono|c0=c{routing['channel']}", "-c:a", "pcm_f32le", str(wav)], check=True)
    rate, data = wavfile.read(wav)
    require(rate == routing["sample_rate"] and data.ndim == 1, "Decoded routing/rate mismatch")
    require(len(data) >= math.ceil((max(r["end"] for r in rows)-start)*rate), "Media lacks requested source context")
    per_page = 4 if spectrogram else 8
    for page in range(0, len(rows), per_page):
        part = rows[page:page+per_page]; height = 2 if spectrogram else 1
        fig, axes = plt.subplots(len(part)*height, 1, figsize=(16, 2.4*len(part)*height), squeeze=False)
        for n, row in enumerate(part):
            ax = axes[n*height, 0]; lo, hi = row["start"], row["end"]
            left, right = max(0, round((lo-start)*rate)), min(len(data), round((hi-start)*rate))
            chunk = data[left:right]; require(len(chunk) > 1, "Empty plot context")
            times = np.arange(left, right)/rate + start
            ax.plot(times, chunk, lw=.45); peak = max(float(abs(chunk).max()), 1e-8)
            for j, (idx, word) in enumerate(wm.items()):
                st, en = word_times(word); p = pm.get(str(idx), {})
                ps, pe = p.get("aligned_start", st), p.get("aligned_end", en)
                if min(st, ps) >= hi or max(en, pe) <= lo:
                    continue
                ax.axvspan(st, en, color="gray", alpha=.08)
                ax.text(max(lo, min(st, ps)), peak*(.35 if j%2 else .75), f"{idx} {word_text(word)}", fontsize=8)
                if p:
                    ax.axvline(ps, color="green", lw=.6); ax.axvline(pe, color="green", lw=.6)
                    for ph in p.get("phones", []):
                        if lo <= ph["start"] < hi:
                            ax.text(ph["start"], -peak*.8, ph["phone"], fontsize=7, color="green")
            ax.set_xlim(lo, hi); ax.ticklabel_format(useOffset=False, style="plain", axis="x"); ax.grid(axis="x", alpha=.25)
            ax.set_title(f"{row['id']} — {word_text(wm[row['word_index']])} | gray: transcript, green: phonemes; NOT cut decisions", fontsize=9)
            if spectrogram:
                sx = axes[n*height+1, 0]
                sx.specgram(chunk, NFFT=min(512, len(chunk)), Fs=rate, noverlap=min(384, len(chunk)//2),
                            xextent=(times[0], times[-1]), cmap="magma")
                sx.set_ylim(0, min(8000, rate/2)); sx.set_xlim(lo,hi); sx.ticklabel_format(useOffset=False, axis="x")
            row["page"] = f"page-{page//per_page+1:03d}.png"
        fig.tight_layout(); fig.savefig(out / part[0]["page"], dpi=110); plt.close(fig)
    index = {"schema": "edit.boundary-inspection/v1", "status": "DIAGNOSTICS_PREPARED_NOT_INSPECTED",
             "selection": pin(selection), "source_words": pin(words_path), "clip_id": clip_id,
             "media": str(media), "media_size": media.stat().st_size, "routing": pin(routing_path),
             "phonemes": pin(phonemes_path) if phonemes_path else None,
             "performance": pin(performance_path) if performance_path else None,
             "audio": pin(wav), "audio_source_offset_seconds": start, "sample_rate": rate,
             "context_seconds": context, "pause_locator_seconds": pause, "regions": rows,
             "limitations": "Hashes bind inputs, not sound quality. Inspect every region; no cut windows, listening or approval inferred."}
    (out / "index.json").write_text(json.dumps(index, indent=2)+"\n")
    return index


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("selection", "routing", "out"):
        p.add_argument("--"+name, type=Path, required=True)
    p.add_argument("--clip-id", required=True)
    p.add_argument("--phonemes", type=Path); p.add_argument("--performance", type=Path)
    p.add_argument("--context-seconds", type=float, default=.6)
    p.add_argument("--pause-locator-seconds", type=float, default=.45)
    p.add_argument("--spectrogram", action="store_true")
    a = p.parse_args()
    r = prepare(a.selection, a.clip_id, a.routing, a.out, a.phonemes, a.performance,
                a.context_seconds, a.pause_locator_seconds, a.spectrogram)
    print(json.dumps({"status": r["status"], "regions": len(r["regions"]), "index": str(a.out/"index.json")}))


if __name__ == "__main__":
    main()
