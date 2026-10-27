#!/usr/bin/env python3
"""Timestamped source contact sheet without optional FFmpeg drawtext. Not listening evidence."""
import argparse,json,math,subprocess
from pathlib import Path
from PIL import Image,ImageDraw

def collect(media,output,start,end,step):
    if not all(math.isfinite(x) for x in (start,end,step)) or not 0 <= start < end or step <= 0:
        raise ValueError('Finite ordered bounds and positive step required')
    count=math.ceil((end-start)/step)
    if count>120:raise ValueError('At most 120 samples per sheet request')
    output.mkdir(parents=True,exist_ok=False)
    sheet=Image.new('RGB',(960,math.ceil(count/4)*165),'#171717');draw=ImageDraw.Draw(sheet);rows=[]
    for i in range(count):
        timestamp=start+i*step;target=output/f'frame-{i:04d}.jpg'
        subprocess.run(['ffmpeg','-nostdin','-n','-v','error','-ss',str(timestamp),'-i',str(media),'-frames:v','1','-vf','scale=240:135:force_original_aspect_ratio=decrease',str(target)],check=True,timeout=60)
        x=(i%4)*240;y=(i//4)*165
        with Image.open(target) as frame:sheet.paste(frame,(x,y+25))
        draw.text((x+4,y+4),f'{timestamp:.3f}s',fill='white');rows.append({'seconds':timestamp,'image':target.name})
    sheet.save(output/'sheet.jpg')
    (output/'index.json').write_text(json.dumps({'source':str(media.resolve()),'status':'extracted-not-reviewed','frames':rows},indent=2)+'\n')
    return {'samples':len(rows),'sheet':str(output/'sheet.jpg')}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--media',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--start',type=float,required=True);p.add_argument('--end',type=float,required=True);p.add_argument('--step',type=float,default=1)
    a=p.parse_args();print(json.dumps(collect(a.media,a.output,a.start,a.end,a.step)))
