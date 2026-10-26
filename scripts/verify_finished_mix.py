#!/usr/bin/env python3
"""Measure rendered dialogue/music gain against exact frozen source clocks.

No loudness normalization, resynchronization or output repair is performed.
This is signal evidence, never listening or editorial approval.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import numpy as np


def decode(path,channels):
    raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-map','0:a:0','-vn','-ar','48000','-ac',str(channels),'-f','f32le','-'])
    return np.frombuffer(raw,dtype='<f4').reshape(-1,channels).astype(np.float64)


def run(a):
    plan=json.loads(a.plan.read_text())
    if plan['sampleRate']!=48000 or len(plan['audio']['music'])!=1:raise ValueError('Requires one music bed and 48 kHz design')
    sources={s['id']:s for s in plan['sources']};music=plan['audio']['music'][0]
    for source in sources.values():
        if hashlib.sha256(Path(source['path']).read_bytes()).hexdigest()!=source['sha256']:raise ValueError('Source bytes changed')
    total=round(sum(c['frames'] for c in plan['cuts'])*48000*plan['fps']['denominator']/plan['fps']['numerator'])
    speech=np.zeros(total);cache={}
    for cut in plan['cuts']:
        sid=cut.get('audioSourceId',cut['sourceId'])
        if sid not in cache:
            streams=[s for s in sources[sid]['probe']['streams'] if s['codec_type']=='audio']
            if len(streams)!=1 or streams[0]['channels']!=1:raise ValueError('This analysis requires verified mono dialogue')
            cache[sid]=decode(sources[sid]['path'],1)[:,0]
        n=cut['audioSamples'];start=cut['audioRecordSample'];src=cut['audioInSample']
        speech[start:start+n]+=cache[sid][src:src+n]
    bed=decode(sources[music['sourceId']]['path'],2)[music['sourceInSample']:music['sourceInSample']+total]
    rendered=decode(a.render,2)
    if a.delay_samples<0 or len(rendered)<total+a.delay_samples:raise ValueError('Render does not cover the requested comparison')
    rendered=rendered[a.delay_samples:a.delay_samples+total]
    rows=[]
    for cut in plan['cuts']:
        lo=max(cut['audioRecordSample']+4800,48000)
        hi=min(cut['audioRecordSample']+cut['audioSamples']-4800,total-48000)
        if hi-lo<4800:continue
        channels=[]
        for ch in range(2):
            x=np.column_stack((speech[lo:hi],bed[lo:hi,ch]));y=rendered[lo:hi,ch]
            gains=np.linalg.lstsq(x,y,rcond=None)[0];residual=y-x@gains
            channels.append({'dialogueDb':float(20*np.log10(abs(gains[0]))),'musicDb':float(20*np.log10(abs(gains[1]))),'residualRms':float(np.sqrt(np.mean(residual**2)))})
        rows.append({'cut':cut['id'],'fromSample':lo,'toSample':hi,'channels':channels})
    result={'schema':'acq-edit/finished-mix-measurement-v1','planSha256':hashlib.sha256(a.plan.read_bytes()).hexdigest(),'render':str(a.render),'renderSha256':hashlib.sha256(a.render.read_bytes()).hexdigest(),'comparisonDelaySamples':a.delay_samples,'plannedSamples':total,'peak':float(np.max(np.abs(rendered))),'windows':rows,'expectedDialogueDb':plan['audio']['gainDb'],'expectedMusicDb':music['gainDb'],'qualification':'Signal measurements only; no listening or human approval'}
    with a.output.open('x') as f:json.dump(result,f,indent=2)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('plan','render','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--delay-samples',type=int,default=0)
    print(json.dumps(run(p.parse_args()),indent=2))
