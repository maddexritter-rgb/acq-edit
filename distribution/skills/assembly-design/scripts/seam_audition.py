#!/usr/bin/env python3
"""Build complete source/played seam evidence and validate revision-bound reviews.

The checker validates evidence coverage, not perception or human acceptance.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import wave

CHECKS = ('retained_speech', 'excluded_speech', 'cadence', 'clicks')


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def pin(path):
    p = Path(path).resolve()
    return {'path': str(p), 'sha256': digest(p)}


def verify_pin(value):
    if digest(value['path']) != value['sha256']:
        raise ValueError('Stale evidence: ' + value['path'])


def save(path, value):
    with Path(path).open('x') as f:
        json.dump(value, f, indent=2, allow_nan=False)
        f.write('\n')


def pcm_context(segment, edge, out, before, after, rate):
    # Explicit played channel, never an implicit stereo downmix.
    if type(segment['channel']) is not int or segment['channel'] < 0:
        raise ValueError('Explicit zero-based played channel required')
    a = max(0, edge - before); b = edge + after
    seek = max(0, a // rate - 1)
    offset = a - seek * rate
    subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-ss', str(seek),
        '-i', segment['media'], '-map', f"0:a:{segment['stream']}", '-vn',
        '-af', f"atrim=start_sample={offset}:end_sample={offset+b-a},asetpts=PTS-STARTPTS,pan=mono|c0=c{segment['channel']}",
        '-c:a', 'pcm_s16le', str(out)], check=True, capture_output=True)
    with wave.open(str(out)) as w:
        if w.getframerate() != rate:
            raise ValueError('Source sample rate differs from declared played clock')
        b = a + w.getnframes()
        if edge > b:
            raise ValueError('Source edge outside decoded media')
    return {**pin(out), 'source_samples': [a, b], 'edge_at_sample': edge-a,
            'media': segment['media'], 'stream': segment['stream'], 'channel': segment['channel']}


def prepare(manifest_path, out):
    data = json.loads(Path(manifest_path).read_text())
    if data['schema'] != 'edit.seam-audition-input/v1' or not data['clips']:
        raise ValueError('Nonempty audition manifest required')
    out = Path(out).resolve(); out.mkdir(parents=True, exist_ok=False)
    packet = {'schema': 'edit.seam-audition-packet/v1', 'manifest': pin(manifest_path),
              'clips': [], 'scope': 'Source and actual played evidence; no auditory verdict.'}
    seen = set()
    for ci, clip in enumerate(data['clips']):
        if clip['id'] in seen:
            raise ValueError('Duplicate clip identity')
        seen.add(clip['id'])
        verify_pin(clip['audio']); verify_pin(clip['geometry']); verify_pin(clip['routing'])
        folder = out / f'clip-{ci+1:03d}'; folder.mkdir()
        with wave.open(clip['audio']['path']) as w:
            params = w.getparams(); rate = w.getframerate(); raw = w.readframes(w.getnframes())
        if params.comptype != 'NONE': raise ValueError('PCM audition required')
        width = params.nchannels * params.sampwidth; length = len(raw)//width
        segs = clip['segments']
        if not segs: raise ValueError('No source segments')
        last = 0
        for s in segs:
            values = [s[k] for k in ('timeline_in','timeline_out','source_in','source_out','stream')]
            if any(type(x) is not int or x < 0 for x in values):
                raise ValueError('Nonnegative integer sample positions required')
            if s['timeline_out']-s['timeline_in'] != s['source_out']-s['source_in'] or s['source_out']<=s['source_in']:
                raise ValueError('Retiming requires an explicit mapped-audio adapter')
            if s['timeline_in'] < last or s['timeline_out'] > length:
                raise ValueError('Overlapping/out-of-range played segments')
            if last and s['timeline_in'] != last:
                raise ValueError('Internal audio hole: repair or explicitly model the intended transition')
            last = s['timeline_out']
        regions = []
        boundaries = [('head', segs[0]['timeline_in'], None, segs[0])]
        boundaries += [(f'join-{i:03d}', left['timeline_out'], left, right)
                       for i,(left,right) in enumerate(zip(segs,segs[1:]),1)]
        boundaries += [('tail', segs[-1]['timeline_out'], segs[-1], None)]
        for rid, t, left, right in boundaries:
            a=max(0,t-2*rate); b=min(length,t+2*rate)
            target=folder/(rid+'-played.wav')
            with wave.open(str(target),'wb') as w:
                w.setparams(params); w.writeframes(raw[a*width:b*width])
            region={'id':rid,'timeline_sample':t,'played':{**pin(target),'clip_samples':[a,b],'edge_at_sample':t-a},'sources':[]}
            for side,s in [('outgoing',left),('incoming',right)]:
                if s is None: continue
                edge=s['source_out' if side=='outgoing' else 'source_in']
                context=pcm_context(s,edge,folder/(rid+'-'+side+'.wav'),2*rate,2*rate,rate)
                region['sources'].append({'side':side,**context})
            regions.append(region)
        regions.append({'id':'full','played':clip['audio'],'sources':[]})
        packet['clips'].append({'id':clip['id'],'audio':clip['audio'],'geometry':clip['geometry'],
                               'routing':clip['routing'],'sample_rate':rate,'regions':regions})
    save(out/'packet.json',packet)
    return out/'packet.json'


def check(packet_path, reviews_path):
    packet=json.loads(Path(packet_path).read_text()); reviews=json.loads(Path(reviews_path).read_text())
    errors=[]; findings=[]
    if packet.get('schema')!='edit.seam-audition-packet/v1' or reviews.get('schema')!='edit.seam-audition-reviews/v1':
        raise ValueError('Unknown schema')
    if reviews.get('packet_sha256')!=digest(packet_path): errors.append('Review belongs to a different packet')
    verify_pin(packet['manifest'])
    manifest=json.loads(Path(packet['manifest']['path']).read_text())
    inputs={c['id']:c for c in manifest['clips']}
    if len(inputs)!=len(manifest['clips']) or [c['id'] for c in packet['clips']]!=[c['id'] for c in manifest['clips']]:
        raise ValueError('Packet clip coverage differs from input manifest')
    for c in packet['clips']:
        source=inputs[c['id']]
        required=['head']+[f'join-{i:03d}' for i in range(1,len(source['segments']))]+['tail','full']
        if [r['id'] for r in c['regions']]!=required:
            raise ValueError('Packet does not cover every source segment boundary')
        for name in ('audio','geometry','routing'):
            if c[name]!=source[name]: raise ValueError('Packet identity differs from manifest')
    known={(c['id'],r['id']) for c in packet['clips'] for r in c['regions']}
    seen={}
    for r in reviews.get('regions',[]):
        k=(r['clip_id'],r['region_id'])
        if k in seen: errors.append('Duplicate review '+str(k))
        seen[k]=r
        if k not in known: errors.append('Unknown region '+str(k))
    for c in packet['clips']:
        for name in ('audio','geometry','routing'): verify_pin(c[name])
        for region in c['regions']:
            k=(c['id'],region['id']); verify_pin(region['played'])
            for source in region['sources']: verify_pin(source)
            r=seen.get(k)
            if not r:
                errors.append('Missing listening '+str(k)); continue
            if r.get('status')!='LISTENED' or not r.get('reviewer') or r.get('method') not in ('human_listening','audio_model'):
                errors.append('No completed listening '+str(k))
            if r.get('method')=='audio_model':
                qualification=r.get('qualification')
                if not qualification:
                    errors.append('No listener qualification '+str(k))
                else:
                    verify_pin(qualification)
                    q=json.loads(Path(qualification['path']).read_text())
                    if (q.get('status')!='QUALIFIED_ON_RECORDED_CONTROLS'
                        or q.get('reviewer')!=r.get('reviewer')
                        or not q.get('controls') or not q.get('response')
                        or any(q.get(n)!=0 for n in ('missed_defects','false_alarms','localization_errors'))):
                        errors.append('Listener not qualified '+str(k))
                    else:
                        verify_pin(q['controls']); verify_pin(q['response'])
            if r.get('played_sha256')!=region['played']['sha256']:
                errors.append('Stale played audio '+str(k))
            if sorted(r.get('source_sha256s',[]))!=sorted(s['sha256'] for s in region['sources']):
                errors.append('Missing source comparison '+str(k))
            if not r.get('observation') or not r.get('response'):
                errors.append('Missing review evidence '+str(k))
            else: verify_pin(r['response'])
            checks=r.get('checks',{})
            for name in CHECKS:
                if checks.get(name)!='pass': findings.append({'clip':c['id'],'region':region['id'],'check':name,'value':checks.get(name,'missing')})
            # A model's blanket PASS never overrides its own defect report.
            if r.get('issues'): findings.append({'clip':c['id'],'region':region['id'],'issues':r['issues']})
    return {'schema':'edit.seam-audition-gate/v1','status':'INCOMPLETE' if errors else 'REPAIR_REQUIRED' if findings else 'REVIEW_EVIDENCE_COMPLETE',
            'errors':errors,'findings':findings,'regions_expected':len(known),'regions_recorded':len(seen),
            'scope':'Coverage and artifact identity only. Does not certify perception, reviewer calibration, or human acceptance.'}


def main():
    ap=argparse.ArgumentParser(description=__doc__);sub=ap.add_subparsers(dest='command',required=True)
    p=sub.add_parser('prepare');p.add_argument('--manifest',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p=sub.add_parser('check');p.add_argument('--packet',type=Path,required=True);p.add_argument('--reviews',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=ap.parse_args()
    try:
        if a.command=='prepare': print(prepare(a.manifest,a.out));return 0
        result=check(a.packet,a.reviews);save(a.out,result);print(json.dumps(result));return 0 if result['status']=='REVIEW_EVIDENCE_COMPLETE' else 2
    except (OSError,ValueError,KeyError,TypeError,subprocess.CalledProcessError) as e:
        print(json.dumps({'status':'ERROR','error':str(e)}));return 2

if __name__=='__main__':raise SystemExit(main())
