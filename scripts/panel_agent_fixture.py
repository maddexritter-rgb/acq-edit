"""Panel scenario preparation and read-only native/pixel checks for the live harness."""
import copy
import json
import subprocess
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
from common import read,save,sha,fingerprint,require,plan as validate_plan


def prepare(seed,second):
    spec=read(seed);camera=read(second);work=Path(seed).parent;source=spec['sources'][0]
    spec.update(width=360,height=640);spec['sources'].append(camera)
    template=spec['cuts'][0]
    spec['cuts']=[{**template,'id':f'cut-{i}','recordFrame':i*25,'sourceInFrame':start,'audioInSample':start*1920} for i,start in enumerate([25,0,50])]
    spec['captions'][0].update(endFrame=75);spec['captions'][0]['style'].update(position=[180,550],size=24)
    shots={}
    for i,cut in enumerate(spec['cuts']):
        if i==1:
            shots[cut['id']]={'mode':'fixed-crop','sourceWidth':640,'sourceHeight':360,'x':300,'y':20,'width':180,'height':320};continue
        panels=[]
        for index,(media,start) in enumerate([(source,cut['sourceInFrame']),(camera,50 if i==0 else 0)]):
            span={'sourceId':media['id'],'sha256':media['sha256'],'inFrame':start,'frames':25}
            crop={'mode':'fixed-crop','sourceWidth':640,'sourceHeight':360,'x':80,'y':20,'width':360,'height':320}
            if index==0:crop.update(mode='tracked-crop',x=60.25,xByFrame=[60.25+.5*j for j in range(25)],sourceRange=copy.deepcopy(span))
            panels.append({'id':'top' if index==0 else 'bottom','sourceRange':span,'rect':{'x':0,'y':320*index,'width':360,'height':320},'crop':crop})
        shots[cut['id']]={'mode':'panel-layout','panels':panels}
    receipt=work/'camera-fixture.json'
    save(receipt,{'schema':'acq-edit/camera-layout-v1','owner':'assembly-design','cutsSha256':fingerprint(spec['cuts']),'width':360,'height':640,'fps':spec['fps'],'layouts':{key:[{k:v for k,v in panel.items() if k!='crop'} for panel in layout['panels']] for key,layout in shots.items() if layout['mode']=='panel-layout'}})
    for layout in shots.values():
        if layout['mode']=='panel-layout':layout.update(cameraReceiptPath=str(receipt),cameraReceiptSha256=sha(receipt))
    framing=work/'framing-fixture.json';save(framing,{'owner':'horizontal-to-vertical','testFixture':True,'purpose':'Frozen source-linked panel geometry, not camera choice or human approval'})
    spec['framing']={'schema':'acq-edit/framing-v1','receiptPath':str(framing),'receiptSha256':sha(framing),'shots':shots}
    return spec


def expected_revision(previous,current):
    expected=copy.deepcopy(previous);old=previous['framing'];new=current['framing']
    require(old['receiptSha256']!=new['receiptSha256'],'Fresh framing receipt required')
    expected['framing'].update(receiptPath=new['receiptPath'],receiptSha256=new['receiptSha256'])
    layout=expected['framing']['shots']['cut-0'];actual=new['shots']['cut-0']
    require(layout['cameraReceiptSha256']!=actual['cameraReceiptSha256'],'Fresh camera layout receipt required')
    layout.update(cameraReceiptPath=actual['cameraReceiptPath'],cameraReceiptSha256=actual['cameraReceiptSha256'])
    top,bottom=layout['panels'];top['rect']['y']=320;bottom['rect']['y']=0
    top['crop'].update(x=80.25,xByFrame=[80.25+.75*i for i in range(25)]);bottom['crop']['x']=60
    require(current==expected,'Panel revision differs from the exact submitted geometry or changed protected plan fields')


def pixels(media,spec):
    raw=subprocess.check_output(['ffmpeg','-v','error','-i',media,'-map','0:v:0','-f','rawvideo','-pix_fmt','rgb24','-'])
    stride=360*640*3;require(len(raw)==75*stride,'Panel frame count changed');errors=[];checked=0
    source_a=spec['sources'][0]['id']
    for cut in spec['cuts']:
        layout=spec['framing']['shots'][cut['id']]
        if layout['mode']!='panel-layout':continue
        for panel in layout['panels']:
            r,crop=panel['rect'],panel['crop'];scale=r['width']/crop['width'];a=panel['sourceRange']['sourceId']==source_a;channel=0 if a else 2;marker=220 if a else 280
            for j in range(25):
                offset=(cut['recordFrame']+j)*stride;row=round(r['y']+(125-crop['y'])*scale)
                xs=[x for x in range(r['x'],r['x']+r['width']) if min(raw[offset+(row*360+x)*3:offset+(row*360+x)*3+3])>210]
                require(xs,'Native panel marker absent');x=crop['xByFrame'][j] if crop['mode']=='tracked-crop' else crop['x'];errors.append(abs(xs[0]-(r['x']+(marker-x)*scale)))
                for cy in [r['y']+1,r['y']+r['height']-2]:
                    for cx in [r['x']+1,r['x']+r['width']-2]:
                        rgb=raw[offset+(cy*360+cx)*3:offset+(cy*360+cx)*3+3];require(rgb[channel]>100 and rgb[channel]>rgb[2-channel]+60,'Panel camera color/placement changed')
                checked+=1
    require(max(errors)<=1.5,'Native panel geometry differs from the plan')
    return {'panelFramesChecked':checked,'maxMarkerEdgeErrorPixels':max(errors)}


def check(fixture,versions):
    import os
    os.environ['ACQ_EDIT_TEST_FIXTURE']='1'
    f=read(fixture);plans=[validate_plan(f['project'],{'plan':v['planPath']}) for v in versions]
    require(plans[0]==read(f['planPath']),'Agent changed the frozen build plan')
    expected_revision(*plans)
    pixel_checks=[pixels(v['media'],p) for v,p in zip(versions,plans)]
    evidence={'pixels':pixel_checks,'nativeGraph':'Resolve graph still requires host inspection'}
    if f['project']['backend']=='filmcraft':
        from framing_plan import verify_filmcraft_framing_data
        from filmcraft_panels import revision_operations,protected_revision
        data=[read(v['nativeCheckpoint']) for v in versions];ft=254016000000//25
        for native,spec in zip(data,plans):verify_filmcraft_framing_data(native,spec,ft)
        operations=revision_operations(data[0],plans[0],plans[1],{'cut-0':['top','bottom']})
        require(protected_revision(data[0],operations,Path(versions[1]['nativeProject']).stem)==protected_revision(data[1],operations),'Protected native panel project changed')
        evidence['nativeGraph']='All native panel clocks/geometry verified; protected saved project preserved'
    return evidence


if __name__=='__main__':
    if sys.argv[1]=='prepare':result=prepare(sys.argv[2],sys.argv[3])
    else:
        require(sys.argv[1]=='check','Unknown panel fixture command');result=check(sys.argv[2],json.loads(sys.argv[3]))
    print(json.dumps(result,indent=2))
