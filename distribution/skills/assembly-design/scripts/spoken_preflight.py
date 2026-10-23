#!/usr/bin/env python3
"""Compare a cheap assembled-audio transcript with selected words before finishing.

Disagreements require source inspection; matching text never certifies phonemes.
No word replacements, cut changes, or approval are generated here.
"""
import argparse
from difflib import SequenceMatcher
import hashlib
import json
from pathlib import Path
import re
import sys

def tokens(text):
    return re.findall(r"[\w]+(?:['’][\w]+)*",text.casefold().replace('’',"'"))

def compare(expected, observed):
    left=[];owners=[]
    for i,w in enumerate(expected):
        ts=tokens(w.get('word',w.get('text','')));left+=ts;owners += [i]*len(ts)
    if not left:raise ValueError('Expected words empty')
    right=tokens(observed);issues=[]
    for op,a,b,c,d in SequenceMatcher(None,left,right,autojunk=False).get_opcodes():
        if op=='equal':continue
        indices=sorted(set(owners[a:b])); adjacent=owners[min(a,len(owners)-1)]
        issues.append({'kind':op,'expected':' '.join(left[a:b]),'heard_transcript':' '.join(right[c:d]),
                       'word_indices':indices,'inspect_word_index':indices[0] if indices else adjacent,
                       'action':'COMPARE_INTACT_SOURCE_AND_ASSEMBLY; ASR disagreement is not proof of a bad cut'})
    return {'schema':'edit.spoken-preflight/v1','status':'REVIEW_REQUIRED' if issues else 'TEXT_MATCH_NOT_ACOUSTIC_APPROVAL',
            'expected_tokens':len(left),'observed_tokens':len(right),'issues':issues,
            'limitations':'Independent recognition may omit, normalize or hallucinate words. Never auto-edit or waive seam audition.'}

def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def build_preview(source, paired, output, channel):
    """Exact-sample mono diagnostic assembly from an explicit zero-clock PCM WAV."""
    import wave
    from fractions import Fraction
    import math
    rate=paired['sample_rate']; count=Fraction(paired['duration_frames'])*rate/Fraction(str(paired['fps']))
    total=math.ceil(count)
    if type(channel) is not int or channel<0:raise ValueError('Explicit played channel required')
    if Path(output).exists():raise ValueError('Preview output exists; use a new revision')
    source_spans=paired['source_samples'];timeline=paired['timeline_samples']
    if not source_spans or len(source_spans)!=len(timeline):raise ValueError('Incomplete paired geometry')
    with wave.open(str(source),'rb') as f:
        if f.getframerate()!=rate or channel>=f.getnchannels() or f.getcomptype()!='NONE':raise ValueError('PCM routing/rate mismatch')
        width=f.getsampwidth();channels=f.getnchannels();pcm=bytearray(total*width);previous=0
        for (a,b),(ta,tb) in zip(source_spans,timeline):
            if any(type(x) is not int for x in (a,b,ta,tb)) or not (0<=a<b<=f.getnframes() and previous<=ta<tb<=total and b-a==tb-ta):raise ValueError('Invalid source/timeline interval')
            if previous and ta!=previous:raise ValueError('Unexpected internal audio gap')
            f.setpos(a);raw=f.readframes(b-a)
            if len(raw)!=(b-a)*channels*width:raise ValueError('Incomplete decoded PCM')
            if channels==1:mono=raw
            else:
                import numpy as np
                mono=np.frombuffer(raw,dtype='u1').reshape(-1,channels,width)[:,channel,:].copy().tobytes()
            pcm[ta*width:tb*width]=mono;previous=tb
    Path(output).parent.mkdir(parents=True,exist_ok=True)
    with Path(output).open('xb') as handle:
        with wave.open(handle,'wb') as f:f.setnchannels(1);f.setsampwidth(width);f.setframerate(rate);f.writeframes(pcm)
    return {'source':str(Path(source).resolve()),'channel':channel,'sample_rate':rate,'samples':total,'scope':'Diagnostic assembled audio, not native export proof'}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--words',type=Path,required=True)
    ap.add_argument('--audio',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--observed',type=Path,help='Replay a saved independent transcript; never treated as a new listening run')
    ap.add_argument('--source-pcm',type=Path,help='Build a cheap diagnostic assembly into --audio before ASR')
    ap.add_argument('--paired',type=Path);ap.add_argument('--channel',type=int)
    a=ap.parse_args()
    if a.source_pcm and (a.paired is None or a.channel is None):ap.error('PCM preview requires --paired and --channel')
    if not a.source_pcm and (a.paired is not None or a.channel is not None):ap.error('Pair/channel require --source-pcm')
    if a.out.exists():ap.error('Use a new revision path')
    preview=build_preview(a.source_pcm,json.loads(a.paired.read_text()),a.audio,a.channel) if a.source_pcm else None
    expected=json.loads(a.words.read_text())['words']
    if a.observed:
        observed=json.loads(a.observed.read_text());method='REPLAY_SAVED_TRANSCRIPT'
    else:
        sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'_shared'))
        from asr import transcribe
        observed=transcribe(str(a.audio),profile='audit',use_cache=True);method='INDEPENDENT_AUDIO_ASR'
    text=observed.get('text',observed.get('transcript'))
    if not isinstance(text,str) or not text.strip():
        text=' '.join(w.get('word',w.get('text','')) for w in observed.get('words',[]))
    if not text.strip():raise ValueError('Independent transcript unavailable; never pass an empty review')
    result=compare(expected,text);result.update(audio={'path':str(a.audio.resolve()),'sha256':digest(a.audio)},
        expected={'path':str(a.words.resolve()),'sha256':digest(a.words)},method=method,observed=observed,preview=preview)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    with a.out.open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
    print(json.dumps({'status':result['status'],'differences':len(result['issues'])}))
    return int(bool(result['issues']))
if __name__=='__main__':raise SystemExit(main())
