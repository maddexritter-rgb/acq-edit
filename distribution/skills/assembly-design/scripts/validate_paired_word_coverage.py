#!/usr/bin/env python3
"""Locate selected words outside paired audio, without certifying phonetic edges.

Use the exact pause-split selection corresponding one-to-one with paired spans.
Word/phoneme locators remain uncertain: a conflict needs source inspection and a
separate corrected timing map, never automatic padding or deletion of selected words.
When phoneme (MFA) bounds describe the same occurrence as the transcript label, they
decide containment: zero-length, squeezed or stretched ASR labels are reported as
superseded, not refused. MFA on another occurrence still refuses.
"""
import argparse
from decimal import Decimal, ROUND_FLOOR, ROUND_CEILING
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from join_check import same_occurrence  # noqa: E402


def pin(path):
    p=Path(path)
    return {'path':str(p.resolve()),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}


def validate(selection_path, paired, clip_id=None, phonemes_path=None):
    selection=json.loads(Path(selection_path).read_text())
    if selection.get('schema')!='edit.assembly-selection/v2':raise ValueError('v2 selection required')
    clips=[c for c in selection['clips'] if clip_id is None or c['id']==clip_id]
    if len(clips)!=1:raise ValueError('select exactly one clip with --clip-id')
    c=clips[0];wp=Path(c['source_words']);words_pin=pin(wp)
    if c.get('source_words_sha256') and c['source_words_sha256']!=words_pin['sha256']:
        raise ValueError('source word hash changed')
    data=json.loads(wp.read_text());ww=data['words'] if isinstance(data,dict) else data
    wm={w.get('word_index',i):w for i,w in enumerate(ww)}
    ranges=c['kept_word_ranges'];spans=paired['source_samples'];rate=paired['sample_rate']
    if paired.get('schema')!='edit.paired-seam-result/v1' or len(ranges)!=len(spans):
        raise ValueError('paired spans must match the exact pause-split selected ranges')
    phones=json.loads(Path(phonemes_path).read_text()).get('words',{}) if phonemes_path else {}
    issues=[]
    for span,((first,last),(head,tail)) in enumerate(zip(ranges,spans)):
        if type(head)is not int or type(tail)is not int or head<0 or tail<=head:raise ValueError('invalid paired samples')
        for i in range(first,last+1):
            w=wm[i]
            locators=[('transcript',w['start'],w['end'])];superseded=False
            if str(i) in phones:
                ph=phones[str(i)]
                if ph.get('word_index',i)!=i:raise ValueError('phoneme word identity mismatch')
                locators.append(('phoneme',ph['aligned_start'],ph['aligned_end']))
                superseded=same_occurrence((w['start'],w['end']),(ph['aligned_start'],ph['aligned_end']))
            conflicts=[]
            for kind,start,end in locators:
                st=int((Decimal(str(start))*rate).to_integral_value(rounding=ROUND_FLOOR))
                en=int((Decimal(str(end))*rate).to_integral_value(rounding=ROUND_CEILING))
                if en<st:raise ValueError('reversed locator')
                outside=en<=head or st>=tail
                partial=st<head or en>tail
                if outside or partial:
                    conflicts.append({'locator':kind,'interval_samples':[st,en],
                                      'relation':'WHOLLY_OUTSIDE' if outside else 'PARTIAL',
                                      'missing_head_samples':max(0,min(en,head)-st),
                                      'missing_tail_samples':max(0,en-max(st,tail)),
                                      **({'superseded_by':'phoneme'} if kind=='transcript' and superseded else {})})
            if conflicts:issues.append({'span':span,'word_index':i,'word':w.get('word',w.get('text')),
                                       'kept_samples':[head,tail],'conflicts':conflicts})
    missing=[i for i in issues if any(c['relation']=='WHOLLY_OUTSIDE' and 'superseded_by' not in c for c in i['conflicts'])]
    return {'schema':'edit.paired-word-coverage/v1','clip_id':c['id'],
            'status':'SELECTED_WORD_OUTSIDE_AUDIO' if missing else ('BOUNDARY_REVIEW_REQUIRED' if issues else 'LOCATORS_CONTAINED'),
            'selection':pin(selection_path),'source_words':words_pin,
            'phonemes':pin(phonemes_path) if phonemes_path else None,
            'scope':'Locator containment only. No listening, phonetic completeness, unwanted-neighbor or cadence certification.',
            'issues':issues,'wholly_outside_word_count':len(missing)}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--selection',type=Path,required=True)
    p.add_argument('--paired',type=Path,required=True);p.add_argument('--clip-id');p.add_argument('--phonemes',type=Path)
    p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    result=validate(a.selection,json.loads(a.paired.read_text()),a.clip_id,a.phonemes);result['paired']=pin(a.paired)
    with a.out.open('x')as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps({'status':result['status'],'wholly_outside_word_count':result['wholly_outside_word_count'],'issues':len(result['issues'])}))
    return 2 if result['wholly_outside_word_count'] else 0


if __name__=='__main__':raise SystemExit(main())
