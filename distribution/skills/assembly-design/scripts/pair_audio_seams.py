#!/usr/bin/env python3
"""Compile editor-inspected sample windows into continuous, sync-preserving joins.

No speech detection, word selection, padding, fades or acoustic certification.
"""
import argparse
from fractions import Fraction
import hashlib
import json
from pathlib import Path

STATUSES={'PROPOSED','LOCALLY_INSPECTED','LISTENED','EDITOR_APPROVED'}

def integer(value):
    if type(value) is not int or value<0:raise ValueError('Nonnegative integer sample/frame required')
    return value

def window(value):
    if not isinstance(value,list) or len(value)!=2:raise ValueError('Inclusive sample window required')
    a,b=map(integer,value)
    if b<a:raise ValueError('Reversed sample window')
    return a,b

def solve_join(row,spf):
    lo,hi=window(row['out_window']);li,hi2=window(row['in_window'])
    po=integer(row['preferred_out']);pi=integer(row['preferred_in'])
    if not lo<=po<=hi or not li<=pi<=hi2:raise ValueError('Preference outside inspected window')
    if not row.get('reason') or not row.get('evidence') or row.get('status') not in STATUSES:
        raise ValueError('Reason, evidence and actual review status required')
    # Exact integer arithmetic also permits a deliberately reordered source span.
    first=-(-(li-hi)//spf);last=(hi2-lo)//spf
    if last-first>10000:raise ValueError('Inspect narrower acoustic windows')
    options=[]
    for removed in range(first,last+1):
        delta=removed*spf;a=max(lo,li-delta);b=min(hi,hi2-delta)
        if a>b:continue
        desired=Fraction(po+pi-delta,2)
        outgoing=max(a,min(b,round(desired)));incoming=outgoing+delta
        cost=(outgoing-po)**2+(incoming-pi)**2
        options.append((cost,outgoing,incoming,removed))
    if not options:raise ValueError('PROVISIONAL_SEAM: no sync-preserving pair inside inspected windows')
    _,outgoing,incoming,removed=min(options)
    frame=round(Fraction(outgoing,spf))
    return {**row,'out_source_sample':outgoing,'in_source_sample':incoming,
            'out_source_frame':frame,'in_source_frame':frame+removed,
            'removed_frames':removed,'shared_offset_samples':outgoing-frame*spf}

def compile_pairs(d):
    if d.get('schema')!='edit.paired-seam-decisions/v1':raise ValueError('Unknown paired decision schema')
    rate=integer(d['sample_rate']);fps=Fraction(d['fps'])
    if rate not in (44100,48000,96000) or fps<=0:raise ValueError('Unsupported clock')
    spf=Fraction(rate,1)/fps
    if spf.denominator!=1:raise ValueError('Non-integer samples per frame; explicit rational-grid planning required')
    spf=int(spf);count=integer(d['span_count'])
    if count<1 or len(d['joins'])!=count-1:raise ValueError('Exactly one join per adjacent span required')
    first=integer(d['first_source_frame']);last=integer(d['last_source_frame'])
    frames=[[None,None] for _ in range(count)];samples=[[None,None] for _ in range(count)]
    frames[0][0]=first;samples[0][0]=integer(d.get('first_source_sample',first*spf));frames[-1][1]=last;samples[-1][1]=integer(d.get('last_source_sample',last*spf))
    if not first*spf<=samples[0][0]<(first+1)*spf or not (last-1)*spf<samples[-1][1]<=last*spf:
        raise ValueError('Outer audio edges must remain within their enclosing picture frame')
    if ('first_source_sample' in d or 'last_source_sample' in d) and not d.get('outer_edge_evidence'):
        raise ValueError('Explicit outer audio edges require source evidence')
    joins=[solve_join(r,spf) for r in d['joins']]
    for i,r in enumerate(joins):
        frames[i][1]=r['out_source_frame'];frames[i+1][0]=r['in_source_frame']
        samples[i][1]=r['out_source_sample'];samples[i+1][0]=r['in_source_sample']
    timeline=[];frame_cursor=0;sample_cursor=samples[0][0]-first*spf
    leading_samples=sample_cursor
    for f,s in zip(frames,samples):
        if f[0]<0 or f[1]<=f[0] or s[0]<0 or s[1]<=s[0]:raise ValueError('Non-positive kept span')
        t=[(frame_cursor-f[0])*spf+x for x in s]
        if t[0]!=sample_cursor:raise ValueError('Unintended audio gap or overlap')
        timeline.append(t);frame_cursor+=f[1]-f[0];sample_cursor=t[1]
    trailing_samples=frame_cursor*spf-sample_cursor
    if not 0<=trailing_samples<spf:raise ValueError('Outer duration mismatch')
    return {'schema':'edit.paired-seam-result/v1','fps':str(fps),'sample_rate':rate,
            'source_frames':frames,'source_samples':samples,'timeline_samples':timeline,
            'joins':joins,'duration_frames':frame_cursor,'internal_gap_samples':0,
            'outer_picture_only_samples':[leading_samples,trailing_samples],
            'verification':'GEOMETRY_ONLY; acoustic status remains attached to each decision'}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('decisions',type=Path);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--selection',type=Path,help='Exact pause-split v2 selection; otherwise use decisions.selection when present')
    p.add_argument('--clip-id');p.add_argument('--phonemes',type=Path);a=p.parse_args()
    data=a.decisions.read_bytes();decisions=json.loads(data);result=compile_pairs(decisions);result.update(decisions_path=str(a.decisions.resolve()),decisions_sha256=hashlib.sha256(data).hexdigest())
    selection=a.selection or decisions.get('selection')
    if selection:
        from validate_paired_word_coverage import validate
        coverage=validate(selection,result,a.clip_id,a.phonemes)
        result['word_coverage']=coverage
        if coverage['wholly_outside_word_count']:
            # Keep the rejected evidence at a different name so an importer cannot
            # mistake the requested output path for an executable successful plan.
            rejected=a.out.with_name(a.out.stem+'.rejected-word-coverage.json')
            with rejected.open('x')as f:json.dump(result,f,indent=2);f.write('\n')
            raise SystemExit('SELECTED_WORD_OUTSIDE_AUDIO: inspect source occurrences; rejected evidence: '+str(rejected))
    else:
        result['word_coverage']={'status':'UNBOUND_LEGACY_GEOMETRY_ONLY','scope':'No selected-word containment was checked; not a new spoken-assembly handoff.'}
    with a.out.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps({'status':'PAIRED_GEOMETRY_COMPILED','spans':len(result['source_frames']),'duration_frames':result['duration_frames']}))

if __name__=='__main__':main()
