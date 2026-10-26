"""Add a linked native seam shadow to explicitly selected two-panel layouts.

Original camera nests, cuts, captions and audio are immutable. Uses only the
repository FilmCraft transport. Profiles are supplied separately from procedure.
"""
import argparse, copy, fcntl, hashlib, json, sys, time, math
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'edit/scripts'))
from filmcraft_client import Filmcraft

def require(value, message):
    if not value: raise RuntimeError(message)
def read(path): return json.loads(Path(path).read_text())
def work_root(path):
    root=next((p for p in Path(path).resolve().parents if p.name=='10_WORK'),None)
    require(root is not None,'Native revision must live under project 10_WORK')
    return root
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save(path,value): Path(path).write_text(json.dumps(value,indent=2)+'\n')
def sequence(data,key): return data['project']['items'][str(key)]['kind']['Sequence']
def motion(item): return next(e['params'] for e in item['effects'] if e['effect']=='motion')

def targets(data,ids):
    master=sequence(data,data['view']['active_sequence'])
    linked={i['item'] for t in master['video_tracks'] for i in t['items']}
    require(ids and len(ids)==len(set(ids)), 'Select unique layout IDs')
    out=[]
    for key in ids:
        require(key in linked,'Layout is not directly used by current master')
        seq=sequence(data,key);w,h=seq['settings']['width'],seq['settings']['height']
        require(h%2==0 and len(seq['video_tracks'])==2 and not seq['audio_tracks'], 'Expected untouched two-panel video-only layout')
        upper=[]
        for t in seq['video_tracks']:
            require(t['enabled'] and not t['locked'] and not t['muted'] and not t['solo'] and not t['effects'] and not t['transitions'] and len(t['items'])==1,'Unexpected panel track state')
            item=t['items'][0];child=sequence(data,item['item']);m=motion(item)
            require(item['enabled'] and item['start']==item['source_in']==0 and item['speed']==1 and not item['reverse'],'Unexpected panel timing')
            require((child['settings']['width'],child['settings']['height'])==(w,h//2) and not child['audio_tracks'],'Expected two equal horizontal panels without audio')
            require([e['effect'] for e in item['effects']]==['motion','opacity','time_remap'],'Custom panel effects require reconciliation')
            require(m['scale']['value']=={'Float':100.0} and not any(x.get('keyframes') for x in m.values()),'Unexpected panel transform')
            if m['position']['value']=={'Vec2':{'x':w/2,'y':h/4}}:upper.append(item)
            else:require(m['position']['value']=={'Vec2':{'x':w/2,'y':h*3/4}},'Unexpected lower panel position')
        require(len(upper)==1,'Expected one upper panel')
        out.append((key,seq,upper[0]))
    return out

def protected(before,after,ids):
    """Strip only append-only owned additions; compare every existing project field."""
    p=copy.deepcopy(after['project']);old=before['project']
    new=set(p['items'])-set(old['items'])
    require(len(new)==len(ids),'Exactly one shadow canvas per selected layout required')
    require(p['root']['children'][:len(old['root']['children'])]==old['root']['children'],'Original root changed')
    require({str(x.get('Item')) for x in p['root']['children'][len(old['root']['children']):]}==new,'Unexpected root additions')
    p['root']['children']=old['root']['children']
    for key in new:del p['items'][key]
    for key in ids:
        tracks=p['items'][str(key)]['kind']['Sequence']['video_tracks']
        require(len(tracks)==4,'Exactly shadow and clean overlay tracks required')
        del tracks[2:]
    for key in ['name','next_id']:p[key]=old[key]
    p['root']['name']=old['root']['name']
    require(p==old,'Protected native project state changed')
    require(after['view']['active_sequence']==before['view']['active_sequence'],'Master sequence changed')

def verify_owned(before,after,ids,profile):
    protected(before,after,ids)
    def values(item,effect):
        effect=next(e for e in item['effects'] if e['effect']==effect)
        require(effect['enabled'] and not effect.get('masks'), 'Owned effect disabled or masked')
        require(not any(v.get('keyframes') for v in effect['params'].values()),'Owned effect unexpectedly animated')
        return {k:next(iter(v['value'].values())) for k,v in effect['params'].items()}
    for key,seq,top in targets(before,ids):
        s=seq['settings'];w,h=s['width'],s['height'];tracks=sequence(after,key)['video_tracks'][2:]
        for t in tracks:
            require(t['enabled'] and not t['muted'] and not t['solo'] and not t['effects'] and not t['transitions'] and len(t['items'])==1,'Shadow overlay track changed')
        shadow,clean=[t['items'][0] for t in tracks]
        for item in [shadow,clean]:
            require(item['start']==item['source_in']==0 and item['duration']==top['duration'] and item['speed']==1 and not item['reverse'] and item['enabled'],'Overlay source clock changed')
        require(clean['item']==top['item'] and clean['effects']==top['effects'],'Clean upper panel no longer follows original camera')
        canvas=sequence(after,shadow['item'])
        require(canvas['settings']['width']==w and canvas['settings']['height']==h and len(canvas['video_tracks'])==1 and not canvas['audio_tracks'],'Shadow canvas changed')
        track=canvas['video_tracks'][0]
        require(len(track['items'])==1 and track['enabled'] and not track['muted'] and not track['solo'] and not track['effects'] and not track['transitions'],'Shadow canvas track changed')
        source=track['items'][0]
        require(source['item']==top['item'] and source['duration']==top['duration'] and source['start']==source['source_in']==0,'Shadow no longer follows original upper panel')
        m=values(source,'motion');require(m['scale']==profile['scale'] and m['position']=={'x':w/2,'y':h/4} and m['anchor']=={'x':w/2,'y':h/4},'Shadow geometry changed')
        expected_source=copy.deepcopy(top['effects'])
        next(e for e in expected_source if e['effect']=='motion')['params']['scale']['value']={'Float':profile['scale']}
        require(source['effects']==expected_source and source['enabled'] and source['speed']==1 and not source['reverse'],'Shadow source effect or playback changed')
        expected_shadow=copy.deepcopy(top['effects']);m=next(e for e in expected_shadow if e['effect']=='motion')['params']
        m['anchor']['value']=m['position']['value']={'Vec2':{'x':w/2,'y':h/2}}
        require([e['effect'] for e in shadow['effects']]==['drop_shadow','motion','opacity','time_remap'] and shadow['effects'][1:]==expected_shadow,'Shadow transform or composition changed')
        v=values(shadow,'drop_shadow')
        expected={'only':True,'opacity':profile['opacity'],'direction':profile['direction'],'distance':profile['distance']*w/profile['referenceWidth'],'softness':profile['softness']*w/profile['referenceWidth']}
        for k,value in expected.items():require(abs(v[k]-value)<.0001,'Shadow parameter changed: '+k)
        require(v['color']==[0.,0.,0.,1.],'Shadow color changed')

def export_revision(binary,receipt_path,media,session):
    work=work_root(read(receipt_path)['nativeProject'])
    with (work/'native.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        return _export_revision(binary,receipt_path,media,session)

def _export_revision(binary,receipt_path,media,session):
    receipt=read(receipt_path);native=Path(receipt['nativeProject']);parent=Path(receipt['parent'])
    require(sha(native)==receipt['nativeSha256'] and sha(parent)==receipt['parentSha256'],'Revision input changed')
    require(not Path(media).exists() and not Path(session).exists(),'Export output/session exists; reconcile original job')
    work=work_root(native)
    require(Path(media).resolve().is_relative_to(work) and Path(session).resolve().is_relative_to(work),'Export work must stay inside this project')
    before,after=read(parent),read(native)
    verify_owned(before,after,receipt['layoutIds'],receipt['profile'])
    # This append-only native revision preserves every original media reference,
    # camera, audio sample range and finishing layer. No recut or reassembly.
    Path(media).parent.mkdir(parents=True,exist_ok=True)
    save(Path(receipt_path).parent/'pre-export-shadow-check.json',{'status':'CONSTRUCTION_VALID','nativeSha256':sha(native),'parentSha256':sha(parent),'protectedStateVerified':True,'ownedShadowVerified':True,'helperSha256':sha(__file__)})
    c=Filmcraft(binary,session,native)
    try:
        baseline=c.tool('sequence_inspect')
        result=c.run('file.exportMedia',{'path':str(Path(media).resolve()),'format':'h264','range':'entire','audio':True,'hardwareEncoding':'off','bitrateMode':'crf','crf':18})
        save(Path(session)/'export-job.json',result)
        deadline=time.monotonic()+3600
        while True:
            jobs=c.run('jobs.list');save(Path(session)/'jobs.json',jobs)
            if all(j.get('finished') for j in jobs):
                require(jobs and not any(j.get('error') or j.get('cancelled') for j in jobs),'Native export failed');break
            require(time.monotonic()<deadline,'Export timeout; reconcile original job before retrying')
            time.sleep(2)
        require(c.tool('sequence_inspect')==baseline and sha(native)==receipt['nativeSha256'],'Native state changed during export')
    finally:c.close()
    save(Path(session)/'receipt.json',{'nativeSha256':sha(native),'media':str(media),'mediaSha256':sha(media),'elapsedSeconds':3600-(deadline-time.monotonic()),'humanApproved':False})

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for arg in ['project','binary','out','profile','targets','export-receipt','media','session']:ap.add_argument('--'+arg,type=Path)
    a=ap.parse_args()
    if a.export_receipt:
        require(a.binary and a.media and a.session,'Export requires binary, media and session')
        return export_revision(a.binary,a.export_receipt,a.media,a.session)
    require(all([a.project,a.binary,a.out,a.profile,a.targets]),'Construction requires project, binary, out, profile and targets')
    src=a.project.resolve();out=a.out.resolve()
    require(not out.exists(),'Output exists; inspect before retrying')
    work=work_root(src);require(out.is_relative_to(work),'Revision output must stay inside project 10_WORK')
    ids=read(a.targets);profile=read(a.profile)
    require(profile['schema']=='acq-edit/native-split-shadow-v1','Unknown shadow profile')
    for key,lo,hi in [('referenceWidth',1,16384),('scale',100,200),('opacity',0,100),('direction',0,360),('distance',0,4000),('softness',0,1000)]:
        value=profile.get(key);require(type(value) in (int,float) and math.isfinite(value) and lo<=value<=hi,'Invalid profile field: '+key)
    before=read(src);selected=targets(before,ids);parent_hash=sha(src)
    out.mkdir(parents=True);native=out/'edit.fcproj';save(native,before)
    with (work/'native.lock').open('a') as lock:
      fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
      require(sha(src)==parent_hash,'Parent changed before native lock')
      c=Filmcraft(a.binary,out/'session',native)
      try:
        baseline=c.tool('sequence_inspect');save(out/'before-inspection.json',baseline)
        for key,seq,top in selected:
          s=seq['settings'];w,h=s['width'],s['height'];scale=w/profile['referenceWidth']
          canvas=c.run('file.newSequence',{'name':'ACQ_SeamShadow_'+str(key),'width':w,'height':h,'fps':s['frame_rate']['num']/s['frame_rate']['den'],'sampleRate':s['sample_rate'],'video':1,'audio':0})['sequence']
          c.run('sequence.nestSequences',{'on':True})
          def place(item,track):
            c.run('timeline.place',{'item':item,'track':track,'time':0,'sourceIn':0,'duration':top['duration'],'video':True,'audio':False,'insert':False})
            return c.tool('sequence_inspect')['video'][int(track[1:])-1]['items'][0]['clip']
          def params(clip,effect,values):
            for name,value in values.items():c.run('effects.setParam',{'clip':clip,'effect':effect,'param':name,'value':value})
          clip=place(top['item'],'V1')
          params(clip,'motion',{'anchor':[w/2,h/4],'position':[w/2,h/4],'scale':profile['scale']})
          c.run('sequence.open',{'item':key});c.run('sequence.addTracks',{'video':2,'audio':0})
          shadow=place(canvas,'V3');params(shadow,'motion',{'anchor':[w/2,h/2],'position':[w/2,h/2],'scale':100})
          c.run('effects.apply',{'clips':[shadow],'effect':'drop_shadow'})
          params(shadow,'drop_shadow',{'color':'#000000','opacity':profile['opacity'],'direction':profile['direction'],'distance':profile['distance']*scale,'softness':profile['softness']*scale,'only':True})
          c.run('timeline.setTrack',{'track':'V3','name':'ACQ seam shadow'})
          clean=place(top['item'],'V4');params(clean,'motion',{'anchor':[w/2,h/4],'position':[w/2,h/4],'scale':100})
          c.run('timeline.setTrack',{'track':'V4','name':'ACQ clean upper panel'})
        c.run('sequence.open',{'item':before['view']['active_sequence']});c.run('file.save')
      finally:c.close()
      after=read(native);verify_owned(before,after,ids,profile);require(sha(src)==parent_hash,'Parent changed during revision')
      c=Filmcraft(a.binary,out/'reopen',native)
      try:save(out/'after-inspection.json',c.tool('sequence_inspect'))
      finally:c.close()
      verify_owned(before,read(native),ids,profile)
      save(out/'receipt.json',{'schema':'acq-edit/native-split-shadow-revision-v1','parent':str(src),'parentSha256':parent_hash,'nativeProject':str(native),'nativeSha256':sha(native),'profile':profile,'profileSha256':sha(a.profile),'helperSha256':sha(__file__),'layoutIds':ids,'protectedStateVerified':True,'renderedMatchApproved':False})
      print(native)
if __name__=='__main__':main()
