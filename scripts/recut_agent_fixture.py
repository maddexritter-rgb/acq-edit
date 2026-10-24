"""Opt-in real-agent recut fixture; synthetic geometry is not speech approval."""
import array
import copy
import json
import math
import os
import sqlite3
import subprocess
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
from common import read,save,sha,require,fingerprint,plan as validate_plan,verify_native_render


def prepare(seed,music_file):
    spec=read(seed);music=read(music_file);work=Path(seed).parent
    spec['sources'].append(music)
    framing=work/'recut-framing-fixture.json';save(framing,{'testFixture':True,'owner':'horizontal-to-vertical','purpose':'Frozen synthetic crops, not subject choice'})
    spec['framing']={'schema':'acq-edit/framing-v1','receiptPath':str(framing),'receiptSha256':sha(framing),'shots':{c['id']:{'mode':'fixed-crop','sourceWidth':640,'sourceHeight':360,'x':80,'y':45,'width':480,'height':270} for c in spec['cuts']}}
    receipt=work/'recut-music-fixture.json';save(receipt,{'testFixture':True,'owner':'music','purpose':'Generated 220 Hz test tone, not music audition'})
    spec['audio']={'gainDb':0,'music':[{'id':'test-bed','sourceId':music['id'],'startFrame':0,'sourceInSample':0,'samples':96000,'gainDb':-12,'fadeInSamples':0,'fadeOutSamples':0,'receiptPath':str(receipt),'receiptSha256':sha(receipt)}]}
    graphic=work/'recut-overlay.mov'
    subprocess.run(['ffmpeg','-v','error','-n','-f','lavfi','-i',"nullsrc=size=640x360:rate=25:duration=1,format=rgba,geq=r=255:g=255:b=0:a='if(between(X,20,79)*between(Y,20,49),255,0)'",'-an','-c:v','prores_ks','-profile:v','4','-pix_fmt','yuva444p10le',str(graphic)],check=True)
    alpha=subprocess.check_output(['ffmpeg','-v','error','-i',str(graphic),'-frames:v','1','-vf','alphaextract','-f','rawvideo','-pix_fmt','gray','-'])
    require(min(alpha)==0 and max(alpha)==255 and sum(v>240 for v in alpha)==1800,'Synthetic graphic alpha differs')
    spec['graphics']=[{'path':str(graphic),'sha256':sha(graphic),'startFrame':25,'frames':25}]
    return spec


def expected_revision(old,new):
    expected=copy.deepcopy(old)
    require(new['editorial']['sha256']!=old['editorial']['sha256'],'Fresh selection required')
    expected['editorial']=new['editorial']
    require(set(new['editorial'])==set(old['editorial']) and new['editorial']['reviewed'] is True,'Editorial contract changed')
    expected['cuts']=[{**old['cuts'][1],'recordFrame':0}]
    expected['captions'][0].update(text='RETAINED SECOND PASSAGE',startFrame=0,endFrame=25)
    require(new['framing']['receiptSha256']!=old['framing']['receiptSha256'],'Fresh framing receipt required')
    expected['framing'].update(receiptPath=new['framing']['receiptPath'],receiptSha256=new['framing']['receiptSha256'],shots={'cut-1':old['framing']['shots']['cut-1']})
    bed=expected['audio']['music'][0];actual=new['audio']['music'][0]
    require(actual['receiptSha256']!=bed['receiptSha256'],'Fresh music receipt required')
    bed.update(sourceInSample=48000,samples=48000,startFrame=0,receiptPath=actual['receiptPath'],receiptSha256=actual['receiptSha256'])
    expected['graphics'][0]['startFrame']=0
    require(new==expected,'Recut differs from requested surviving source ranges, finishing or protected fields')


def native(spec,state,data):
    from framing_plan import verify_filmcraft_framing_data
    ft=254016000000//25;st=254016000000//48000
    verify_filmcraft_framing_data(data,spec,ft)
    def source(item):return data['project']['items'][str(item['item'])]['kind']['Media']['media']['File']['path']
    require(len(state['video'][0]['items'])==len(state['audio'][0]['items'])==len(spec['cuts']),'Native picture/dialogue coverage differs')
    for cut,v,a in zip(spec['cuts'],state['video'][0]['items'],state['audio'][0]['items']):
        media=next(s for s in spec['sources'] if s['id']==cut['sourceId'])
        require(source(v)==source(a)==media['path'],'Native source differs')
        require((v['start'],v['sourceIn'],v['duration'])==(cut['recordFrame']*ft,cut['sourceInFrame']*ft,cut['frames']*ft),'Native picture range differs')
        require((a['start'],a['sourceIn'],a['duration'])==(cut['recordFrame']*ft,cut['audioInSample']*st,cut['audioSamples']*st),'Native audio range differs')
        require(v['link'] is not None and v['link']==a['link'],'Native AV links differ')
    require(len(state['audio'][1]['items'])==1,'Expected one native music bed')
    bed=spec['audio']['music'][0];item=state['audio'][1]['items'][0]
    require(source(item)==next(s['path'] for s in spec['sources'] if s['id']==bed['sourceId']),'Native music source differs')
    require((item['start'],item['sourceIn'],item['duration'])==(bed['startFrame']*ft,bed['sourceInSample']*st,bed['samples']*st),'Native music timing differs')
    sequence=data['project']['items'][str(data['view']['active_sequence'])]['kind']['Sequence']
    saved=sequence['audio_tracks'][1]['items'][0]
    volume=next(e for e in saved['effects'] if e['effect']=='volume')
    require(item['gainDb']==saved['gain_db']==0 and volume['enabled'] and volume['params']['bypass']['value']=={'Bool':False} and volume['params']['level']['value']=={'Float':bed['gainDb']} and not volume['params']['level'].get('keyframes'),'Native music gain differs')
    require(len(state['video'][1]['items'])==len(state['video'][2]['items'])==1,'Expected one native caption and graphic')
    card=spec['captions'][0];caption=state['video'][1]['items'][0]
    require((caption['start'],caption['duration'])==(card['startFrame']*ft,(card['endFrame']-card['startFrame'])*ft) and card['text'] in json.dumps(caption),'Native caption timing/text differs')
    asset=spec['graphics'][0];item=state['video'][2]['items'][0]
    require(source(item)==asset['path'] and (item['start'],item['sourceIn'],item['duration'])==(asset['startFrame']*ft,0,asset['frames']*ft),'Native graphic source/timing differs')


def rendered(versions):
    images=[]
    for v in versions:
        images.append(subprocess.check_output(['ffmpeg','-v','error','-i',v['media'],'-vf','crop=500:160:100:70','-an','-f','rawvideo','-pix_fmt','rgb24','-']))
    stride=500*160*3;a=images[0][25*stride:];b=images[1]
    require(len(a)==len(b)==25*stride,'Surviving picture coverage differs')
    mse=sum((x-y)**2 for x,y in zip(a,b))/len(a);psnr=10*math.log10(255**2/mse) if mse else None
    require(psnr is None or psnr>35,'Surviving source picture differs beyond the fixture tolerance')
    overlay=subprocess.check_output(['ffmpeg','-v','error','-i',versions[1]['media'],'-vf','crop=50:20:24:24','-an','-f','rawvideo','-pix_fmt','rgb24','-'])
    require(len(overlay)==25*50*20*3,'Retimed overlay coverage differs')
    for frame in range(25):
        pixels=overlay[frame*3000:(frame+1)*3000]
        require(sum(pixels[i]>180 and pixels[i+1]>180 and pixels[i+2]<80 for i in range(0,3000,3))>950,'Retimed graphic is not visible on every frame')
    pcm=array.array('f',subprocess.check_output(['ffmpeg','-v','error','-i',versions[1]['media'],'-map','0:a:0','-ac','1','-ar','48000','-f','f32le','-']))
    if sys.byteorder!='little':pcm.byteswap()
    require(len(pcm)>=48000,'Recut audio is truncated');samples=pcm[4800:43200]
    def amplitude(hz):
        return 2*abs(sum(x*complex(math.cos(2*math.pi*hz*i/48000),math.sin(2*math.pi*hz*i/48000)) for i,x in enumerate(samples)))/len(samples)
    tones={hz:amplitude(hz) for hz in [220,440,880]}
    require(tones[880]>.05 and tones[880]>20*tones[440],'Wrong passage remains in decoded audio')
    ratio=tones[220]/tones[880];require(.20<ratio<.33,'Retimed music is missing or wrong gain')
    return {'survivingPictureFrames':25,'visibleGraphicFrames':25,'survivingRegionPsnrDb':psnr,'toneAmplitudes':tones,'musicToDialogueRatio':ratio}


def check(file):
    os.environ['ACQ_EDIT_TEST_FIXTURE']='1'
    f=read(file);require(f['project']['backend']=='filmcraft','This native recut checker is FilmCraft-specific')
    require(sha(f['planPath'])==f['initialPlanSha256'],'Frozen fixture changed')
    db=sqlite3.connect('file:'+str(Path(f['home'])/'state.sqlite')+'?mode=ro',uri=True)
    def rows(query,*args):return [json.loads(r[0]) for r in db.execute(query,args)]
    try:
        jobs=rows('SELECT data FROM jobs WHERE project_id=? ORDER BY rowid',f['project']['id']);versions=rows('SELECT data FROM versions WHERE clip_id=? ORDER BY rowid',f['clip']['id'])
        require(len(jobs)==len(versions)==2 and all(j['state']=='ready' and j.get('agentSession') and not j.get('error') for j in jobs),'Expected exactly two real ready jobs and versions')
        v1,v2=versions;require(v2['parentId']==v1['id'],'Wrong parent')
        plans=[]
        for j,v in zip(jobs,versions):
            require(v['jobId']==j['id'],'Wrong publication owner')
            require(read(Path(f['project']['root'])/'10_WORK/jobs'/j['id']/'result.json')=={'jobId':j['id'],'versionIds':[v['id']]},'Job result differs')
            for key,pin in [('media','sha256'),('nativeCheckpoint','nativeFingerprint'),('planPath','planSha256'),('inspectionPath','inspectionSha256'),('receiptPath','receiptSha256')]:require(sha(v[key])==v[pin],'Changed published '+key)
            spec=validate_plan(f['project'],{'plan':v['planPath']});plans.append(spec)
            verify_native_render(v['media'],spec);native(spec,read(v['inspectionPath']),read(v['nativeCheckpoint']))
            receipt=read(v['receiptPath']);require(receipt['nativeRendered'] and receipt['backend']=='filmcraft' and receipt['jobId']==j['id'],'Missing native render evidence')
        require(plans[0]==read(f['planPath']),'Build changed frozen plan');expected_revision(*plans)
        require(sha(v2['recutVerificationPath'])==v2['recutVerificationSha256'],'Changed archived recut proof')
        proof=read(v2['recutVerificationPath']);require(proof['parentPreserved'] and proof['parentVersionId']==v1['id'] and proof['parentPlanSha256']==v1['planSha256'] and proof['planSha256']==v2['planSha256'] and proof['newNativeSha256']==v2['nativeFingerprint'],'Recut proof does not bind these versions')
        require(proof['parentFingerprint']==fingerprint({'state':read(v1['inspectionPath']),'fileHash':v1['nativeFingerprint']}) and proof['construction']['fingerprint']==fingerprint({'state':read(v2['inspectionPath']),'fileHash':v2['nativeFingerprint']}),'Recut native fingerprints differ')
        require(sha(v1['nativeProject'])==v1['nativeFingerprint'],'Parent working project changed')
        for source in rows('SELECT data FROM sources WHERE project_id=?',f['project']['id']):require(sha(source['path'])==source['sha256'],'Source changed')
        request=read(Path(file).parent/'revision-request.json');submitted=jobs[1]['snapshot'][0]
        require(submitted['version']['id']==v1['id'] and submitted['feedback']['notes']==request['notes'] and len(submitted['feedback']['comments'])==1 and submitted['feedback']['comments'][0]['text']==request['comment'],'Wrong submitted request')
        require('assembly-design' in submitted['owners'] and 'caption-clips' in submitted['owners'] and 'horizontal-to-vertical' in submitted['owners'],'Recut missed dependent owners')
        require(rows('SELECT data FROM feedback WHERE version_id=?',v2['id'])[0]['decision'] is None,'Changed version needs fresh review')
        pending=rows('SELECT data FROM deferred_feedback WHERE clip_id=? AND consumed_by IS NULL',f['clip']['id']);require(len(pending)==1,'Late feedback absent or duplicated')
        require(pending[0]['sourceVersion']['id']==v1['id'] and len(pending[0]['latest']['comments'])==2 and pending[0]['latest']['comments'][1]['text']==request['lateComment'],'Late feedback lost its original version')
        require(1<pending[0]['latest']['comments'][1]['seconds']<2,'Historical comment must test a time beyond the shorter revision')
        return {'passed':True,'scope':'synthetic FilmCraft real-agent recut, not editorial or speech acceptance','versions':[v['id'] for v in versions],'frames':[50,25],'nativeSourcesCutsLinksFinishingVerified':True,'parentAndSourcesPreserved':True,'lateFeedbackPreserved':True,'rendered':rendered(versions)}
    finally:db.close()


if __name__=='__main__':
    result=prepare(sys.argv[2],sys.argv[3]) if sys.argv[1]=='prepare' else check(sys.argv[2])
    print(json.dumps(result,indent=2))
