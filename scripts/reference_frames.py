#!/usr/bin/env python3
"""Prepare dense, timestamped reference evidence. Extraction is not viewing/listening."""
import argparse,json,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('out',type=Path);p.add_argument('--start',type=float,default=0);p.add_argument('--end',type=float,required=True);p.add_argument('--fps',type=int,default=12);a=p.parse_args()
if a.start<0 or a.end<=a.start or a.fps<1 or a.fps>60:raise SystemExit('Invalid bounded inspection interval')
a.out.mkdir(parents=True,exist_ok=False)
subprocess.run(['ffmpeg','-v','error','-ss',str(a.start),'-i',str(a.source),'-t',str(a.end-a.start),'-vf',f'fps={a.fps},scale=960:-2',str(a.out/'frame-%06d.jpg')],check=True)
subprocess.run(['ffmpeg','-v','error','-ss',str(a.start),'-i',str(a.source),'-t',str(a.end-a.start),'-vn','-c:a','pcm_s16le',str(a.out/'audio.wav')],check=True)
(a.out/'index.json').write_text(json.dumps({'source':str(a.source.resolve()),'start':a.start,'end':a.end,'fps':a.fps,'frames':[{'file':f.name,'seconds':a.start+i/a.fps} for i,f in enumerate(sorted(a.out.glob('frame-*.jpg')))],'evidence':'extracted-not-yet-viewed-or-listened'},indent=2))
