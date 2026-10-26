#!/usr/bin/env python3
"""Map explicit caption-owner word groups onto frozen native cuts.

No phrase grouping, speaker guessing, capitalization or emphasis selection occurs
here. Each group is an authored decision. Refuse skipped/duplicated words and groups
crossing picture cuts, so dependent captions cannot silently use stale clocks.
"""
import argparse,copy,hashlib,json,math,sys
from pathlib import Path

def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def normalize_display(text, profile):
    # Reuse the owning caption implementation, including punctuation and case.
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'.local/skills/caption-clips/scripts'))
    from filmcraft_caption_contract import normalize_profile_case
    from caption_profiles import clean_profile_display_words
    tokens=[{'word':t.strip('“”"')} for t in text.split()]
    return normalize_profile_case(' '.join(w['word'] for w in clean_profile_display_words(tokens)),profile)

def prepare(plan,words,decisions):
    cards=[];coverage=[];fps=plan['fps']['numerator']/plan['fps']['denominator'];sr=plan['sampleRate']
    groups=decisions['groups'];cursor=0
    profile=json.loads(Path(decisions['profile']['path']).read_text()) if decisions['profile'].get('path') else None
    for cut in plan['cuts']:
        expected=[int(i) for i in cut['wordIds']];used=[]
        while cursor<len(groups) and len(used)<len(expected):
            g=groups[cursor];first,last=g['words'];ids=list(range(first,last+1))
            if last<first or expected[len(used):len(used)+len(ids)]!=ids:raise ValueError('Caption groups must cover every kept word once in playback order and remain inside a cut')
            text=' '.join(words[i]['word'] for i in ids)
            style=copy.deepcopy(decisions['styles'][g['role']]);style['emphasis']=[]
            for emphasis in g.get('emphasis',[]):
                display=normalize_display(text,profile) if profile is not None else text
                if g.get('quote'):display='“'+display+'”'
                phrase=normalize_display(emphasis['text'],profile) if profile is not None else emphasis['text'];start=display.lower().find(phrase.lower())
                if start<0 or display.lower().find(phrase.lower(),start+1)>=0:raise ValueError('Emphasis text must identify one exact caption occurrence')
                style['emphasis'].append({**emphasis,'start':start,'end':start+len(phrase),'text':display[start:start+len(phrase)]})
            offset=(cut['audioRecordSample']-cut['audioInSample'])/sr
            start=max(cut['recordFrame'],round((words[first]['start']+offset)*fps))
            end=min((cut['recordFrame']+cut['frames'])/fps,words[last]['end']+offset)
            if end<=start/fps:raise ValueError('Caption word clock does not fit cut')
            ident=f'card-{cursor+1:03d}'
            cards.append({'id':ident,'text':text,'start_frame':start,'speech_end':end,'quote':g.get('quote',False),'role':g['role'],'elapsed_frames':0,'style':style})
            coverage.append({'id':ident,'word_ids':ids});used+=ids;cursor+=1
        if used!=expected:raise ValueError('Caption groups omit selected speech')
    if cursor!=len(groups):raise ValueError('Unconsumed caption groups')
    return {'schema':'acq-edit/caption-handoff-v1','owner':'caption-clips','projectId':plan['projectId'],'clipId':plan['clipId'],'cutsFingerprint':digest(plan['cuts']),'profile':decisions['profile'],'cards':cards},coverage

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('plan','words','decisions','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();raw=json.loads(a.words.read_text());h,c=prepare(json.loads(a.plan.read_text()),raw['words'],json.loads(a.decisions.read_text()));a.output.mkdir(parents=True,exist_ok=False)
    (a.output/'handoff.json').write_text(json.dumps(h,indent=2));(a.output/'coverage.json').write_text(json.dumps(c,indent=2));print(json.dumps({'cards':len(c),'status':'authored-decisions-mapped-awaiting-ink-measurement'}))
if __name__=='__main__':main()
