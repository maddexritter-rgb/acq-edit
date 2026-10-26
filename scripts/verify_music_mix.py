#!/usr/bin/env python3
"""Measure an additive native music render against its dialogue-only baseline.

This is signal comparison, not listening or editorial approval. Supply the full
project-owned music source and exact selected source-in sample at 48 kHz.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import numpy as np
from scipy.signal import correlate


def pcm(path):
    result=subprocess.run(['ffmpeg','-v','error','-i',str(path),'-map','0:a:0','-vn','-ar','48000','-ac','2','-f','f32le','-'],capture_output=True,check=True)
    return np.frombuffer(result.stdout,dtype='<f4').reshape(-1,2).astype(np.float64)


def video_hash(path):
    return subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-map','0:v:0','-an','-pix_fmt','yuv420p','-f','hash','-hash','sha256','-'],text=True).strip()


def measure(baseline, mixed, source, source_in_sample, duration_samples):
    if source_in_sample<0 or duration_samples<=0:raise ValueError('Invalid source range')
    before,after,music=pcm(baseline),pcm(mixed),pcm(source)
    if len(before)!=len(after) or len(before)<duration_samples or len(music)<source_in_sample+duration_samples:
        raise ValueError('Rendered lengths or selected source range differ')
    # Locate the actual recording independently of native source-mark metadata.
    # Use the added signal in a steady body window; this also catches wrong
    # subclip offsets that can pass a metadata-only readback.
    stride=48;rate=48000/stride;start,stop=5*48000,15*48000
    if duration_samples<stop:raise ValueError('Offset comparison needs a 15-second clip')
    query=(after[start:stop]-before[start:stop]).mean(axis=1)[::stride]
    full=music.mean(axis=1)[::stride]
    correlations=correlate(full,query,mode='valid',method='fft')
    energies=full*full
    cumulative=np.concatenate(([0.],np.cumsum(energies)))
    windows=cumulative[len(query):]-cumulative[:-len(query)]
    scores=correlations/np.sqrt(np.maximum(windows*float(query@query),1e-30))
    best=int(np.argmax(scores))
    fine_start=max(0,best*stride-2*stride)
    fine_stop=min(len(music),best*stride+len(query)*stride+2*stride)
    fine_query=(after[start:stop]-before[start:stop]).mean(axis=1)
    fine_source=music[fine_start:fine_stop].mean(axis=1)
    fine=correlate(fine_source,fine_query,mode='valid',method='fft')
    detected_sample=fine_start+int(np.argmax(fine))-start
    actual_start=detected_sample/48000
    offset={'bodyWindow':[5,15],'coarseResolutionSeconds':stride/48000,
            'expectedSourceStartSeconds':source_in_sample/48000,
            'detectedSourceStartSeconds':actual_start,'detectedSourceStartSample':detected_sample,
            'differenceSamples':detected_sample-source_in_sample,'coarseCorrelation':float(scores[best])}
    if detected_sample>=0 and detected_sample+stop<=len(music):
        x=music[detected_sample+start:detected_sample+stop]
        y=after[start:stop]-before[start:stop]
        offset['alignedBodyGainDb']=[float(20*np.log10(abs(float(x[:,ch]@y[:,ch])/float(x[:,ch]@x[:,ch])))) for ch in range(2)]
    music=music[source_in_sample:source_in_sample+duration_samples]
    rows=[]
    end=duration_samples/48000
    for start,stop in [(0,.1),(.2,.3),(.6,1.6),(10,20),(30,40),(end-.6,end-.5),(end-.1,end)]:
        lo,hi=round(start*48000),round(stop*48000)
        if lo<0 or hi>duration_samples:continue
        # Joint regression separates the original speech and source music. It
        # exposes incorrect routing/gain even when total mix energy is nonzero.
        channels=[]
        for channel in range(2):
            x=np.stack([before[lo:hi,channel],music[lo:hi,channel]],axis=1)
            y=after[lo:hi,channel]
            gain,_,_,_=np.linalg.lstsq(x,y,rcond=None)
            residual=y-x@gain
            channels.append({'dialogueGain':float(gain[0]),'musicGain':float(gain[1]),
                             'musicDb':float(20*np.log10(abs(gain[1]))) if gain[1] else None,
                             'residualRms':float(np.sqrt(np.mean(residual**2)))})
        rows.append({'start':start,'end':stop,'channels':channels})
    a,b=video_hash(baseline),video_hash(mixed)
    return {'schema':'acq-edit/music-mix-measurement-v1','audioFrames':len(before),'plannedFrames':duration_samples,
            'decodedPicturesIdentical':a==b,'baselinePictureHash':a,'mixedPictureHash':b,
            'sourceOffsetCheck':offset,'windows':rows,'qualification':'Measured signals only; no listening, caption/content review, or human approval.'}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['baseline','mixed','source','out']:p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--source-in-sample',type=int,required=True);p.add_argument('--duration-samples',type=int,required=True)
    args=p.parse_args()
    if args.out.exists():raise ValueError('Measurement output exists')
    result=measure(args.baseline,args.mixed,args.source,args.source_in_sample,args.duration_samples)
    result['inputs']={key:{'path':str(getattr(args,key).resolve()),'sha256':hashlib.sha256(getattr(args,key).read_bytes()).hexdigest()} for key in ['baseline','mixed','source']}
    with args.out.open('x') as stream:json.dump(result,stream,indent=2)
    print(json.dumps(result,indent=2))
