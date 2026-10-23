#!/usr/bin/env python3
"""Prepare source-linked PCM-in-MOV for sample edits without re-encoding picture.

Do this before ingest/assembly on new jobs. Existing designs require an explicit
source revision with the same video clock; never relink a reviewed timeline.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
    return h.hexdigest()


def probe(path, ffprobe):
    return json.loads(subprocess.check_output([ffprobe,'-v','error','-show_streams','-show_format','-of','json',str(path)]))


def packet_identity(path, ffprobe):
    # Packet payload and presentation clocks establish unchanged picture; audio
    # equivalence and seam listening are separate, explicitly unclaimed checks.
    raw=subprocess.check_output([ffprobe,'-v','error','-select_streams','v:0','-show_packets','-show_data_hash','sha256','-show_entries','packet=pts_time,duration_time,data_hash','-of','json',str(path)])
    return json.loads(raw)['packets']


def prepare(source, output_dir, sample_rate=48000, ffmpeg='ffmpeg', ffprobe='ffprobe'):
    source=Path(source).resolve();out=Path(output_dir).resolve()
    if sample_rate not in (44100,48000,96000):raise ValueError('Unsupported sample rate')
    info=probe(source,ffprobe)
    video=[s for s in info['streams'] if s['codec_type']=='video']
    audio=[s for s in info['streams'] if s['codec_type']=='audio']
    if len(video)!=1 or len(audio)!=1:raise ValueError('Explicit track routing required for multiple video/audio streams')
    if any(abs(float(s.get('start_time','0')))>1e-6 for s in (video[0],audio[0])):
        raise ValueError('Nonzero source stream clocks require an explicit clock-mapping workflow')
    if int(audio[0]['channels'])>2:raise ValueError('Multichannel dialogue needs explicit routing; do not downmix implicitly')
    out.mkdir(parents=True,exist_ok=False)
    media=out/'precision-source.mov';receipt=out/'audio_precision_source.json'
    data={'schema':'edit.audio-precision-source/v1','status':'PREPARING','source_path':str(source),'source_sha256':digest(source),'media_path':str(media),'sample_rate':sample_rate,'source_probe':info,'source_clock_offset_seconds':0,'listening':'not_run'}
    receipt.write_text(json.dumps(data,indent=2))
    try:
        subprocess.run([ffmpeg,'-v','error','-i',str(source),'-map','0:v:0','-map','0:a:0','-c:v','copy','-c:a','pcm_s24le','-ar',str(sample_rate),'-map_metadata','0','-n',str(media)],check=True)
        observed=probe(media,ffprobe);data['output_probe']=observed
        va=next(s for s in observed['streams'] if s['codec_type']=='video');aa=next(s for s in observed['streams'] if s['codec_type']=='audio')
        if any(va[k]!=video[0][k] for k in ('width','height','r_frame_rate','codec_name')):raise ValueError('Picture format changed')
        if aa['codec_name']!='pcm_s24le' or int(aa['sample_rate'])!=sample_rate or aa['channels']!=audio[0]['channels']:raise ValueError('PCM format mismatch')
        if any(abs(float(s.get('start_time','0')))>1e-6 for s in (va,aa)):raise ValueError('Output stream clock changed')
        a=packet_identity(source,ffprobe);b=packet_identity(media,ffprobe)
        if a!=b:raise ValueError('Compressed picture packets or presentation times changed')
        data.update(status='PCM_PREPARED_PICTURE_CLOCK_VERIFIED',media_sha256=digest(media),video_packet_count=len(a),video_packets_and_pts_identical=True,audio_source_registration='zero-start decoder clock; verify heard boundary on this derived media',audible_seam_quality='not_verified')
    except Exception as exc:
        data.update(status='FAILED_KEEP_PARTIAL_FOR_INSPECTION',error=str(exc));raise
    finally:receipt.write_text(json.dumps(data,indent=2))
    return data


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',required=True);p.add_argument('--output-dir',required=True)
    p.add_argument('--sample-rate',type=int,default=48000);p.add_argument('--ffmpeg',default='ffmpeg');p.add_argument('--ffprobe',default='ffprobe')
    a=p.parse_args();r=prepare(a.source,a.output_dir,a.sample_rate,a.ffmpeg,a.ffprobe)
    print(json.dumps({k:r[k] for k in ('status','media_path','sample_rate','video_packet_count')}))


if __name__=='__main__':main()
