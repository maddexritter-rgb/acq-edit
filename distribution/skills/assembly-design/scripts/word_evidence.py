#!/usr/bin/env python3
"""One per-word evidence table: what was said (AssemblyAI), where the sound is
separable (waveform), and how it sounds (Gemini delivery map).

`build` writes the table once per source. `view` prints an interaction for the
paper cut: the literal words with their indices, plus only the words where a source
flags something (fused boundary, phantom or missing word, stumble, emphasis...).
Millisecond cut points still come from MFA + waveform at the chosen joins
(audio-precision.md); this table is for choosing words and spotting risky joins.
It selects nothing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np

SCHEMA = 'assembly.word-evidence/v1'
SR = 16000
HOP = 80  # 5 ms at 16 kHz
FILLERS = {'um', 'uh', 'ah', 'erm', 'hmm', 'mm'}


def envelope(audio, cache_dir):
    """5 ms RMS envelope in dB, streamed so a 10-hour source never sits in memory."""
    st = Path(audio).stat()
    key = hashlib.sha256(f'{Path(audio).resolve()}|{st.st_size}|{st.st_mtime_ns}|{SR}|{HOP}'.encode()).hexdigest()[:24]
    cache = Path(cache_dir) / f'envelope-{key}.npy'
    if cache.exists():
        return np.load(cache)
    proc = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', str(audio), '-vn', '-ac', '1', '-ar', str(SR),
                             '-f', 'f32le', '-'], stdout=subprocess.PIPE)
    parts, rest = [], np.zeros(0, np.float32)
    while True:
        block = proc.stdout.read(SR * 4 * 60)
        if not block:
            break
        x = np.concatenate([rest, np.frombuffer(block, '<f4')])
        n = len(x) // HOP
        parts.append(np.sqrt((x[:n * HOP].reshape(n, HOP) ** 2).mean(1)))
        rest = x[n * HOP:]
    proc.stdout.close()
    if proc.wait():
        raise RuntimeError('ffmpeg could not decode the played audio')
    env = (20 * np.log10(np.concatenate(parts) + 1e-9)).astype(np.float32)
    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    np.save(cache, env)
    return env


def span_db(env, t0, t1, fn):
    a, b = int(t0 * SR / HOP), max(int(t0 * SR / HOP) + 1, int(np.ceil(t1 * SR / HOP)))
    seg = env[max(0, a):min(len(env), b)]
    return float(fn(seg)) if len(seg) else None


def boundary(env, left_end, right_start, floor):
    """How separable the join between two adjacent words is in the waveform."""
    gap = right_start - left_end
    lo, hi = (left_end, right_start) if gap >= 0.010 else (min(left_end, right_start) - 0.015,
                                                             max(left_end, right_start) + 0.015)
    valley = span_db(env, lo, hi, np.min)
    if valley is None:
        return None
    quiet = valley <= floor + 12
    state = 'clean' if quiet and gap >= 0.040 else ('tight' if quiet else 'fused')
    return {'gap_ms': round(gap * 1000), 'valley_db': round(valley, 1), 'state': state}


def build(words_path, audio, cache_dir, delivery_map=None):
    words = json.loads(Path(words_path).read_text())['words']
    env = envelope(audio, cache_dir)
    floor = float(np.percentile(env, 10))
    tags, heard = {}, set()
    dm = json.loads(Path(delivery_map).read_text()) if delivery_map else None
    if dm:
        if dm['source']['words_sha256'] != hashlib.sha256(Path(words_path).read_bytes()).hexdigest():
            raise ValueError('delivery map was made from a different transcript')
        for c in dm['chunks']:
            if c['status'] != 'UNAVAILABLE':
                heard.update(range(c['word_range'][0], c['word_range'][1] + 1))
        for t in dm['tags']:
            for i in range(t['word_first'], t['word_last'] + 1):
                tags.setdefault(i, []).append({k: t[k] for k in ('type', 'confidence', 'note', 'heard', 'vote') if k in t})
    rows = []
    for i, w in enumerate(words):
        nxt = words[i + 1] if i + 1 < len(words) else None
        after = boundary(env, w['end'], nxt['start'], floor) if nxt else None
        g = tags.get(i, [])
        types = {t['type'] for t in g}
        flags = []
        if w['end'] - w['start'] < 0.02:
            flags.append('zero_length_label')
        if (w.get('confidence') or 1) < 0.5:
            flags.append('low_asr_confidence')
        votes = [t['vote'] for t in g if t.get('vote')]
        if any(v['winner'] == 'gemini' for v in votes):
            flags.append('transcript_wrong_use_heard_text')
        elif any(v['winner'] == 'unresolved' for v in votes):
            flags.append('transcript_disputed')
        if 'phantom_word' in types:
            flags.append('gemini_says_not_audible')
        if 'missing_word' in types:
            flags.append('gemini_heard_extra_speech')
        if 'phantom_word' in types and after and after['state'] == 'clean' and span_db(env, w['start'], w['end'], np.median) is not None \
                and span_db(env, w['start'], w['end'], np.median) <= floor + 10:
            flags.append('waveform_agrees_silent')
        # Gemini tags only some fillers, so a missing filler tag is not evidence; no flag for it.
        rows.append({'i': i, 'word': w['word'], 'speaker': w.get('speaker'), 'start': w['start'], 'end': w['end'],
                     'confidence': w.get('confidence'),
                     'speech_db': None if w['end'] <= w['start'] else round(span_db(env, w['start'], w['end'], np.median), 1),
                     'after': after, 'gemini': g, 'flags': flags})
    return {'schema': SCHEMA, 'source': {'words': str(Path(words_path).resolve()), 'audio': str(Path(audio).resolve()),
            'delivery_map': str(Path(delivery_map).resolve()) if delivery_map else None,
            'gemini_coverage': (dm or {}).get('coverage', {'status': 'NOT_RUN'})},
            'room_floor_db': round(floor, 1), 'words': rows,
            'scope': 'Evidence for choosing words and spotting risky joins. MFA + waveform set exact cut points.'}


def crosscheck(table, first, last, audio, cache_dir, transcriber=None):
    """Second transcript for one interaction: local Whisper vs AssemblyAI, word by word.

    Every non-filler mismatch is a caption/word dispute. A Gemini note on the same words
    is the third vote; two matching sources decide, otherwise it stays DISPUTED.
    """
    import difflib
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'long-form-ingest/scripts'))
    from delivery_map import norm, local_whisper
    transcriber = transcriber or local_whisper
    rows = table['words']
    start, end = max(0.0, rows[first]['start'] - 0.3), rows[last]['end'] + 0.3
    key = hashlib.sha256(f"{Path(audio).resolve()}|{start:.3f}|{end:.3f}".encode()).hexdigest()[:20]
    cache = Path(cache_dir) / f'whisper-{key}.json'
    if cache.exists():
        text = json.loads(cache.read_text())['text']
    else:
        try:
            text = transcriber(audio, start, end) or ''
        except Exception as exc:
            return {'status': 'UNAVAILABLE', 'detail': f'local Whisper failed: {type(exc).__name__}', 'disputes': []}
        Path(cache_dir).mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps({'text': text}))
    asm = [(r['i'], t) for r in rows[first:last + 1] for t in norm(r['word']).split()]
    wsp = norm(text).split()
    disputes = []
    for op, a0, a1, b0, b1 in difflib.SequenceMatcher(None, [t for _, t in asm], wsp, autojunk=False).get_opcodes():
        if op == 'equal':
            continue
        asm_toks = [t for _, t in asm[a0:a1]]
        if asm_toks and all(t in FILLERS or t in ('like', 'you', 'know', 'yeah') for t in asm_toks) and not wsp[b0:b1]:
            continue  # Whisper drops fillers by design; not a dispute
        if not asm_toks:
            continue  # extra Whisper words with no transcript words: nothing to caption-fix
        idx = sorted({i for i, _ in asm[a0:a1]})
        gem = [g for i in idx for g in rows[i]['gemini'] if g.get('heard')]
        heard = gem[0]['heard'] if gem else None
        decided = None
        if heard and difflib.SequenceMatcher(None, norm(heard), ' '.join(wsp[b0:b1])).ratio() >= 0.6:
            decided = 'TRANSCRIPT_WRONG'  # Gemini and Whisper agree
        disputes.append({'words': [idx[0], idx[-1]], 'whisper_tokens': [b0, b1], 'gemini': heard,
                         'status': decided or 'DISPUTED'})
    # Merge disagreements a few words apart into one phrase so each side reads as its own sentence.
    merged = []
    for d in disputes:
        if merged and d['words'][0] - merged[-1]['words'][1] <= 3:
            m = merged[-1]
            m['words'][1], m['whisper_tokens'][1] = d['words'][1], d['whisper_tokens'][1]
            m['gemini'] = m['gemini'] or d['gemini']
            m['status'] = 'TRANSCRIPT_WRONG' if 'TRANSCRIPT_WRONG' in (m['status'], d['status']) else 'DISPUTED'
        else:
            merged.append(d)
    for d in merged:
        d['assemblyai'] = ' '.join(rows[i]['word'] for i in range(d['words'][0], d['words'][1] + 1))
        d['whisper'] = ' '.join(wsp[d['whisper_tokens'][0]:d['whisper_tokens'][1]])
    return {'status': 'OK', 'whisper_text': text, 'disputes': merged}


ADJUDICATE = """Each numbered snippet below is recorded speech with two candidate transcripts of the same
words. Listen to the snippet and say which candidate matches what is actually audible. Answer
"A", "B", or "neither" (then give the audible words). Judge sound only; do not prefer the more
grammatical sentence. Return JSON exactly:
{{"snippets":[{{"n":int,"choice":"A|B|neither","audible":"only for neither","confidence":"high|medium|low"}}]}}
{listing}
"""


def check_kept(table, kept_ranges, audio, cache_dir, transcriber=None, caller=None, encoder=None,
               models=None):
    """Words to verify by ear before captioning: every place the clip's kept words differ
    between AssemblyAI and local Whisper, with Gemini's forced A/B choice as a third vote.

    2026-10-15 test: Gemini's choice flipped between runs on the same words, so votes are
    reported, never applied. Caption text changes only after a human or the source confirms."""
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).resolve().parents[2] / '_shared'))
    import gemini_audio
    rows = table['words']
    first, last = min(a for a, _ in kept_ranges), max(b for _, b in kept_ranges)
    kept = {i for a, b in kept_ranges for i in range(a, b + 1)}
    cross = crosscheck(table, max(0, first - 3), min(len(rows) - 1, last + 3), audio, cache_dir, transcriber)
    if cross['status'] != 'OK':
        return {**cross, 'disputes': []}
    disputes = [d for d in cross['disputes'] if any(i in kept for i in range(d['words'][0], d['words'][1] + 1))]
    if disputes:
        pcm, listing, cursor = [], [], 0.0
        for n, d in enumerate(disputes, 1):
            a, b = max(0, d['words'][0] - 2), min(len(rows) - 1, d['words'][1] + 2)
            before = ' '.join(rows[i]['word'] for i in range(a, d['words'][0]))
            after = ' '.join(rows[i]['word'] for i in range(d['words'][1] + 1, b + 1))
            t0 = max(0.0, rows[a]['start'] - 0.25)
            seg = np.frombuffer(subprocess.check_output(['ffmpeg', '-v', 'error', '-ss', f'{t0:.3f}', '-t',
                                f'{rows[b]["end"] + 0.25 - t0:.3f}', '-i', str(audio), '-ac', '1', '-ar', str(SR),
                                '-f', 'f32le', '-']), '<f4')
            listing.append(f'Snippet {n} ({cursor:.1f}-{cursor + len(seg) / SR:.1f} s): '
                           f'A = "{before} {d["assemblyai"]} {after}" | B = "{before} {d["whisper"]} {after}"')
            pcm += [seg, np.zeros(SR, np.float32)]
            cursor += len(seg) / SR + 1.0
        joined = np.concatenate(pcm[:-1]).astype('<f4').tobytes()
        audio_bytes = (encoder(joined) if encoder else subprocess.run(
            ['ffmpeg', '-v', 'error', '-f', 'f32le', '-ar', str(SR), '-ac', '1', '-i', '-', '-c:a', 'libmp3lame',
             '-b:a', '48k', '-f', 'mp3', '-'], input=joined, stdout=subprocess.PIPE, check=True).stdout)
        r = (caller or gemini_audio.call_chain)(audio_bytes, ADJUDICATE.format(listing='\n'.join(listing)),
                                               cache_dir=cache_dir, budget=gemini_audio.Budget(2.0, 3),
                                               **({'models': models} if models else {}))
        answers = {int(x['n']): x for x in ((r.get('result') or {}).get('snippets') or [])
                   if isinstance(x, dict) and str(x.get('n', '')).isdigit()} if r['status'] in ('OK', 'CACHED') else {}
        for n, d in enumerate(disputes, 1):
            x = answers.get(n, {})
            d['gemini_choice'] = x.get('choice')
            if x.get('choice') == 'neither':
                d['gemini'] = x.get('audible')
            d['status'] = {'A': 'VERIFY_2_OF_3_SAY_ASSEMBLYAI', 'B': 'VERIFY_2_OF_3_SAY_WHISPER'}.get(
                x.get('choice'), 'VERIFY_NO_MAJORITY')
        cross['adjudication'] = {'status': r['status'], 'model': r.get('model'), 'usd': round(r.get('usd', 0.0), 4)}
    for d in disputes:
        d.setdefault('status', 'VERIFY_NO_MAJORITY')
        if d['status'] in ('DISPUTED', 'TRANSCRIPT_WRONG'):
            d['status'] = 'VERIFY_NO_MAJORITY'
    cross['disputes'] = disputes
    cross['scope'] = 'Verify these words by ear before captions; votes are evidence, not corrections.'
    return cross


def view(table, first, last, cross=None):
    # Text marks where a cut can land: '‖' clean silence, '¦' quiet but tight, nothing = fused.
    rows = table['words'][first:last + 1]
    lines, line, speaker = [], [], None
    for r in rows:
        if r['speaker'] != speaker:
            if line:
                lines.append(' '.join(line))
            line, speaker = [f"[{r['speaker']}]"], r['speaker']
        mark = '*' if r['flags'] or r['gemini'] else ''
        cut = {'clean': ' ‖', 'tight': ' ¦'}.get((r['after'] or {}).get('state'), '')
        line.append(f"{r['i']}:{r['word']}{mark}{cut}")
        if len(line) >= 16:
            lines.append(' '.join(line))
            line = []
    if line:
        lines.append(' '.join(line))
    notes = []
    for r in rows:
        bits = []
        for g in r['gemini']:
            vote = g.get('vote') or {}
            if vote.get('winner') == 'assemblyai':
                continue  # the transcript won the three-way vote; nothing to act on
            text = f"{g['type']}({g['confidence']}): {g['note']}"
            if vote.get('winner') == 'gemini':
                text = f"TRANSCRIPT WRONG, audible: \"{vote['gemini']}\" (Gemini + Whisper agree)"
            elif vote:
                text += f" [disputed: {vote.get('reason') or vote.get('scores')}]"
            bits.append(text)
        bits += [f for f in r['flags'] if not f.startswith('gemini_')]
        if bits:
            notes.append(f"  {r['i']} '{r['word']}' [{r['speaker']}] {r['start']:.2f}s — " + '; '.join(bits))
    if cross:
        notes.append('Transcript cross-check (AssemblyAI vs local Whisper' + (', Gemini 3rd vote):' if cross['status'] == 'OK' else f"): {cross['status']} {cross.get('detail', '')}"))
        for d in cross.get('disputes', []):
            notes.append(f"  {d['words'][0]}-{d['words'][1]} {d['status']}: AssemblyAI \"{d['assemblyai']}\" | Whisper \"{d['whisper']}\""
                         + (f" | Gemini \"{d['gemini']}\"" if d['gemini'] else '') + ' -> verify before captioning or cutting on these words')
    cov = table['source']['gemini_coverage'].get('status')
    head = f"Word evidence {first}-{last} | room floor {table['room_floor_db']} dB | Gemini: {cov}"
    key = "Cut marks: '‖' clean silence after the word, '¦' quiet but tight, none = words run together (cut there only after MFA/waveform inspection)."
    return head + '\n' + key + '\n' + '\n'.join(lines) + '\n\nFlagged words (* above):\n' + ('\n'.join(notes) or '  none')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    b = sub.add_parser('build')
    b.add_argument('--words', required=True, type=Path)
    b.add_argument('--audio', required=True, type=Path, help='played dialogue on the transcript clock')
    b.add_argument('--delivery-map', type=Path, help='long-form-ingest delivery_map.vN.json (optional)')
    b.add_argument('--cache-dir', required=True, type=Path)
    b.add_argument('--out', required=True, type=Path)
    v = sub.add_parser('view')
    v.add_argument('table', type=Path)
    v.add_argument('first', type=int)
    v.add_argument('last', type=int)
    v.add_argument('--crosscheck-cache', type=Path, help='run the local-Whisper transcript cross-check (cached here)')
    k = sub.add_parser('check-kept', help='caption truth for a designed clip: Whisper cross-check + Gemini A/B adjudication')
    k.add_argument('table', type=Path)
    k.add_argument('--selection', required=True, type=Path)
    k.add_argument('--clip-id', required=True)
    k.add_argument('--cache-dir', required=True, type=Path)
    k.add_argument('--out', required=True, type=Path)
    a = ap.parse_args()
    if a.cmd == 'build':
        if a.out.exists():
            ap.error('output exists; use a new revision path')
        t = build(a.words, a.audio, a.cache_dir, a.delivery_map)
        a.out.write_text(json.dumps(t) + '\n')
        flagged = sum(1 for r in t['words'] if r['flags'] or r['gemini'])
        print(json.dumps({'status': 'WORD_EVIDENCE_BUILT', 'words': len(t['words']), 'flagged': flagged,
                          'gemini': t['source']['gemini_coverage'].get('status')}))
    elif a.cmd == 'check-kept':
        if a.out.exists():
            ap.error('output exists; use a new revision path')
        t = json.loads(a.table.read_text())
        clip = next(c for c in json.loads(a.selection.read_text())['clips'] if c['id'] == a.clip_id)
        r = check_kept(t, clip['kept_word_ranges'], t['source']['audio'], a.cache_dir)
        a.out.write_text(json.dumps(r, indent=1) + '\n')
        print(json.dumps({'status': r['status'], 'adjudication': r.get('adjudication'),
                          'verify_by_ear': [{'words': d['words'], 'vote': d['status'], 'assemblyai': d['assemblyai'],
                                             'whisper': d['whisper'], 'gemini': d.get('gemini') or d.get('gemini_choice')}
                                            for d in r['disputes']]}, indent=1))
    else:
        t = json.loads(a.table.read_text())
        cross = crosscheck(t, a.first, a.last, t['source']['audio'], a.crosscheck_cache) if a.crosscheck_cache else None
        print(view(t, a.first, a.last, cross))


if __name__ == '__main__':
    main()
