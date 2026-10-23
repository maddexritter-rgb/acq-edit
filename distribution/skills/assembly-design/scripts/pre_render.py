#!/usr/bin/env python3
"""Validate a backend-neutral construction packet before starting an exporter.
This is evidence/geometry validation, never an acoustic or editorial approval.
"""
import argparse,hashlib,json,pathlib,subprocess,sys
from fractions import Fraction

_digests={}
def digest(p):
    p=pathlib.Path(p).resolve();st=p.stat();key=(str(p),st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns)
    if key not in _digests:
        h=hashlib.sha256()
        with p.open('rb') as f:
            for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
        _digests[key]=h.hexdigest()
    return _digests[key]
def evidence(e):
    if not isinstance(e,dict)or not e.get('path')or not e.get('sha256'):raise ValueError('Missing bound evidence')
    if digest(e['path'])!=e['sha256']:raise ValueError('Stale evidence: '+str(e['path']))
def inspect_picture_plan(x):
    """Validate the assembly-owned plan; visual evidence remains owner-inspected."""
    if 'picture_plan' not in x:
        if x.get('content_format')=='qa':
            raise ValueError('Q&A requires an opening split picture plan')
        return  # Historical/single-camera packets retain their existing contract.
    evidence(x['picture_plan'])
    plan=json.loads(pathlib.Path(x['picture_plan']['path']).read_text())
    if plan.get('schema')!='edit.picture-plan/v2':
        raise ValueError('Expected edit.picture-plan/v2')
    evidence(plan['spoken_selection'])
    if plan['spoken_selection']!=x.get('spoken_selection'):
        raise ValueError('Picture plan targets a different spoken revision')
    if not plan.get('split_opportunities'):
        raise ValueError('Missing split opportunity decision')
    if not x.get('content_format') or not plan.get('content_format'):
        raise ValueError('Picture handoff requires explicit content_format in packet and plan')
    if x['content_format']!=plan['content_format']:
        raise ValueError('Picture plan content_format differs from construction packet')
    formats={x.get('content_format'),plan.get('content_format')}
    if 'qa' in formats:
        shots=plan.get('shots',[])
        opening=shots[0] if shots else {}
        override=plan.get('opening_layout_override',{})
        waived=(override.get('authority')=='user' and bool(override.get('instruction','').strip()))
        if not waived:
            if opening.get('timeline_frames',[None])[0]!=0 or opening.get('layout')!='split':
                raise ValueError('Q&A requires synchronized opening split from frame zero; coverage gaps must be resolved, not silently replaced by a single')
            roles={p.get('role') for p in opening.get('panels',[])}
            if roles!={'host','guest'}:
                raise ValueError('Q&A opening split must show the actual host and guest')
    ticks=254016000000
    frame_ticks=Fraction(ticks,1)/Fraction(x['fps'])
    end=0
    ids=set()
    for shot in plan['shots']:
        a,b=shot['timeline_frames']
        if type(a)!=int or type(b)!=int or a!=end or b<=a:
            raise ValueError('Picture plan has a gap, overlap or invalid interval')
        if not shot.get('id') or shot['id'] in ids:
            raise ValueError('Missing/duplicate picture occurrence ID')
        ids.add(shot['id'])
        layout=shot['layout'];panels=shot['panels']
        if layout not in ('single','split') or len(panels)!=(2 if layout=='split' else 1):
            raise ValueError('Missing or unexpected picture panel')
        if not shot.get('editorial_reason'):
            raise ValueError('Picture decision lacks a reason')
        positions=[];clocks=[]
        for panel in panels:
            if panel.get('quality')!='usable' or panel.get('face_visible') is not True:
                raise ValueError('Unusable dialogue panel: focus/visibility/rear view unresolved')
            if not panel.get('role') or not panel.get('visible_participant') or not panel.get('observed_picture'):
                raise ValueError('Panel participant or observed picture missing')
            if panel.get('participant_matches_intent') is not True:
                raise ValueError('Wrong or unresolved picture participant')
            evidence(panel['media']);source=panel['source_ticks']
            if len(source)!=2 or any(type(v)!=int for v in source) or source[0]<0 or source[1]-source[0]!=(b-a)*frame_ticks:
                raise ValueError('Panel source duration/clock mismatch')
            if not panel.get('visual_evidence'):
                raise ValueError('Panel lacks bound visual evidence')
            for e in panel['visual_evidence']:evidence(e)
            if layout=='split':
                framing=panel.get('panel_framing',{})
                if framing.get('status')!='INSPECTED' or not framing.get('samples'):
                    raise ValueError('Split requires inspected complete-head framing')
                left,top,right,bottom=framing['panel_rect']
                if not(left<right and top<bottom):raise ValueError('Invalid panel rectangle')
                clearance=framing['minimum_headroom_px']
                if clearance<=0:raise ValueError('Missing deliberate panel headroom')
                for sample in framing['samples']:
                    evidence(sample['evidence'])
                    x0,y0,x1,y1=sample['head_bounds']
                    if not(left<=x0<x1<=right and top+clearance<=y0<y1<=bottom):
                        raise ValueError('Complete head violates panel bounds/headroom')
                    if (y1-y0)/(bottom-top)>framing['maximum_head_height_fraction']:
                        raise ValueError('Subject exceeds planned panel shot size')
            positions.append(panel['placement'])
            offset=panel['session_offset_ticks']
            if type(offset)!=int:raise ValueError('Invalid panel session clock')
            clocks.append(source[0]+offset)
        if len(set(positions))!=len(positions):
            raise ValueError('Duplicate split panel placement')
        if layout=='single' and positions!=['full']:
            raise ValueError('Single shot requires full placement')
        if layout=='split' and max(clocks)-min(clocks)>ticks/x['sample_rate']:
            raise ValueError('Split panels are not synchronized')
        end=b
    if end!=x['duration_frames']:
        raise ValueError('Picture plan does not cover the current dialogue')

def inspect_approved_cta(x, body_end):
    """Check a full catalog asset after spoken spans, without synthetic words."""
    spec=x.get('approved_cta')
    if spec is None:return body_end
    for key in ('compiled','media','native_baseline'):evidence(spec[key])
    sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[2]/'edit/scripts'))
    from compile_assembly import validate_compiled
    compiled=validate_compiled(pathlib.Path(spec['compiled']['path']))
    clips=[c for c in compiled['clips']if c['id']==spec['clip_id']]
    if len(clips)!=1 or not clips[0].get('approved_cta'):raise ValueError('Missing compiled approved CTA')
    clip=clips[0];cta=clip['approved_cta'];f,g=spec['source_frames'];a,b=spec['timeline_frames']
    if (any(type(n)is not int for n in (f,g,a,b))or [f,g]!=cta['source_frames']or f!=0
            or a!=body_end or b-a!=g-f or b!=x['duration_frames']
            or spec['media']!={'path':cta['media'],'sha256':cta['media_sha256']}
            or str(pathlib.Path(x['source_words']['path']).resolve())!=clip['source_words']
            or Fraction(cta['fps'])!=Fraction(x['fps'])):
        raise ValueError('CTA is not the intact compiled asset directly after the body')
    baseline=json.loads(pathlib.Path(spec['native_baseline']['path']).read_text())
    baseline=baseline.get('data',baseline)
    if baseline.get('project')!=str(pathlib.Path(x['native_project']['path']).resolve())or baseline.get('sequence')!=spec['sequence_id']:
        raise ValueError('CTA native baseline project/sequence mismatch')
    offset=int(spec['native_start_ticks']);step=Fraction(254016000000,1)/Fraction(x['fps'])
    if step.denominator!=1:raise ValueError('CTA frame grid is not exact')
    start,end=offset+a*step,offset+b*step
    for kind in (0,1):
        overlaps=[]
        for track in baseline['state']['tracks']:
            if track['kind']!=kind:continue
            for item in track['clips']:
                if int(item['start'])<end and int(item['end'])>start:
                    if track.get('muted')or item.get('disabled'):raise ValueError('Muted/disabled CTA')
                    overlaps.append(item)
        if len(overlaps)!=1:raise ValueError('Unexpected picture/audio over the CTA interval')
        item=overlaps[0]
        if (item['path']!=cta['media']or [int(item['start']),int(item['end']),int(item['sourceIn']),int(item['sourceOut'])]
                !=[start,end,f*step,g*step]):raise ValueError('Native CTA differs from full-asset placement')
    return b


def inspect(x):
    if x.get('schema')!='edit.pre-render/v1':raise ValueError('Expected edit.pre-render/v1')
    for key in ['native_project','source_words','picture_evidence']:evidence(x[key])
    for pin in x.get('dependencies',[]):evidence(pin)
    inspect_picture_plan(x)
    words=json.loads(pathlib.Path(x['source_words']['path']).read_text())['words']
    visual=json.loads(pathlib.Path(x['picture_evidence']['path']).read_text())
    evidence(visual['source']);evidence(x['audio_source'])
    if visual['source']!=x['picture_source']:raise ValueError('Picture evidence source identity mismatch')
    fps=Fraction(x['fps']);rate=x['sample_rate'];spf=Fraction(rate,1)/fps
    if fps<=0 or not isinstance(rate,int)or rate<=0:raise ValueError('Invalid clock')
    spans=x['spans'];issues=[];prev_audio=None;prev_frame=0
    if not spans:raise ValueError('Empty assembly')
    if len(visual['spans'])!=len(spans):raise ValueError('Missing picture coverage')
    for i,(s,v)in enumerate(zip(spans,visual['spans'])):
        a,b=s['source_samples'];t,u=s['timeline_samples'];f,g=s['source_frames'];ft,gt=s['timeline_frames']
        if any(not isinstance(n,int)for n in [a,b,t,u,f,g,ft,gt]):raise ValueError('Noninteger geometry')
        if not(0<=a<b and 0<=t<u and 0<=f<g and ft==prev_frame<gt):raise ValueError('Invalid/noncontinuous picture geometry')
        if u-t!=b-a or (prev_audio is not None and t!=prev_audio):raise ValueError('Audio gap/overlap or retiming')
        if g-f!=gt-ft:raise ValueError('Unsupported picture retiming')
        if abs(Fraction(t-a)-(ft-f)*spf)>spf:raise ValueError('AV offset exceeds one frame')
        if v['source_frames']!=[f,g]:raise ValueError('Stale ordered tracking geometry')
        if v.get('status')not in ('subject_visible','intentional_cutaway'):issues.append({'span':i,'reason':'NO_PICTURE_COVERAGE'})
        if v.get('status')=='intentional_cutaway':evidence(v['treatment'])
        first,last=s['word_range']
        if not 0<=first<=last<len(words):raise ValueError('Invalid source words')
        if words[first]['end']<=a/rate or words[last]['start']>=b/rate:issues.append({'span':i,'reason':'SELECTED_WORD_OUTSIDE_AUDIO'})
        nxt=words[last+1]['start']if last+1<len(words)else float('inf');end=words[last]['end']
        fused=nxt-end<.040 and b/rate<end+.020
        if fused:
            resolution=s.get('release_resolution')
            if resolution and resolution.get('source_sample')==b and resolution.get('method')in ('source_inspected','user_accepted'):
                evidence(resolution['evidence'])
            else:issues.append({'span':i,'reason':'FUSED_RELEASE_CONTEXT','action':'Inspect intact phrase or choose a source-native phrase; do not add blanket padding.'})
        prev_audio=u;prev_frame=gt
    body_end=prev_frame
    prev_frame=inspect_approved_cta(x,body_end)
    if prev_frame!=x['duration_frames']:raise ValueError('Duration mismatch')
    required=x.get('required_picture_lead_frames',0)
    if spans[0]['timeline_samples'][0]<required*spf:issues.append({'reason':'MISSING_REQUIRED_PICTURE_LEAD'})
    if prev_audio>prev_frame*spf:raise ValueError('Audio extends beyond picture')
    return {'status':'BLOCKED'if issues else'CONSTRUCTION_VALID','issues':issues,'claims':'Bound construction evidence only; not listening, human approval or semantic judgment.'}
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--packet',required=True);ap.add_argument('--out',required=True);ap.add_argument('command',nargs=argparse.REMAINDER);a=ap.parse_args()
    path=pathlib.Path(a.packet);before=digest(path);x=json.loads(path.read_text())
    try:r=inspect(x)
    except (ValueError,KeyError,TypeError,IndexError,OSError,ZeroDivisionError)as e:r={'status':'BLOCKED','issues':[{'reason':str(e)}]}
    r['packet_sha256']=before;out=pathlib.Path(a.out);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(r,indent=2))
    if r['status']!='CONSTRUCTION_VALID':print(json.dumps(r));raise SystemExit(2)
    if digest(path)!=before:raise SystemExit('Packet changed during inspection')
    cmd=a.command[1:]if a.command[:1]==['--']else a.command
    if cmd:
        # Recheck bound inputs immediately before starting the exact exporter supplied by the owner.
        if inspect(x)['status']!='CONSTRUCTION_VALID':raise SystemExit(2)
        raise SystemExit(subprocess.run(cmd).returncode)
    print(json.dumps(r))
if __name__=='__main__':main()
