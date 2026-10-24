#!/usr/bin/env python3
"""Extract reference evidence with decoded timestamps. Extraction is not inspection."""
import argparse
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def extract(source,out,start,end,fps=12,all_frames=False,native_size=False):
    source,out=Path(source).resolve(),Path(out).resolve()
    if not math.isfinite(start) or not math.isfinite(end) or start<0 or end<=start:
        raise ValueError('Invalid finite inspection interval')
    if type(fps) is not int or not 1<=fps<=60:raise ValueError('Sampling fps must be 1 through 60')
    if not source.is_file():raise ValueError('Reference source is missing')
    pin=digest(source)
    probe=json.loads(subprocess.run(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(source)],check=True,capture_output=True,text=True).stdout)
    videos=[s for s in probe['streams'] if s['codec_type']=='video' and not s.get('disposition',{}).get('attached_pic')]
    if len(videos)!=1:raise ValueError('Exactly one reference video stream is required')
    duration=float(probe['format']['duration'])
    if not math.isfinite(duration) or duration<=0 or end>duration+1e-6:raise ValueError('Inspection interval exceeds finite source duration')
    audio=[s for s in probe['streams'] if s['codec_type']=='audio']
    if len(audio)>1:raise ValueError('Select a reference with one explicit audio mix before extraction')
    out.mkdir(parents=True,exist_ok=False)
    manifest={'schema':'acq-edit/reference-frames-v2','source':str(source),'sourceSha256':pin,'start':start,'end':end,
              'fps':None if all_frames else fps,'sampling':'every-native-frame' if all_frames else 'first-source-frame-per-sampling-bin',
              'imageMode':'native-display-size-png' if native_size else '960-wide-jpeg',
              'timestampBasis':'decoded presentation timestamps normalized by FFmpeg input start',
              'inputFormatStartSeconds':probe['format'].get('start_time','0'),'videoStreamIndex':videos[0]['index'],
              'evidence':'extracted-not-yet-viewed-or-listened','frames':[],'audio':None,'status':'extracting'}
    try:
        select=f'gte(t,{start})*lt(t,{end})'
        if not all_frames:select+=f'*(isnan(prev_selected_t)+gt(floor((t-{start})*{fps}),floor((prev_selected_t-{start})*{fps})))'
        suffix='png' if native_size else 'jpg'
        filters=f"select='{select}'"+('' if native_size else ',scale=960:-2')+',showinfo'
        command=['ffmpeg','-nostdin','-n','-v','info','-t',str(end),'-i',str(source),'-map',f'0:{videos[0]["index"]}',
                 '-vf',filters,'-fps_mode','vfr',str(out/f'frame-%06d.{suffix}')]
        with (out/'extraction.log').open('x') as log:
            result=subprocess.run(command,stdout=subprocess.DEVNULL,stderr=log)
        if result.returncode:raise RuntimeError(f'Frame extraction failed with status {result.returncode}; inspect extraction.log')
        log=(out/'extraction.log').read_text()
        bases=re.findall(r'config in time_base:\s*(\d+/\d+)',log)
        if not bases or len(set(bases))!=1:raise RuntimeError('Cannot establish a single decoded frame time base')
        time_base=Fraction(bases[0]);records=re.findall(r'\bn:\s*(\d+)\s+pts:\s*(-?\d+)\s+pts_time:',log)
        files=sorted(out.glob(f'frame-*.{suffix}'))
        if not records or len(records)!=len(files):raise RuntimeError('Decoded frame metadata does not match extracted images')
        previous=None
        for i,((number,pts),file) in enumerate(zip(records,files)):
            stamp=int(pts)*time_base
            if int(number)!=i or previous is not None and stamp<=previous:raise RuntimeError('Decoded frame timestamps are not ordered')
            if not start-1e-9<=float(stamp)<end+1e-9:raise RuntimeError('Decoded frame is outside the inspection interval')
            manifest['frames'].append({'file':file.name,'seconds':float(stamp),'pts':int(pts),'timeBase':str(time_base),'sha256':digest(file)})
            previous=stamp
        if audio:
            target=out/'audio.wav'
            subprocess.run(['ffmpeg','-nostdin','-n','-v','error','-ss',str(start),'-i',str(source),'-t',str(end-start),'-map',f'0:{audio[0]["index"]}','-vn','-c:a','pcm_s16le',str(target)],check=True)
            decoded=json.loads(subprocess.run(['ffprobe','-v','error','-show_streams','-of','json',str(target)],check=True,capture_output=True,text=True).stdout)['streams']
            if len(decoded)!=1 or decoded[0].get('codec_name')!='pcm_s16le' or not decoded[0].get('duration_ts'):
                raise RuntimeError('Requested interval produced no verified PCM audio samples')
            pcm=decoded[0];rate=int(pcm['sample_rate']);samples=Fraction(pcm['duration_ts'])*Fraction(pcm['time_base'])*rate
            if samples.denominator!=1 or samples<=0:raise RuntimeError('Extracted audio sample count is invalid')
            manifest['audio']={'file':target.name,'sha256':digest(target),'streamIndex':audio[0]['index'],'requestedStartSeconds':start,'requestedEndSeconds':end,'sampleRate':rate,'sampleCount':int(samples),'channels':pcm['channels'],'evidence':'extracted-not-yet-listened'}
        else:manifest['audioAbsence']='No source audio stream; do not infer silence from unplayed media'
        if digest(source)!=pin:raise RuntimeError('Reference source changed during extraction')
        manifest['status']='extracted'
    except Exception as error:
        manifest.update(status='failed',error=str(error));raise
    finally:
        with (out/'index.json').open('x') as stream:json.dump(manifest,stream,indent=2)
    return manifest


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('out',type=Path)
    p.add_argument('--start',type=float,default=0);p.add_argument('--end',type=float,required=True)
    group=p.add_mutually_exclusive_group();group.add_argument('--fps',type=int,default=12);group.add_argument('--all-frames',action='store_true')
    p.add_argument('--native-size',action='store_true',help='Keep native display dimensions and write lossless PNG images')
    a=p.parse_args();extract(a.source,a.out,a.start,a.end,a.fps,a.all_frames,a.native_size)


if __name__=='__main__':main()
