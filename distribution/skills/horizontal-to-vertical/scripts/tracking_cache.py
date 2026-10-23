"""Source-range tracking cache. Geometry changes miss; interrupted writes never hit."""
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile

_IDENTITIES = {}
def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)

def fingerprint(path):
    path = Path(path).resolve()
    def stat_key():
        s=path.stat(); return (str(path),s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
    before=stat_key()
    if before not in _IDENTITIES:
        h=hashlib.sha256()
        with path.open('rb') as f:
            for b in iter(lambda:f.read(8*1024*1024),b''): h.update(b)
        if stat_key()!=before: raise ValueError('Input changed while hashing')
        _IDENTITIES[before]=h.hexdigest()
    return {'path':str(path),'sha256':_IDENTITIES[before]}

def binding(item,preset,sample_seconds,dependencies):
    a,b=float(item['source_in']),float(item['source_out'])
    if not all(math.isfinite(x) for x in (a,b,sample_seconds)) or not 0<=a<b or sample_seconds<=0:
        raise ValueError('Invalid source range/sample interval')
    return json.loads(canonical({'schema':'edit.tracking-cache/v1','source':fingerprint(item['media_path']),
        'source_in':a,'source_out':b,'preset':preset,'sample_seconds':sample_seconds,
        'dependencies':[fingerprint(p) for p in dependencies]}))

def validate_result(data, duration):
    times=data['relative_times']; xs=data['face_x']; ys=data['face_y']
    if not times or len(times)!=len(xs) or len(xs)!=len(ys): raise ValueError('Incomplete tracking arrays')
    if any(not isinstance(x,(int,float)) or isinstance(x,bool) or not math.isfinite(x) for x in times+xs+ys):
        raise ValueError('Nonfinite tracking data')
    if any(not 0<=x<=1 for x in xs+ys): raise ValueError('Invalid normalized face position')
    if times[0]!=0 or any(a>=b for a,b in zip(times,times[1:])) or times[-1]>duration:
        raise ValueError('Tracking time geometry mismatch')
    if not isinstance(data.get('fps'),(int,float)) or not math.isfinite(data['fps']) or not data['fps']>0 or duration-times[-1]>2/data['fps']:
        raise ValueError('Tracking does not cover final source frame')

def get_or_compute(item,preset,sample_seconds,cache_dir,producer,dependencies):
    spec=binding(item,preset,sample_seconds,dependencies)
    key=hashlib.sha256(canonical(spec).encode()).hexdigest()
    root=Path(cache_dir);root.mkdir(parents=True,exist_ok=True);path=root/(key+'.json')
    with (root/(key+'.lock')).open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        if path.exists():
            try:
                record=json.loads(path.read_text()); data=record['result']
                if record['binding']!=spec or record['result_sha256']!=hashlib.sha256(canonical(data).encode()).hexdigest():
                    raise ValueError('Cache receipt mismatch')
                validate_result(data,spec['source_out']-spec['source_in'])
                return data,{'hit':True,'key':key,'path':str(path),'binding':spec}
            except (ValueError,KeyError,TypeError):
                # Keep the old entry until a replacement successfully validates.
                pass
        data=producer(item,preset,sample_seconds)
        validate_result(data,spec['source_out']-spec['source_in'])
        if binding(item,preset,sample_seconds,dependencies)!=spec: raise ValueError('Inputs changed during tracking')
        record={'binding':spec,'result':data,'result_sha256':hashlib.sha256(canonical(data).encode()).hexdigest()}
        fd,temp=tempfile.mkstemp(prefix=key+'.',suffix='.pending',dir=root)
        try:
            with os.fdopen(fd,'w') as f: f.write(canonical(record));f.flush();os.fsync(f.fileno())
            os.replace(temp,path)
        finally:
            if os.path.exists(temp):os.unlink(temp)
        return data,{'hit':False,'key':key,'path':str(path),'binding':spec}
