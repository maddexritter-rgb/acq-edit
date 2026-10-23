#!/usr/bin/env python3
"""Place a bound source-word/paired-sample design in a NEW isolated Filmcraft project.

No selection, waveform inference, caption design, or live-project replacement.
"""
import argparse
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/'edit/scripts'))
from filmcraft_client import Filmcraft
from compile_assembly import validate_compiled
from pair_audio_seams import compile_pairs
from validate_paired_word_coverage import validate
T=254016000000

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def probe(p):return json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(p)]))['streams']
def prepare(packet):
    x=json.loads(Path(packet).read_text());comp=validate_compiled(Path(x['compiled']))
    if json.loads(Path(comp['design_path']).read_text()).get('schema')!='edit.assembly-selection/v2':raise ValueError('v2 selection required')
    clips=[c for c in comp['clips'] if c['id']==x['clip_id']]
    if len(clips)!=1:raise ValueError('Exact clip id required')
    clip=clips[0];dec=json.loads(Path(x['decisions']).read_text());p=compile_pairs(dec)
    coverage=validate(comp['design_path'],p,x['clip_id'],x.get('phonemes'))
    if coverage['wholly_outside_word_count']:raise ValueError('Selected word outside played audio')
    if any(j['status']=='PROPOSED' for j in p['joins']):raise ValueError('Inspect both sides of every join before execution')
    if dec.get('outer_edge_evidence',{}).get('status') not in ('LOCALLY_INSPECTED','LISTENED','EDITOR_APPROVED'):raise ValueError('Inspect both outer edges')
    routing=json.loads(Path(x['routing']).read_text());e=routing['evidence']
    if sha(e['path'])!=e['sha256']:raise ValueError('Stale routing evidence')
    if Path(routing['media']).resolve()!=Path(x['audio']).resolve() or Path(clip['media']).resolve()!=Path(x['audio']).resolve():raise ValueError('Selection, routing and played audio identity differ')
    if Path(routing['picture']).resolve()!=Path(x['picture']).resolve():raise ValueError('Picture routing identity differs')
    if routing.get('source_clock_offset_samples')!=0:raise ValueError('Conform nonzero picture/audio source offsets first')
    rate=p['sample_rate'];fps=Fraction(p['fps']);ft=Fraction(T,1)/fps;st=Fraction(T,rate)
    if ft.denominator!=1 or st.denominator!=1:raise ValueError('Unsupported tick grid')
    au=[s for s in probe(x['audio']) if s['codec_type']=='audio'];vi=[s for s in probe(x['picture']) if s['codec_type']=='video']
    if len(au)!=1 or not au[0]['codec_name'].startswith('pcm_') or int(au[0]['sample_rate'])!=rate:raise ValueError('Matched-rate PCM with one explicit stream required')
    if au[0]['channels'] not in (1,2) or routing.get('stream')!=0 or routing.get('channel') not in range(au[0]['channels']):raise ValueError('Unsupported/unknown routing')
    if len(vi)!=1 or Fraction(vi[0]['r_frame_rate'])!=fps or Fraction(vi[0]['avg_frame_rate'])!=fps:raise ValueError('This adapter requires matched constant source/sequence fps')
    if len(clip['spans'])!=len(p['source_frames']):raise ValueError('Span mismatch')
    p['word_coverage']=coverage
    return x,clip,p,int(ft),int(st),vi[0]

def execute(packet,binary,out):
    x,clip,p,F,S,video=prepare(packet);out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False)
    proof={k:{'path':str(Path(x[k]).resolve()),'sha256':sha(x[k])} for k in ('compiled','decisions','routing')};(out/'input-proof.json').write_text(json.dumps(proof,indent=2));(out/'paired.json').write_text(json.dumps(p,indent=2))
    m=Filmcraft(binary,out/'build')
    try:
        imp=m.tool('media_import',{'paths':[x['picture'],x['audio']]})
        if imp.get('errors'):raise RuntimeError(imp)
        m.run('file.newSequence',{'name':x.get('title',clip['id']),'width':video['width'],'height':video['height'],'fps':float(Fraction(p['fps'])),'video':3,'audio':1});cur=0
        for a,b in p['source_frames']:
            m.run('timeline.place',{'item':imp['items'][0],'track':'V1','audioTrack':'A1','time':cur*F,'sourceIn':a*F,'duration':(b-a)*F,'insert':False});cur+=b-a
        m.run('file.saveAs',{'path':str(out/'frame-assembly.fcproj')})
    finally:m.close()
    data=json.loads((out/'frame-assembly.fcproj').read_text());seq=data['project']['items'][str(data['view']['active_sequence'])]['kind']['Sequence'];audio=seq['audio_tracks'][0]['items']
    if len(audio)!=len(p['source_samples']):raise ValueError('Expected linked audio from picture import; no silent fallback')
    for c,(a,b),(ta,tb) in zip(audio,p['source_samples'],p['timeline_samples']):c.update(item=imp['items'][1],name='Source PCM dialogue',start=ta*S,duration=(b-a)*S,source_in=a*S)
    fc=out/'assembly.fcproj';fc.write_text(json.dumps(data,indent=2));m=Filmcraft(binary,out/'reopen',fc)
    try:
        s=m.tool('sequence_inspect');vv=s['video'][0]['items'];aa=s['audio'][0]['items'];assert len(vv)==len(aa)==len(p['source_frames']);assert s['durationFrames']==p['duration_frames'];cur=0
        for v,a,(fi,fo),(si,so),(ti,to) in zip(vv,aa,p['source_frames'],p['source_samples'],p['timeline_samples']):
            assert (v['start'],v['sourceIn'],v['duration'])==(cur*F,fi*F,(fo-fi)*F)
            assert (a['start'],a['sourceIn'],a['duration'])==(ti*S,si*S,(so-si)*S)
            assert v['link'] is not None and v['link']==a['link']
            assert v['start']-v['sourceIn']==a['start']-a['sourceIn'];cur+=fo-fi
        (out/'readback.json').write_text(json.dumps(s,indent=2));m.run('file.save')
    finally:m.close()
    result={'project':str(fc),'frames':cur,'linked_pairs':len(vv),'word_coverage':p['word_coverage'],'verification':'NATIVE_GEOMETRY_AND_REOPEN; export/listening remain separate'};(out/'result.json').write_text(json.dumps(result,indent=2));return result

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--packet',required=True);ap.add_argument('--binary',required=True);ap.add_argument('--out',required=True);ap.add_argument('--validate-only',action='store_true');a=ap.parse_args()
    if a.validate_only:
        x,c,p,*_=prepare(a.packet);print(json.dumps({'clip':c['id'],'frames':p['duration_frames'],'word_coverage':p['word_coverage']}))
    else:print(json.dumps(execute(a.packet,a.binary,a.out)))
if __name__=='__main__':main()
