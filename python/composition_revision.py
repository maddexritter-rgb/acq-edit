"""Guarded FilmCraft crop/mode revision; editorial composition stays with its skill."""
import copy
import shutil
import sys
from pathlib import Path
from common import SKILLS, inside, read, save, sha, require, fingerprint, plan
from framing_plan import filmcraft_motion, filmcraft_tracking, verify_filmcraft_framing_data
sys.path.insert(0, str(SKILLS/'horizontal-to-vertical/scripts'))
from composition_review import validate as validate_composition
from filmcraft_split_shadow import verify_owned


def crops(spec):
    result = {}
    for cut in spec['cuts']:
        shot = spec['framing']['shots'][cut['id']]
        if shot['mode'] == 'panel-layout':
            for panel in shot['panels']:
                result[(cut['id'],panel['id'])] = panel['crop']
        else:
            result[(cut['id'],None)] = shot
    return result


def compare(previous, current, targets):
    selected = {(t['cutId'],t.get('panelId')) for t in targets}
    require(selected and len(selected)==len(targets), 'Select unique composition targets')
    require({k:v for k,v in previous.items() if k!='framing'} == {k:v for k,v in current.items() if k!='framing'}, 'Composition revision preserves cuts, captions, audio, graphics and sources')
    old, new = previous['framing'], current['framing']
    require(old['receiptSha256']!=new['receiptSha256'], 'Fresh framing-owner receipt required')
    a,b=crops(previous),crops(current)
    require(set(a)==set(b) and selected<=set(a), 'Camera/layout identities cannot change during composition repair')
    for cut in previous['cuts']:
        x,y=old['shots'][cut['id']],new['shots'][cut['id']]
        require((x['mode']=='panel-layout')==(y['mode']=='panel-layout'), 'Composition cannot change camera layout')
        if x['mode']=='panel-layout':
            strip=lambda s:{**s,'panels':[{k:v for k,v in p.items() if k!='crop'} for p in s['panels']]}
            require(strip(x)==strip(y), 'Panel order, source sync, rectangles and camera receipts are protected')
    for key, crop in a.items():
        other=b[key]
        if key not in selected:require(crop==other,'Unselected crop changed');continue
        require(crop!=other, 'Selected composition has no change')
        require(crop['mode'] in ('fixed-crop','tracked-crop') and other['mode'] in ('fixed-crop','tracked-crop'), 'Unsupported composition mode')
        require((crop['sourceWidth'],crop['sourceHeight'])==(other['sourceWidth'],other['sourceHeight']), 'Source geometry changed')
    return selected


def without_shadow(data, receipt):
    """Read-only projection of known append-only shadow layers; verify all ownership."""
    original=read(receipt['parent']);value=copy.deepcopy(data)
    extras=set(read(receipt['nativeProject'])['project']['items'])-set(original['project']['items'])
    require(len(extras)==len(receipt['layoutIds']), 'Unexpected shadow additions')
    for key in extras:del value['project']['items'][key]
    value['project']['root']['children']=[c for c in value['project']['root']['children'] if str(c.get('Item')) not in extras]
    value['project']['next_id']=original['project']['next_id']
    for key in receipt['layoutIds']:
        tracks=value['project']['items'][str(key)]['kind']['Sequence']['video_tracks']
        require(len(tracks)==4,'Shadow layout changed');del tracks[2:]
    verify_owned(value,data,receipt['layoutIds'],receipt['profile'])
    return value


def operations(data, spec, selected):
    master=data['view']['active_sequence'];items=data['project']['items'];sequence=items[str(master)]['kind']['Sequence'];result=[]
    for cut,item in zip(spec['cuts'],sequence['video_tracks'][0]['items']):
        shot=spec['framing']['shots'][cut['id']]
        if shot['mode']=='panel-layout':
            from panel_layout import panel_spec
            container=items[str(item['item'])]['kind']['Sequence']
            for index,panel in enumerate(shot['panels']):
                if (cut['id'],panel['id']) not in selected:continue
                child=container['video_tracks'][index]['items'][0]['item'];camera=items[str(child)]['kind']['Sequence']['video_tracks'][0]['items'][0]
                child_spec=panel_spec(spec,cut,panel)
                result.append({'sequence':child,'clip':camera['id'],'cut':child_spec['cuts'][0],'spec':child_spec,'crop':panel['crop']})
        elif (cut['id'],None) in selected:
            result.append({'sequence':master,'clip':item['id'],'cut':cut,'spec':spec,'crop':shot})
    require(len(result)==len(selected),'Native composition target missing')
    return result


def protected(data, ops, name):
    value=copy.deepcopy(data['project']);value['name']=name;value['root']['name']=name
    for op in ops:
        seq=value['items'][str(op['sequence'])]['kind']['Sequence']
        item=next(i for i in seq['video_tracks'][0]['items'] if i['id']==op['clip'])
        motion=next(e['params'] for e in item['effects'] if e['effect']=='motion')
        motion['anchor'].pop('value');motion['anchor'].pop('keyframes',None)
        motion['scale'].pop('value')
    return fingerprint({'project':value,'activeSequence':data['view']['active_sequence']})


def revise(adapter, project, packet):
    require(project['backend']=='filmcraft','Composition mode revisions currently require FilmCraft')
    previous_path=inside(project['root'],packet['previousPlan']);require(sha(previous_path)==packet['previousPlanSha256'],'Previous plan changed')
    previous=plan(project,{'plan':str(previous_path)});current=plan(project,packet)
    selected=compare(previous,current,packet['targets'])
    review_path=inside(project['root'],packet['compositionReview']);require(sha(review_path)==packet['compositionReviewSha256'],'Composition review changed')
    review=read(review_path);profile_path=inside(project['root'],review['profile']['path']);require(sha(profile_path)==review['profile']['sha256'],'Composition profile changed')
    quality=validate_composition(current,review,read(profile_path))
    for entry in review['entries']:
        for sample in entry['samples']:
            evidence=sample['evidence'];file=inside(project['root'],evidence['path']);require(sha(file)==evidence['sha256'],'Composition evidence image changed')
    native=inside(project['root'],packet['nativeProject']);before=adapter.inspect(project,{'nativeProject':str(native),'session':packet['inspectSession']})
    require(before['fingerprint']==packet['expectedFingerprint'],'Native project changed; reconcile intervening edits')
    parent_hash=sha(native);data=read(native);shadow=None
    if packet.get('shadowReceipt'):
        r=inside(project['root'],packet['shadowReceipt']);require(sha(r)==packet['shadowReceiptSha256'],'Shadow receipt changed');shadow=read(r)
        for key,hashkey in [('parent','parentSha256'),('nativeProject','nativeSha256')]:require(sha(inside(project['root'],shadow[key]))==shadow[hashkey],'Shadow lineage changed')
        require(Path(shadow['nativeProject']).resolve()==native and shadow['nativeSha256']==parent_hash,'Wrong shadow checkpoint')
    projection=without_shadow(data,shadow) if shadow else data
    ft=254016000000*current['fps']['denominator']//current['fps']['numerator']
    verify_filmcraft_framing_data(projection,previous,ft)
    ops=operations(data,current,selected);target=inside(project['root'],packet['outputProject']);require(not target.exists(),'Revision destination exists')
    baseline=protected(data,ops,target.stem);shutil.copy2(native,target)
    from filmcraft import Filmcraft
    c=Filmcraft(adapter.config['filmcraft'],inside(project['root'],packet['session']),str(target))
    try:
        for op in ops:
            c.run('sequence.open',{'item':op['sequence']})
            state=c.tool('sequence_inspect');item=next(i for i in state['video'][0]['items'] if i['clip']==op['clip']);m=next(e['params'] for e in item['effects'] if e['effect']=='motion')
            if m['anchor']['keyframes']:c.run('effects.toggleAnimation',{'clip':op['clip'],'effect':'motion','param':'anchor'})
            for key,value in filmcraft_motion(op['spec'],op['crop']).items():
                if key!='position':c.run('effects.setParam',{'clip':op['clip'],'effect':'motion','param':key,'value':value})
            filmcraft_tracking(c,{'clip':op['clip']},op['cut'],op['crop'],ft)
        c.run('sequence.open',{'item':data['view']['active_sequence']});c.run('file.save')
        after=read(target);plain=without_shadow(after,shadow) if shadow else after
        verify_filmcraft_framing_data(plain,current,ft)
        require(protected(after,ops,target.stem)==baseline,'Composition revision changed protected native state')
        from caption_plan import validate,verify_native
        if current.get('captionContract'):verify_native(target,current,validate(project,current),ft)
        require(sha(native)==parent_hash,'Parent changed during composition revision')
        state=c.tool('sequence_inspect');save(inside(project['root'],packet['inspection']),state)
    finally:c.close()
    result={'nativeProject':str(target),'fingerprint':fingerprint({'state':state,'fileHash':sha(target)}),'status':'revised-native-render-pending','protectedStateVerified':True,'composition':quality}
    if shadow:
        parent=target.parent/'shadow-parent.fcproj';save(parent,plain)
        receipt={**shadow,'parent':str(parent),'parentSha256':sha(parent),'nativeProject':str(target),'nativeSha256':sha(target),'renderedMatchApproved':False}
        file=target.parent/'shadow-receipt.json';save(file,receipt);result['shadowReceipt']=str(file)
    return result
