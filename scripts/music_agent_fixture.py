"""Real-agent FilmCraft music replacement qualification using generated tones."""
import array,copy,json,math,os,sqlite3,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
from common import read,save,sha,require,plan as validate_plan,verify_native_render


def expected_revision(previous,current,replacement):
    expected=copy.deepcopy(previous);expected['sources'].append(replacement)
    before=previous['audio']['music'][0];after=current['audio']['music'][0]
    require(after['sourceId']==replacement['id'],'Wrong replacement source')
    require(after['receiptPath']!=before['receiptPath'] and after['receiptSha256']!=before['receiptSha256'],'Fresh music receipt required')
    expected['audio']['music'][0].update(sourceId=replacement['id'],receiptPath=after['receiptPath'],receiptSha256=after['receiptSha256'])
    require(current==expected,'Music revision changed unrequested plan fields')


def native_state(previous,current,old_plan,new_plan,new_name):
    """Independently compare saved native data, including every protected field."""
    require(previous['view']['active_sequence']==current['view']['active_sequence'],'Active native sequence changed')
    a=copy.deepcopy(previous['project']);b=copy.deepcopy(current['project']);sid=str(previous['view']['active_sequence'])
    for data,spec in [(a,old_plan),(b,new_plan)]:
        seq=data['items'][sid]['kind']['Sequence'];require(len(seq['audio_tracks'])==2,'Unexpected audio tracks')
        beds=seq['audio_tracks'][1]['items'];require(len(beds)==2,'Expected two native music placements')
        for clip,bed in zip(beds,spec['audio']['music']):
            source=next(s for s in spec['sources'] if s['id']==bed['sourceId'])
            require(Path(data['items'][str(clip['item'])]['kind']['Media']['media']['File']['path']).resolve()==Path(source['path']).resolve(),'Native bed source differs')
            require((clip['start'],clip['duration'],clip['source_in'])==(bed['startFrame']*254016000000//25,bed['samples']*254016000000//48000,bed['sourceInSample']*254016000000//48000),'Native music clocks differ')
    target=b['items'][sid]['kind']['Sequence']['audio_tracks'][1]['items'][0]['item'];key=str(target)
    require(set(b['items'])-set(a['items'])=={key} and set(a['items'])<=set(b['items']),'Unexpected imported native media')
    require(target==a['next_id'] and b['next_id']==a['next_id']+1,'Unexpected native ID allocation')
    a['items'][key]=b['items'][key];a['next_id']+=1;a['root']['children'].append({'Item':target})
    a['items'][sid]['kind']['Sequence']['audio_tracks'][1]['items'][0]['item']=target
    a['name']=a['root']['name']=new_name
    require(a==b,'Music revision changed protected native data')


def audio(file):
    values=array.array('f',subprocess.check_output(['ffmpeg','-v','error','-i',str(file),'-map','0:a:0','-ac','1','-ar','48000','-f','f32le','-']))
    if sys.byteorder!='little':values.byteswap()
    require(all(math.isfinite(x) for x in values),'Nonfinite audio')
    return values

def amplitude(values,start,end,hz):
    lo,hi=round(start*48000),round(end*48000);require(len(values)>=hi,'Audio window truncated')
    return 2*math.hypot(sum(values[i]*math.cos(2*math.pi*hz*i/48000) for i in range(lo,hi)),sum(values[i]*math.sin(2*math.pi*hz*i/48000) for i in range(lo,hi)))/(hi-lo)

def rendered(versions):
    pcm=[audio(v['media']) for v in versions];require(len(pcm[0])==len(pcm[1]),'Audio length changed');measurements={}
    for label,start,end in [('selected',.35,.65),('unselected',1.35,1.65)]:
        m={str(hz):{'before':amplitude(pcm[0],start,end,hz),'after':amplitude(pcm[1],start,end,hz)} for hz in [220,440,1320]};measurements[label]=m
        require(.345<m['220']['before']/max(m['440']['before'],1e-12)<.365,'Initial music/dialogue balance differs')
        require(m['440']['before']>.01 and abs(20*math.log10(m['440']['after']/m['440']['before']))<.01,'Dialogue level changed')
        if label=='selected':require(m['220']['before']>.01 and m['1320']['after']>.01 and m['220']['before']>100*max(m['220']['after'],1e-12) and m['1320']['after']>100*max(m['1320']['before'],1e-12),'Selected bed did not change to the expected tone')
        else:require(m['220']['before']>.01 and abs(20*math.log10(m['220']['after']/m['220']['before']))<.01,'Unselected bed changed')
    pictures=[subprocess.check_output(['ffmpeg','-v','error','-i',v['media'],'-map','0:v:0','-f','rawvideo','-pix_fmt','rgb24','-']) for v in versions]
    require(pictures[0]==pictures[1],'Music replacement changed decoded pictures')
    return {'picturesIdentical':True,'audioSampleFrames':len(pcm[0]),'toneMeasurements':measurements}


def check(file):
    os.environ['ACQ_EDIT_TEST_FIXTURE']='1';f=read(file);require(f['project']['backend']=='filmcraft','This independent music agent checker currently qualifies FilmCraft only')
    require(sha(f['planPath'])==f['initialPlanSha256'],'Frozen plan changed')
    db=sqlite3.connect('file:'+str(Path(f['home'])/'state.sqlite')+'?mode=ro',uri=True)
    def rows(query,*args):return [json.loads(r[0]) for r in db.execute(query,args)]
    try:
        jobs=rows('SELECT data FROM jobs WHERE project_id=? ORDER BY rowid',f['project']['id']);versions=rows('SELECT data FROM versions WHERE clip_id=? ORDER BY rowid',f['clip']['id'])
        require(len(jobs)==len(versions)==2 and all(j['state']=='ready' and j.get('agentSession') and not j.get('error') for j in jobs),'Expected two real ready jobs and immutable versions')
        require(not rows("SELECT data FROM native_operations WHERE project_id=? AND state NOT IN ('succeeded','reconciled')",f['project']['id']),'Unresolved native operation')
        old,new=versions;require(new['parentId']==old['id'],'Wrong parent');plans=[]
        for job,v in zip(jobs,versions):
            require(v['jobId']==job['id'],'Wrong job attribution')
            require(read(Path(f['project']['root'])/'10_WORK/jobs'/job['id']/'result.json')=={'jobId':job['id'],'versionIds':[v['id']]},'Wrong job result')
            for key,pin in [('media','sha256'),('nativeCheckpoint','nativeFingerprint'),('planPath','planSha256'),('receiptPath','receiptSha256'),('inspectionPath','inspectionSha256')]:require(sha(v[key])==v[pin],'Published artifact changed: '+key)
            spec=validate_plan(f['project'],{'plan':v['planPath']});plans.append(spec);verify_native_render(v['media'],spec)
            receipt=read(v['receiptPath']);require(receipt['nativeRendered'] is True and receipt['backend']=='filmcraft' and receipt['jobId']==job['id'],'Native receipt differs')
        replacement=read(Path(file).parent/'replacement-source.json');require(plans[0]==read(f['planPath']),'Initial build changed frozen plan');expected_revision(*plans,replacement)
        native_state(read(old['nativeCheckpoint']),read(new['nativeCheckpoint']),*plans,Path(new['nativeProject']).stem)
        require(sha(old['nativeProject'])==old['nativeFingerprint'],'Original working native project changed')
        for source in rows('SELECT data FROM sources WHERE project_id=?',f['project']['id']):require(sha(source['path'])==source['sha256'],'Project-owned source changed')
        request=read(Path(file).parent/'revision-request.json');submitted=jobs[1]['snapshot'][0]
        require(submitted['version']['id']==old['id'] and submitted['feedback']['notes']==request['notes'] and len(submitted['feedback']['comments'])==1 and submitted['feedback']['comments'][0]['text']==request['comment'],'Submitted request differs')
        require('music' in submitted['owners'],'Music owner missing');require(rows('SELECT data FROM feedback WHERE version_id=?',new['id'])[0]['decision'] is None,'Changed version is not freshly unreviewed')
        pending=rows('SELECT data FROM deferred_feedback WHERE clip_id=? AND consumed_by IS NULL',f['clip']['id']);require(len(pending)==1,'Late feedback missing or duplicated')
        require(pending[0]['sourceVersion']['id']==old['id'] and len(pending[0]['latest']['comments'])==2 and pending[0]['latest']['comments'][1]['text']==request['lateComment'],'Late feedback or source version changed')
        return {'passed':True,'qualification':'synthetic FilmCraft agent/review music replacement, not listening or editorial approval','versions':[v['id'] for v in versions],'nativeJobs':2,'nativeProtectedStatePreserved':True,'sourcesAndParentPreserved':True,'lateFeedbackPreserved':True,'rendered':rendered(versions)}
    finally:db.close()

if __name__=='__main__':print(json.dumps(check(sys.argv[1]),indent=2))
