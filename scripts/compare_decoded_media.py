#!/usr/bin/env python3
"""Compare every decoded picture frame and audio sample of an unchanged rebuild."""
import argparse, concurrent.futures, hashlib, json, subprocess, time
from pathlib import Path

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--reference',type=Path,required=True)
    ap.add_argument('--candidate',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    a=ap.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    def decode(label,media):
        start=time.monotonic()
        paths=[a.output/(label+'-'+kind+'.framemd5') for kind in ['video','audio']]
        subprocess.run(['ffmpeg','-nostdin','-n','-v','error','-xerror','-i',str(media),
            '-map','0:v:0','-fps_mode','passthrough','-f','framemd5',str(paths[0]),
            '-map','0:a:0','-c:a','pcm_f32le','-f','framemd5',str(paths[1])],check=True)
        rows=[[line for line in p.read_text().splitlines() if line and not line.startswith('#')] for p in paths]
        return {'seconds':time.monotonic()-start,'rows':rows,'mediaSha256':hashlib.file_digest(media.open('rb'),'sha256').hexdigest()}
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        old=pool.submit(decode,'reference',a.reference);new=pool.submit(decode,'candidate',a.candidate)
        old,new=old.result(),new.result()
    result={'schema':'acq-edit/decoded-comparison-v1','reference':str(a.reference),'candidate':str(a.candidate),
        'videoIdentical':bool(old['rows'][0]) and old['rows'][0]==new['rows'][0],
        'audioIdentical':bool(old['rows'][1]) and old['rows'][1]==new['rows'][1],
        'referenceVideoFrames':len(old['rows'][0]),'candidateVideoFrames':len(new['rows'][0]),
        'referenceAudioBlocks':len(old['rows'][1]),'candidateAudioBlocks':len(new['rows'][1]),
        'referenceSha256':old['mediaSha256'],'candidateSha256':new['mediaSha256'],
        'referenceDecodeSeconds':old['seconds'],'candidateDecodeSeconds':new['seconds'],
        'qualification':'Exact decoded data and timestamps; not independent listening or editorial approval'}
    (a.output/'comparison.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
    if not (result['videoIdentical'] and result['audioIdentical']):raise SystemExit(1)

if __name__=='__main__':main()
