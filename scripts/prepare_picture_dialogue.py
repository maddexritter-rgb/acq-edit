#!/usr/bin/env python3
"""Register same-clock picture and explicit PCM dialogue as a Premiere source.

Copies compressed picture and PCM packets; never renders or cuts a timeline.
The supplied source-clock evidence must establish the shared zero origin.
"""
import argparse, hashlib, json, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.local/skills/assembly-design/scripts'))
from prepare_audio_precision import digest, probe, packet_identity

def audio_hash(path):
    return subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-map','0:a:0','-c:a','pcm_s24le','-f','hash','-hash','sha256','-']).decode().strip()

def prepare(picture,dialogue,evidence,output):
    picture,dialogue,evidence,output=map(lambda p:Path(p).resolve(),(picture,dialogue,evidence,output))
    if not evidence.is_file():raise ValueError('Shared source-clock evidence required')
    pp=probe(picture,'ffprobe');ap=probe(dialogue,'ffprobe')
    vv=[s for s in pp['streams'] if s['codec_type']=='video'];aa=[s for s in ap['streams'] if s['codec_type']=='audio']
    if len(vv)!=1 or len(aa)!=1:raise ValueError('Exactly one picture and one explicit dialogue stream required')
    v,a=vv[0],aa[0]
    if a['codec_name']!='pcm_s24le' or a['sample_rate']!='48000' or a['channels']!=1:raise ValueError('Verified mono 48k PCM24 dialogue required')
    if any(abs(float(s.get('start_time',0)))>1e-6 for s in (v,a)):raise ValueError('Nonzero input origin requires separate mapping')
    if abs(float(v['duration'])-float(a['duration']))>1:raise ValueError('Source durations differ; reconcile clocks')
    output.mkdir(parents=True,exist_ok=False);media=output/'picture-dialogue.mov';receipt=output/'receipt.json'
    data={'schema':'acq-edit/picture-dialogue-source-v1','status':'preparing','picture':str(picture),'dialogue':str(dialogue),'clockEvidence':str(evidence),'clockEvidenceSha256':digest(evidence),'pictureSha256':digest(picture),'dialogueSha256':digest(dialogue),'listening':'not-performed'}
    receipt.write_text(json.dumps(data,indent=2))
    try:
        subprocess.run(['ffmpeg','-nostdin','-v','error','-i',str(picture),'-i',str(dialogue),'-map','0:v:0','-map','1:a:0','-c','copy','-n',str(media)],check=True)
        out=probe(media,'ffprobe');ov=next(s for s in out['streams'] if s['codec_type']=='video');oa=next(s for s in out['streams'] if s['codec_type']=='audio')
        if any(ov[k]!=v[k] for k in ('width','height','r_frame_rate','codec_name')):raise ValueError('Picture format changed')
        if any(oa[k]!=a[k] for k in ('codec_name','sample_rate','channels')):raise ValueError('Dialogue format changed')
        if any(abs(float(s.get('start_time',0)))>1e-6 for s in (ov,oa)):raise ValueError('Output origin changed')
        before=packet_identity(picture,'ffprobe');after=packet_identity(media,'ffprobe')
        if before!=after:raise ValueError('Compressed picture packets or clocks changed')
        h=audio_hash(dialogue)
        if audio_hash(media)!=h:raise ValueError('Decoded dialogue changed')
        data.update(status='verified',mediaPath=str(media),mediaSha256=digest(media),videoPackets=len(before),picturePacketsAndClocksIdentical=True,decodedDialogueHash=h)
    except Exception as exc:
        data.update(status='failed-preserve-evidence',error=str(exc));raise
    finally:receipt.write_text(json.dumps(data,indent=2))
    return data

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('picture','dialogue','evidence','output'):p.add_argument('--'+n,required=True)
    a=p.parse_args();print(json.dumps(prepare(a.picture,a.dialogue,a.evidence,a.output),indent=2))
