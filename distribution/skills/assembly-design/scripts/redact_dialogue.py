#!/usr/bin/env python3
"""Replace an explicitly reviewed dialogue interval; never infer name boundaries."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfiltfilt


def mask_interval(audio, sr, start, end, ramp, seed=42):
    if not (0 <= start < end <= len(audio)):
        raise ValueError('Interval outside dialogue')
    if not (0 < ramp and 2*ramp < end-start):
        raise ValueError('Ramps must fit inside the inspected interval')
    n = end-start
    env = np.ones(n)
    env[:ramp] = np.sin(np.linspace(0, np.pi/2, ramp))**2
    env[-ramp:] = np.cos(np.linspace(0, np.pi/2, ramp))**2
    noise = sosfiltfilt(butter(3, 170, fs=sr, output='sos'), np.random.default_rng(seed).normal(size=n))
    noise /= max(float(np.max(abs(noise))), 1e-6)
    replacement = (.012*noise + .009*np.sin(2*np.pi*105*np.arange(n)/sr))*env
    result = audio.copy()
    result[start:end] = audio[start:end]*(1-env[:,None]) + replacement[:,None]
    assert np.array_equal(result[:start],audio[:start]) and np.array_equal(result[end:],audio[end:])
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('source',type=Path);p.add_argument('output',type=Path)
    p.add_argument('--start-sample',type=int,required=True);p.add_argument('--end-sample',type=int,required=True)
    p.add_argument('--source-word-id',required=True);p.add_argument('--label',required=True)
    p.add_argument('--evidence',type=Path,required=True);p.add_argument('--ramp-ms',type=float,default=8)
    a=p.parse_args()
    if a.output.exists() or a.output.with_suffix('.redaction.json').exists():p.error('Use new output paths; originals are never overwritten')
    if not a.evidence.is_file():p.error('Inspected boundary evidence is required')
    x,sr=sf.read(a.source,always_2d=True)
    y=mask_interval(x,sr,a.start_sample,a.end_sample,round(a.ramp_ms*sr/1000))
    info=sf.info(a.source)
    sf.write(a.output,y,sr,subtype=info.subtype if info.subtype in ('PCM_16','PCM_24','PCM_32','FLOAT','DOUBLE') else 'PCM_24')
    a.output.with_suffix('.redaction.json').write_text(json.dumps({'source':str(a.source),'source_sha256':hashlib.sha256(a.source.read_bytes()).hexdigest(),'source_word_id':a.source_word_id,'caption_label':a.label,'sample_range':[a.start_sample,a.end_sample],'sample_rate':sr,'frames':len(y),'evidence':str(a.evidence),'outside_interval_unchanged_before_encoding':True,'method':'Synthetic low-frequency mask; original central speech replaced; boundary ramps require inspected speech-free margins','listening':'Not established by this helper'},indent=2))
if __name__=='__main__':main()
