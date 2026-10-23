#!/usr/bin/env python3
"""Remove descriptive delivery metadata on a new copy; preserve decoded AV/signalling."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def probe(path):
    return json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(path)]))


def media_signature(data):
    keys=('codec_type','codec_name','profile','width','height','pix_fmt','sample_rate','channels',
          'channel_layout','avg_frame_rate','color_range','color_space','color_transfer','color_primaries',
          'field_order','sample_aspect_ratio')
    result=[]
    for stream in data['streams']:
        if stream['codec_type'] not in ('video','audio'):continue
        row={k:stream.get(k) for k in keys}
        row['side_data_list']=stream.get('side_data_list',[])
        row['rotation_tag']=stream.get('tags',{}).get('rotate')
        result.append(row)
    return result


def decoded_identity(path):
    # No shell; decode once per file and retain bounded stream hashes/counts/clocks.
    args=['ffmpeg','-v','error','-i',str(path),'-map','0:v','-map','0:a?',
          '-fps_mode','passthrough','-f','framemd5','-']
    proc=subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    streams={}
    for line in proc.stdout:
        if line.startswith('#') or not line.strip():continue
        stream,dts,pts,duration,size,digest=[x.strip() for x in line.split(',')]
        row=streams.setdefault(stream,{'count':0,'sha':hashlib.sha256(),'first_pts':pts,'last_pts':pts})
        row['count']+=1;row['last_pts']=pts;row['sha'].update((duration+','+size+','+digest+'\n').encode())
    err=proc.stderr.read()
    if proc.wait():raise RuntimeError('Decode verification failed: '+err[-1000:])
    return {k:{**{x:v for x,v in r.items() if x!='sha'},'sha256':r['sha'].hexdigest()} for k,r in streams.items()}


def sanitize(source, output, receipt):
    source,output,receipt=map(Path,(source,output,receipt))
    if source.resolve()==output.resolve() or output.exists() or receipt.exists():
        raise ValueError('Use new output and receipt paths; originals are preserved')
    before=probe(source)
    output.parent.mkdir(parents=True,exist_ok=True)
    command=['ffmpeg','-v','error','-n','-i',str(source),'-map','0:v','-map','0:a?',
             '-c','copy','-map_metadata','-1','-map_metadata:s','-1','-map_chapters','-1',
             '-fflags','+bitexact','-metadata','encoder=','-movflags','+faststart',str(output)]
    subprocess.run(command,check=True)
    after=probe(output)
    original_decoded=decoded_identity(source);copy_decoded=decoded_identity(output)
    same=media_signature(before)==media_signature(after) and original_decoded==copy_decoded
    report={'schema':'edit.delivery-metadata/v1','source':str(source.resolve()),'output':str(output.resolve()),
            'status':'VERIFIED' if same else 'PLAYBACK_DIFFERENCE','command':command,
            'before':before,'after':after,'decoded_source':original_decoded,'decoded_output':copy_decoded,
            'claim':'Container housekeeping; no claim about platform labels or performance'}
    receipt.parent.mkdir(parents=True,exist_ok=True)
    with receipt.open('x') as f:json.dump(report,f,indent=2)
    if not same:raise ValueError('Sanitation changed decoded media or required signalling; keep original and inspect receipt')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source');p.add_argument('--out',required=True);p.add_argument('--receipt',required=True)
    a=p.parse_args();r=sanitize(a.source,a.out,a.receipt);print(json.dumps({'status':r['status'],'output':r['output']}))
