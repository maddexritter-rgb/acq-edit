#!/usr/bin/env python3
"""Sample an actual render at caption centers and cut edges; evidence, not approval."""
import argparse, hashlib, json, subprocess
from pathlib import Path
from PIL import Image, ImageDraw


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--plan',required=True,type=Path);ap.add_argument('--media',required=True,type=Path);ap.add_argument('--output',required=True,type=Path);a=ap.parse_args()
    p=json.loads(a.plan.read_text());fps=p['fps']['numerator']/p['fps']['denominator'];total=max(c['recordFrame']+c['frames'] for c in p['cuts'])
    points={}
    def add(frame,label):
        if not 0<=frame<total:raise ValueError('Sample outside timeline')
        points.setdefault(frame,[]).append(label)
    for i,c in enumerate(p['captions']):add((c['startFrame']+c['endFrame']-1)//2,f'caption {i+1}: {c["text"]}')
    for c in p['cuts']:
        for f in sorted({c['recordFrame'],c['recordFrame']+c['frames']//2,c['recordFrame']+c['frames']-1}):add(f,c['id'])
    a.output.mkdir(parents=True,exist_ok=False);frames=sorted(points)
    terms=[f'eq(n,{f})' for f in frames]
    while len(terms)>1:
        terms=[f'({terms[i]}+{terms[i+1]})' if i+1<len(terms) else terms[i] for i in range(0,len(terms),2)]
    expr=terms[0]
    subprocess.run(['ffmpeg','-nostdin','-n','-v','error','-i',str(a.media),'-vf',f"select='{expr}',scale=540:960",'-fps_mode','vfr',str(a.output/'frame-%04d.jpg')],check=True)
    images=sorted(a.output.glob('frame-*.jpg'))
    if len(images)!=len(frames):raise RuntimeError('Decoded sample count differs')
    rows=[]
    for f,image in zip(frames,images):rows.append({'frame':f,'seconds':f/fps,'labels':points[f],'image':image.name})
    for page in range((len(rows)+23)//24):
        sheet=Image.new('RGB',(1080,1408),'#171717');draw=ImageDraw.Draw(sheet)
        for slot,row in enumerate(rows[page*24:(page+1)*24]):
            x=(slot%6)*180;y=(slot//6)*352
            with Image.open(a.output/row['image']) as im:sheet.paste(im.resize((180,320)),(x,y+32))
            draw.text((x+3,y+2),f'{row["seconds"]:.2f}s / f{row["frame"]}',fill='white')
            draw.text((x+3,y+15),row['labels'][0][:26],fill='white')
        sheet.save(a.output/f'review-{page+1}.jpg',quality=92)
    pin=lambda f:hashlib.file_digest(open(f,'rb'),'sha256').hexdigest()
    (a.output/'index.json').write_text(json.dumps({'schema':'acq-edit/render-samples-v1','status':'extracted-not-yet-reviewed','mediaSha256':pin(a.media),'planSha256':pin(a.plan),'frames':rows},indent=2))
    print(json.dumps({'samples':len(rows),'pages':(len(rows)+23)//24}))

if __name__=='__main__':main()
